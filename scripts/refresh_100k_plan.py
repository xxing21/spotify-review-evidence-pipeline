"""Regenerate the approved 100k planning estimate offline; does not initialize a run."""
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spotify_pipeline.common import atomic_text, now, read_json, write_json
from spotify_pipeline.scaling_cost import compute


def main():
    directory = Path("cost/planning_100k")
    plan = read_json(directory/"run_plan.json")
    result, _ = compute(plan["measurement_directory"], volume=plan["target_nonempty_ids"],
        verification_fraction=plan["verification_fraction"])
    candidate = result["verification_batch_candidate"]
    assert all(p["verification_source_ids"]==plan["verification_sample_size"] for p in candidate["projections"])
    ledger = read_json("cost/budget_ledger.json")["spent_plus_unresolved_reservations_usd"]
    output = {"saved_at": now(), "status": "estimate_not_execution", "plan": plan,
        "existing_spend_plus_reservations_usd": ledger, "calculator": result}
    write_json(directory/"approved_projection.json", output)
    lines = ["# Approved 100k plan: 5% independent verification", "",
        "Planned only. No 100k paid execution has started. All 100,000 original IDs would still be classified; 5,000 would receive independent model checks.", "",
        "The user approved reducing future verification from 20% to 5%. The assignment requires a declared independent random sample without a minimum percentage. Completed pilots retain their original 20% samples, prompts, labels, calls and timings.", "",
        "Estimates combine measured 16-worker/20-review Luna enrichment with measured ten-review GPT Decisions verification batches. The proposed 100k inputs contain 78,288 distinct texts and 21,712 exact-text duplicates. Sustained rate limits are included; this is not a timed 100k run.", "",
        "| Scenario | Estimated minutes | Estimated API cost | Including existing work/reservations |", "|---|---:|---:|---:|"]
    for p in candidate["projections"]:
        amount = Decimal(p["estimated_api_usd"])
        lines.append(f"| {p['scenario']} | {p['estimated_hours']*60:.1f} | US${amount:.2f} | US${amount+Decimal(ledger):.2f} |")
    lines += ["", "The conservative case includes at least 10% retries and 50% slower throughput. Local/hosting costs and unmeasured larger-run overhead are separate. Under two hours remains a target rather than a guarantee.", "",
        "Keep the 50 human labels/evaluation, planted-error and injection tests, and disagreement inspection. Lower verification checks fewer individual records and does not establish higher label accuracy.", "",
        "The US$10 shared API cap includes all prior spend and unresolved reservations. Full-run execution mode remains to be implemented.", "",
        "Regenerate without a key or model calls:", "", "```sh", "python3 scripts/refresh_100k_plan.py", "```", ""]
    atomic_text(directory/"approved_report.md", "\n".join(lines))
    print(json.dumps({"verification_fraction": plan["verification_fraction"], "verification_reviews": plan["verification_sample_size"],
        "projections": [{"scenario": p["scenario"], "estimated_minutes": p["estimated_hours"]*60, "estimated_api_usd": p["estimated_api_usd"]} for p in candidate["projections"]],
        "new_model_calls": 0}, indent=2))


if __name__ == "__main__":
    main()
