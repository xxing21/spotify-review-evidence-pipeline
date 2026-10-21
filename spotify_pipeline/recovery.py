"""One explicit, bounded recovery after the 10k run exposed UUID copying errors."""
import collections
import shutil
import time
from pathlib import Path

from .common import (config, label_config, now, read_json, require_key, row_sha,
    sha, validate_labels, LABEL_FIELDS, write_json, write_jsonl)
from .pipeline import downstream, enrich, export, initialize, snapshot
from .provider import ModelClient
from .runner import recorded_worker
from .store import Store, experiment_lock


def recover(db, cap=2, allow_final_invalid_attempt=False):
    if not 0 < cap <= 2:
        raise ValueError("Shared maximum is US$2")
    manifest = read_json("manifest.json")
    path = "analysis_10000.csv"
    if sha(path) != manifest["files"][path]["sha256"]:
        raise ValueError("Unchanged supplied 10,000-review input required")
    require_key()
    run_id, source_run = "pilot-10000-v3", "pilot-10000-v2"
    directory, cost = Path("artifacts/runs") / run_id, Path("cost/checkpoint_10000")
    cfg = config() | {"schema_version": "spotify-label-v3-id-enum", "routing_schema": "review-id-enum-v1"}
    with experiment_lock(directory):
        store = Store(db)
        old = store.run(source_run)
        if not old or old["config"] != config():
            raise ValueError("Expected the unchanged v2 source settings")
        old_calls = store.calls(source_run)
        old_records = store.records(source_run)
        old_seconds = store.get(source_run, "active_seconds", 0)
        info, rows = initialize(store, run_id, path, cfg, kind="checkpoint_10000_recovery", max_records=10000)
        source = {r["review_id"]: r for r in rows}
        if not store.get(run_id, "recovery_seeded"):
            completed = [r for r in old_records if r["status"] == "completed"]
            for r in completed:
                if r["source_sha256"] != row_sha(source[r["review_id"]]) or r["label_config"] != label_config(old["config"]):
                    raise ValueError("Original classification provenance differs")
                validate_labels({"records": [{k: r[k] for k in ("review_id", *LABEL_FIELDS)}]}, [source[r["review_id"]]])
            attempts = collections.Counter(rid for c in old_calls if c["role"] == "enrich" for rid in c["review_ids"])
            completed_ids = {r["review_id"] for r in completed}
            prior = {rid: n for rid, n in attempts.items() if rid not in completed_ids}
            if any(n >= 3 for n in prior.values()):
                raise ValueError("A remaining ID already exhausted all three attempts; no additional charges permitted")
            store.save_records(run_id, [dict(r, reused_from_run=source_run) for r in completed], source, label_config(old["config"]))
            if not allow_final_invalid_attempt:
                store.save_records(run_id, [r for r in old_records if r["status"] == "quarantined"], source, label_config(old["config"]))
            inherited = store.get(source_run, "inherited_call_evidence", []) + old_calls
            store.put(run_id, "inherited_call_evidence", inherited)
            store.put(run_id, "inherited_ids", sorted(completed_ids))
            store.put(run_id, "checkpoint_before", store.get(source_run, "checkpoint_before"))
            store.put(run_id, "prior_enrichment_attempt_counts", prior)
            store.put(run_id, "active_limit_seconds", max(0, 10800 - old_seconds))
            store.put(run_id, "inheritance", {"source_run": source_run, "record_count": len(completed),
                "new_api_calls_for_inheritance": 0, "label_settings": "Identical prompts, model and label definitions; new response schema restricts IDs to the request's IDs",
                "mixed_config_provenance": "Inherited outputs retain their v2 label_config; new outputs use the distinct v3 cache key. No output is silently assigned a different configuration.",
                "historical_calls_excluded_from_duplicate_billing": True})
            store.put(run_id, "recovery_seeded", {"at": now(), "approved_final_invalid_attempt": allow_final_invalid_attempt,
                "max_total_attempts_per_remaining_enrichment_id": 3, "original_failed_evidence_preserved": True,
                "prior_active_seconds": old_seconds, "total_active_limit_seconds": 10800})
            shutil.copy2(Path("artifacts/runs") / source_run / "recovery.cast", directory / "recovery_inherited.cast")
        started = time.monotonic()
        prior_wall = store.get(run_id, "recovery_wall_seconds", 0)
        try:
            if not store.get(run_id, "extension_summary"):
                inherited_count = len(store.get(run_id, "inherited_ids"))
                if not store.get(run_id, "checkpoint_extension_before"):
                    code = recorded_worker(db, run_id, directory, "resume", cap, stop_after=inherited_count + 20)
                    if code != 130:
                        raise RuntimeError(f"Recovery checkpoint exited {code}; evidence saved")
                code = recorded_worker(db, run_id, directory, "resume", cap)
                if code:
                    raise RuntimeError(f"Recovery exited {code}; evidence saved")
                snapshot(store, run_id, "checkpoint_extension_after")
                records = store.records(run_id)
                combined = old_calls + store.calls(run_id)
                successful_ids = {rid for c in combined if c["role"] == "enrich" and c["outcome"] == "succeeded" for rid in c["review_ids"]}
                wall = store.get(source_run, "extension_wall_seconds", 0) + prior_wall + time.monotonic() - started
                summary = {"status": "completed" if len(records) == 10000 and all(r["status"] == "completed" for r in records) else "incomplete",
                    "measurement_kind": "incremental_checkpoint", "run_id": run_id, "source_run": "pilot-500-v2",
                    "recovery_source_run": source_run, "input_count": 10000, "input_sha256": info["dataset"],
                    "input_ids": [r["review_id"] for r in rows], "completed": sum(r["status"] == "completed" for r in records),
                    "quarantined": sum(r["status"] == "quarantined" for r in records), "pending": 10000-len(records),
                    "inherited_completed_records": 500, "validated_v2_results_preserved": inherited_count,
                    "new_completed_records": sum(r["status"] == "completed" for r in records) - 500,
                    "enrichment_work_count": len(successful_ids), "unique_nonempty_texts": len({r["review_text"] for r in rows}),
                    "exact_text_reuses": sum(bool(r.get("cache_source_id")) for r in records),
                    "verification_sample_count": len(store.get(run_id, "verification", {}).get("sample_ids", [])),
                    "verification_sampling_unit": "source_rows", "cold_seconds": None, "incremental_seconds": wall,
                    "active_seconds": old_seconds + store.get(run_id, "active_seconds", 0), "max_active_minutes": 180,
                    "new_records_per_second": 9500 / wall, "config": cfg, "label_configs_present": sorted({r.get("label_config") for r in records if r["status"] == "completed"}),
                    "time_note": "Includes both the interrupted v2 extension and bounded v3 recovery, plus new verification and analysis. Earlier 100/500 execution is excluded.",
                    "cost_note": "pilot_calls.jsonl includes each actual v2/v3 checkpoint attempt once. Historical 100/500 calls are separate and not billed again."}
                store.put(run_id, "extension_summary", summary)
            summary = store.get(run_id, "extension_summary")
            if not store.get(run_id, "warm_summary"):
                before = len(store.calls(run_id)); warm_start = time.monotonic()
                client = ModelClient(store, run_id, cfg, cap, directory)
                enrich(store, run_id, client, "resume"); downstream(store, run_id, client, directory)
                warm = {"warm_seconds": time.monotonic() - warm_start, "warm_new_calls": len(store.calls(run_id)) - before,
                    "warm_incremental_api_usd": "0" if len(store.calls(run_id)) == before else None,
                    "warm_record_cache_hits": len(store.records(run_id)), "warm_downstream_cache_hits": client.cache_hits}
                store.put(run_id, "warm_summary", warm)
                if warm["warm_new_calls"]:
                    raise RuntimeError("Warm recovery made new calls")
            summary = dict(summary, **store.get(run_id, "warm_summary"))
            write_json(cost / "pilot_summary.json", summary)
        finally:
            store.put(run_id, "recovery_wall_seconds", prior_wall + time.monotonic() - started)
            records = export(store, run_id, directory)
            write_jsonl(cost / "pilot_records.jsonl", records)
            write_jsonl(cost / "pilot_calls.jsonl", old_calls + store.calls(run_id))
            write_jsonl(cost / "inherited_calls.jsonl", store.get(source_run, "inherited_call_evidence", []))
            if not store.get(run_id, "extension_summary"):
                write_json(cost / "pilot_summary.json", {"status": "incomplete", "run_id": run_id, "input_count": 10000,
                    "completed": sum(r["status"] == "completed" for r in records), "cold_seconds": None, "warm_seconds": None,
                    "measurement_kind": "incremental_checkpoint", "incremental_seconds": store.get(source_run, "extension_wall_seconds", 0) + store.get(run_id, "recovery_wall_seconds"),
                    "reason": "Recovery incomplete; all actual attempts retained"})
            ledger = {"cap_usd": cap, "spent_plus_unresolved_reservations_usd": str(store.committed_spend()),
                "scope": "All actual attempts in all experiments; inherited evidence is never recharged"}
            write_json("cost/budget_ledger.json", ledger); write_json(cost / "budget_ledger.json", ledger)
            shutil.copy2("cost/rates.csv", cost / "rates.csv")
            store.close()
            from .calculator import replay
            replay(directory=cost, rates_path=cost / "rates.csv", budget=cap)
    return summary
