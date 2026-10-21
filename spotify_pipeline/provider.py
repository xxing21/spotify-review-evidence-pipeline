"""Direct Responses HTTPS adapter; no SDK, hidden retries, tools or fallbacks."""
import json
import copy
import os
import random
import socket
import time
import urllib.error
import urllib.request
import uuid
from decimal import Decimal
from pathlib import Path

from .common import MODEL, canonical, csv_rows, digest, loads, now, prompt, require_key, write_json


def rates(path="cost/rates.csv"):
    result = {}
    for r in csv_rows(path):
        if (r["provider"], r["model"], r["tier"], r["currency"], r["unit"]) != ("openai", MODEL, "default", "USD", "tokens"):
            raise ValueError("Rate card must use OpenAI gpt-6-luna Standard USD/token rates")
        if r["item"] in result or Decimal(r["price_per_unit"]) < 0:
            raise ValueError("Duplicate or negative rate")
        result[r["item"]] = Decimal(r["price_per_unit"])
    if set(result) != {"input", "cached_input", "cache_write", "output"}:
        raise ValueError("Incomplete rate card")
    return result


def billing_units(usage):
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int for k in ("input_tokens", "output_tokens")):
        raise ValueError("Provider usage unavailable")
    details = usage.get("input_tokens_details") or {}
    cached = details.get("cached_tokens", 0)
    writes = details.get("cache_write_tokens", 0)
    result = {"input": usage["input_tokens"] - cached - writes, "cached_input": cached,
              "cache_write": writes, "output": usage["output_tokens"]}
    if any(type(v) is not int or v < 0 for v in result.values()):
        raise ValueError("Provider usage has inconsistent billing categories")
    return result


def charge(usage, card):
    return sum((Decimal(v) * card[k] for k, v in billing_units(usage).items()), Decimal(0))


class TransientError(RuntimeError):
    def __init__(self, message, retry_after=0, code=None, request_id=None):
        super().__init__(message)
        self.retry_after, self.code, self.request_id = retry_after, code, request_id


class AccountError(RuntimeError):
    pass


def https_response(payload):
    return https_json(payload, "responses")


def https_json(payload, endpoint):
    if endpoint not in {"responses", "decisions"}:
        raise ValueError("Unsupported provider endpoint")
    request = urllib.request.Request("https://api.openai.com/v1/" + endpoint,
        data=canonical(payload).encode(), method="POST", headers={
            "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            value = json.load(response)
            value["http_request_id"] = response.headers.get("x-request-id")
            value["rate_limit_headers"] = {k: v for k, v in response.headers.items()
                if k.lower().startswith("x-ratelimit-") or k.lower() == "retry-after"}
            return value
    except urllib.error.HTTPError as e:
        # Record only safe error identifiers, never raw error bodies or authorization headers.
        try:
            error = json.loads(e.read()).get("error", {})
            code = error.get("code")
            code = code if isinstance(code, str) and code.replace("_", "").isalnum() else None
            import re
            param = error.get("param")
            param = param if isinstance(param, str) and re.fullmatch(r"[A-Za-z0-9_.\[\]]{1,160}", param) else None
        except (ValueError, TypeError, AttributeError):
            code, param = None, None
        account_codes = {"insufficient_quota", "credit_balance_exhausted", "organization_spend_limit_exceeded",
            "project_spend_limit_exceeded", "organization_usage_limit_exceeded", "billing_hard_limit_reached"}
        if code in account_codes:
            raise AccountError(f"OpenAI HTTP {e.code}: {code}; correct account credits/limits before retrying") from None
        if e.code == 429 or e.code >= 500:
            try:
                delay = max(0, float(e.headers.get("Retry-After", 0)))
            except ValueError:
                delay = 0
            raise TransientError(f"HTTP {e.code}: {code or 'unspecified'}; usage/charges unavailable",
                delay, code, e.headers.get("x-request-id")) from None
        raise RuntimeError(f"OpenAI HTTP {e.code}: {code or 'unspecified'}" + (f" at {param}" if param else "") +
            "; check request/account/model access; no automatic model substitution") from None
    except (urllib.error.URLError, TimeoutError, socket.timeout):
        raise TransientError("Network/timeout; usage and charge unknown, reservation retained") from None


class ModelClient:
    def __init__(self, store, run_id, cfg, cap, directory, transport=None, deadline=None, sleeper=time.sleep,
                 run_cap=None, limiter=None):
        allowed_workers = {"scaling-pilot-v1": range(1, 9), "scaling-pilot-v2": range(1, 17),
            "production-100k-v1": range(1, 17)}.get(cfg.get("execution_mode"), (1,))
        if cfg["model"] != MODEL or cfg["effort"] != "none" or cfg["workers"] not in allowed_workers or cfg["fallback_fraction"] != 0:
            raise ValueError("Unsupported model, effort, worker count or fallback configuration")
        if not 1 <= cfg["max_output_tokens"] <= 4096 or not 1 <= cfg["batch_size"] <= 50:
            raise ValueError("Pilot token/batch cap exceeded")
        self.store, self.run_id, self.cfg, self.cap = store, run_id, cfg, Decimal(str(cap))
        self.directory = Path(directory)
        self.transport = transport or https_response
        self.real = transport is None
        self.deadline = deadline or time.monotonic() + 1200
        self.sleeper = sleeper
        self.card = rates()
        self.cache_hits = 0
        self.run_cap, self.limiter = run_cap, limiter

    def call(self, role, data, schema, validator, phase="initial", label_config="", review_ids=None):
        if role == "verify" and self.cfg.get("verification_endpoint") == "decisions":
            size = self.cfg.get("verification_batch_size", 10)
            if len(data["reviews"]) > size:
                from .common import ground_labels
                combined = {"records": []}
                for i in range(0, len(data["reviews"]), size):
                    subset = data["reviews"][i:i+size]
                    answer = self.call(role, {"reviews": subset}, schema, lambda x: ground_labels(x, subset),
                        phase, label_config, [r["review_id"] for r in subset])
                    combined["records"].extend(answer["records"])
                validator(combined)
                return combined
        if role == "enrich" and not 1 <= len(review_ids or []) <= 50:
            raise ValueError("Enrichment request must contain 1–50 validated routing IDs")
        if self.real:
            require_key()
        if role in {"enrich", "verify"} and self.cfg.get("routing_schema") == "review-id-enum-v1":
            schema = copy.deepcopy(schema)
            schema["properties"]["records"]["items"]["properties"]["review_id"]["enum"] = list(review_ids)
        payload = {"model": self.cfg["model"], "reasoning": {"effort": self.cfg["effort"]},
            "service_tier": "default", "store": False, "max_output_tokens": self.cfg["max_output_tokens"],
            "input": [{"role": "system", "content": prompt(role)},
                      {"role": "user", "content": canonical(data)}],
            "text": {"format": {"type": "json_schema", "name": "spotify_" + role, "strict": True, "schema": schema}}}
        endpoint = "responses"
        if role == "verify" and self.cfg.get("verification_endpoint") == "decisions":
            from .decisions import decision_payload
            payload = decision_payload(data["reviews"])
            endpoint = "decisions"
        base_key = digest(payload) if endpoint == "responses" else digest({"endpoint": endpoint, "payload": payload,
            "verification_schema_version": self.cfg.get("verification_schema_version"),
            "sentiment_mapping": self.cfg.get("verification_sentiment_mapping"),
            "predicate_threshold": self.cfg.get("verification_predicate_threshold")})
        window = self.store.get(self.run_id, "attempt_window", 0)
        key = digest({"payload": payload, "attempt_window": window}) if window else base_key
        saved = self.store.saved_call(self.run_id, key)
        if saved is None and window:
            # A repaired account must not invalidate any successful task from earlier windows.
            row = self.store.db.execute("SELECT result FROM calls WHERE run_id=? AND result IS NOT NULL AND "
                "(task_key=? OR json_extract(event,'$.payload_sha256')=?) ORDER BY rowid DESC LIMIT 1",
                (self.run_id, base_key, base_key)).fetchone()
            saved = json.loads(row[0]) if row else None
        if saved is not None:
            validator(saved)
            self.cache_hits += 1
            return saved
        invalid_count = self.store.db.execute("SELECT COUNT(*) FROM calls WHERE run_id=? AND task_key=? AND json_extract(event,'$.error_kind')='invalid_output'", (self.run_id, key)).fetchone()[0]
        failures = self.store.attempts(self.run_id, key)
        prior = max((self.store.get(self.run_id, "prior_enrichment_attempt_counts", {}).get(rid, 0)
            for rid in (review_ids or [])), default=0) if role == "enrich" else max((
            self.cfg.get("prior_verification_attempts", {}).get(rid, 0) for rid in (review_ids or [])), default=0) if role == "verify" else 0
        attempt_limit = min(3 - prior, self.cfg.get("max_task_attempts", 3))
        if invalid_count >= 2 or failures >= attempt_limit:
            raise ValueError("Task retry limit already exhausted; no automatic repeat charges")
        for attempt in range(failures + 1, attempt_limit + 1):
            if time.monotonic() >= self.deadline:
                raise TimeoutError("Active run time limit reached; saved work retained")
            local_id = str(uuid.uuid4())
            event = {"local_call_id": local_id, "request_id": local_id, "run_id": self.run_id,
                "role": role, "review_ids": review_ids or [], "model": MODEL, "requested_model": MODEL,
                "effort": self.cfg["effort"], "service_tier": "default", "phase": phase,
                "outcome": "failed", "error_kind": "interrupted_in_flight", "label_config": label_config,
                "task_key": key, "payload_sha256": base_key, "attempt_window": window,
                "schema_version": self.cfg["schema_version"],
                "prompt_hash": self.cfg["prompt_hashes"][role], "batch_size": len(review_ids or []),
                "worker_count": self.cfg["workers"], "attempt": prior + attempt, "task_attempt": attempt,
                "prior_enrichment_attempts": prior, "routing_schema": self.cfg.get("routing_schema"),
                "started_at": now(), "usage": None,
                "input_tokens": None, "output_tokens": None, "synthetic": not self.real}
            event.update(endpoint=endpoint, queue_task_key=self.cfg.get("queue_task_key"),
                worker_id=self.cfg.get("worker_id"),
                requested_reasoning_effort="none" if endpoint == "responses" else None,
                requested_max_output_tokens=self.cfg["max_output_tokens"] if endpoint == "responses" else None)
            if endpoint == "decisions":
                event["verification_config"] = {k: self.cfg.get(k) for k in ("verification_schema_version",
                    "verification_sentiment_mapping", "verification_predicate_threshold", "verification_batch_size")}
            event["rate_snapshot_usd_per_token"] = {k: str(v) for k, v in self.card.items()}
            event["code_version"] = "0.1.0"
            # UTF-8 byte count is an intentionally loose input-token upper bound; add framing allowance.
            max_input = len(canonical(payload).encode()) + 4096
            reserve = Decimal(max_input) * max(self.card[k] for k in ("input", "cached_input", "cache_write"))
            reserve += Decimal(self.cfg["max_output_tokens"]) * self.card["output"]
            if endpoint == "decisions":
                reserve = Decimal(max_input) * self.card["input"]
                event["rate_snapshot_usd_per_token"] = {"input": str(self.card["input"]),
                    "cached_input": "0", "cache_write": "0", "output": "0"}
            if self.limiter:
                self.limiter.acquire(max_input + (4096 if endpoint == "responses" else 0), self.deadline)
                event["started_at"] = now()
            event["reservation_usd"] = str(reserve)
            if self.run_cap is None:
                self.store.reserve(event, key, reserve, self.cap)
            else:
                self.store.reserve(event, key, reserve, self.cap, run_cap=self.run_cap)
            start = time.monotonic()
            actual = result = raw = None
            retry = False
            retry_after = 0
            try:
                raw = https_json(payload, endpoint) if self.real and endpoint == "decisions" else self.transport(payload)
                event["returned_model"] = raw.get("model")
                event["provider_request_id"] = raw.get("http_request_id")
                event["response_id"] = raw.get("id")
                event["usage"] = raw.get("usage")
                event["rate_limit_headers"] = raw.get("rate_limit_headers", {})
                if self.limiter:
                    self.limiter.observe(raw, max_input + (4096 if endpoint == "responses" else 0))
                if event["usage"] is not None:
                    try:
                        actual = charge(event["usage"], self.card)
                        if endpoint == "decisions":
                            from .decisions import decision_charge
                            actual = decision_charge(event["usage"], self.card)
                        event.update({k: event["usage"][k] for k in ("input_tokens", "output_tokens")})
                    except (ValueError, KeyError, TypeError):
                        event["usage_warning"] = "Unresolved usage; reservation retained"
                if raw.get("service_tier", "default") != "default":
                    actual = None
                    raise RuntimeError("Unexpected processing tier; stop to reconcile rates")
                if raw.get("model") != MODEL:
                    raise RuntimeError("Unexpected returned model; stop rather than silently changing model")
                if raw.get("status", "completed" if endpoint == "decisions" else None) != "completed":
                    raise ValueError("Incomplete or refused provider response")
                if endpoint == "decisions":
                    from .decisions import parse_decision
                    result = parse_decision(raw, data["reviews"])
                else:
                    content = [c for item in raw.get("output", []) for c in item.get("content", []) if c.get("type") == "output_text"]
                    if len(content) != 1:
                        raise ValueError("Missing/ambiguous structured response")
                    result = loads(content[0]["text"])
                validator(result)
                event["outcome"] = "succeeded"
                event.pop("error_kind", None)
            except TransientError as e:
                event.update(error_kind="transient", error=str(e))
                event.update(provider_error_code=e.code, provider_request_id=e.request_id)
                retry_after = e.retry_after
                if self.limiter:
                    self.limiter.penalize(max(2, e.retry_after))
                retry = attempt < attempt_limit
            except AccountError as e:
                event.update(error_kind="account", error=str(e))
            except (ValueError, KeyError, TypeError) as e:
                invalid_count += 1
                event.update(error_kind="invalid_output", error=str(e)[:250])
                retry = invalid_count < 2 and attempt < attempt_limit
            except RuntimeError as e:
                event.update(error_kind="provider_error", error=str(e)[:250])
            except BaseException:
                event["duration_seconds"] = time.monotonic() - start
                self.store.finish_call(event, actual)
                raise
            event["duration_seconds"] = time.monotonic() - start
            event["ended_at"] = now()
            event["calculated_api_usd"] = str(actual) if actual is not None else None
            self.store.finish_call(event, actual, result if event["outcome"] == "succeeded" else None)
            write_json(self.directory / "handoffs" / (local_id + ".json"),
                {"request": payload, "response": raw, "attempt": event})
            if event["outcome"] == "succeeded":
                return result
            if not retry:
                raise RuntimeError(event.get("error", "Model task failed"))
            delay = max(retry_after, min(8, 2 ** (attempt - 1)) + random.uniform(0, 0.25))
            if delay > 60 or time.monotonic() + delay >= self.deadline:
                raise RuntimeError("Provider requested a long retry delay; saved work retained for later resume")
            self.sleeper(delay)
        raise RuntimeError("Task attempts exhausted")
