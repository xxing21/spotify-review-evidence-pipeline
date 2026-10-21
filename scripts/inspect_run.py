"""Create human-readable, deterministic evidence links from a saved real run."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spotify_pipeline.common import atomic_text, read_json, read_jsonl, write_json


def inspect(run_id="pilot-100-v2"):
    directory = Path("artifacts/runs") / run_id
    records = read_jsonl(directory / "records.jsonl")
    completed = {r["review_id"]: r for r in records if r["status"] == "completed"}
    verification = read_json(directory / "verification.json")
    verifier = {r["review_id"]: r for r in verification["predictions"]}
    memo = read_json(directory / "memo.json")
    evidence = read_json(directory / "evidence.json")
    cited = [e for e in evidence if e["review_id"] in memo["review_ids"]]
    selected = next((e for e in cited if e["review_id"] in verifier), cited[0] if cited else None)
    trace = {"run_id": run_id, "scope": "pilot_only"}
    if selected:
        rid = selected["review_id"]
        trace.update(review_id=rid, source_sha256=completed[rid]["source_sha256"], enrichment=completed[rid],
            independent_verification=verifier.get(rid), membership=selected["issue_id"],
            memo_claim_ids=[c for c in memo["claim_ids"] if c.startswith(selected["issue_id"] + "-")])
    ambiguous = [r for r in completed.values() if r["needs_review"]]
    failures = [r for r in records if r["status"] != "completed"]
    disagreements = [c for c in verification["comparisons"] if c["different_fields"]]
    trace["ambiguous_or_failed_case"] = (ambiguous or failures or disagreements or [None])[0]
    trace["human_inspection_status"] = "pending"
    write_json(directory / "trace.json", trace)
    lines = ["# Source-to-claim trace — actual pilot evidence", ""]
    if selected:
        lines += [f"Review ID: `{trace['review_id']}`", f"Source row hash: `{trace['source_sha256']}`", "",
            f"Enrichment: {trace['enrichment']['topic']} / {trace['enrichment']['intent']} / severity {trace['enrichment']['severity']}.",
            "Independent verifier: " + (json.dumps(trace["independent_verification"], ensure_ascii=False) if trace["independent_verification"] else "not selected by the declared random sample; no verification is claimed for this ID"),
            f"Membership: `{trace['membership']}`; see membership.csv and ranking.csv.",
            "Memo claim references: " + ", ".join(trace["memo_claim_ids"]), "",
            "Exact quote: " + json.dumps(trace["enrichment"]["evidence_quote"], ensure_ascii=False), ""]
    lines += ["## Failure/ambiguity handling", "",
        json.dumps(trace["ambiguous_or_failed_case"], ensure_ascii=False, indent=2), "",
        "Ambiguous cases are retained with needs_review and are not silently excluded from business counts.",
        "All failed provider attempts remain in calls.jsonl; unknown charges keep reservations.",
        "Human inspection of label correctness and the final argument remains pending."]
    atomic_text(directory / "trace.md", "\n".join(lines) + "\n")
    return trace


if __name__ == "__main__":
    result = inspect(sys.argv[1] if len(sys.argv) > 1 else "pilot-100-v2")
    print(json.dumps({"review_id": result.get("review_id"), "human_inspection_status": result["human_inspection_status"]}))
