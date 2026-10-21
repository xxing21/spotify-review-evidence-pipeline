"""Offline audit of the fresh 500-review scaling experiment; no model calls."""
import collections
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_submission import audit, reference, reference_hash
from spotify_pipeline.common import (LABEL_FIELDS, csv_rows, digest, load_env, now, read_json,
    read_jsonl, row_sha, sha, source_records, write_csv, write_json)
from spotify_pipeline.pipeline import rerank_exports
from spotify_pipeline.scaling_cost import compute, replay


def run(variant="eight"):
    root = Path.cwd()
    run_id = "scaling-500-16w-v1" if variant == "sixteen" else "scaling-500-v1"
    suffix = "scaling_500_16w" if variant == "sixteen" else "scaling_500"
    directory = root/"artifacts/runs"/run_id
    cost = root/"cost"/suffix
    evaluation = root/"evals"/suffix
    evaluation.mkdir(parents=True, exist_ok=True)
    summary = read_json(cost/"pilot_summary.json")
    rows = source_records(directory/"input_500.csv")
    records = read_jsonl(directory/"records.jsonl")
    calls = read_jsonl(cost/"pilot_calls.jsonl")
    indexed = {r["review_id"]: r for r in records}
    selected_ids = {r["review_id"] for r in rows}
    original = {r["review_id"]: r for r in csv_rows("spotify_reviews_18months.csv") if r["review_id"] in selected_ids}
    source_match = all(row_sha(r) == row_sha(original[r["review_id"]]) for r in rows)
    ref = reference("spotify_reviews_18months.csv", directory/"input_500.csv")
    checker = audit(directory/"grading", ref, ref_digest=reference_hash(ref))
    write_json(directory/"reference.json", ref)
    write_json(directory/"self-check.json", checker)
    verification = read_json(directory/"verification.json")
    differences = []
    agreement = {}
    for field in LABEL_FIELDS:
        agreement[field] = sum(p[field] == indexed[p["review_id"]][field] for p in verification["predictions"])/100
    for p in verification["predictions"]:
        differences.append({"review_id": p["review_id"], "source_text": original[p["review_id"]]["review_text"],
            "enrichment": {k: indexed[p["review_id"]][k] for k in LABEL_FIELDS},
            "independent_verification": {k: p[k] for k in LABEL_FIELDS},
            "different_fields": [k for k in LABEL_FIELDS if p[k] != indexed[p["review_id"]][k]]})
    write_json(evaluation/"verification_review.json", {"sample_count": 100,
        "method": "Independent original-text/rubric GPT Decisions, not human truth; same gpt-6-luna model family",
        "agreement": agreement,
        "severity_mae": sum(abs(p["severity"]-indexed[p["review_id"]]["severity"]) for p in verification["predictions"])/100,
        "sentiment_mae": sum(abs(p["sentiment"]-indexed[p["review_id"]]["sentiment"]) for p in verification["predictions"])/100,
        "core_label_disagreements": verification["label_disagreements"], "cases": differences})
    source_only = True
    for p in (directory/"handoffs").glob("*.json"):
        handoff = read_json(p)
        if handoff["attempt"]["role"] in {"enrich", "verify"}:
            data = json.loads(handoff["request"]["input"][1]["content"])
            source_only &= set(data) == {"reviews"} and all(set(r) == {"review_id", "review_text"} for r in data["reviews"])
    phases = []
    for name in dict.fromkeys(p["phase"] for p in summary["phase_measurements"]):
        points = []
        for c in calls:
            if (c.get("worker_id") or "").startswith(name+"-") and c.get("duration_seconds") is not None:
                started = datetime.fromisoformat(c["started_at"]).timestamp()
                points += [(started, 1), (started+c["duration_seconds"], -1)]
        active = peak = 0
        for _, delta in sorted(points):
            active += delta
            peak = max(active, peak)
        phases.append({"phase": name, "peak_overlapping_attempts": peak})
    write_json(evaluation/"concurrency.json", {"measure": "Overlap of recorded request start timestamps and monotonic durations",
        "phases": phases, "note": "Verifier pool limit eight; actual overlap can be lower for fast requests and limiter pacing."})
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        ranking = (directory/"ranking.csv").read_bytes()
        portable = temp/"portable"
        portable.mkdir()
        for name in ("records.jsonl", "membership.csv", "ranking.csv", "claims.csv"):
            shutil.copy2(directory/name, portable/name)
        rerank_exports(portable)
        rerank_same = (portable/"ranking.csv").read_bytes() == ranking
        rates_rows = list(csv_rows(cost/"rates.csv"))
        for rate in rates_rows:
            rate["price_per_unit"] = str(Decimal(rate["price_per_unit"])*2)
        doubled_path = temp/"double_rates.csv"
        write_csv(doubled_path, rates_rows, list(rates_rows[0]))
        base, _ = compute(cost)
        doubled, _ = compute(cost, doubled_path)
        volume_changed, _ = compute(cost, volume=200000)
        rates_double = Decimal(doubled["measured"]["known_api_usd"]) == 2 * Decimal(base["measured"]["known_api_usd"])
        time_same = doubled["measured"]["cold_seconds"] == base["measured"]["cold_seconds"]
        volume_preserves = volume_changed["measured"] == base["measured"]
    load_env()
    secret = os.environ.get("OPENAI_API_KEY", "")
    inspected = [p for parent in (directory, cost, evaluation) for p in parent.rglob("*") if p.is_file()]
    leaks = [str(p.relative_to(root)) for p in inspected if secret and secret.encode() in p.read_bytes()]
    write_json(evaluation/"secret_check.json", {"passed": not leaks, "files_scanned": len(inspected), "affected_paths": leaks})
    attempts = collections.Counter((c["role"], rid) for c in calls for rid in c["review_ids"])
    prior_texts = set()
    from spotify_pipeline.store import Store
    store = Store()
    try:
        prior_texts = {r[0] for r in store.db.execute("SELECT DISTINCT text_sha FROM cache WHERE run_id!=?", (run_id,))}
        ledger = str(store.committed_spend())
    finally:
        store.close()
    all_in_budget = Decimal(summary["known_api_usd"]) + Decimal(summary["unresolved_reservations_usd"]) <= Decimal('.25') and Decimal(ledger) <= 10
    acceptance = {"saved_at": now(), "scope": "500 fresh original source IDs; not a 100k execution",
        "completed_original_ids": checker["coverage"]["valid_completed"], "original_source_values_match": source_match,
        "fresh_unique_texts": len({r["review_text"] for r in rows}) == 500,
        "no_prior_text_results_used": not any(digest(r["review_text"]) in prior_texts for r in rows),
        "classification_and_verification_inputs_source_only": source_only,
        "verification_count": len(verification["predictions"]), "warm_new_calls": summary["warm_new_calls"],
        "configured_worker_limit": summary["config"]["workers"],
        "actual_enrichment_peak_concurrency": next(p["peak_overlapping_attempts"] for p in phases if p["phase"] == summary.get("enrichment_projection_phase", "enrich-8")),
        "maximum_label_attempts_per_review": max(attempts.values()),
        "offline_ranking_identical": rerank_same, "doubled_rates_double_api_cost": rates_double,
        "doubled_rates_preserve_measured_time": time_same, "changed_volume_preserves_measurements": volume_preserves,
        "earlier_artifacts_unchanged": summary["original_artifacts_unchanged"], "secret_check_passed": not leaks,
        "within_both_budget_caps": all_in_budget, "checker_status": checker["status"],
        "checker_issue_counts": checker["issue_counts"], "unresolved_usage_calls": summary["unknown_usage_calls"]}
    acceptance["processing_and_scaling_checks_passed"] = all([
        acceptance["completed_original_ids"] == 500, source_match, acceptance["fresh_unique_texts"],
        acceptance["no_prior_text_results_used"], source_only, acceptance["verification_count"] == 100,
        acceptance["warm_new_calls"] == 0,
        8 < acceptance["actual_enrichment_peak_concurrency"] <= 16 if variant == "sixteen" else acceptance["actual_enrichment_peak_concurrency"] == 8,
        acceptance["maximum_label_attempts_per_review"] <= 3, rerank_same, rates_double, time_same,
        volume_preserves, summary["original_artifacts_unchanged"], not leaks, all_in_budget])
    acceptance["fully_reconciled_checker_pass"] = checker["status"] == "pass"
    write_json(evaluation/"acceptance.json", acceptance)
    write_json("cost/budget_ledger.json", {"cap_usd": 10, "spent_plus_unresolved_reservations_usd": ledger,
        "scope": "All experiments in shared SQLite ledger, including the scaling pilot; no budget reset on resume"})
    replay(cost)
    print(json.dumps(acceptance, indent=2))
    return acceptance


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("eight", "sixteen"), default="eight")
    outcome = run(parser.parse_args().variant)
    raise SystemExit(0 if outcome["processing_and_scaling_checks_passed"] else 1)
