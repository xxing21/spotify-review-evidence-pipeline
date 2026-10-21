"""Code orchestrates roles; models only interpret bounded language tasks."""
import collections
import json
import re
import time
from pathlib import Path

from check_submission import profile
from .common import (GROUP_SCHEMA, LABEL_FIELDS, LABEL_SCHEMA, MEMO_SCHEMA, TOPICS,
    atomic_text, canonical, config, csv_rows, digest, ground_labels, label_config, mean_string, now,
    row_sha, sha, source_records, validate_labels, write_csv, write_json, write_jsonl)
from .provider import ModelClient
from .store import BudgetExceeded, Store

RANK_FIELDS = ["rank", "issue_id", "complaint_count", "severity_sum", "mean_severity", "priority_score"]


def prepare(store, path, out="artifacts/ingestion"):
    path, out = Path(path), Path(out)
    started = time.monotonic()
    result = profile(path)  # Exact, unmodified instructor helper.
    if result["counts"]["duplicate_review_ids"]:
        raise ValueError("Duplicate source IDs must be resolved explicitly before ingestion")
    dataset = result["file_sha256"]
    texts = set()
    empty_records = []
    missing = collections.Counter()
    def stream():
        for row in csv_rows(path):
            missing.update(k for k, v in row.items() if not v.strip())
            if row["review_text"].strip():
                texts.add(row["review_text"])
            else:
                empty_records.append({"review_id": row["review_id"], "source_sha256": row_sha(row),
                    "status": "quarantined", "reason": "empty_review_text", "attempt_count": 0})
            yield row
    store.add_dataset(dataset, stream(), {"path": str(path.resolve()), "profile": result})
    summary = {"dataset_sha256": dataset, "profile": result,
        "distinct_nonempty_texts": len(texts),
        "duplicate_nonempty_rows": result["counts"]["records"] - result["counts"]["empty_review_text"] - len(texts),
        "missingness": dict(missing), "empty_text_quarantines": len(empty_records),
        "elapsed_seconds": time.monotonic() - started, "generated_at": now()}
    write_json(out / "ingestion.json", result)
    write_json(out / "report.json", summary)
    write_jsonl(out / "quarantine.jsonl", empty_records)
    manifest_path = Path("manifest.json")
    if manifest_path.exists() and path.name == "spotify_reviews_18months.csv":
        supplied = json.loads(manifest_path.read_text())
        if dataset != supplied["files"][path.name]["sha256"]:
            raise ValueError("Full source checksum differs from supplied manifest")
        if any(result["counts"][k] != v for k, v in supplied["profile"].items()):
            raise ValueError("Full profile differs from supplied manifest")
    lines = ["# Full-file ingestion (no model calls)", "", f"SHA-256: `{dataset}`", ""]
    lines.extend(f"- {k}: {v:,}" for k, v in result["counts"].items())
    lines += [f"- Distinct nonempty exact texts: {len(texts):,}", "",
        "Original strings, IDs and source row hashes are saved in SQLite.",
        "This accounts for the full source; it does not classify it."]
    atomic_text(out / "report.md", "\n".join(lines) + "\n")
    return summary


def initialize(store, run_id, path, cfg=None, kind="pilot", max_records=100):
    rows = source_records(path)
    if max_records not in {100, 500, 10000} or not 1 <= len(rows) <= max_records:
        raise ValueError(f"Pilot safety limit: input must have 1–{max_records} rows; larger inputs are refused, never truncated")
    golden_path = Path("golden_50_to_label.csv")
    if kind != "golden_evaluation" and golden_path.exists():
        golden_ids = {r["review_id"] for r in csv_rows(golden_path)}
        if golden_ids.intersection(r["review_id"] for r in rows):
            raise ValueError("Golden reviews are held out: use evaluate --execute-paid only after human labeling")
    cfg = cfg or config()
    dataset = sha(path)
    store.add_dataset(dataset, rows, {"path": str(Path(path).resolve()), "count": len(rows)})
    info = store.new_run(run_id, dataset, cfg,
        {"input_path": str(Path(path).resolve()), "input_count": len(rows), "kind": kind, "scope": "development_only"})
    return info, rows


def enrich(store, run_id, client, phase="initial", stop_after=None):
    info = store.run(run_id)
    rows = store.sources(info["dataset"])
    source = {r["review_id"]: r for r in rows}
    cfg = label_config(info["config"])
    prior_attempts = store.get(run_id, "prior_enrichment_attempt_counts", {})
    while True:
        current = {r["review_id"]: r for r in store.records(run_id)}
        pending = [r for r in rows if r["review_id"] not in current]
        if prior_attempts:
            pending.sort(key=lambda r: -prior_attempts.get(r["review_id"], 0))
        if not pending:
            break
        batch, seen = [], set()
        reused = []
        for r in pending:
            if not r["review_text"].strip():
                reused.append({"review_id": r["review_id"], "source_sha256": row_sha(r),
                    "status": "quarantined", "reason": "empty_review_text", "attempt_count": 0})
                continue
            cached = store.cached(run_id, r["review_text"], cfg)
            if cached:
                alias = dict(cached, review_id=r["review_id"], source_sha256=row_sha(r), cache_source_id=cached["review_id"])
                alias.pop("reused_from_run", None)  # This is a new ID with identical text, not an inherited original ID.
                reused.append(alias)
            elif (r["review_text"] not in seen and len(batch) < info["config"]["batch_size"]
                  and (not batch or prior_attempts.get(r["review_id"], 0) == prior_attempts.get(batch[0]["review_id"], 0))):
                seen.add(r["review_text"])
                batch.append(r)
        if reused:
            store.save_records(run_id, reused, source, cfg)
        if batch:
            supplied = [{"review_id": r["review_id"], "review_text": r["review_text"]} for r in batch]
            try:
                answer = client.call("enrich", {"reviews": supplied}, LABEL_SCHEMA,
                    lambda x: ground_labels(x, batch), phase, cfg, [r["review_id"] for r in batch])
                predictions = [dict(p, source_sha256=row_sha(source[p["review_id"]]),
                                    status="completed", label_config=cfg) for p in answer["records"]]
            except (BudgetExceeded, TimeoutError):
                raise
            except RuntimeError as e:
                # Account/model/config errors stop the run; bad language outputs are explicit quarantines.
                if "HTTP" in str(e) or "Unexpected" in str(e):
                    raise
                predictions = [{"review_id": r["review_id"], "source_sha256": row_sha(r),
                    "status": "quarantined", "reason": "model_stage_failed: " + str(e),
                    "attempt_count": prior_attempts.get(r["review_id"], 0) + sum(r["review_id"] in c["review_ids"] for c in store.calls(run_id) if c["role"] == "enrich")}
                    for r in batch]
            store.save_records(run_id, predictions, source, cfg)
        completed = sum(r["status"] == "completed" for r in store.records(run_id))
        print(f"Saved enrichment: {completed}/{len(rows)} completed", flush=True)
        if stop_after is not None and completed >= stop_after:
            return


def rank_records(records, membership=None):
    by_id = {r["review_id"]: r for r in records if r["status"] == "completed"}
    if membership is None:
        membership = [{"issue_id": "ISSUE-" + r["topic"].upper(), "review_id": r["review_id"]}
            for r in by_id.values() if r["intent"] in {"complaint", "cancellation"}]
    membership = sorted(membership, key=lambda x: (x["issue_id"], x["review_id"]))
    pairs, members, assigned = set(), collections.defaultdict(list), set()
    for m in membership:
        pair = (m["issue_id"], m["review_id"])
        r = by_id.get(m["review_id"])
        if pair in pairs or not r or r["intent"] not in {"complaint", "cancellation"} or r["review_id"] in assigned:
            raise ValueError("Invalid/duplicate/multi-issue membership")
        pairs.add(pair)
        assigned.add(r["review_id"])
        members[m["issue_id"]].append(r["severity"])
    if assigned != {rid for rid, r in by_id.items() if r["intent"] in {"complaint", "cancellation"}}:
        raise ValueError("Every complaint/cancellation must have one membership")
    ranking = [{"issue_id": iid, "complaint_count": len(vals), "severity_sum": sum(vals),
        "mean_severity": mean_string(sum(vals), len(vals)), "priority_score": sum(vals)} for iid, vals in members.items()]
    ranking.sort(key=lambda r: (-r["priority_score"], r["issue_id"]))
    for i, row in enumerate(ranking, 1):
        row["rank"] = i
    claims = [{"claim_id": f"{r['issue_id']}-{metric}", "issue_id": r["issue_id"], "metric": metric, "value": str(r[metric])}
        for r in ranking for metric in ("complaint_count", "severity_sum", "mean_severity", "priority_score")]
    return membership, ranking, claims


def validate_groups(answer, issue_ids):
    if not isinstance(answer, dict) or set(answer) != {"issues"} or not isinstance(answer["issues"], list):
        raise ValueError("Expected issues array")
    ids = []
    for row in answer["issues"]:
        if not isinstance(row, dict) or set(row) != {"issue_id", "name", "description"}:
            raise ValueError("Invalid issue schema")
        if any(not isinstance(row[k], str) or not row[k].strip() for k in row):
            raise ValueError("Empty issue name/description")
        if re.search(r"\d", row["name"] + row["description"]):
            raise ValueError("Issue names must not introduce numeric claims")
        ids.append(row["issue_id"])
    if len(ids) != len(set(ids)) or set(ids) != set(issue_ids):
        raise ValueError("Grouping changed fixed issue IDs")


def validate_memo(answer, ranking, claims, evidence):
    if not isinstance(answer, dict) or set(answer) != set(MEMO_SCHEMA["properties"]):
        raise ValueError("Invalid memo schema")
    for k in ("priority_issue_id", "rationale", "limitations"):
        if not isinstance(answer[k], str):
            raise ValueError("Memo text must be strings")
    for k in ("alternative_issue_ids", "claim_ids", "review_ids"):
        if not isinstance(answer[k], list) or any(not isinstance(x, str) for x in answer[k]):
            raise ValueError("Memo references must be string arrays")
    issue_ids = {r["issue_id"] for r in ranking}
    if answer["priority_issue_id"] not in (issue_ids or {""}) or not set(answer["alternative_issue_ids"]) <= issue_ids:
        raise ValueError("Memo cites unknown issue")
    if ranking and (not answer["claim_ids"] or not answer["review_ids"]):
        raise ValueError("Memo requires supporting claim and review references")
    if not set(answer["claim_ids"]) <= {c["claim_id"] for c in claims} or not set(answer["review_ids"]) <= {e["review_id"] for e in evidence}:
        raise ValueError("Memo invented claim or review ID")
    if ranking and len(ranking) > 1 and not answer["alternative_issue_ids"]:
        raise ValueError("Memo must compare an available alternative")
    if answer["priority_issue_id"] in answer["alternative_issue_ids"]:
        raise ValueError("Alternative must differ from priority")
    prose = answer["rationale"] + " " + answer["limitations"]
    if re.search(r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|million|percent)\b", prose, re.I):
        raise ValueError("Numerical prose must use claim references instead")


def downstream(store, run_id, client, directory, saved_verification=False):
    info = store.run(run_id)
    rows = store.sources(info["dataset"])
    source = {r["review_id"]: r for r in rows}
    records = store.records(run_id)
    successful = {r["review_id"]: r for r in records if r["status"] == "completed"}
    # Sampling is declared from inputs, never conditioned on enrichment success.
    from decimal import Decimal, ROUND_CEILING
    eligible = [r for r in rows if r["review_text"].strip()]
    count = int((Decimal(len(eligible))*Decimal(str(info["config"].get("verification_fraction", .2)))).to_integral_value(rounding=ROUND_CEILING))
    selected = sorted(eligible,
        key=lambda r: digest(info["config"]["verification_seed"] + r["review_id"]))[:max(1, count)]
    verified = []
    if saved_verification:
        saved = store.get(run_id, "verification")
        if not saved or saved["sample_ids"] != [r["review_id"] for r in selected] or len(saved["predictions"])+len(saved.get("refusals",[])) != len(selected):
            raise ValueError("Saved independent verification does not match declared sample")
        verified = saved["predictions"]
    for offset in range(0, 0 if saved_verification else len(selected), 10):
        batch = selected[offset:offset + 10]
        supplied = [{"review_id": r["review_id"], "review_text": r["review_text"]} for r in batch]
        answer = client.call("verify", {"reviews": supplied}, LABEL_SCHEMA, lambda x: ground_labels(x, batch),
            review_ids=[r["review_id"] for r in batch])
        verified.extend(answer["records"])
        print(f"Saved verification: {len(verified)}/{len(selected)} independently checked", flush=True)
    comparisons = [{"review_id": p["review_id"], "missing_enrichment": p["review_id"] not in successful,
        "different_fields": [k for k in LABEL_FIELDS if p[k] != successful.get(p["review_id"], {}).get(k)]}
        for p in verified]
    store.put(run_id, "verification", {"seed": info["config"]["verification_seed"],
        "sample_ids": [r["review_id"] for r in selected], "predictions": verified, "comparisons": comparisons,
        **({"refusals":saved.get("refusals",[])} if saved_verification else {}),
        "label_disagreements": sum(any(k in c["different_fields"] for k in ("topic", "intent", "severity")) for c in comparisons),
        "any_field_disagreements": sum(bool(c["different_fields"]) for c in comparisons)})
    membership, ranking, claims = rank_records(records)
    with store.db:
        store.db.execute("DELETE FROM membership WHERE run_id=?", (run_id,))
        store.db.executemany("INSERT INTO membership VALUES (?,?,?)",
                            ((run_id, m["issue_id"], m["review_id"]) for m in membership))
    pack = []
    for ranked in ranking:
        members = sorted([successful[m["review_id"]] for m in membership if m["issue_id"] == ranked["issue_id"]],
                         key=lambda r: (-r["severity"], r["review_id"]))[:3]
        pack.append({"issue_id": ranked["issue_id"], "topic": members[0]["topic"],
            "examples": [{"review_id": r["review_id"], "evidence_quote": r["evidence_quote"], "severity": r["severity"]} for r in members]})
    group_answer = client.call("group", {"issues": pack}, GROUP_SCHEMA,
        lambda x: validate_groups(x, [r["issue_id"] for r in ranking]))
    evidence = [dict(e, issue_id=p["issue_id"]) for p in pack for e in p["examples"][:2]]
    memo_scope = info["scope"] if info["config"].get("execution_mode")=="production-100k-v1" else "development pilot only"
    memo_input = {"scope": memo_scope, "completed": len(successful), "input_count": len(rows),
        "ranking": ranking, "claims": claims, "issues": group_answer["issues"], "evidence": evidence}
    memo = client.call("memo", memo_input, MEMO_SCHEMA, lambda x: validate_memo(x, ranking, claims, evidence))
    for name, value in {"membership": membership, "ranking": ranking, "claims": claims,
                        "issues": group_answer["issues"], "evidence": evidence, "memo": memo}.items():
        store.put(run_id, name, value)
    export(store, run_id, directory)


def export(store, run_id, directory):
    directory = Path(directory)
    info = store.run(run_id)
    records = store.records(run_id)
    by_id = {r["review_id"]: r for r in records}
    all_rows = store.sources(info["dataset"])
    calls = store.calls(run_id)
    attempt_counts = collections.Counter(rid for c in calls if c["role"] == "enrich" for rid in c["review_ids"])
    inherited_calls = store.get(run_id, "inherited_call_evidence", [])
    for r in all_rows:
        if r["review_id"] not in by_id:
            records.append({"review_id": r["review_id"], "source_sha256": row_sha(r), "status": "pending",
                "reason": "not_attempted_or_stopped",
                "attempt_count": attempt_counts[r["review_id"]]})
    records.sort(key=lambda r: r["review_id"])
    write_json(directory / "run_manifest.json", dict(info,
        code_versions_reported=sorted({c["code_version"] for c in calls if c.get("code_version")}),
        source_code_sha256_at_export=digest({p.name: sha(p) for p in sorted(Path(__file__).parent.glob("*.py"))}),
        code_identity_note="Package version is recorded per final-pilot call; export hash identifies the current saved source, not a Git commit."))
    write_jsonl(directory / "records.jsonl", records)
    write_jsonl(directory / "enriched.jsonl", [r for r in records if r["status"] == "completed"])
    write_jsonl(directory / "quarantine.jsonl", [r for r in records if r["status"] == "quarantined"])
    write_jsonl(directory / "calls.jsonl", calls)
    if inherited_calls:
        write_jsonl(directory / "inherited_calls.jsonl", inherited_calls)
    write_jsonl(directory / "run_log.jsonl", calls)
    write_json(directory / "run_summary.json", {"run_id": run_id, "scope": info.get("scope", "development_only"),
        "input_count": len(all_rows), "statuses": dict(collections.Counter(r["status"] for r in records)),
        "exact_text_reuses": sum(bool(r.get("cache_source_id")) for r in records),
        "model_attempts": len(calls), "failed_attempts": sum(c["outcome"] != "succeeded" for c in calls),
        "inherited_record_count": len(store.get(run_id, "inherited_ids", [])),
        "inherited_model_attempts": len(inherited_calls),
        "active_seconds": store.get(run_id, "active_seconds", 0),
        "spent_plus_unresolved_reservations_global_usd": str(store.committed_spend()),
        "account_repair_windows": store.get(run_id, "account_repair_windows", []), "config": info["config"]})
    membership = store.get(run_id, "membership", [])
    ranking = store.get(run_id, "ranking", [])
    claims = store.get(run_id, "claims", [])
    write_csv(directory / "membership.csv", membership, ["issue_id", "review_id"])
    write_csv(directory / "ranking.csv", ranking, RANK_FIELDS)
    write_csv(directory / "claims.csv", claims, ["claim_id", "issue_id", "metric", "value"])
    for name in ("verification", "issues", "evidence", "memo", "checkpoint_before", "checkpoint_after",
                 "checkpoint_extension_before", "checkpoint_extension_after", "inheritance",
                 "verification_contract_repair", "verification_runtime_config", "scaling_phase_measurements"):
        value = store.get(run_id, name)
        if value is not None:
            write_json(directory / (name + ".json"), value)
    memo = store.get(run_id, "memo")
    if memo:
        production = info["config"].get("execution_mode") == "production-100k-v1"
        lines = ["# Spotify product decision — " + ("100k sample" if production else "pilot only"), "", f"Priority: **{memo['priority_issue_id']}**", "", memo["rationale"], "",
                 "Alternatives: " + ", ".join(memo["alternative_issue_ids"]), "", "## Supporting calculations", ""]
        for c in claims:
            if c["claim_id"] in memo["claim_ids"]:
                lines.append(f"- [{c['claim_id']}] {c['issue_id']} {c['metric']}: {c['value']}")
        lines += ["", "## Source evidence", ""]
        for e in store.get(run_id, "evidence", []):
            if e["review_id"] in memo["review_ids"]:
                lines.append(f"- {e['issue_id']} / `{e['review_id']}`: {json.dumps(e['evidence_quote'], ensure_ascii=False)}")
        lines += ["", "## Limitations", "", memo["limitations"], "",
            f"Coverage: {sum(r['status'] == 'completed' for r in records)} completed of {len(all_rows)} {'sample' if production else 'pilot'} inputs. No full-corpus recommendation is established.",
            "Human inspection of the argument and quote support remains required."]
        atomic_text(directory / "memo.md", "\n".join(lines) + "\n")
    grading = directory / "grading"
    write_json(grading / "run.json", {"version": "a5-audit-v1", "analysis_count": len(all_rows),
        "analysis_sha256": info["dataset"], "classification_input_fields": ["review_text"],
        "allow_multi_issue": False, "scope": info.get("scope", "pilot_only"), "run_id": run_id})
    ingestion_path = Path("artifacts/ingestion/ingestion.json")
    if ingestion_path.exists():
        write_json(grading / "ingestion.json", json.loads(ingestion_path.read_text()))
    write_jsonl(grading / "records.jsonl", records)
    # Historical call evidence is retained verbatim for inherited original IDs.
    # It is not inserted into the spending ledger or reported as a new API call.
    write_jsonl(grading / "calls.jsonl", inherited_calls + calls)
    write_csv(grading / "membership.csv", membership, ["issue_id", "review_id"])
    write_csv(grading / "ranking.csv", ranking, RANK_FIELDS)
    write_csv(grading / "claims.csv", claims, ["claim_id", "issue_id", "metric", "value"])
    for name in ("checkpoint_before", "checkpoint_after"):
        write_json(grading / (name + ".json"), store.get(run_id, name, {"completed_ids": []}))
    return records


def rerank(store, run_id, directory):
    info = store.run(run_id)
    if not info:
        raise ValueError("Unknown run ID")
    membership = store.get(run_id, "membership")
    if membership is None:
        raise ValueError("No accepted membership saved yet")
    membership, ranking, claims = rank_records(store.records(run_id), membership)
    store.put(run_id, "ranking", ranking)
    store.put(run_id, "claims", claims)
    export(store, run_id, directory)
    return ranking


def rerank_exports(directory):
    """Portable replay from committed JSONL/CSV, without the local SQLite database."""
    from .common import read_jsonl
    directory = Path(directory)
    records = read_jsonl(directory / "records.jsonl")
    if not any(r["status"] == "completed" for r in records):
        raise ValueError("No completed records yet; ranking is pending actual model execution")
    membership = list(csv_rows(directory / "membership.csv"))
    membership, ranking, claims = rank_records(records, membership)
    write_csv(directory / "ranking.csv", ranking, RANK_FIELDS)
    write_csv(directory / "claims.csv", claims, ["claim_id", "issue_id", "metric", "value"])
    if (directory / "grading").exists():
        write_csv(directory / "grading/ranking.csv", ranking, RANK_FIELDS)
        write_csv(directory / "grading/claims.csv", claims, ["claim_id", "issue_id", "metric", "value"])
    return ranking


def snapshot(store, run_id, name):
    value = {"completed_ids": sorted(r["review_id"] for r in store.records(run_id) if r["status"] == "completed"),
             "saved_at": now(), "run_id": run_id}
    store.put(run_id, name, value)
    return value
