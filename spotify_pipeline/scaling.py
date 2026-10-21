"""Fresh-input 500-review concurrency experiment, capped independently and globally."""
import collections
import concurrent.futures
import heapq
import json
import statistics
import threading
import time
import contextlib
import sys
from decimal import Decimal
from pathlib import Path

from .common import (FIELDS, LABEL_SCHEMA, canonical, config, csv_rows, digest, ground_labels,
    label_config, now, read_json, row_sha, sha, source_records, write_csv, write_json, write_jsonl)
from .decisions import verification_prompt
from .pipeline import downstream, export, initialize, rank_records, rerank_exports, snapshot
from .provider import ModelClient
from .store import BudgetExceeded, Store, experiment_lock

RUN_ID = "scaling-500-v1"
SIXTEEN_RUN_ID = "scaling-500-16w-v1"
PHASES = (("enrich-1", 1, 40), ("enrich-2", 2, 60), ("enrich-4", 4, 80), ("enrich-8", 8, 320))
SIXTEEN_PHASES = (("enrich-probe", 1, 20), ("enrich-16", 16, 480))


@contextlib.contextmanager
def terminal_recording(path):
    """Record actual process stdout as asciinema events while continuing to display it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stream, start = sys.stdout, time.monotonic()
    with path.open("x", encoding="utf-8") as recording:
        recording.write(json.dumps({"version": 2, "width": 110, "height": 30,
            "timestamp": int(time.time()), "title": "Spotify scaling pilot: actual process output"}) + "\n")
        class Tee:
            def write(self, value):
                stream.write(value)
                recording.write(json.dumps([time.monotonic()-start, "o", value]) + "\n")
                recording.flush()
                return len(value)
            def flush(self):
                stream.flush()
                recording.flush()
        with contextlib.redirect_stdout(Tee()):
            yield


class SharedLimiter:
    """One process-wide request/token bucket and shared throttle pause for all workers."""
    def __init__(self):
        self.lock = threading.Lock()
        self.rpm, self.tpm = 120., 120000.
        self.tokens, self.updated = self.tpm, time.monotonic()
        self.next_request = self.pause_until = 0.
        self.observed_headers = []

    def acquire(self, tokens, deadline):
        while True:
            with self.lock:
                current = time.monotonic()
                self.tokens = min(self.tpm, self.tokens + (current - self.updated) * self.tpm / 60)
                self.updated = current
                if tokens > self.tpm:
                    raise ValueError("Request exceeds conservative shared token limiter")
                wait = max(self.pause_until-current, self.next_request-current,
                    (tokens-self.tokens) * 60/self.tpm, 0)
                if current + wait >= deadline:
                    raise TimeoutError("Active execution deadline reached while queued")
                if wait <= 0:
                    self.tokens -= tokens
                    self.next_request = current + 60 / self.rpm
                    return
            time.sleep(min(wait, .25))

    def observe(self, raw, reserved_tokens):
        headers = {k.lower(): v for k, v in raw.get("rate_limit_headers", {}).items()}
        with self.lock:
            self.observed_headers.append(headers)
            previous_tpm = self.tpm
            # Only raise local limits when the provider actually reports higher capacity.
            for key, attr, ceiling in (("x-ratelimit-limit-requests", "rpm", 600),
                                      ("x-ratelimit-limit-tokens", "tpm", 600000)):
                try:
                    setattr(self, attr, max(1., min(ceiling, float(headers[key]) * .75)))
                except (KeyError, ValueError, TypeError):
                    pass
            try:
                project = float(headers["x-ratelimit-limit-project-tokens"]) * .75
                self.tpm = max(1., min(self.tpm, project))
            except (KeyError, ValueError, TypeError):
                pass
            self.tokens = min(self.tpm, self.tokens + max(0., self.tpm-previous_tpm))
            usage = raw.get("usage") or {}
            used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            if type(used) is int and used >= 0 and usage:
                self.tokens = min(self.tpm, self.tokens + max(0, reserved_tokens-used))
            try:
                self.tokens = min(self.tokens, max(0., float(headers["x-ratelimit-remaining-tokens"]) * .75))
            except (KeyError, ValueError, TypeError):
                pass

    def penalize(self, delay):
        with self.lock:
            self.pause_until = max(self.pause_until, time.monotonic() + delay)
            self.rpm = max(1., self.rpm / 2)


class WorkQueue:
    def __init__(self, store):
        self.store = store
        store.db.execute("""CREATE TABLE IF NOT EXISTS scaling_queue(
            run_id TEXT, task_key TEXT, role TEXT, phase TEXT, ordinal INTEGER,
            rows_json TEXT NOT NULL, status TEXT NOT NULL, worker_id TEXT, error TEXT,
            PRIMARY KEY(run_id,task_key))""")
        store.db.execute("CREATE INDEX IF NOT EXISTS queue_claim ON scaling_queue(run_id,phase,status,ordinal)")
        store.db.commit()

    def add(self, run_id, role, phase, batches, cfg):
        with self.store.db:
            for i, batch in enumerate(batches):
                key = digest({"role": role, "rows": batch,
                    "configuration": label_config(cfg) if role == "enrich" else cfg["prompt_hashes"]["verify"]})
                self.store.db.execute("INSERT OR IGNORE INTO scaling_queue VALUES (?,?,?,?,?,?,?,NULL,NULL)",
                    (run_id, key, role, phase, i, canonical(batch), "pending"))

    def recover(self, run_id):
        running = self.store.db.execute("SELECT task_key FROM scaling_queue WHERE run_id=? AND status='running'", (run_id,)).fetchall()
        for row in running:
            calls = self.store.db.execute("SELECT event FROM calls WHERE run_id=? AND json_extract(event,'$.queue_task_key')=?",
                (run_id, row[0])).fetchall()
            uncertain = any(not json.loads(c[0]).get("ended_at") for c in calls)
            with self.store.db:
                self.store.db.execute("UPDATE scaling_queue SET status=?,error=? WHERE run_id=? AND task_key=?",
                    ("uncertain" if uncertain else "pending",
                     "Unfinished provider outcome; no automatic redispatch" if uncertain else None, run_id, row[0]))

    def claim(self, run_id, phase, worker_id):
        db = self.store.db
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute("SELECT * FROM scaling_queue WHERE run_id=? AND phase=? AND status='pending' ORDER BY ordinal LIMIT 1",
                (run_id, phase)).fetchone()
            if row:
                db.execute("UPDATE scaling_queue SET status='running',worker_id=? WHERE run_id=? AND task_key=?",
                    (worker_id, run_id, row["task_key"]))
            db.commit()
            return dict(row) if row else None
        except BaseException:
            db.rollback()
            raise

    def finish(self, run_id, key, status="completed", error=None):
        with self.store.db:
            self.store.db.execute("UPDATE scaling_queue SET status=?,error=? WHERE run_id=? AND task_key=?",
                (status, error, run_id, key))

    def counts(self, run_id, phase=None):
        query = "SELECT status,COUNT(*) FROM scaling_queue WHERE run_id=? AND status!='superseded'" + (" AND phase=?" if phase else "") + " GROUP BY status"
        return dict(self.store.db.execute(query, (run_id, phase) if phase else (run_id,)))


def batches(rows, size=10):
    return [rows[i:i+size] for i in range(0, len(rows), size)]


def select_fresh(store, path):
    full = read_json("manifest.json")["files"]["spotify_reviews_18months.csv"]["sha256"]
    full_path = Path("spotify_reviews_18months.csv")
    if sha(full_path) != full:
        raise ValueError("Full source differs from supplied checksum")
    known = {r[0] for r in store.db.execute("SELECT DISTINCT text_sha FROM cache")}
    golden = source_records("golden_50_to_label.csv")
    known.update(digest(r["review_text"]) for r in golden)
    def candidates():
        # Stream the unchanged CSV instead of sorting large source rows through SQLite's text-hash index.
        for row in csv_rows(full_path):
            text_sha = digest(row["review_text"])
            if text_sha in known:
                continue
            if not row["review_text"].strip():
                continue
            # Each unique eligible exact text gets one canonical source ID before sampling.
            known.add(text_sha)
            yield row
    rows = heapq.nsmallest(500, candidates(), key=lambda r: digest("scaling-500-fresh-v1:" + r["review_id"]))
    if len(rows) != 500:
        raise ValueError("Need 500 ingested nonempty unseen exact texts")
    write_csv(path, rows, list(FIELDS))
    return rows


def process_phase(db, run_id, cfg, directory, phase, workers, limiter, deadline, transport=None):
    stop = threading.Event()
    def worker(number, single=False):
        store = Store(db)
        queue = WorkQueue(store)
        worker_id = f"{phase}-worker-{number}"
        try:
            while not stop.is_set():
                task = queue.claim(run_id, phase, worker_id)
                if not task:
                    return
                rows = json.loads(task["rows_json"])
                local_cfg = cfg | {"workers": 1 if single else workers, "worker_id": worker_id, "queue_task_key": task["task_key"]}
                client = ModelClient(store, run_id, local_cfg, 10, directory, transport=transport,
                    deadline=deadline, run_cap=cfg.get("pilot_run_cap_usd", .25), limiter=limiter)
                try:
                    supplied = [{"review_id": r["review_id"], "review_text": r["review_text"]} for r in rows]
                    result = client.call(task["role"], {"reviews": supplied}, LABEL_SCHEMA,
                        lambda x: ground_labels(x, rows), "initial" if phase == cfg.get("initial_phase", "enrich-1") else "resume",
                        label_config(cfg) if task["role"] == "enrich" else "",
                        [r["review_id"] for r in rows])
                    if task["role"] == "enrich":
                        source = {r["review_id"]: r for r in rows}
                        store.save_records(run_id, [dict(p, status="completed", label_config=label_config(cfg),
                            source_sha256=row_sha(source[p["review_id"]])) for p in result["records"]], source, label_config(cfg))
                    queue.finish(run_id, task["task_key"])
                    if single:
                        return
                except (BudgetExceeded, TimeoutError) as e:
                    queue.finish(run_id, task["task_key"], "pending", str(e))
                    stop.set()
                    raise
                except Exception as e:
                    queue.finish(run_id, task["task_key"], "failed", str(e)[:250])
                    stop.set()
                    raise
        finally:
            store.close()
    if phase == "verify-8":
        probe_store = Store(db)
        succeeded = any(c.get("endpoint") == "decisions" and c["outcome"] == "succeeded" for c in probe_store.calls(run_id))
        probe_store.close()
        if not succeeded:
            # Check endpoint compatibility once before exposing a whole worker pool.
            worker("endpoint-probe", single=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker, i) for i in range(workers)]
        errors = []
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
            except Exception as e:
                stop.set()
                errors.append(str(e))
        if errors:
            raise RuntimeError("Worker stopped; saved queue retained: " + errors[0])


def projection(store, run_id):
    calls = store.calls(run_id)
    timing = store.get(run_id, "scaling_phase_measurements", [])
    roles = {}
    for role, count in (("enrich", 500), ("verify", 100)):
        relevant = [c for c in calls if c["role"] == role]
        failed = sum(c["outcome"] != "succeeded" for c in relevant)
        roles[role] = {"cost_per_record": str(sum((Decimal(c["calculated_api_usd"]) for c in relevant
            if c.get("calculated_api_usd") is not None), Decimal(0)) / count),
            "retry_ratio": failed / max(1, len(relevant)-failed)}
    enrichment_phase = "enrich-16" if store.run(run_id)["config"]["workers"] == 16 else "enrich-8"
    enrich8 = next((x for x in timing if x["phase"] == enrichment_phase and x["completed"]), None)
    verify8 = next((x for x in timing if x["phase"] == "verify-8" and x["completed"]), None)
    if not enrich8 or not verify8:
        return {"status": "insufficient_completed_measurement"}
    overhead_cost = sum((Decimal(c["calculated_api_usd"]) for c in calls
        if c["role"] in {"group", "memo"} and c.get("calculated_api_usd") is not None), Decimal(0))
    overhead_seconds = store.get(run_id, "scaling_analysis_seconds", 0)
    forecasts = []
    for reuse in (True, False):
        unique = round(100000 * 484189/660609) if reuse else 100000
        for conservative in (False, True):
            cost, seconds = overhead_cost, overhead_seconds
            for role, count, duration, measured_count in (("enrich", unique, enrich8["elapsed_seconds"], enrich8["records"]),
                                                       ("verify", 20000, verify8["elapsed_seconds"], 100)):
                ratio = roles[role]["retry_ratio"]
                factor = (1+max(.1, ratio))/(1+ratio) if conservative else 1
                cost += Decimal(roles[role]["cost_per_record"]) * count * Decimal(str(factor))
                seconds += duration / measured_count * count * factor * (1.5 if conservative else 1)
            forecasts.append({"scenario": ("conservative" if conservative else "base") + ("_exact_reuse" if reuse else "_no_reuse"),
                "estimated_api_usd": str(cost), "estimated_hours": seconds/3600,
                "target_classified_nonempty_ids": 100000, "estimated_distinct_texts": unique,
                "verification_source_ids": 20000, "workers": enrich8["workers"], "estimate_not_execution": True})
    return {"status": "estimated", "projections": forecasts,
        "notes": ["Extrapolates the measured parallel phase, not divided single-worker time.",
            "Exact reuse fraction is corpus-level; actual 100k subset distinct count is not yet measured.",
            "Unknown charges, hosting/local compute and unused historical caches are not included in these forecast subtotals.",
            "Short fresh-input phases may overstate sustained throughput; conservative case adds 50% time and at least 10% retries."]}


def scaling_pilot(db, run_id=RUN_ID):
    if run_id not in {RUN_ID, SIXTEEN_RUN_ID}:
        raise ValueError("Only explicitly authorized fixed 500-review scaling experiments are allowed")
    sixteen = run_id == SIXTEEN_RUN_ID
    phases = SIXTEEN_PHASES if sixteen else PHASES
    directory, cost = Path("artifacts/runs")/run_id, Path("cost/scaling_500_16w" if sixteen else "cost/scaling_500")
    preparation_started = time.monotonic()
    directory.mkdir(parents=True, exist_ok=True)
    cost.mkdir(parents=True, exist_ok=True)
    store = Store(db)
    try:
        cfg = config() | {"schema_version": "spotify-label-v3-id-enum", "routing_schema": "review-id-enum-v1",
            "execution_mode": "scaling-pilot-v1", "workers": 8, "verification_endpoint": "decisions",
            "verification_schema_version": "decisions-verifier-v2-bounded-arrays", "verification_sentiment_mapping": "index_0_4_to_minus1_plus1",
            "verification_predicate_threshold": .5, "verification_batch_size": 2}
        cfg["prompt_hashes"] = cfg["prompt_hashes"] | {"verify": digest(verification_prompt())}
        if sixteen:
            cfg.update(schema_version="spotify-label-v4-batch20", execution_mode="scaling-pilot-v2",
                workers=16, batch_size=20, label_batch_identity="batch-context-v1", initial_phase="enrich-probe")
        old_run = store.run(run_id)
        if old_run:
            cfg = old_run["config"]
        queue = WorkQueue(store)
        path = directory/"input_500.csv"
        if not path.exists():
            rows = select_fresh(store, path)
        info, rows = initialize(store, run_id, path, cfg, kind="scaling_pilot_500", max_records=500)
        if cfg.get("verification_schema_version") == "decisions-verifier-v1":
            override = {"verification_schema_version": "decisions-verifier-v2-bounded-arrays",
                "verification_sentiment_mapping": "index_0_4_to_minus1_plus1", "verification_batch_size": 2}
            if not store.get(run_id, "verification_contract_repair"):
                # Preserve the failed request configuration and never rewrite the saved enrichment settings.
                import shutil
                archive = cost/"initial_attempt"
                archive.mkdir(parents=True, exist_ok=True)
                for name in ("pilot_summary.json", "pilot_calls.jsonl", "budget_ledger.json"):
                    if (cost/name).exists():
                        shutil.copy2(cost/name, archive/name)
                prior_calls = store.calls(run_id)
                invalid = [c for c in prior_calls if c["role"] == "verify"]
                if invalid and not all(c.get("provider_error_code") == "array_above_max_length" or
                    "array_above_max_length" in c.get("error", "") for c in invalid):
                    raise RuntimeError("Unexpected verification failure requires inspection")
                prior_counts = collections.Counter(rid for c in invalid for rid in c["review_ids"])
                if any(n >= 3 for n in prior_counts.values()):
                    raise RuntimeError("Verification task exhausted its total attempts")
                store.put(run_id, "verification_contract_repair", {"saved_at": now(),
                    "reason": "HTTP 400 array_above_max_length; bound both question and sentiment-level arrays",
                    "original_configuration": {k: cfg.get(k) for k in override}, "new_configuration": override,
                    "prior_attempts": dict(prior_counts), "enrichment_relabeling": False})
                with store.db:
                    store.db.execute("UPDATE scaling_queue SET status='superseded' WHERE run_id=? AND role='verify'", (run_id,))
            cfg = cfg | override | {"prior_verification_attempts": store.get(run_id, "verification_contract_repair")["prior_attempts"]}
            store.put(run_id, "verification_runtime_config", {k: cfg.get(k) for k in (*override, "prior_verification_attempts")})
        original = store.get(run_id, "scaling_original_artifact_hashes")
        if original is None:
            protected = [Path("cost/checkpoint_10000/calculator.json"), Path("cost/pilot_summary.json"),
                Path("cost/checkpoint_500/pilot_summary.json"), Path("evals/golden_labels.json"), Path("evals/golden_report.json")]
            if sixteen:
                protected += [Path("cost/scaling_500")/name for name in ("pilot_summary.json", "pilot_calls.jsonl", "calculator.json")]
            original = {str(p): sha(p) for p in protected if p.exists()}
            store.put(run_id, "scaling_original_artifact_hashes", original)
            store.put(run_id, "scaling_start_spend", str(store.committed_spend()))
            write_json(directory/"preflight.json", {"saved_at": now(), "input_sha256": sha(path),
                "input_count": len(rows), "distinct_nonempty_texts": len({r["review_text"] for r in rows}),
                "sample_method": "seeded smallest hash over unseen unique texts; canonical source occurrence; excludes golden texts",
                "experiment_cache_initially_empty": not store.records(run_id), "protected_artifacts": original,
                "source_code_hashes": {str(p): sha(p) for p in sorted(Path("spotify_pipeline").rglob("*")) if p.suffix in {".py", ".md"}},
                "pilot_cap_usd": ".25", "shared_total_cap_usd": "10", "prior_ledger_usd": store.get(run_id, "scaling_start_spend")})
        if store.get(run_id, "scaling_summary"):
            return store.get(run_id, "scaling_summary")
        queue.recover(run_id)
        if any(k in queue.counts(run_id) for k in ("uncertain", "failed")):
            raise RuntimeError("Queue contains failed/uncertain tasks; inspect evidence before further paid work")
        offset = 0
        for phase, workers, count in phases:
            queue.add(run_id, "enrich", phase, batches(rows[offset:offset+count], cfg["batch_size"]), cfg)
            offset += count
        selected = sorted(rows, key=lambda r: digest(cfg["verification_seed"]+r["review_id"]))[:100]
        queue.add(run_id, "verify", "verify-8", batches(selected, cfg.get("verification_batch_size", 10)), cfg)
        limiter, started = SharedLimiter(), time.monotonic()
        if sixteen and store.get(run_id, "scaling_preparation_seconds") is None:
            store.put(run_id, "scaling_preparation_seconds", started-preparation_started)
        deadline = started + 1200 - store.get(run_id, "scaling_active_seconds", 0)
        error = None
        try:
            for phase, workers, count in (*phases, ("verify-8", 8, 100)):
                size = cfg.get("verification_batch_size", 10) if phase == "verify-8" else cfg["batch_size"]
                expected_tasks = (count+size-1)//size
                if queue.counts(run_id, phase) == {"completed": expected_tasks}:
                    continue
                phase_start = time.monotonic()
                before = len(store.calls(run_id))
                print(f"START {phase}: {count} fresh reviews, {workers} worker(s)", flush=True)
                completed = False
                try:
                    process_phase(db, run_id, cfg, directory, phase, workers, limiter, deadline)
                    completed = queue.counts(run_id, phase) == {"completed": expected_tasks}
                finally:
                    elapsed = time.monotonic()-phase_start
                    measurements = store.get(run_id, "scaling_phase_measurements", [])
                    measurements.append({"phase": phase, "workers": workers, "records": count,
                        "elapsed_seconds": elapsed, "completed": completed,
                        "new_calls": len(store.calls(run_id))-before, "saved_at": now(),
                        "source_utf8_bytes": sum(len(r["review_text"].encode()) for batch in store.db.execute(
                            "SELECT rows_json FROM scaling_queue WHERE run_id=? AND phase=?", (run_id, phase)) for r in json.loads(batch[0]))})
                    store.put(run_id, "scaling_phase_measurements", measurements)
                print(f"SAVED {phase}: {elapsed:.2f}s, {queue.counts(run_id, phase)}", flush=True)
                if phase == cfg.get("initial_phase", "enrich-1"):
                    snapshot(store, run_id, "checkpoint_before")
            analysis_start = time.monotonic()
            client = ModelClient(store, run_id, cfg | {"workers": 1}, 10, directory, deadline=deadline, run_cap=.25, limiter=limiter)
            # Verification task results are already saved. The downstream role reads those exact cached handoffs.
            downstream(store, run_id, client, directory)
            store.put(run_id, "scaling_analysis_seconds", time.monotonic()-analysis_start)
            snapshot(store, run_id, "checkpoint_after")
        except (Exception, KeyboardInterrupt) as e:
            error = str(e) or type(e).__name__
        finally:
            store.put(run_id, "scaling_active_seconds", store.get(run_id, "scaling_active_seconds", 0) + time.monotonic()-started)
            export(store, run_id, directory)
            write_jsonl(directory/"queue.jsonl", [dict(r) for r in store.db.execute("SELECT * FROM scaling_queue WHERE run_id=?", (run_id,))])
        records, calls = store.records(run_id), store.calls(run_id)
        known = sum((Decimal(c["calculated_api_usd"]) for c in calls if c.get("calculated_api_usd") is not None), Decimal(0))
        unknown = [c for c in calls if c.get("calculated_api_usd") is None]
        completed = len(records) == 500 and all(r["status"] == "completed" for r in records) and store.get(run_id, "memo") is not None and error is None
        summary = {"status": "completed" if completed else "incomplete", "run_id": run_id,
            "scope": "500 fresh unique review texts; development experiment only", "input_count": 500,
            "completed": len(records), "pending": 500-len(records), "verification_sample_count": len(store.get(run_id, "verification", {}).get("sample_ids", [])),
            "cold_seconds": store.get(run_id, "scaling_active_seconds"), "known_api_usd": str(known),
            "unknown_usage_calls": len(unknown), "unresolved_reservations_usd": str(sum((Decimal(c["reservation_usd"]) for c in unknown), Decimal(0))),
            "pilot_cap_usd": ".25", "shared_cap_usd": "10", "shared_committed_usd": str(store.committed_spend()),
            "phase_measurements": store.get(run_id, "scaling_phase_measurements", []), "error": error,
            "calls": len(calls), "failed_calls": sum(c["outcome"] != "succeeded" for c in calls),
            "original_artifacts_unchanged": all(sha(p) == h for p, h in original.items()),
            "verification_method": "Independent GPT Decisions with original text/rubric only; same-model repeatability, not human accuracy",
            "config": cfg}
        if sixteen:
            summary.update(preparation_seconds=store.get(run_id, "scaling_preparation_seconds", 0),
                enrichment_projection_phase="enrich-16", verification_projection_phase="verify-8",
                runtime_target_seconds=7200)
            summary["processing_plus_initial_preparation_seconds"] = summary["cold_seconds"] + summary["preparation_seconds"]
        if completed:
            warm_start, call_count = time.monotonic(), len(calls)
            membership, ranking, claims = rank_records(records)
            if ranking != store.get(run_id, "ranking"):
                raise ValueError("Offline ranking differs")
            # Re-run every role path: queue claims find no work; downstream resolves saved handoffs.
            for phase, workers, _ in (*phases, ("verify-8", 8, 100)):
                process_phase(db, run_id, cfg, directory, phase, workers, limiter, deadline)
            downstream(store, run_id, client, directory)
            warm_calls = len(store.calls(run_id))-call_count
            if warm_calls:
                raise ValueError("Warm path unexpectedly dispatched paid work")
            summary.update(warm_seconds=time.monotonic()-warm_start, warm_new_calls=warm_calls,
                offline_ranking_identical=True)
            store.put(run_id, "scaling_summary", summary)
        write_json(cost/"pilot_summary.json", summary)
        write_jsonl(cost/"pilot_calls.jsonl", store.calls(run_id))
        write_json(cost/"projection_100k.json", projection(store, run_id) if completed else {"status": "incomplete_pilot"})
        write_json(cost/"budget_ledger.json", {"shared_cap_usd": "10", "shared_spent_plus_reserved_usd": str(store.committed_spend()),
            "pilot_spent_plus_reserved_usd": str(known + sum((Decimal(c["reservation_usd"]) for c in unknown), Decimal(0))), "pilot_cap_usd": ".25"})
        return summary
    finally:
        store.close()
