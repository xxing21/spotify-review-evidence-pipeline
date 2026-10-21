"""Explicit, resumable 100k source-ID run using the measured scaling configuration."""
import collections
import json
import threading
import time
from decimal import Decimal
from pathlib import Path

from .common import (FIELDS, LABEL_FIELDS, digest, label_config, now, read_json, row_sha,
    sha, source_records, write_csv, write_json, write_jsonl)
from .pipeline import downstream, export, rank_records, snapshot
from .provider import ModelClient
from .scaling import SharedLimiter, WorkQueue, batches, process_phase
from .store import Store

RUN_ID = "production-100k-v1"


def canonical_rows(rows):
    seen, selected = set(), []
    for row in rows:
        if row["review_text"] not in seen:
            seen.add(row["review_text"])
            selected.append(row)
    return selected


def verification_rows(rows, cfg):
    from decimal import ROUND_CEILING
    count = int((Decimal(len(rows))*Decimal(str(cfg["verification_fraction"]))).to_integral_value(rounding=ROUND_CEILING))
    if not 1 <= count <= len(rows):
        raise ValueError("Independent verification sample size is invalid")
    return sorted(rows, key=lambda r: digest(cfg["verification_seed"]+r["review_id"]))[:count]


def materialize_aliases(store, run_id, rows, cfg):
    current = {r["review_id"]: r for r in store.records(run_id)}
    origins = {r["review_id"]: r for r in canonical_rows(rows)}
    by_text = {r["review_text"]: current[rid] for rid,r in origins.items()
        if rid in current and current[rid]["status"]=="completed"}
    aliases = []
    for row in rows:
        if row["review_id"] in current or row["review_text"] not in by_text:
            continue
        original = by_text[row["review_text"]]
        aliases.append(dict(original, review_id=row["review_id"], source_sha256=row_sha(row),
            cache_source_id=original["review_id"]))
    source = {r["review_id"]: r for r in rows}
    store.save_records(run_id, aliases, source, label_config(cfg))
    return len(aliases)


def save_verification(store, run_id, selected, cfg):
    predictions = list(store.get(run_id,"verification_recovered_predictions",[]))
    refusals = store.get(run_id,"verification_refusals",[])
    for row in store.db.execute("SELECT result FROM calls WHERE run_id=? AND result IS NOT NULL AND json_extract(event,'$.role')='verify' ORDER BY rowid", (run_id,)):
        predictions.extend(json.loads(row[0])["records"])
    by_id = {p["review_id"]: p for p in predictions}
    refusal_ids={r["review_id"] for r in refusals}
    if len(predictions)+len(refusals)!=len(selected) or len(by_id)!=len(predictions) or set(by_id)&refusal_ids or set(by_id)|refusal_ids!={r["review_id"] for r in selected}:
        raise ValueError("Verification is incomplete, duplicated or contains foreign IDs")
    successful = {r["review_id"]: r for r in store.records(run_id)}
    ordered = [by_id[r["review_id"]] for r in selected if r["review_id"] in by_id]
    comparisons = [{"review_id": p["review_id"], "missing_enrichment": p["review_id"] not in successful,
        "different_fields": [k for k in LABEL_FIELDS if p[k]!=successful.get(p["review_id"], {}).get(k)]} for p in ordered]
    store.put(run_id, "verification", {"seed": cfg["verification_seed"], "fraction": cfg["verification_fraction"],
        "sample_ids": [r["review_id"] for r in selected], "predictions": ordered, "comparisons": comparisons,"refusals":refusals,
        "label_disagreements": sum(any(k in c["different_fields"] for k in ("topic","intent","severity")) for c in comparisons),
        "any_field_disagreements": sum(bool(c["different_fields"]) for c in comparisons)})


def production(db, input_path, prepare_only=False, stop_after_checkpoint=False):
    directory = Path("artifacts/runs")/RUN_ID
    directory.mkdir(parents=True, exist_ok=True)
    cost = Path("cost/production_100k")
    cost.mkdir(parents=True, exist_ok=True)
    store = Store(db)
    started = time.monotonic()
    monitor_stop = threading.Event()
    thread = None
    try:
        plan = read_json("cost/planning_100k/run_plan.json")
        profile = read_json(plan["source_profile"])
        expected = read_json("manifest.json")["files"]["spotify_reviews_18months.csv"]["sha256"]
        if sha(input_path)!=expected or profile["source_sha256"]!=expected:
            raise ValueError("Production source must match the supplied unchanged full CSV")
        if (plan["target_nonempty_ids"], plan["verification_fraction"], plan["shared_api_cap_usd"])!=(100000,.05,10):
            raise ValueError("Production command is bound to the approved 100k / 5% / US$10 plan")
        from .common import csv_rows
        ids_path = Path(plan["proposed_source_ids"])
        if sha(ids_path)!=profile["selected_ids_sha256"]:
            raise ValueError("Proposed source-ID manifest changed")
        ids = [r["review_id"] for r in csv_rows(ids_path)]
        selected = set(ids)
        source = {r["review_id"]: r for r in csv_rows(input_path) if r["review_id"] in selected}
        rows = [source[rid] for rid in ids]
        if len(rows)!=100000 or len(selected)!=100000 or any(not r["review_text"].strip() for r in rows):
            raise ValueError("Need exactly 100000 distinct nonempty original source IDs")
        unique = canonical_rows(rows)
        if len(unique)!=profile["distinct_nonempty_texts"]:
            raise ValueError("Actual exact-text count differs from the approved profile")
        parent = store.run("scaling-500-16w-v1")
        if not parent:
            raise ValueError("The measured sixteen-worker pilot must exist")
        cfg = parent["config"] | {"execution_mode": "production-100k-v1", "verification_fraction": .05,
            "verification_seed": plan["verification_seed"], "verification_batch_size": 10,
            "verification_schema_version": "decisions-verifier-v3-batch10-five-levels",
            "initial_phase": "enrich-probe", "pilot_run_cap_usd": 10}
        path = directory/"input_100000.csv"
        if not path.exists():
            write_csv(path, rows, list(FIELDS))
        dataset = sha(path)
        store.add_dataset(dataset, rows, {"path": str(path.resolve()), "full_source_sha256": expected, "count": 100000})
        store.new_run(RUN_ID, dataset, cfg, {"kind": "production_100k", "input_path": str(path.resolve()),
            "input_count": 100000, "scope": "100000 original nonempty source-ID sample; full-file ingestion is separate"})
        existing = store.get(RUN_ID, "production_summary")
        if existing and existing["status"]=="completed":
            return existing
        preflight = directory/"preflight.json"
        if not preflight.exists():
            write_json(preflight, {"created_at": now(), "plan": plan, "source_profile": profile,
                "input_sha256": dataset, "label_config": label_config(cfg), "actual_unique_texts": len(unique),
                "model_inputs": ["review_id", "review_text"], "golden_answers_supplied": False,
                "initial_global_committed_usd": str(store.committed_spend()),
                "max_active_seconds": 10800, "runtime_target_seconds": 7200,
                "cache_note": "Exact texts reused within this run. Earlier paid experiments remain separate and unchanged.",
                "source_code_sha256": {str(p):sha(p) for p in Path("spotify_pipeline").rglob("*.py")}})
        queue = WorkQueue(store)
        queue.recover(RUN_ID)
        counts = queue.counts(RUN_ID)
        if any(counts.get(k,0) for k in ("uncertain","failed")):
            raise RuntimeError("Failed or uncertain task outcomes require inspection before resume; no blind repeat calls")
        queue.add(RUN_ID,"enrich","enrich-probe",batches(unique[:20],20),cfg)
        queue.add(RUN_ID,"enrich","enrich-16",batches(unique[20:],20),cfg)
        sample = verification_rows(rows,cfg)
        if len(sample)!=5000:
            raise ValueError("The approved independent sample must contain 5000 original IDs")
        queue.add(RUN_ID,"verify","verify-8",batches(sample,10),cfg)
        write_json(directory/"verification_sample.json", {"seed":cfg["verification_seed"], "fraction":.05,
            "sampling_unit":"original_source_ids", "selection":"smallest SHA256(canonical JSON of seed + review_id)",
            "sample_ids":[r["review_id"] for r in sample], "enrichment_labels_used":False})
        if prepare_only:
            return {"status":"prepared", "run_id":RUN_ID, "input_count":len(rows), "distinct_texts":len(unique),
                "verification_count":len(sample), "queued_tasks":queue.counts(RUN_ID), "new_model_calls":0}
        previous = store.get(RUN_ID,"active_seconds",0)
        started = time.monotonic()
        deadline = started+10800-previous
        limiter = SharedLimiter()
        def monitor():
            state = Store(db)
            try:
                while not monitor_stop.wait(15):
                    progress = {"saved_at":now(),"run_id":RUN_ID,"status":"running",
                        "saved_records":state.db.execute("SELECT COUNT(*) FROM records WHERE run_id=?",(RUN_ID,)).fetchone()[0],
                        "queue":WorkQueue(state).counts(RUN_ID),"active_seconds":previous+time.monotonic()-started,
                        "global_spent_plus_reserved_usd":str(state.committed_spend())}
                    state.put(RUN_ID,"active_seconds",progress["active_seconds"])
                    write_json(directory/"progress.json",progress)
                    print(f"PROGRESS {progress['saved_records']}/100000 saved; {progress['queue']}; global US${progress['global_spent_plus_reserved_usd']}",flush=True)
            finally:
                state.close()
        thread = threading.Thread(target=monitor,daemon=True)
        thread.start()
        error, checkpoint_stop = None, False
        try:
            for phase, workers in (("enrich-probe",1),("enrich-16",16),("verify-8",8)):
                if phase=="verify-8":
                    materialize_aliases(store,RUN_ID,rows,cfg)
                    if len(store.records(RUN_ID))!=100000:
                        raise ValueError("All 100k classifications must be saved before independent checks")
                if not queue.counts(RUN_ID,phase).get("pending",0):
                    continue
                print(f"START {phase}: {workers} workers; {queue.counts(RUN_ID,phase)}",flush=True)
                phase_start=time.monotonic()
                try:
                    process_phase(db,RUN_ID,cfg,directory,phase,workers,limiter,deadline)
                finally:
                    timing=store.get(RUN_ID,"phase_measurements",[])
                    timing.append({"phase":phase,"workers":workers,"seconds":time.monotonic()-phase_start,"saved_at":now(),"queue":queue.counts(RUN_ID,phase)})
                    store.put(RUN_ID,"phase_measurements",timing)
                if phase=="enrich-probe" and not store.get(RUN_ID,"checkpoint_before"):
                    snapshot(store,RUN_ID,"checkpoint_before")
                    if stop_after_checkpoint:
                        checkpoint_stop=True
                        break
            if not checkpoint_stop:
                save_verification(store,RUN_ID,sample,cfg)
                client=ModelClient(store,RUN_ID,cfg|{"workers":1},10,directory,deadline=deadline,run_cap=10,limiter=limiter)
                downstream(store,RUN_ID,client,directory,saved_verification=True)
                snapshot(store,RUN_ID,"checkpoint_after")
        except (Exception,KeyboardInterrupt) as e:
            error=str(e) or type(e).__name__
        finally:
            monitor_stop.set()
            thread.join(timeout=5)
            store.put(RUN_ID,"active_seconds",previous+time.monotonic()-started)
            materialize_aliases(store,RUN_ID,rows,cfg)
            export(store,RUN_ID,directory)
        records,calls=store.records(RUN_ID),store.calls(RUN_ID)
        known=sum((Decimal(c["calculated_api_usd"]) for c in calls if c.get("calculated_api_usd") is not None),Decimal(0))
        unknown=[c for c in calls if c.get("calculated_api_usd") is None]
        complete=len(records)==100000 and all(r["status"]=="completed" for r in records) and store.get(RUN_ID,"memo") is not None and error is None
        summary={"status":"completed" if complete else "checkpoint_saved" if checkpoint_stop else "incomplete", "run_id":RUN_ID,
            "completed":len(records),"pending":100000-len(records),"input_count":100000,"unique_texts":len(unique),
            "exact_text_reuses":sum(bool(r.get("cache_source_id")) for r in records),"active_seconds":store.get(RUN_ID,"active_seconds"),
            "verification_count":len(store.get(RUN_ID,"verification",{}).get("sample_ids",[])),"verification_fraction":.05,
            "verification_complete_prediction_count":len(store.get(RUN_ID,"verification",{}).get("predictions",[])),
            "verification_refusal_count":len(store.get(RUN_ID,"verification",{}).get("refusals",[])),
            "calls":len(calls),"known_api_usd":str(known),"unknown_usage_calls":len(unknown),
            "unresolved_reserved_usd":str(sum((Decimal(c["reservation_usd"]) for c in unknown),Decimal(0))),
            "global_committed_usd":str(store.committed_spend()),"shared_cap_usd":10,"error":error,
            "phase_measurements":store.get(RUN_ID,"phase_measurements",[]),"config":cfg}
        if complete:
            before=len(calls)
            warm=time.monotonic()
            # Offline rank equality and saved downstream task keys must dispatch no new work.
            if rank_records(records)[1]!=store.get(RUN_ID,"ranking"):
                raise ValueError("Saved ranking does not reproduce offline")
            downstream(store,RUN_ID,client,directory,saved_verification=True)
            summary.update(warm_seconds=time.monotonic()-warm,warm_new_calls=len(store.calls(RUN_ID))-before)
            if summary["warm_new_calls"]:
                raise ValueError("Warm execution dispatched unexpected new calls")
        store.put(RUN_ID,"production_summary",summary)
        write_json(directory/"summary.json",summary)
        write_json(cost/"run_summary.json",summary)
        write_jsonl(cost/"calls.jsonl",store.calls(RUN_ID))
        write_json(directory/"progress.json",summary)
        write_json("cost/budget_ledger.json",{"cap_usd":10,"spent_plus_unresolved_reservations_usd":str(store.committed_spend()),"scope":"All experiments and production, including unresolved reservations"})
        return summary
    finally:
        monitor_stop.set()
        if thread:
            thread.join(timeout=5)
        store.close()
