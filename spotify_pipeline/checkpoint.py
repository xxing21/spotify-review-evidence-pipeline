"""Explicit, checksum-bound 500 and 10,000 review development checkpoints."""
import json
import shutil
import time
from pathlib import Path

from .common import (config, label_config, now, require_key, row_sha, sha,
                     validate_labels, LABEL_FIELDS, write_json, write_jsonl)
from .pipeline import downstream, enrich, export, initialize, snapshot
from .provider import ModelClient
from .runner import recorded_worker
from .store import Store, experiment_lock


def inherit_previous(store, run_id, source_run, directory):
    """Reuse same original IDs, and keep their historical call evidence verbatim."""
    info, old = store.run(run_id), store.run(source_run)
    if not old or old["config"] != info["config"]:
        raise ValueError("The source run must exist with identical model/prompt/schema settings")
    rows = {r["review_id"]: r for r in store.sources(info["dataset"])}
    previous = {r["review_id"]: r for r in store.sources(old["dataset"])}
    records = store.records(source_run)
    if not records or len(records) != len(previous) or any(r["status"] != "completed" for r in records):
        raise ValueError("The inherited source run must be completely classified")
    expected = label_config(info["config"])
    for r in records:
        rid = r["review_id"]
        if rid not in rows or rows[rid] != previous[rid] or r["source_sha256"] != row_sha(rows[rid]) or r["label_config"] != expected:
            raise ValueError("Inherited original row or classification configuration does not match")
        validate_labels({"records": [{k:r[k] for k in ("review_id", *LABEL_FIELDS)}]}, [rows[rid]])
    history = store.get(source_run, "inherited_call_evidence", []) + store.calls(source_run)
    calls = list({c["local_call_id"]: c for c in history
        if c["role"] == "enrich" and c["outcome"] == "succeeded"}.values())
    evidence_ids = {rid for c in calls if c.get("label_config") == expected for rid in c["review_ids"]}
    if any(r["review_id"] not in evidence_ids and not r.get("cache_source_id") for r in records):
        raise ValueError("Missing historical model-call evidence for inherited classifications")
    before = store.get(source_run, "checkpoint_before")
    if not before or not before["completed_ids"]:
        raise ValueError("Source interruption checkpoint is required for provenance")
    if store.get(run_id, "inheritance"):
        if store.get(run_id, "inheritance")["source_run"] != source_run:
            raise ValueError("Cannot change the inherited source run")
        return
    copied = [dict(r, reused_from_run=source_run) for r in records]
    store.save_records(run_id, copied, rows, expected)
    store.put(run_id, "inherited_ids", sorted(r["review_id"] for r in records))
    store.put(run_id, "inherited_call_evidence", calls)
    store.put(run_id, "checkpoint_before", dict(before, inherited_from_run=source_run))
    store.put(run_id, "inheritance", {"source_run": source_run, "source_input_sha256": old["dataset"],
        "record_count": len(records), "historical_enrichment_calls": len(calls), "imported_at": now(),
        "original_phase_and_request_ids_preserved": True, "new_api_calls_for_inheritance": 0,
        "historical_calls_excluded_from_incremental_spend": True,
        "checkpoint_lineage": "Original 20-ID interruption snapshot is retained; extension snapshots record this run's new interruption and restart."})
    recording = Path("artifacts/runs") / source_run / "recovery.cast"
    if recording.exists():
        Path(directory).mkdir(parents=True, exist_ok=True)
        shutil.copy2(recording, Path(directory) / "recovery_inherited.cast")


def checkpoint(db, path, run_id=None, source_run=None, cap=2, max_active_minutes=20):
    from .calculator import replay
    if not 0 < cap <= 2:
        raise ValueError("The existing US$2 global pilot cap remains enforced")
    supplied = json.loads(Path("manifest.json").read_text())
    choices = {"checkpoint_500.csv": (500, "pilot-500-v2", "pilot-100-v2", 100),
               "analysis_10000.csv": (10000, "pilot-10000-v2", "pilot-500-v2", 500)}
    name = Path(path).name
    if name not in choices or sha(path) != supplied["files"][name]["sha256"]:
        raise ValueError("Only unchanged supplied 500 or 10,000 review checkpoint files are authorized")
    count, default_run, default_source, source_count = choices[name]
    run_id, source_run = run_id or default_run, source_run or default_source
    if not 0 < max_active_minutes <= (180 if count == 10000 else 20):
        raise ValueError("Active limit must be positive; maximum 20 minutes for 500 or 180 minutes for 10,000")
    if count == 10000:
        state = Store(db)
        try:
            if state.run("pilot-10000-v3"):
                raise ValueError("The ID-constrained recovery supersedes this attempt; use recover-checkpoint to resume/reuse it")
        finally:
            state.close()
    require_key()
    directory, cost_dir = Path("artifacts/runs") / run_id, Path(f"cost/checkpoint_{count}")
    cost_dir.mkdir(parents=True, exist_ok=True)
    with experiment_lock(directory):
        store = Store(db)
        try:
            info, rows = initialize(store, run_id, path, kind=f"checkpoint_{count}", max_records=count)
            if len(rows) != count:
                raise ValueError(f"Expected exactly {count} source reviews")
            old = store.run(source_run)
            if not old or old["input_count"] != source_count:
                raise ValueError(f"A completed {source_count}-review source checkpoint is required")
            saved_limit = store.get(run_id, "active_limit_seconds")
            requested_limit = max_active_minutes * 60
            if saved_limit is not None and saved_limit != requested_limit:
                raise ValueError("Saved active limit differs; resume with the original explicit limit")
            store.put(run_id, "active_limit_seconds", requested_limit)
            inherit_previous(store, run_id, source_run, directory)
            if not store.get(run_id, "extension_summary"):
                session_start = time.monotonic()
                if not store.get(run_id, "extension_started_at"):
                    store.put(run_id, "extension_started_at", now())
                previous_seconds = store.get(run_id, "extension_wall_seconds", 0)
                try:
                    if not store.get(run_id, "checkpoint_extension_before"):
                        code = recorded_worker(db, run_id, directory, "resume", cap, stop_after=source_count + 20)
                        if code != 130:
                            raise RuntimeError(f"Checkpoint worker exited {code}; saved progress retained")
                    code = recorded_worker(db, run_id, directory, "resume", cap)
                    if code:
                        raise RuntimeError(f"Resume worker exited {code}; saved progress retained")
                finally:
                    store.put(run_id, "extension_wall_seconds", previous_seconds + time.monotonic()-session_start)
                records = store.records(run_id)
                snapshot(store, run_id, "checkpoint_extension_after")
                new_calls = store.calls(run_id)
                successful_ids = {rid for c in new_calls if c["role"] == "enrich" and c["outcome"] == "succeeded" for rid in c["review_ids"]}
                summary = {"status": "completed" if len(records)==count and all(r["status"]=="completed" for r in records) else "incomplete",
                    "measurement_kind": "incremental_checkpoint", "run_id":run_id, "input_count":count,
                    "input_sha256":info["dataset"], "input_ids":[r["review_id"] for r in rows],
                    "completed":sum(r["status"]=="completed" for r in records),
                    "quarantined":sum(r["status"]=="quarantined" for r in records), "pending":count-len(records),
                    "inherited_completed_records":len(store.get(run_id,"inherited_ids")),
                    "new_completed_records":sum(r["status"]=="completed" and r["review_id"] not in set(store.get(run_id,"inherited_ids")) for r in records),
                    "new_enrichment_records":len(successful_ids), "enrichment_work_count":len(successful_ids),
                    "unique_nonempty_texts":len({r["review_text"] for r in rows if r["review_text"].strip()}),
                    "exact_text_reuses":sum(bool(r.get("cache_source_id")) for r in records),
                    "verification_sample_count":len(store.get(run_id,"verification",{}).get("sample_ids",[])),
                    "verification_sampling_unit":"source_rows", "cold_seconds":None,
                    "incremental_seconds":store.get(run_id,"extension_wall_seconds"),
                    "active_seconds":store.get(run_id,"active_seconds"), "config":info["config"],
                    "source_run":source_run, "max_active_minutes":max_active_minutes,
                    "time_note":"Measured extension time for new work, verification and new analysis; not a fresh-cache 500-review cold run."}
                summary["new_records_per_second"] = summary["new_completed_records"] / summary["incremental_seconds"]
                store.put(run_id,"extension_summary",summary)
            summary=store.get(run_id,"extension_summary")
            if not store.get(run_id,"warm_summary"):
                before=len(store.calls(run_id)); start=time.monotonic()
                client=ModelClient(store,run_id,info["config"],cap,directory)
                enrich(store,run_id,client,"resume")
                downstream(store,run_id,client,directory)
                warm={"warm_seconds":time.monotonic()-start,"warm_new_calls":len(store.calls(run_id))-before,
                    "warm_incremental_api_usd":"0" if len(store.calls(run_id))==before else None,
                    "warm_record_cache_hits":len(store.records(run_id)), "warm_downstream_cache_hits":client.cache_hits}
                store.put(run_id,"warm_summary",warm)
                if warm["warm_new_calls"]:
                    raise RuntimeError("Warm checkpoint replay unexpectedly made new calls")
            summary=dict(summary,**store.get(run_id,"warm_summary"))
            write_json(cost_dir/"pilot_summary.json",summary)
        finally:
            if store.run(run_id):
                records=export(store,run_id,directory)
                write_jsonl(cost_dir/"pilot_records.jsonl",records)
                write_jsonl(cost_dir/"pilot_calls.jsonl",store.calls(run_id))
                write_jsonl(cost_dir/"inherited_calls.jsonl",store.get(run_id,"inherited_call_evidence",[]))
                if not store.get(run_id,"extension_summary"):
                    write_json(cost_dir/"pilot_summary.json",{"status":"incomplete","run_id":run_id,"input_count":count,
                        "measurement_kind":"incremental_checkpoint","completed":sum(r["status"]=="completed" for r in records),
                        "quarantined":sum(r["status"]=="quarantined" for r in records),
                        "pending":sum(r["status"]=="pending" for r in records),"cold_seconds":None,"warm_seconds":None,
                        "incremental_seconds":store.get(run_id,"extension_wall_seconds",0),
                        "reason":"See saved attempts; incomplete checkpoint is not a successful run"})
            ledger={"cap_usd":cap,"spent_plus_unresolved_reservations_usd":str(store.committed_spend()),
                "scope":"All actual attempts across all development checkpoints and diagnostics; inherited calls are not billed twice"}
            write_json("cost/budget_ledger.json",ledger); write_json(cost_dir/"budget_ledger.json",ledger)
            shutil.copy2("cost/rates.csv",cost_dir/"rates.csv")
            store.close()
            replay(directory=cost_dir,rates_path=cost_dir/"rates.csv",budget=cap)
    return summary
