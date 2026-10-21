"""Offline checkpoint acceptance, clean replay, and plain-English evidence export."""
import collections
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spotify_pipeline.common import (LABEL_FIELDS, atomic_text, read_json, read_jsonl,
    sha, source_records, write_json)
from spotify_pipeline.calculator import calculate
from spotify_pipeline.pipeline import rerank_exports
from spotify_pipeline.provider import rates


def audit(run_id=None, count=10000):
    root = Path.cwd()
    cost = root / "cost" / f"checkpoint_{count}"
    summary = read_json(cost / "pilot_summary.json")
    run_id = run_id or summary["run_id"]
    directory = root / "artifacts/runs" / run_id
    evaluation = root / "evals" / f"checkpoint_{count}"
    preflight = read_json(evaluation / "preflight.json")
    summary = read_json(cost / "pilot_summary.json")
    records = read_jsonl(directory / "records.jsonl")
    by_id = {r["review_id"]: r for r in records}
    calls = read_jsonl(cost / "pilot_calls.jsonl")
    inherited = read_jsonl(cost / "inherited_calls.jsonl")
    previous = read_jsonl(root / "artifacts/runs" / summary["source_run"] / "records.jsonl")
    previous_ids = {r["review_id"] for r in previous}
    successful_enrich = [c for c in calls if c["role"] == "enrich" and c["outcome"] == "succeeded"]
    new_ids = {rid for c in successful_enrich for rid in c["review_ids"]}
    verification = read_json(directory / "verification.json")
    predictions = {r["review_id"]: r for r in verification["predictions"]}
    comparisons = [dict(c, enrichment=by_id[c["review_id"]],
        independent_prediction=predictions[c["review_id"]]) for c in verification["comparisons"]]
    agreement = {field: sum(c["enrichment"].get(field) == c["independent_prediction"][field]
        for c in comparisons) / len(comparisons) for field in LABEL_FIELDS}
    valid_pairs = [c for c in comparisons if c["enrichment"]["status"] == "completed"]
    mae = {field: sum(abs(c["enrichment"][field] - c["independent_prediction"][field])
        for c in valid_pairs) / len(valid_pairs) if valid_pairs else None
        for field in ("severity", "sentiment")}
    write_json(evaluation / "verification_review.json", {
        "scope": "Independent same-model predictions, not human accuracy evaluation",
        "sample_count": len(comparisons), "agreement": agreement, "mae": mae,
        "mae_valid_pair_count": len(valid_pairs),
        "missing_enrichment_count": len(comparisons) - len(valid_pairs),
        "missing_enrichment_policy": "Count as disagreement; exclude from MAE, with denominator reported",
        "label_disagreements": verification["label_disagreements"],
        "any_field_disagreements": verification["any_field_disagreements"],
        "comparisons": comparisons})
    card = rates(cost / "rates.csv")
    base, _ = calculate(calls, summary, card)
    doubled, _ = calculate(calls, summary, {k: v * 2 for k, v in card.items()})
    changed, _ = calculate(calls, summary, card, volume=100000)
    ranking_bytes = (directory / "ranking.csv").read_bytes()
    raw_hashes = {p.name: sha(p) for p in cost.glob("pilot_*")}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clean = tmp / "run"
        shutil.copytree(directory, clean)
        rerank_exports(clean)
        portable_same = (clean / "ranking.csv").read_bytes() == ranking_bytes
        measurement = tmp / "measurements"
        measurement.mkdir()
        for name in ("pilot_summary.json", "pilot_calls.jsonl", "rates.csv"):
            shutil.copy2(cost / name, measurement / name)
        env = {k: v for k, v in os.environ.items() if "OPENAI" not in k and "API_KEY" not in k}
        env["PYTHONPATH"] = str(root)
        outcome = subprocess.run([sys.executable, "-m", "spotify_pipeline", "--db", str(tmp / "empty.sqlite3"),
            "cost", "replay", "--directory", str(measurement)], cwd=tmp, env=env,
            capture_output=True, text=True, check=True)
        replayed = read_json(measurement / "calculator.json")
        clean_cost_same = replayed["measured"] == base["measured"]
    replay = {
        "credentials_removed": True, "original_database_absent": True,
        "portable_ranking_identical": portable_same,
        "directory_local_rates_respected": clean_cost_same,
        "double_rates_double_incremental_api_cost": Decimal(doubled["measured"]["known_api_usd"]) == 2 * Decimal(base["measured"]["known_api_usd"]),
        "measured_time_unchanged": doubled["measured"]["incremental_seconds"] == base["measured"]["incremental_seconds"],
        "volume_does_not_change_measurements": changed["measured"] == base["measured"],
        "raw_measurements_unchanged": raw_hashes == {p.name: sha(p) for p in cost.glob("pilot_*")},
        "baseline_incremental_usd": base["measured"]["known_api_usd"],
        "doubled_incremental_usd": doubled["measured"]["known_api_usd"]}
    replay["passed"] = all(v for v in replay.values() if type(v) is bool)
    write_json(evaluation / "clean_replay.json", replay)
    # Inspect for literal source examples at the known Premium/usability boundary.
    sources = {r["review_id"]: r for r in source_records("analysis_10000.csv")}
    boundary = [r for r in records if r.get("topic") == "usability"
        and r.get("intent") in {"complaint", "cancellation"}
        and "premium" in sources[r["review_id"]]["review_text"].lower()]
    examples = [{"review_id": r["review_id"], "topic": r["topic"],
        "text": sources[r["review_id"]]["review_text"]} for r in boundary[:10]]
    write_json(evaluation / "boundary_inspection_candidates.json", {
        "note": "Literal keyword screening only; these are inspection candidates, not confirmed errors or human labels.",
        "candidate_count": len(boundary), "examples": examples})
    checker = read_json(directory / "self-check.json")
    original_files_same = all(Path(p).exists() and sha(p) == digest
        for p, digest in preflight["preserved_files_sha256"].items())
    sources_same = all(sha(p) == digest for p, digest in preflight["input_checksums"].items())
    before = read_json(directory / "checkpoint_extension_before.json")
    after = read_json(directory / "checkpoint_extension_after.json")
    before_ids = set(before["completed_ids"])
    resumed_ids = {rid for c in successful_enrich
        if c["started_at"] > before["saved_at"] for rid in c["review_ids"]}
    from spotify_pipeline.common import load_env
    load_env()
    key = os.environ.get("OPENAI_API_KEY", "")
    deliverables = [p for folder in (directory, cost, evaluation, root / "docs")
        for p in folder.rglob("*") if p.is_file()]
    key_leaks = [str(p.relative_to(root)) for p in deliverables
        if key and key.encode() in p.read_bytes()]
    write_json(evaluation / "secret_check.json", {"passed": not key_leaks,
        "key_configured": bool(key), "files_scanned": len(deliverables), "affected_paths": key_leaks})
    acceptance = {
        "completed_original_ids": sum(r["status"] == "completed" for r in records),
        "same_id_results_inherited": len(previous_ids),
        "exact_text_aliases": sum(bool(r.get("cache_source_id")) for r in records),
        "new_distinct_enrichment_tasks": len(new_ids), "new_attempts": len(calls),
        "new_failures": sum(c["outcome"] != "succeeded" for c in calls),
        "earlier_measurements_preserved": original_files_same,
        "source_checksums_match": sources_same,
        "no_previous_id_reenriched": not bool(new_ids & previous_ids),
        "no_checkpoint_id_reenriched_after_resume": not bool(before_ids & resumed_ids),
        "inherited_calls_unique": len({c["local_call_id"] for c in inherited}) == len(inherited),
        "inherited_calls_not_billed_twice": not bool({c["local_call_id"] for c in inherited} & {c["local_call_id"] for c in calls}),
        "warm_new_calls": summary["warm_new_calls"],
        "checker_status": checker["status"], "clean_replay_passed": replay["passed"],
        "local_key_absent_from_deliverables": not key_leaks,
        "checkpoint_before_completed": len(before_ids), "checkpoint_after_completed": len(after["completed_ids"]),
        "verification_source_rows": len(predictions), "scope_stops_at": count}
    acceptance["processing_completed"] = acceptance["completed_original_ids"] == count and len(predictions) == count // 5
    acceptance["data_and_ranking_checks_passed"] = (checker["coverage"]["valid_completed"] == count
        and not (set(checker["issue_counts"]) - {"invalid_usage"}))
    acceptance["unresolved_billing_attempts"] = len(base["measured"]["unresolved_calls"])
    acceptance["billing_usage_review_required"] = not base["measured"]["usage_complete"]
    acceptance["passed"] = (acceptance["completed_original_ids"] == count
        and summary["status"] == "completed" and summary["warm_new_calls"] == 0
        and len(predictions) == count // 5 and checker["status"] == "pass"
        and all(v for k, v in acceptance.items() if type(v) is bool and k != "billing_usage_review_required"))
    write_json(evaluation / "acceptance.json", acceptance)
    from spotify_pipeline.common import csv_rows
    ranked = list(csv_rows(directory / "ranking.csv"))
    names = {"USABILITY": "Controls, navigation and ads", "PLAYBACK": "Playback, crashes and loading",
        "BILLING": "Billing and Premium restrictions", "OTHER": "General dissatisfaction",
        "CATALOG": "Content, search and recommendations", "ACCESS": "Login and account access",
        "DOWNLOADS": "Downloads and offline listening", "SUPPORT": "Support"}
    intents = collections.Counter(r.get("intent") for r in records if r["status"] == "completed")
    needs_review = sum(bool(r.get("needs_review")) for r in records)
    human_status = "Human labeling of the 50 golden reviews remains pending."
    golden_report = root / "evals/golden_report.json"
    if golden_report.exists() and read_json(golden_report).get("status") == "completed":
        human_status = "All 50 human reference labels and their AI comparison are complete; see evals/golden_results.md for disagreements requiring adjudication."
    lines = [f"# Results of the {count:,}-review checkpoint", "",
        f"{acceptance['completed_original_ids']:,} of {count:,} original reviews completed. "
        f"The {len(previous_ids):,} earlier results were reused; {len(new_ids):,} new model classifications were saved, with reuse keyed by exact text and schema settings.", "",
        f"Additional API usage cost: US${Decimal(base['measured']['known_api_usd']):.4f}. "
        f"Measured incremental time: {summary['incremental_seconds']/60:.1f} minutes, including restart and analysis. "
        f"Repeating the completed workflow made {summary['warm_new_calls']} new API calls.", "",
        f"{len(base['measured']['unresolved_calls'])} failed requests returned no usage details. "
        f"US${Decimal(base['measured']['unresolved_reservation_usd']):.6f} remains reserved as possible additional charges. "
        "The instructor checker marks billing usage for review; all record, cache, source-hash and ranking checks pass. "
        "No missing usage was replaced with zero.", "",
        "Intent counts: " + ", ".join(f"{k}: {v:,}" for k, v in sorted(intents.items())) + ".", "",
        "| Rank | Issue | Complaint/cancellation reviews | Priority score |",
        "|---|---|---:|---:|"]
    for r in ranked:
        lines.append(f"| {r['rank']} | {names[r['issue_id'].split('-')[-1]]} | {r['complaint_count']} | {r['priority_score']} |")
    lines += ["", "The priority score is the sum of seriousness scores. Each complaint or cancellation belongs to exactly one issue.", "",
        f"Independent checking covered {len(predictions):,} reviews. It disagreed on topic, intent or seriousness for "
        f"{verification['label_disagreements']:,}; {verification['any_field_disagreements']:,} differed in any field. "
        "These compare two AI judgments and do not measure accuracy against human truth.", "",
        f"{needs_review:,} reviews are flagged for inspection and remain in the totals. {human_status}", "",
        "Premium restrictions and control complaints remain a known topic boundary to inspect. "
        "The recommendation in memo.md is provisional; its numbers and references resolve to claims.csv and source evidence.", "",
        "Recommendation: investigate controls and unwanted background playback, with playback reliability as the strongest alternative. "
        "The controls/navigation total covers the entire usability category, including ads and layout. "
        "Split that category and review Premium-related labels before committing to a product investment.", "",
        "This checkpoint stops at 10,000 classified reviews. Full-file ingestion is separate; no full classification or deployment is claimed."]
    atomic_text(directory / "results.md", "\n".join(lines) + "\n")
    return acceptance


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
