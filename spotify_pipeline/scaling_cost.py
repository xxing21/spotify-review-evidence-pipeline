"""Portable offline billing replay and forecasts for the measured scaling pilot."""
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

from .calculator import calculate
from .common import atomic_text, read_json, read_jsonl, write_csv, write_json
from .provider import rates


def sustained_limits(calls):
    limits = {"rpm": 600., "tpm": 600000.}
    for call in calls:
        headers = {k.lower(): v for k, v in call.get("rate_limit_headers", {}).items()}
        for key, name in (("x-ratelimit-limit-requests", "rpm"), ("x-ratelimit-limit-tokens", "tpm"),
                          ("x-ratelimit-limit-project-tokens", "tpm")):
            if key in headers:
                limits[name] = min(limits[name], max(1., float(headers[key])*.75))
    return limits


def forecast(summary, stages, volume, limits=None, exact_texts=None, verification_fraction=.2):
    if type(volume) is not int or volume < 1:
        raise ValueError("Projected nonempty volume must be a positive integer")
    if exact_texts is not None and (type(exact_texts) is not int or not 1 <= exact_texts <= volume):
        raise ValueError("Profiled distinct text count must be an integer within the target volume")
    fraction = Decimal(str(verification_fraction))
    if not fraction.is_finite() or not 0 < fraction <= 1:
        raise ValueError("Verification fraction must be greater than zero and at most one")
    verification_count = int((Decimal(volume)*fraction).to_integral_value(rounding=ROUND_CEILING))
    phases = summary["phase_measurements"]
    e = next(x for x in phases if x["phase"] == summary.get("enrichment_projection_phase", "enrich-8") and x["completed"])
    v = next(x for x in phases if x["phase"] == summary.get("verification_projection_phase", "verify-8") and x["completed"])
    overhead_seconds = max(0, summary["cold_seconds"] - sum(p["elapsed_seconds"] for p in phases)) + summary.get("preparation_seconds", 0)
    overhead_cost = sum((Decimal(stages[r]["known_api_usd"]) for r in ("group", "memo")), Decimal(0))
    estimates = []
    for reuse in (True, False):
        unique = (exact_texts if exact_texts is not None else round(volume * 484189/660609)) if reuse else volume
        for conservative in (False, True):
            cost, seconds = overhead_cost, overhead_seconds
            constraints = {}
            for role, work, measured_count, timing in (("enrich", unique, 500, e), ("verify", verification_count, 100, v)):
                stage = stages[role]
                observed = stage["failed_attempts"] / max(1, stage["attempts"]-stage["failed_attempts"])
                factor = (1+max(.1, observed))/(1+observed) if conservative else 1
                cost += Decimal(stage["known_api_usd"]) / measured_count * work * Decimal(str(factor))
                bounds = {"measured_throughput": timing["elapsed_seconds"] / timing["records"] * work}
                if limits:
                    bounds["sustained_token_limit"] = (stage["input_tokens"] + stage["output_tokens"]) / measured_count * work / limits["tpm"] * 60
                    bounds["sustained_request_limit"] = stage["attempts"] / measured_count * work / limits["rpm"] * 60
                constraints[role] = {"seconds_before_conservative_factor": bounds,
                    "binding_constraint": max(bounds, key=bounds.get)}
                seconds += max(bounds.values()) * factor * (1.5 if conservative else 1)
            estimates.append({"scenario": ("conservative" if conservative else "base") + ("_exact_reuse" if reuse else "_no_reuse"),
                "estimated_api_usd": str(cost), "estimated_hours": seconds/3600,
                "target_classified_nonempty_ids": volume, "estimated_distinct_texts": unique,
                "verification_source_ids": verification_count, "workers": e["workers"], "estimate_not_execution": True,
                "under_two_hour_target": seconds <= 7200, "throughput_constraints": constraints})
    return estimates


def compute(directory="cost/scaling_500", rates_path=None, volume=100000, verification_fraction=.2):
    directory = Path(directory)
    summary = read_json(directory/"pilot_summary.json")
    calls = read_jsonl(directory/"pilot_calls.jsonl")
    card = rates(rates_path or directory/"rates.csv")
    # The generic pilot calculator's time projection is serial; use only its audited billing arithmetic.
    normalized = summary | {"status": "offline_scaling_replay", "unique_nonempty_texts": 500}
    result, units = calculate(calls, normalized, card, volume=volume, budget=10)
    result["measured"]["status"] = summary["status"]
    limits = sustained_limits(calls) if summary["config"]["execution_mode"] == "scaling-pilot-v2" else None
    profile_path = directory/"target_profile.json"
    profile = read_json(profile_path) if profile_path.exists() else None
    exact_texts = profile["distinct_nonempty_texts"] if profile and profile["selected_nonempty_ids"] == volume else None
    result["projections"] = forecast(summary, result["stages"], volume, limits, exact_texts, verification_fraction) if summary["status"] == "completed" else []
    if exact_texts is not None:
        result["target_input_profile"] = profile
    if limits:
        result["sustained_rate_limits"] = limits
        result["forecast_version"] = "parallel-steady-rate-limits-v2"
    result["controls"] = {"shared_total_cap_usd": 10, "pilot_cap_usd": .25,
        "max_workers": summary["config"]["workers"], "max_output_tokens_responses": 4096, "verification_fraction": verification_fraction, "fallback_fraction": 0}
    result["projection_notes"] = [
        "Estimates, not executions. Time comes from the selected measured parallel phases.",
        (f"Exact reuse uses the offline proposed target profile: {volume:,} original IDs and {exact_texts:,} distinct texts. No target model calls have been made; selection changes require a new profile." if exact_texts is not None else "Exact reuse assumes the full corpus distinct/nonempty ratio; this projected volume has no matching target profile."),
        "Cold is cumulative active processing: ramp stages, failed requests, corrected verification, grouping and memo. Source selection, process startup, development/repair and human/approval waiting are excluded.",
        "Disjoint fresh batches test ramp stages; review length/content and small sample sizes confound direct speedup comparisons.",
        "Conservative case includes at least 10% retries and 50% slower processing; sustained performance is unproven.",
        "Unknown charges remain separate. Hosting/local compute and historical paid work are excluded from projected API subtotals.",
        "Decisions is billed on all input tokens only; no Responses cached-input discount or output fee is applied to that endpoint.",
        "No provider Batch discount is assumed; requests used synchronous Standard processing."]
    if verification_fraction != .2:
        result["projection_notes"].append(f"Future verification is projected at {verification_fraction:.1%}; the measured pilot checked 100 of 500 reviews (20%) and its measurements are unchanged.")
    if limits:
        result["projection_notes"] += [
            f"Steady-state forecast uses the slower of measured throughput, {limits['rpm']:g} requests/minute and {limits['tpm']:g} tokens/minute. Burst credits are not extrapolated indefinitely.",
            "The current pipeline runs enrichment then verification sequentially; no unmeasured overlap or higher limiter capacity is assumed."]
    trial_path = directory/"verification_batch_trial.json"
    if limits and trial_path.exists():
        trial = read_json(trial_path)
        trial_calls = read_jsonl(directory/"verification_batch_trial_calls.jsonl")
        if trial["status"] == "completed" and trial["completed_predictions"] == 100 and trial["parent_measurements_unchanged"]:
            trial_billing, _ = calculate(trial_calls, normalized, card, volume=volume, budget=10)
            candidate_stages = result["stages"] | {"verify": trial_billing["stages"]["verify"]}
            # Replace the verification timing while preserving the parent's measured fixed overhead.
            candidate_summary = dict(summary)
            candidate_summary["phase_measurements"] = [dict(p) for p in summary["phase_measurements"]]
            verification_phase = next(p for p in candidate_summary["phase_measurements"] if p["phase"] == "verify-8")
            candidate_summary["cold_seconds"] += trial["elapsed_seconds"]-verification_phase["elapsed_seconds"]
            verification_phase["elapsed_seconds"] = trial["elapsed_seconds"]
            candidate = {"measurement_sources": {"enrichment_group_memo": trial["parent_run"], "verification": trial["run_id"]},
                "method": "Derived projection combining separately measured stages; not a composite cold execution. Same 500-review sample, same 100 independently checked source IDs.",
                "verification_batch_size": 10, "stages": candidate_stages,
                "trial_elapsed_seconds": trial["elapsed_seconds"], "trial_known_api_usd": trial_billing["measured"]["known_api_usd"],
                "combined_measured_known_api_usd": str(Decimal(result["measured"]["known_api_usd"])+Decimal(trial_billing["measured"]["known_api_usd"])),
                "sustained_rate_limits": sustained_limits(calls+trial_calls),
                "projections": forecast(candidate_summary, candidate_stages, volume, sustained_limits(calls+trial_calls), exact_texts, verification_fraction)}
            result["verification_batch_candidate"] = candidate
    return result, units


def replay(directory="cost/scaling_500", rates_path=None, volume=100000):
    directory = Path(directory)
    result, units = compute(directory, rates_path, volume)
    write_json(directory/"calculator.json", result)
    if result.get("sustained_rate_limits"):
        selected = result.get("verification_batch_candidate", result)
        projection_name = f"projection_{volume//1000}k.json" if volume % 1000 == 0 else f"projection_{volume}.json"
        write_json(directory/projection_name, {
            "status": "estimated", "forecast_version": result["forecast_version"],
            "measurement_sources": selected.get("measurement_sources", {"all_stages": result["measured"]["run_id"]}),
            "method": selected.get("method", "Projection from the measured parallel pilot phases"),
            "projections": selected["projections"], "primary_baseline_projections": result["projections"],
            "sustained_rate_limits": result["sustained_rate_limits"], "notes": result["projection_notes"]})
    write_csv(directory/"usage.csv", units, ["local_call_id", "role", "item", "billed_units", "price_per_unit", "calculated_usd", "currency"])
    measured = result["measured"]
    lines = ["# Measured 500-review scaling pilot", "", f"Status: **{measured['status']}**", "",
        f"Completed: {measured['completed']}/500. Cold processing: {measured['cold_seconds']:.3f} seconds.",
        f"Known usage-based API cost: US${measured['known_api_usd']}. Unknown-usage calls: {len(measured['unresolved_calls'])}.",
        f"Unresolved reservations: US${measured['unresolved_reservation_usd']}.",
        f"Warm replay: {measured.get('warm_seconds')} seconds; {measured.get('warm_new_calls')} new model calls.", "",
        "## Actual ramp measurements", "", "| Stage | Worker limit | Planned reviews | Seconds | Status | Completed reviews/second |", "|---|---:|---:|---:|---|---:|"]
    if "processing_plus_initial_preparation_seconds" in measured:
        lines[4:4] = [f"Initial source preparation plus active processing: {measured['processing_plus_initial_preparation_seconds']:.3f} seconds; process startup excluded.", ""]
    for phase in measured["phase_measurements"]:
        throughput = f"{phase['records']/phase['elapsed_seconds']:.3f}" if phase['completed'] else "—"
        lines.append(f"| {phase['phase']} | {phase['workers']} | {phase['records']} | {phase['elapsed_seconds']:.3f} | {'completed' if phase['completed'] else 'failed request contract'} | {throughput} |")
    lines += ["", f"## Estimated {volume:,}-review processing", "", "| Scenario | Estimated API cost | Estimated hours | Under two hours? |", "|---|---:|---:|---|"]
    for p in result["projections"]:
        lines.append(f"| {p['scenario']} | US${Decimal(p['estimated_api_usd']):.3f} | {p['estimated_hours']:.2f} | {'yes, estimated' if p['under_two_hour_target'] else 'no'} |")
    candidate = result.get("verification_batch_candidate")
    if candidate:
        lines += ["", "## Tested verification batching candidate", "", candidate["method"], "",
            f"Ten reviews per verification request: 100 saved predictions in {candidate['trial_elapsed_seconds']:.3f} seconds across ten requests. Extra usage cost: US${candidate['trial_known_api_usd']}.",
            f"Actual parent pilot plus additional trial cost: US${candidate['combined_measured_known_api_usd']}; original cold/warm measurements above remain unchanged.", "",
            "Forecast below replaces the verifier stage basis with this trial; it does not double-count the original and replacement verification. Verification remains 20% of source IDs.", "",
            "| Scenario | Estimated API cost | Estimated minutes | Under two hours? |", "|---|---:|---:|---|"]
        for p in candidate["projections"]:
            lines.append(f"| {p['scenario']} | US${Decimal(p['estimated_api_usd']):.3f} | {p['estimated_hours']*60:.1f} | {'yes, estimated' if p['under_two_hour_target'] else 'no'} |")
    lines += ["", "## Limits and interpretation", ""] + ["- " + n for n in result["projection_notes"]]
    lines += ["", "Independent verification compares Luna Responses against GPT Decisions using the same model family. It measures consistency, not independent human accuracy.", "",
        "Offline replay (no API key or model calls):", "", "```sh", f"python3 -m spotify_pipeline scaling-replay --directory {directory}", "```", ""]
    atomic_text(directory/"report.md", "\n".join(lines))
    return result
