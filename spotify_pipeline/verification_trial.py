"""Bounded verifier batching experiment on the completed 16-worker pilot's same sample."""
import time
from decimal import Decimal
from pathlib import Path

from .common import LABEL_FIELDS, now, read_json, sha, write_json, write_jsonl
from .scaling import SharedLimiter, WorkQueue, batches, process_phase
from .store import Store

PARENT = "scaling-500-16w-v1"
RUN = "scaling-500-16w-verify10-v1"


def trial(db):
    store = Store(db)
    directory = Path("artifacts/runs")/RUN
    directory.mkdir(parents=True, exist_ok=True)
    cost = Path("cost/scaling_500_16w")
    try:
        old = store.get(RUN, "trial_summary")
        if old:
            return old
        parent = store.run(PARENT)
        summary = store.get(PARENT, "scaling_summary")
        if not parent or not summary or summary["status"] != "completed":
            raise ValueError("Complete the 500-review 16-worker pilot first")
        parent_calls = store.calls(PARENT)
        parent_committed = sum((Decimal(c.get("calculated_api_usd") or c["reservation_usd"]) for c in parent_calls), Decimal(0))
        cap = store.get(RUN, "fixed_trial_cap")
        if cap is None:
            cap = str(Decimal('.25')-parent_committed)
            if Decimal(cap) <= 0:
                raise ValueError("Parent pilot already exhausted the combined US$0.25 cap")
            store.put(RUN, "fixed_trial_cap", cap)
        cfg = parent["config"] | {"verification_schema_version": "decisions-verifier-v3-batch10-five-levels",
            "verification_batch_size": 10, "max_task_attempts": 1, "pilot_run_cap_usd": cap, "initial_phase": "verify-8"}
        store.new_run(RUN, parent["dataset"], cfg, {"kind": "verification_batch_benchmark", "parent_run": PARENT,
            "scope": "Same 100 verification IDs from the same 500-review pilot; no enrichment relabeling"})
        verification = store.get(PARENT, "verification")
        source = {r["review_id"]: r for r in store.sources(parent["dataset"])}
        selected = [source[rid] for rid in verification["sample_ids"]]
        protected = {str(p): sha(p) for p in [cost/"pilot_summary.json", cost/"pilot_calls.jsonl",
            Path("artifacts/runs")/PARENT/"records.jsonl", Path("artifacts/runs")/PARENT/"verification.json"]}
        queue = WorkQueue(store)
        queue.recover(RUN)
        queue.add(RUN, "verify", "verify-8", batches(selected, 10), cfg)
        started = time.monotonic()
        error = None
        try:
            process_phase(db, RUN, cfg, directory, "verify-8", 8, SharedLimiter(), started+120, transport=None)
        except Exception as e:
            error = str(e)
        seconds = time.monotonic()-started
        calls = store.calls(RUN)
        parsed = []
        for row in store.db.execute("SELECT result FROM calls WHERE run_id=? AND result IS NOT NULL ORDER BY rowid", (RUN,)):
            import json
            parsed.extend(json.loads(row[0])["records"])
        by_id = {r["review_id"]: r for r in store.records(PARENT)}
        known = sum((Decimal(c["calculated_api_usd"]) for c in calls if c.get("calculated_api_usd") is not None), Decimal(0))
        unknown = [c for c in calls if c.get("calculated_api_usd") is None]
        result = {"status": "completed" if len(parsed)==100 and not error else "incomplete", "run_id": RUN,
            "parent_run": PARENT, "scope": "Verification batching candidate on the same 100 original IDs; parent enrichment unchanged",
            "config": cfg, "sample_count": 100, "completed_predictions": len(parsed),
            "elapsed_seconds": seconds, "calls": len(calls), "known_api_usd": str(known),
            "unresolved_reservations_usd": str(sum((Decimal(c["reservation_usd"]) for c in unknown), Decimal(0))),
            "pilot_plus_trial_known_usd": str(parent_committed+known), "combined_pilot_cap_usd": ".25",
            "shared_committed_usd": str(store.committed_spend()), "unknown_usage_calls": len(unknown), "error": error,
            "parent_measurements_unchanged": all(sha(p)==h for p,h in protected.items()),
            "agreement": {k: sum(p[k]==by_id[p["review_id"]][k] for p in parsed)/len(parsed)
                for k in LABEL_FIELDS} if parsed else {},
            "method_note": "Same-model independent consistency, not human accuracy; fixed severity choices and five-level weighted sentiment mapping unchanged"}
        write_json(directory/"summary.json", result)
        write_jsonl(directory/"calls.jsonl", calls)
        write_json(directory/"predictions.json", {"sample_ids": verification["sample_ids"], "records": parsed})
        write_json(cost/"verification_batch_trial.json", result)
        write_jsonl(cost/"verification_batch_trial_calls.jsonl", calls)
        if result["status"] == "completed":
            store.put(RUN, "trial_summary", result)
        return result
    finally:
        store.close()
