"""Shared contract, schemas and atomic artifacts (standard library only)."""
import csv
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

from check_submission import FIELDS, INTENTS, TOPICS, canonical, csv_rows, loads, mean_string, row_sha, sha

MODEL = "gpt-6-luna"
EFFORT = "none"
SCHEMA_VERSION = "spotify-label-v2-code-grounding"
PROMPTS = Path(__file__).with_name("prompts")
LABEL_FIELDS = ("topic", "intent", "sentiment", "severity", "entities", "evidence_quote", "needs_review")


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def write_json(path, obj):
    atomic_text(path, json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_jsonl(path, rows):
    atomic_text(path, "".join(canonical(r) + "\n" for r in rows))


def write_csv(path, rows, fields):
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_text(path, buffer.getvalue())


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(s) for s in Path(path).read_text(encoding="utf-8").splitlines() if s.strip()]


def prompt(role):
    parts = [(PROMPTS / f"{role}.md").read_text()]
    if role in {"enrich", "verify"}:
        parts.append((PROMPTS / "labels.md").read_text())
    return "\n\n".join(parts)


def config():
    return {"model": MODEL, "effort": EFFORT, "schema_version": SCHEMA_VERSION,
            "prompt_hashes": {r: digest(prompt(r)) for r in ("enrich", "verify", "group", "memo")},
            "batch_size": 10, "workers": 1, "max_output_tokens": 4096,
            "verification_fraction": 0.2, "verification_seed": "spotify-pilot-verify-v1",
            "fallback_fraction": 0, "service_tier": "default", "max_attempts": 3}


def label_config(cfg):
    # A grouping/memo edit does not invalidate already-paid classification results.
    identity = {k: cfg[k] for k in ("model", "effort", "schema_version", "max_output_tokens", "service_tier")} | {
        "enrich_prompt": cfg["prompt_hashes"]["enrich"], "actual_label_schema": LABEL_SCHEMA}
    if cfg.get("routing_schema"):
        identity["routing_schema"] = cfg["routing_schema"]
    if cfg.get("label_batch_identity"):
        identity["batch_context"] = {"version": cfg["label_batch_identity"], "batch_size": cfg["batch_size"]}
    return MODEL + ":" + digest(identity)


def obj_schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def arr(items):
    return {"type": "array", "items": items}


def string():
    return {"type": "string"}


PREDICTION_SCHEMA = obj_schema({
    "review_id": string(), "topic": {"type": "string", "enum": list(TOPICS)},
    "intent": {"type": "string", "enum": list(INTENTS)},
    "sentiment": {"type": "number", "minimum": -1, "maximum": 1},
    "severity": {"type": "integer", "minimum": 1, "maximum": 5},
    "entities": arr(string()), "evidence_quote": string(), "needs_review": {"type": "boolean"}})
LABEL_SCHEMA = obj_schema({"records": arr(PREDICTION_SCHEMA)})
GROUP_SCHEMA = obj_schema({"issues": arr(obj_schema({"issue_id": string(), "name": string(), "description": string()}))})
MEMO_SCHEMA = obj_schema({"priority_issue_id": string(), "rationale": string(),
    "alternative_issue_ids": arr(string()), "claim_ids": arr(string()),
    "review_ids": arr(string()), "limitations": string()})


def validate_labels(result, source_rows):
    if not isinstance(result, dict) or set(result) != {"records"} or not isinstance(result["records"], list):
        raise ValueError("Expected records array")
    expected = {r["review_id"]: r for r in source_rows}
    seen = set()
    for p in result["records"]:
        if not isinstance(p, dict) or set(p) != set(PREDICTION_SCHEMA["properties"]):
            raise ValueError("Prediction keys differ from schema")
        rid = p["review_id"]
        if not isinstance(rid, str) or rid not in expected or rid in seen:
            raise ValueError("Missing, duplicate or foreign review ID")
        seen.add(rid)
        if p["topic"] not in TOPICS or p["intent"] not in INTENTS:
            raise ValueError("Unknown label")
        if type(p["severity"]) is not int or not 1 <= p["severity"] <= 5:
            raise ValueError("Invalid severity")
        if type(p["sentiment"]) not in (int, float) or not math.isfinite(p["sentiment"]) or not -1 <= p["sentiment"] <= 1:
            raise ValueError("Invalid sentiment")
        if type(p["needs_review"]) is not bool or not isinstance(p["entities"], list):
            raise ValueError("Invalid review flag/entities")
        text = expected[rid]["review_text"]
        quote = p["evidence_quote"]
        if not isinstance(quote, str) or not quote.strip() or quote not in text:
            raise ValueError("Evidence quote is not an exact nonempty source substring")
        if any(not isinstance(e, str) or not e.strip() or e not in text for e in p["entities"]):
            raise ValueError("Entity must be an exact source substring")
    if seen != set(expected):
        raise ValueError("Returned IDs do not exactly cover requested IDs")
    return result


def ground_labels(result, source_rows):
    """Code owns literal extraction; the model owns only language judgments.

    The entire review is the quote, so no normalization or paraphrase can break
    source membership. Raw model placeholders stay in the handoff response.
    """
    import re
    if not isinstance(result, dict) or set(result) != {"records"} or not isinstance(result["records"], list):
        raise ValueError("Expected records array")
    source = {r["review_id"]: r for r in source_rows}
    seen = set()
    for p in result["records"]:
        if not isinstance(p, dict) or set(p) != set(PREDICTION_SCHEMA["properties"]):
            raise ValueError("Prediction keys differ from schema")
        rid = p["review_id"]
        if not isinstance(rid, str) or rid not in source or rid in seen:
            raise ValueError("Duplicate/foreign review ID")
        seen.add(rid)
        if not isinstance(p["evidence_quote"], str) or not isinstance(p["entities"], list) or any(not isinstance(e,str) for e in p["entities"]):
            raise ValueError("Invalid extraction placeholders")
        text = source[rid]["review_text"]
        p["evidence_quote"] = text
        p["entities"] = list(dict.fromkeys(m.group() for m in re.finditer(
            r"\b(?:Spotify|Premium|ads?|downloads?|offline|lyrics|podcasts?|playlists?|queue|login|sign in)\b", text, re.I)))
    return validate_labels(result, source_rows)


def load_env(path=".env"):
    """Only read the user-created local file. Never execute shell syntax."""
    if Path(path).exists():
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if sep and key.strip() == "OPENAI_API_KEY":
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def require_key():
    load_env()
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ValueError("Paid pilot pending: set OPENAI_API_KEY in local .env (never in chat or logs).")


def source_records(path):
    rows = list(csv_rows(path))
    if any(not all(k in r for k in FIELDS) for r in rows):
        raise ValueError("Input CSV must contain all six source fields")
    if len({r["review_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate source IDs")
    return [{k: r[k] for k in FIELDS} for r in rows]
