"""Offline usage arithmetic. This module cannot dispatch model calls."""
import collections
from decimal import Decimal
from pathlib import Path

from .common import atomic_text, read_json, read_jsonl, write_csv, write_json
from .provider import billing_units, charge, rates


def calculate(calls, summary, card, volume=660622, budget=2):
    if volume < 1:
        raise ValueError("Projected volume must be positive")
    stages = {}
    usage_rows = []
    unresolved = []
    for call in calls:
        if call.get("synthetic"):
            raise ValueError("Synthetic calls are forbidden in measured pilot arithmetic")
        stage = stages.setdefault(call["role"], {"attempts": 0, "failed_attempts": 0,
            "input_tokens": 0, "output_tokens": 0, "known_api_usd": Decimal(0), "call_seconds": 0.0,
            "unknown_usage_attempts": 0})
        stage["attempts"] += 1
        stage["failed_attempts"] += call["outcome"] != "succeeded"
        stage["call_seconds"] += call.get("duration_seconds", 0)
        try:
            units = billing_units(call.get("usage"))
            amount = charge(call["usage"], card)
            if call.get("endpoint") == "decisions":
                from .decisions import decision_charge
                amount = decision_charge(call["usage"], card)
                units = {"input": call["usage"]["input_tokens"], "cached_input": 0, "cache_write": 0, "output": 0}
            stage["input_tokens"] += call["usage"]["input_tokens"]
            stage["output_tokens"] += call["usage"]["output_tokens"]
            stage["known_api_usd"] += amount
            for item, count in units.items():
                usage_rows.append({"local_call_id": call["local_call_id"], "role": call["role"],
                    "item": item, "billed_units": count, "price_per_unit": str(card[item]),
                    "calculated_usd": str(Decimal(count) * card[item]), "currency": "USD"})
        except (ValueError, TypeError, KeyError):
            stage["unknown_usage_attempts"] += 1
            unresolved.append({"local_call_id": call["local_call_id"], "reservation_usd": call.get("reservation_usd"),
                               "reason": "usage unavailable; not assumed zero"})
    total = sum((s["known_api_usd"] for s in stages.values()), Decimal(0))
    measured = dict(summary)
    measured.update(known_api_usd=str(total), usage_complete=not unresolved, unresolved_calls=unresolved,
        unresolved_reservation_usd=str(sum((Decimal(c.get("reservation_usd") or "0") for c in unresolved), Decimal(0))),
        cost_per_1000_input_usd=str(total * 1000 / Decimal(summary["input_count"])) if calls else None,
        cost_per_completed_usd=str(total / Decimal(summary["completed"])) if summary.get("completed") and calls else None,
        local_compute_usd=None, local_compute_note="Not measured; hardware/electricity are unknown, not zero")
    for s in stages.values():
        s["known_api_usd"] = str(s["known_api_usd"])
    for role, stage in stages.items():
        related = [c for c in calls if c["role"] == role]
        succeeded = {rid for c in related if c["outcome"] == "succeeded" for rid in c.get("review_ids", [])}
        failed_ids = {rid for c in related if c["outcome"] != "succeeded" for rid in c.get("review_ids", [])}
        stage["completed_records"] = len(succeeded)
        stage["unresolved_failed_record_ids"] = sorted(failed_ids - succeeded)
        stage["model"] = related[0].get("model")
        stage["effort"] = related[0].get("effort")
        stage["prompt_hash"] = related[0].get("prompt_hash")
    projections = []
    if summary.get("status") == "completed" and all(r in stages for r in ("enrich", "verify", "group", "memo")):
        empty = 13 if volume == 660622 else round(volume * 13 / 660622)
        nonempty = volume - empty
        distinct = 484189 if volume == 660622 else round(nonempty * 484189 / 660609)
        e = stages["enrich"]
        failed = e["failed_attempts"]
        successful_tasks = max(1, e["attempts"] - failed)
        observed_retry_fraction = failed / successful_tasks
        for reuse, count in ((True, distinct), (False, nonempty)):
            for conservative in (False, True):
                retry_fraction = max(0.1, observed_retry_fraction) if conservative else observed_retry_fraction
                cost = Decimal(0)
                seconds = 0.0
                stage_work = {}
                for role, s in stages.items():
                    if role == "enrich":
                        work = count
                        factor = Decimal(work) / Decimal(summary.get("enrichment_work_count", summary["unique_nonempty_texts"]))
                    elif role == "verify":
                        frame = nonempty if summary.get("verification_sampling_unit") == "source_rows" else count
                        work = (frame + 4) // 5
                        factor = Decimal(work) / Decimal(summary["verification_sample_count"])
                    else:
                        work, factor = 1, Decimal(1)
                    if role in {"enrich", "verify"}:
                        observed = s["failed_attempts"] / max(1, s["attempts"]-s["failed_attempts"])
                        scenario_retry = max(0.1, observed) if conservative else observed
                        factor *= Decimal(str((1+scenario_retry)/(1+observed)))
                    cost += Decimal(s["known_api_usd"]) * factor
                    seconds += s["call_seconds"] * float(factor) * (1.5 if conservative else 1)
                    stage_work[role] = work
                # One-time measured local/restart overhead, never multiplied per record.
                measured_seconds = summary.get("incremental_seconds") if summary.get("measurement_kind") == "incremental_checkpoint" else summary["cold_seconds"]
                overhead = max(0, measured_seconds - sum(s["call_seconds"] for s in stages.values()))
                seconds += overhead
                projections.append({"scenario": ("conservative" if conservative else "base") + ("_exact_reuse" if reuse else "_no_reuse"),
                    "input_rows": volume, "nonempty_classifications": nonempty, "empty_quarantines": empty,
                    "stage_work": stage_work, "estimated_api_usd": str(cost), "estimated_seconds": seconds,
                    "retry_fraction": retry_fraction, "verification_fraction": 0.2, "fallback_fraction": 0,
                    "workers": 1, "exceeds_budget": cost > Decimal(str(budget)),
                    "verification_sampling_unit":summary.get("verification_sampling_unit","distinct_texts"),
                    "usage_complete": not unresolved, "fixed_overhead_seconds": overhead})
    return {"measured": measured, "stages": stages, "projections": projections,
        "controls": {"budget_usd": budget, "max_output_tokens": 4096, "max_workers": 1, "max_fallback_fraction": 0},
        "projection_notes": ["Estimates, not executions; recalibrate after 500 and 10,000 reviews.",
            "The summary declares the verification sampling frame. Exact reuse preserves all original IDs in business counts.",
            "Grouping and memo are bounded fixed overhead once each; no provider Batch discounts are assumed.",
            "Single-worker projection uses observed stage durations; sustained throughput and local ingestion costs remain uncertain."]}, usage_rows


def replay(directory="cost", rates_path="cost/rates.csv", volume=660622, budget=2):
    directory = Path(directory)
    summary_path = directory / "pilot_summary.json"
    calls_path = directory / "pilot_calls.jsonl"
    if not summary_path.exists():
        summary = {"status": "pending_paid_pilot", "input_count": 100, "completed": 0,
                   "cold_seconds": None, "warm_seconds": None}
    else:
        summary = read_json(summary_path)
    if summary.get("config", {}).get("execution_mode") in {"scaling-pilot-v1", "scaling-pilot-v2"}:
        raise ValueError("Use scaling-replay for the concurrency experiment; the generic calculator projects serial execution")
    calls = read_jsonl(calls_path) if calls_path.exists() else []
    result, usage = calculate(calls, summary, rates(rates_path), volume, budget)
    write_json(directory / "calculator.json", result)
    write_csv(directory / "usage.csv", usage, ["local_call_id", "role", "item", "billed_units", "price_per_unit", "calculated_usd", "currency"])
    measured = result["measured"]
    incremental = measured.get("measurement_kind") == "incremental_checkpoint"
    title = f"# Measured {measured['input_count']}-review " + ("checkpoint (incremental)" if incremental else "pilot") + " and offline calculator"
    lines = [title, "", f"Status: **{measured['status']}**", "",
        "Only saved provider usage is used here. Replay needs no API key and makes no network requests.", "",
        "## Measured results", "", f"- Input rows: {measured['input_count']}", f"- Completed: {measured.get('completed', 0)}",
        f"- Quarantined: {measured.get('quarantined', 'pending')}",
        "- Fresh-cache cold time: not measured; earlier results were reused" if incremental else f"- Cold wall seconds: {measured.get('cold_seconds')}",
        f"- Warm wall seconds: {measured.get('warm_seconds')}", f"- Warm new model calls: {measured.get('warm_new_calls', 'pending')}",
        f"- Known API subtotal (USD): {measured['known_api_usd']}" + ("" if calls else " (no calls recorded; no measured pilot yet)"),
        f"- Cost per 1,000 inputs (USD): {measured['cost_per_1000_input_usd']}",
        f"- Cost per completed record (USD): {measured['cost_per_completed_usd']}",
        f"- Usage complete: {measured['usage_complete']}",
        f"- Unresolved attempts: {len(measured['unresolved_calls'])}; historical reservations retained (USD): {measured['unresolved_reservation_usd']}",
        "- Reservations are possible charges at the saved rate card, not reported usage or invoice reconciliation.",
        "- Local compute cost: unknown/unmeasured", "",
        "## Per-stage measured calls", "", "| Role | Attempts | Failures | Input tokens | Output tokens | Known USD | Unknown usage | Call seconds |",
        "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for role, s in result["stages"].items():
        lines.append(f"| {role} | {s['attempts']} | {s['failed_attempts']} | {s['input_tokens']} | {s['output_tokens']} | {s['known_api_usd']} | {s['unknown_usage_attempts']} | {s['call_seconds']:.3f} |")
    if incremental:
        lines += ["", "## Incremental checkpoint measurement", "",
            f"- Reused original IDs from the previous checkpoint: {measured.get('inherited_completed_records','pending')}",
            f"- Newly completed original IDs: {measured.get('new_completed_records','pending')}",
            f"- New enrichment work units (text/configuration pairs): {measured.get('enrichment_work_count','pending')}",
            f"- Measured incremental wall seconds: {measured.get('incremental_seconds','pending')}",
            f"- New records per second (including verification and analysis): {measured.get('new_records_per_second','pending')}",
            "No fresh-cache cold time is claimed. The subtotal includes only new attempted calls; inherited calls are saved separately and are not billed twice.",
            "Enrichment projections use the newly classified text count as their denominator, rather than all saved outputs.",
            "Verification projections use 20% of original nonempty source rows, matching this checkpoint's random sample."]
        if measured.get("recovery_source_run"):
            lines += [f"- Recovery source: {measured['recovery_source_run']}; valid results preserved: {measured['validated_v2_results_preserved']}",
                "The measured subtotal and elapsed time include both checkpoint attempts. Inherited outputs keep their original label_config; the ID-constrained response schema has a distinct cache key.",
                "Active execution and subprocess restart are measured; development/approval waiting between invocations is excluded."]
    lines += ["", "Provider: OpenAI. Recorded usage × editable rates is a calculated API charge estimate, not an invoice reconciliation.", "",
        "| Role | Model | Effort | Prompt hash | Completed review IDs |",
        "|---|---|---|---|---:|"]
    for role, s in result["stages"].items():
        lines.append(f"| {role} | {s['model']} | {s['effort']} | `{s['prompt_hash']}` | {s['completed_records']} |")
    lines += ["", f"Input SHA-256: `{measured.get('input_sha256', 'pending')}`.",
        f"Distinct nonempty texts: {measured.get('unique_nonempty_texts', 'pending')}; cold exact-text reuse: {measured.get('exact_text_reuses', 'pending')}; warm record cache hits: {measured.get('warm_record_cache_hits', 'pending')}.",
        (f"Incremental throughput: {measured.get('new_records_per_second', 'pending')} new completed records/second." if incremental else f"Cold throughput: {measured.get('cold_throughput_records_per_second', 'pending')} completed records/second."),
        "The schema version, worker/batch/output limits and complete per-call usage are saved in pilot_summary.json and pilot_calls.jsonl."]
    lines += ["", "## Full-run projections — not measured runs", "",
        "| Scenario | Estimated API USD | Estimated hours | Over pilot cap? |",
        "|---|---:|---:|---|"]
    for p in result["projections"]:
        lines.append(f"| {p['scenario']} | {Decimal(p['estimated_api_usd']):.4f} | {p['estimated_seconds']/3600:.2f} | {p['exceeds_budget']} |")
    if not measured["usage_complete"]:
        lines += ["", "Usage is incomplete. These API projections extrapolate known reported usage only; unknown charges remain separately reserved. They are not all-inclusive cost quotes."]
    lines += ["", "These projections do not authorize a full run. The US$2 cap covers all actual calls in the local pilot ledger.", "",
        "## Arithmetic and assumptions", "", "Each item = billed units × editable USD/unit. Input, cached input, cache write and output are mutually exclusive. Reasoning is already included in output.",
        ("Incremental time includes this checkpoint's interruption/restart and analysis; prior checkpoint execution time is excluded. Warm time is separate." if incremental else "Cold time includes the recorded interruption/process restart. Warm time is incremental. Summed call time is shown separately from wall time."),
        "Unknown charges retain ledger reservations and are excluded from the known subtotal; see calculator.json.",
        "Standard processing; one worker; batches of ten; output cap 4096; verification fraction 20%; stronger fallback 0%.",
        "Base projections use observed retries. Conservative projections use at least 10% retries and 50% slower stage durations.",
        "Rates are editable in rates.csv, with official source and check date. Raw measurements remain unchanged when rates or volume change.",
        "See pilot_summary.json for input checksum, IDs, cache counts, settings and measured throughput; pilot_calls.jsonl for every attempt.",
        ("The earlier synthetic-input model diagnostics remain under cost/; they are not repeated or included in this checkpoint's cost." if incremental else "Diagnostics, if executed, are separate in diagnostics_calls.jsonl and diagnostics.json; they share the global budget but are excluded from measured-100 projections."), "",
        "Offline command: `python -m spotify_pipeline cost replay" + (f" --directory {directory}" if directory != Path('cost') else "") + "`."]
    atomic_text(directory / "report.md", "\n".join(lines) + "\n")
    return result
