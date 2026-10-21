"""Explicit paid commands; every other command is offline."""
import argparse
import json
import sys
import time
from pathlib import Path

from .common import config, label_config, require_key, write_json
from .store import Store, experiment_lock


def parser():
    p = argparse.ArgumentParser(description="Auditable Spotify pilot. No paid calls unless --execute-paid is explicit.")
    p.add_argument("--db", default="state/pipeline.sqlite3")
    sub = p.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="Read/profile all rows with no model calls")
    prep.add_argument("--input", required=True)
    pilot = sub.add_parser("pilot", help="Real measured 100-review cold/warm run; explicit paid flag required")
    pilot.add_argument("--input", default="cost_100.csv")
    pilot.add_argument("--run-id", default="pilot-100-v2")
    pilot.add_argument("--execute-paid", action="store_true")
    pilot.add_argument("--budget-usd", type=float, default=2)
    pilot.add_argument("--retry-after-fix", action="store_true", help="Explicit new bounded attempt window after account repair; retains all prior evidence")
    checkpoint = sub.add_parser("checkpoint", help="Explicit supplied 500 or 10,000 review extension with saved-result reuse")
    checkpoint.add_argument("--input", default="checkpoint_500.csv")
    checkpoint.add_argument("--run-id", default=None)
    checkpoint.add_argument("--source-run", default=None)
    checkpoint.add_argument("--max-active-minutes", type=float, default=20, help="Explicit active time limit; maximum 180 for 10,000 reviews, 20 otherwise")
    checkpoint.add_argument("--execute-paid", action="store_true")
    checkpoint.add_argument("--budget-usd", type=float, default=2)
    recovery = sub.add_parser("recover-checkpoint", help="Bounded 10,000-review recovery with request-specific ID constraints")
    recovery.add_argument("--execute-paid", action="store_true")
    recovery.add_argument("--allow-final-invalid-attempt", action="store_true", help="Explicitly authorize one final attempt after two invalid outputs; absolute maximum remains three")
    recovery.add_argument("--budget-usd", type=float, default=2)
    scaling = sub.add_parser("scaling-pilot", help="Fresh 500-review staged 1/2/4/8-worker pilot; US$0.25 within US$10 shared cap")
    scaling.add_argument("--execute-paid", action="store_true")
    scaling.add_argument("--variant", choices=("eight", "sixteen"), default="eight", help="Separate authorized fixed experiment: eight workers/batch 10 or sixteen workers/batch 20")
    scaling.add_argument("--verify-batch-trial", action="store_true", help="Bounded verifier batch-10 test on the same completed sixteen-worker pilot sample")
    scaled_cost = sub.add_parser("scaling-replay", help="Offline replay of the new 500-review concurrency measurements")
    scaled_cost.add_argument("--directory", default="cost/scaling_500")
    scaled_cost.add_argument("--rates", default=None)
    scaled_cost.add_argument("--volume", type=int, default=100000)
    production = sub.add_parser("production", help="Approved 100k source-ID run: 16 workers, five-percent checks, US$10 shared ledger")
    production.add_argument("--input", default="spotify_reviews_18months.csv")
    production.add_argument("--execute-paid", action="store_true")
    production.add_argument("--prepare-only", action="store_true", help="Validate inputs and queue tasks without model calls")
    production.add_argument("--stop-after-checkpoint", action="store_true", help="Exit after the first saved batch for a real resume demonstration")
    production_cost=sub.add_parser("production-replay",help="Offline replay of actual 100k usage and current full-corpus estimates")
    production_cost.add_argument("--directory",default="cost/production_100k")
    production_cost.add_argument("--rates",default=None)
    production_cost.add_argument("--volume",type=int,default=660622)
    run = sub.add_parser("run", help="Run stages on an arbitrary supplied CSV of 1–100 rows")
    run.add_argument("--input", required=True)
    run.add_argument("--run-id", required=True)
    run.add_argument("--execute-paid", action="store_true")
    run.add_argument("--budget-usd", type=float, default=2)
    cost = sub.add_parser("cost", help="Offline only")
    cs = cost.add_subparsers(dest="cost_command", required=True)
    replay = cs.add_parser("replay")
    replay.add_argument("--rates", default=None, help="Editable rates; defaults to rates.csv in the selected measurement directory")
    replay.add_argument("--volume", type=int, default=660622)
    replay.add_argument("--budget-usd", type=float, default=2)
    replay.add_argument("--directory", default="cost", help="Saved measurements folder; cost/checkpoint_500 for the 500-review extension")
    rank = sub.add_parser("rank", help="Regenerate ranking from saved membership; no API calls")
    rank.add_argument("--run-id", required=True)
    sub.add_parser("label-golden", help="Human labeling helper; no model suggestions or calls")
    ev = sub.add_parser("evaluate", help="Requires all 50 human labels before inspecting predictions")
    ev.add_argument("--run-id", required=True)
    ev.add_argument("--labels", default="evals/golden_labels.json")
    ev.add_argument("--execute-paid", action="store_true", help="Explicitly classify golden texts after human answers are complete")
    ev.add_argument("--budget-usd", type=float, default=2)
    check = sub.add_parser("check", help="Run instructor checker against pilot-scoped export, no API calls")
    check.add_argument("--run-id", default="pilot-100-v2")
    check.add_argument("--full", default="spotify_reviews_18months.csv")
    sub.add_parser("status", help="Show local accounting; no API calls")
    worker = sub.add_parser("_worker", help=argparse.SUPPRESS)
    worker.add_argument("--run-id", required=True)
    worker.add_argument("--directory", required=True)
    worker.add_argument("--phase", choices=["initial", "resume"], required=True)
    worker.add_argument("--budget-usd", type=float, default=2)
    worker.add_argument("--stop-after", type=int)
    return p


def main(argv=None):
    p = parser()
    a = p.parse_args(argv)
    try:
        if a.command=="production-replay":
            from .production_cost import replay
            result=replay(a.directory,a.rates,a.volume)
            print(json.dumps({"status":result["measured"]["status"],"known_api_usd":result["measured"]["known_api_usd"],"projections":result["projections"]},indent=2))
            return
        if a.command == "production":
            from .production import production as production_run
            from .scaling import terminal_recording
            if not a.prepare_only and not a.execute_paid:
                p.error("Production execution requires --execute-paid; use --prepare-only for zero-call preparation")
            if not a.prepare_only:
                require_key()
            with experiment_lock(Path(a.db).parent/"paid-command"):
                recording=Path("artifacts/runs/production-100k-v1/terminal")/f"execution-{time.time_ns()}.cast"
                with terminal_recording(recording):
                    result=production_run(a.db,a.input,a.prepare_only,a.stop_after_checkpoint)
                    print(json.dumps({k:v for k,v in result.items() if k!="config"},indent=2))
            if result["status"]=="checkpoint_saved":
                raise SystemExit(130)
            if result["status"] not in {"prepared","completed"}:
                raise SystemExit(1)
            return
        if a.command in {"pilot", "run", "checkpoint", "recover-checkpoint", "scaling-pilot"} and not a.execute_paid:
            p.error("No model calls made. Paid execution requires --execute-paid.")
        if a.command == "scaling-pilot":
            from .scaling import scaling_pilot, terminal_recording
            require_key()
            if a.verify_batch_trial and a.variant != "sixteen":
                p.error("Verifier batching trial requires the sixteen-worker parent experiment")
            with experiment_lock(Path(a.db).parent / "paid-command"):
                run_id = "scaling-500-16w-v1" if a.variant == "sixteen" else "scaling-500-v1"
                recording = Path("artifacts/runs")/run_id/"terminal"/f"execution-{time.time_ns()}.cast"
                with terminal_recording(recording):
                    if a.verify_batch_trial:
                        from .verification_trial import trial
                        result = trial(a.db)
                    else:
                        result = scaling_pilot(a.db, run_id)
                    print(json.dumps({k:v for k,v in result.items() if k not in {"config", "phase_measurements"}}, indent=2))
            if result["status"] != "completed":
                raise SystemExit(1)
            return
        if a.command == "scaling-replay":
            from .scaling_cost import replay as scaling_replay
            result = scaling_replay(a.directory, a.rates, a.volume)
            print(json.dumps({"status": result["measured"]["status"], "known_api_usd": result["measured"]["known_api_usd"],
                "projections": result["projections"]}, indent=2))
            return
        if a.command == "recover-checkpoint":
            from .recovery import recover
            with experiment_lock(Path(a.db).parent / "paid-command"):
                result = recover(a.db, a.budget_usd, a.allow_final_invalid_attempt)
            print(json.dumps({k:v for k,v in result.items() if k not in {"input_ids", "config"}}, indent=2))
            if result["status"] != "completed":
                raise SystemExit(1)
            return
        if a.command == "cost":
            from .calculator import replay
            r = replay(directory=a.directory, rates_path=a.rates or Path(a.directory)/"rates.csv", volume=a.volume, budget=a.budget_usd)
            print(json.dumps({"status": r["measured"]["status"], "known_api_usd": r["measured"]["known_api_usd"],
                              "report": str(Path(a.directory) / "report.md")}, indent=2))
            return
        if a.command == "checkpoint":
            from .checkpoint import checkpoint
            with experiment_lock(Path(a.db).parent / "paid-command"):
                result = checkpoint(a.db, a.input, a.run_id, a.source_run, a.budget_usd, a.max_active_minutes)
            print(json.dumps({k:v for k,v in result.items() if k not in {"input_ids", "config"}},indent=2))
            if result["status"] != "completed":
                raise SystemExit(1)
            return
        if a.command == "pilot":
            from .runner import pilot
            with experiment_lock(Path(a.db).parent / "paid-command"):
                result = pilot(a.db, a.input, a.run_id, a.budget_usd, a.retry_after_fix)
            print(json.dumps(result, indent=2))
            if result["status"] != "completed":
                raise SystemExit(1)
            return
        if a.command == "_worker":
            from .runner import worker
            worker(a.db, a.run_id, a.directory, a.phase, a.budget_usd, a.stop_after)
            return
        if a.command == "label-golden":
            from .evaluation import human_labels
            human_labels()
            return
        store = Store(a.db)
        try:
            if a.command == "prepare":
                from .pipeline import prepare
                result = prepare(store, a.input)
            elif a.command == "run":
                from .pipeline import downstream, enrich, export, initialize
                from .provider import ModelClient
                if not 0 < a.budget_usd <= 2:
                    raise ValueError("Pilot maximum is US$2")
                require_key()
                directory = Path("artifacts/runs") / a.run_id
                with experiment_lock(Path(a.db).parent / "paid-command"), experiment_lock(directory):
                    info, _ = initialize(store, a.run_id, a.input, kind="development")
                    client = ModelClient(store, a.run_id, info["config"], a.budget_usd, directory)
                    try:
                        enrich(store, a.run_id, client, "resume" if store.records(a.run_id) else "initial")
                        downstream(store, a.run_id, client, directory)
                    finally:
                        export(store, a.run_id, directory)
                result = {"run_id": a.run_id, "records": len(store.records(a.run_id))}
            elif a.command == "rank":
                from .pipeline import rerank, rerank_exports
                directory = Path("artifacts/runs") / a.run_id
                result = rerank(store, a.run_id, directory) if store.run(a.run_id) else rerank_exports(directory)
            elif a.command == "evaluate":
                from .evaluation import check_human_labels, evaluate
                from .pipeline import enrich, export, initialize
                from .provider import ModelClient
                predictions = None
                if not a.execute_paid and check_human_labels(a.labels) is not None:
                    target_run = store.run(a.run_id)
                    if target_run:
                        cached_golden_id = "golden-" + label_config(target_run["config"]).split(":")[-1][:12]
                        if store.run(cached_golden_id):
                            predictions = store.records(cached_golden_id)
                if a.execute_paid:
                    if check_human_labels(a.labels) is None:
                        raise ValueError("Complete all 50 human labels before golden model execution")
                    if not 0 < a.budget_usd <= 2:
                        raise ValueError("Pilot maximum is US$2")
                    require_key()
                    target_run = store.run(a.run_id)
                    if not target_run:
                        raise ValueError("Unknown evaluation target run")
                    cfg = target_run["config"]
                    if cfg["prompt_hashes"] != config()["prompt_hashes"]:
                        raise ValueError("Saved run prompts differ from current prompts; restore or explicitly version them before evaluation")
                    golden_id = "golden-" + label_config(cfg).split(":")[-1][:12]
                    directory = Path("artifacts/evaluation") / golden_id
                    with experiment_lock(Path(a.db).parent / "paid-command"), experiment_lock(directory):
                        initialize(store, golden_id, "golden_50_to_label.csv", cfg, kind="golden_evaluation")
                        client = ModelClient(store, golden_id, cfg, a.budget_usd, directory)
                        # Only text and ID reach this function. Human answer fields are never read by it.
                        enrich(store, golden_id, client, "resume" if store.records(golden_id) else "initial")
                        export(store, golden_id, directory)
                        predictions = store.records(golden_id)
                result = evaluate(store, a.run_id, a.labels, predictions)
            elif a.command == "check":
                from check_submission import audit, reference, reference_hash
                info = store.run(a.run_id)
                if not info:
                    manifest = Path("artifacts/runs") / a.run_id / "run_manifest.json"
                    if not manifest.exists():
                        raise ValueError("Unknown run; real pilot has not been run")
                    info = json.loads(manifest.read_text())
                directory = Path("artifacts/runs") / a.run_id
                input_path = Path(info["input_path"])
                if not input_path.exists():
                    input_path = Path(input_path.name)
                ref = reference(a.full, input_path)
                write_json("artifacts/local-reference-pilot.json", ref)
                result = audit(directory / "grading", ref, ref_digest=reference_hash(ref))
                write_json(directory / "self-check.json", result)
            elif a.command == "status":
                from .common import load_env
                import os
                load_env()
                runs = [json.loads(r[0]) for r in store.db.execute("SELECT info FROM runs ORDER BY rowid")]
                result = {"key_configured": bool(os.environ.get("OPENAI_API_KEY")),
                    "runs": [{"run_id": r["run_id"], "kind": r["kind"], "record_statuses": dict(__import__('collections').Counter(
                        x["status"] for x in store.records(r["run_id"])))} for r in runs],
                    "spent_plus_unresolved_reservations_usd": str(store.committed_spend())}
            else:
                raise ValueError("Unsupported command")
            display = {k:v for k,v in result.items() if k != "cases"} if a.command == "evaluate" else result
            print(json.dumps(display, indent=2, ensure_ascii=False))
            if a.command == "check" and result["status"] != "pass":
                raise SystemExit(1)
        finally:
            store.close()
    except KeyboardInterrupt:
        print("Interrupted after saved progress. Resume with the same explicit command.", flush=True)
        raise SystemExit(130)
    except (ValueError, RuntimeError, TimeoutError, OSError) as e:
        print(f"Stopped: {e}", file=sys.stderr)
        raise SystemExit(1)
