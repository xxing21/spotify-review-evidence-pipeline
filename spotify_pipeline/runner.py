"""Real subprocess interruption/resume and cold/warm measurement driver."""
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .common import canonical, config, digest, now, require_key, sha, write_json, write_jsonl
from .pipeline import downstream, enrich, export, initialize, snapshot
from .provider import ModelClient
from .store import Store, experiment_lock


def worker(db, run_id, directory, phase, cap, stop_after=None):
    store = Store(db)
    info = store.run(run_id)
    progress = store.get(run_id, "active_seconds", 0)
    active_limit = store.get(run_id, "active_limit_seconds", 1200)
    if progress >= active_limit:
        raise TimeoutError("Saved active time limit exhausted")
    start = time.monotonic()
    client = ModelClient(store, run_id, info["config"], cap, directory, deadline=start + active_limit-progress)
    try:
        enrich(store, run_id, client, phase, stop_after)
        if stop_after is not None:
            name = "checkpoint_extension_before" if info["kind"].startswith("checkpoint_") else "checkpoint_before"
            before = snapshot(store, run_id, name)
            export(store, run_id, directory)
            print(f"CHECKPOINT saved: {len(before['completed_ids'])} IDs; sending SIGINT to this worker", flush=True)
            os.kill(os.getpid(), signal.SIGINT)
        snapshot(store, run_id, "checkpoint_after")
        downstream(store, run_id, client, directory)
    finally:
        store.put(run_id, "active_seconds", progress + time.monotonic()-start)
        export(store, run_id, directory)
        store.close()


def recorded_worker(db, run_id, directory, phase, cap, stop_after=None):
    recording = Path(directory) / "recovery.cast"
    if not recording.exists():
        recording.parent.mkdir(parents=True, exist_ok=True)
        recording.write_text(canonical({"version": 2, "width": 110, "height": 30,
            "timestamp": int(time.time()), "title": "Actual pipeline subprocess output: interruption and resume"}) + "\n")
    header = json.loads(recording.open().readline())
    args = [sys.executable, "-u", "-m", "spotify_pipeline", "--db", str(db), "_worker",
            "--run-id", run_id, "--directory", str(directory), "--phase", phase, "--budget-usd", str(cap)]
    if stop_after is not None:
        args += ["--stop-after", str(stop_after)]
    with recording.open("a") as cast:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            for line in process.stdout:
                print(line, end="", flush=True)
                cast.write(canonical([round(time.time()-header["timestamp"], 6), "o", line.replace("\n", "\r\n")]) + "\n")
                cast.flush()
            return process.wait()
        except BaseException:
            process.send_signal(signal.SIGINT)
            process.wait(timeout=70)
            raise


def pilot(db, path, run_id="pilot-100", cap=2, retry_after_fix=False):
    from .calculator import replay
    from .evaluation import paid_diagnostics
    if not 0 < cap <= 2:
        raise ValueError("This pilot implementation enforces a maximum US$2 global cap")
    require_key()
    supplied = json.loads(Path("manifest.json").read_text())
    if sha(path) != supplied["files"]["cost_100.csv"]["sha256"]:
        raise ValueError("Measured pilot requires unchanged cost_100.csv; use run for another input of at most 100 rows")
    directory = Path("artifacts/runs") / run_id
    with experiment_lock(directory):
        store = Store(db)
        info, rows = initialize(store, run_id, path)
        if retry_after_fix:
            if store.get(run_id, "cold_summary"):
                raise ValueError("Cold run already completed; account-repair retry is unnecessary")
            previous = store.get(run_id, "attempt_window", 0)
            store.put(run_id, "attempt_window", previous + 1)
            windows = store.get(run_id, "account_repair_windows", [])
            store.put(run_id, "account_repair_windows", windows + [{"window": previous+1, "at": now(),
                "reason": "Explicit --retry-after-fix: user reports account access repaired; old attempts retained"}])
        if not store.get(run_id, "cold_started_at"):
            store.put(run_id, "cold_started_at", now())
        try:
            if not store.get(run_id, "cold_summary"):
                completed = sum(r["status"] == "completed" for r in store.records(run_id))
                if completed < 20 and not store.get(run_id, "checkpoint_before"):
                    code = recorded_worker(db, run_id, directory, "initial", cap, stop_after=20)
                    if code != 130:
                        raise RuntimeError(f"Initial worker exited {code}; progress preserved; inspect call evidence")
                code = recorded_worker(db, run_id, directory, "resume", cap)
                if code:
                    raise RuntimeError(f"Resume worker exited {code}; progress preserved; rerun the same command")
                records = store.records(run_id)
                summary = {"status": "completed" if sum(r["status"] == "completed" for r in records) == 100 else "incomplete",
                    "run_id": run_id, "input_count": 100, "input_sha256": info["dataset"],
                    "input_ids": [r["review_id"] for r in rows], "unique_nonempty_texts": len({r["review_text"] for r in rows if r["review_text"].strip()}),
                    "completed": sum(r["status"] == "completed" for r in records),
                    "quarantined": sum(r["status"] == "quarantined" for r in records),
                    "pending": 100-len(records), "exact_text_reuses": sum(bool(r.get("cache_source_id")) for r in records),
                    "verification_sample_count": len(store.get(run_id, "verification", {}).get("sample_ids", [])),
                    "cold_seconds": (datetime.fromisoformat(now())-datetime.fromisoformat(store.get(run_id, "cold_started_at"))).total_seconds(),
                    "active_seconds": store.get(run_id, "active_seconds"), "config": info["config"]}
                summary["cold_throughput_records_per_second"] = summary["completed"] / summary["cold_seconds"]
                store.put(run_id, "cold_summary", summary)
            summary = store.get(run_id, "cold_summary")
            if not store.get(run_id, "warm_summary"):
                before = len(store.calls(run_id))
                start = time.monotonic()
                client = ModelClient(store, run_id, info["config"], cap, directory)
                enrich(store, run_id, client, "resume")
                downstream(store, run_id, client, directory)
                warm = {"warm_seconds": time.monotonic()-start, "warm_new_calls": len(store.calls(run_id))-before,
                    "warm_incremental_api_usd": "0" if len(store.calls(run_id)) == before else None,
                    "warm_record_cache_hits": sum(r["status"] == "completed" for r in store.records(run_id)),
                    "warm_downstream_cache_hits": client.cache_hits}
                store.put(run_id, "warm_summary", warm)
                if warm["warm_new_calls"]:
                    raise RuntimeError("Warm run made new calls; inspect cache invalidation before scaling")
            summary = dict(summary, **store.get(run_id, "warm_summary"))
            write_json("cost/pilot_summary.json", summary)
            diag_id = run_id + "-diagnostics"
            store.new_run(diag_id, "synthetic-diagnostics", config(), {"kind": "synthetic_model_tests"})
            if not store.get(diag_id, "results"):
                try:
                    result = paid_diagnostics(ModelClient(store, diag_id, config(), cap, Path("artifacts/diagnostics")))
                    store.put(diag_id, "results", result)
                except Exception as e:
                    write_json("cost/diagnostics.json", {"status": "incomplete", "error": str(e)})
            write_jsonl("cost/diagnostics_calls.jsonl", store.calls(diag_id))
            write_json("cost/budget_ledger.json", {"cap_usd": cap, "spent_plus_unresolved_reservations_usd": str(store.committed_spend()),
                "scope": "All attempts in local database, including pilot, diagnostics and any golden evaluation"})
        finally:
            records = export(store, run_id, directory)
            write_jsonl("cost/pilot_records.jsonl", records)
            write_jsonl("cost/pilot_calls.jsonl", store.calls(run_id))
            if not store.get(run_id, "cold_summary"):
                write_json("cost/pilot_summary.json", {"status": "incomplete", "run_id": run_id, "input_count": 100,
                    "input_sha256": info["dataset"], "input_ids": [r["review_id"] for r in rows],
                    "completed": sum(r["status"] == "completed" for r in records),
                    "quarantined": sum(r["status"] == "quarantined" for r in records),
                    "pending": sum(r["status"] == "pending" for r in records),
                    "unique_nonempty_texts": len({r["review_text"] for r in rows if r["review_text"].strip()}),
                    "cold_seconds": None, "warm_seconds": None,
                    "attempted_cold_wall_seconds": (datetime.fromisoformat(now())-datetime.fromisoformat(store.get(run_id, "cold_started_at"))).total_seconds(),
                    "active_seconds": store.get(run_id, "active_seconds", 0), "config": info["config"],
                    "reason": "See failed call evidence; no successful measured-100 run is claimed"})
            write_json("cost/budget_ledger.json", {"cap_usd": cap,
                "spent_plus_unresolved_reservations_usd": str(store.committed_spend()),
                "scope": "All real attempts in local database; unknown charges retain reservations"})
            store.close()
            replay(budget=cap)
    return summary
