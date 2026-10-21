"""Offline acceptance for the bounded batch-10 verification trial; no model calls."""
import json
import os
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spotify_pipeline.common import csv_rows, ground_labels, load_env, now, read_json, read_jsonl, sha, write_csv, write_json
from spotify_pipeline.decisions import decision_charge, parse_decision
from spotify_pipeline.provider import rates
from spotify_pipeline.scaling_cost import compute
from spotify_pipeline.store import Store


def run():
    cost = Path("cost/scaling_500_16w")
    evaluation = Path("evals/scaling_500_16w")
    trial = read_json(cost/"verification_batch_trial.json")
    directory = Path("artifacts/runs")/trial["run_id"]
    parent = Path("artifacts/runs")/trial["parent_run"]
    source = {r["review_id"]: r["review_text"] for r in csv_rows(parent/"input_500.csv")}
    expected = read_json(parent/"verification.json")["sample_ids"]
    saved = read_json(directory/"predictions.json")["records"]
    reconstructed, source_only, billing_matches = [], True, True
    for p in sorted((directory/"handoffs").glob("*.json")):
        handoff = read_json(p)
        reviews = json.loads(handoff["request"]["input"][1]["content"])["reviews"]
        source_only &= len(reviews) == 10 and all(set(r)=={"review_id", "review_text"} and source.get(r["review_id"])==r["review_text"] for r in reviews)
        reconstructed.extend(ground_labels(parse_decision(handoff["response"], reviews), reviews)["records"])
        billing_matches &= decision_charge(handoff["response"]["usage"], rates(cost/"rates.csv")) == Decimal(handoff["attempt"]["calculated_api_usd"])
    calls = read_jsonl(cost/"verification_batch_trial_calls.jsonl")
    with tempfile.TemporaryDirectory() as temp:
        rows = list(csv_rows(cost/"rates.csv"))
        for row in rows:
            row["price_per_unit"] = str(Decimal(row["price_per_unit"])*2)
        doubled_path = Path(temp)/"rates.csv"
        write_csv(doubled_path, rows, list(rows[0]))
        base, _ = compute(cost)
        doubled, _ = compute(cost, doubled_path)
        volume, _ = compute(cost, volume=200000)
    candidate = base["verification_batch_candidate"]
    profile = base["target_input_profile"]
    planned_ids = [r["review_id"] for r in csv_rows("cost/planning_100k/proposed_100k_ids.csv")]
    selected_ids = set(planned_ids)
    selected = [r for r in csv_rows("spotify_reviews_18months.csv") if r["review_id"] in selected_ids]
    profile_matches = (len(planned_ids)==len(selected_ids)==len(selected)==profile["selected_nonempty_ids"]==100000
        and all(r["review_text"] for r in selected)
        and len({r["review_text"] for r in selected})==profile["distinct_nonempty_texts"]
        and sha("cost/planning_100k/proposed_100k_ids.csv")==profile["selected_ids_sha256"]
        and sha("spotify_reviews_18months.csv")==profile["source_sha256"])
    rates_double = all(Decimal(q["estimated_api_usd"]) == 2*Decimal(p["estimated_api_usd"]) for p,q in zip(candidate["projections"], doubled["verification_batch_candidate"]["projections"]))
    time_same = [p["estimated_hours"] for p in candidate["projections"]] == [p["estimated_hours"] for p in doubled["verification_batch_candidate"]["projections"]]
    measures_same = base["measured"] == volume["measured"] and candidate["trial_elapsed_seconds"] == volume["verification_batch_candidate"]["trial_elapsed_seconds"]
    load_env()
    secret = os.environ.get("OPENAI_API_KEY", "")
    paths = [p for root in (directory, cost, evaluation) for p in root.rglob("*") if p.is_file()]
    secret_clean = not any(secret and secret.encode() in p.read_bytes() for p in paths)
    store = Store()
    try:
        committed = store.committed_spend()
    finally:
        store.close()
    comparison = {r["review_id"]: r for r in reconstructed}
    outcome = {"saved_at": now(), "scope": "Same 500-review sample, independent recheck of the same 100 source IDs; not 100 additional enrichment records",
        "completed_predictions": len(saved), "exact_sample_ids": len(saved)==100 and {r["review_id"] for r in saved}==set(expected),
        "saved_predictions_reproduce_raw_answers": all(comparison.get(r["review_id"])==r for r in saved) and len(reconstructed)==100,
        "source_only_inputs": source_only, "billing_matches_raw_usage": billing_matches,
        "maximum_one_attempt_per_task": len(calls)==10 and all(c["task_attempt"]==1 for c in calls),
        "parent_measurements_unchanged": trial["parent_measurements_unchanged"],
        "all_usage_available": trial["unknown_usage_calls"]==0,
        "rates_double_projection_cost": rates_double, "rates_preserve_projection_time": time_same,
        "volume_preserves_measurements": measures_same, "secret_check_passed": secret_clean,
        "proposed_target_profile_matches_original_sources": profile_matches,
        "combined_pilot_cost_usd": trial["pilot_plus_trial_known_usd"],
        "global_committed_usd": str(committed),
        "within_caps": Decimal(trial["pilot_plus_trial_known_usd"])+Decimal(trial["unresolved_reservations_usd"])<=Decimal('.25') and committed<=10}
    outcome["passed"] = all(v for k,v in outcome.items() if type(v) is bool)
    write_json(evaluation/"verification_batch_trial_acceptance.json", outcome)
    write_json("cost/budget_ledger.json", {"cap_usd": 10, "spent_plus_unresolved_reservations_usd": str(committed),
        "scope": "All experiments in shared SQLite ledger, including the verifier batching trial; no budget reset on resume"})
    print(json.dumps(outcome, indent=2))
    return outcome["passed"]


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
