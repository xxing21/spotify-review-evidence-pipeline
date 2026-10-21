"""Offline system tests. Fake provider responses are never measured pilot evidence."""
import copy
import csv
import io
import json
import math
import tempfile
import time
import unittest
import urllib.error
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from check_submission import audit, canonical, profile, reference, row_sha
from spotify_pipeline.calculator import calculate
from spotify_pipeline.common import (FIELDS, LABEL_SCHEMA, config, ground_labels, label_config,
    source_records, validate_labels, write_csv, write_json)
from spotify_pipeline.pipeline import (downstream, enrich, export, initialize,
    rank_records, rerank, rerank_exports, snapshot, validate_memo)
from spotify_pipeline.provider import AccountError, ModelClient, TransientError, billing_units, charge, https_response, rates
from spotify_pipeline.store import BudgetExceeded, Store
from spotify_pipeline.checkpoint import inherit_previous


def source(rid="a", text="I cannot log in at all."):
    return dict(zip(FIELDS, [rid, text, "1", "0", "", "2023-01-01 00:00:00"]))


def prediction(rid="a", text="I cannot log in at all."):
    return {"review_id": rid, "topic": "access", "intent": "complaint", "sentiment": -0.8,
            "severity": 4, "entities": [], "evidence_quote": text, "needs_review": False}


class FakeProvider:
    def __init__(self, failure=None):
        self.payloads = []
        self.failure = failure

    def __call__(self, payload):
        self.payloads.append(copy.deepcopy(payload))
        if len(self.payloads) == 1 and self.failure == "transient":
            raise TransientError("simulated HTTP 429")
        data = json.loads(payload["input"][1]["content"])
        role = payload["text"]["format"]["name"].split("_")[-1]
        if role in {"enrich", "verify"}:
            result = {"records": [prediction(r["review_id"], r["review_text"]) for r in data["reviews"]]}
        elif role == "group":
            result = {"issues": [{"issue_id": r["issue_id"], "name": "Access failure", "description": "Users report blocked access."} for r in data["issues"]]}
        else:
            result = {"priority_issue_id": data["ranking"][0]["issue_id"] if data["ranking"] else "",
                "rationale": "Prioritize restoring access based on the saved evidence.",
                "alternative_issue_ids": [], "claim_ids": [r["claim_id"] for r in data["claims"]],
                "review_ids": [r["review_id"] for r in data["evidence"]],
                "limitations": "Historical self-selected reviews and pilot scope limit generalization."}
        if self.failure == "invalid" and len(self.payloads) == 1:
            result = {"records": []}
        if self.failure == "always_invalid":
            result = {"records": []}
        return {"id": "fake-not-a-provider-request", "model": "gpt-6-luna", "status": "completed", "service_tier": "default",
            "usage": {"input_tokens": 100, "output_tokens": 60, "input_tokens_details": {"cached_tokens": 20}},
            "output": [{"content": [{"type": "output_text", "text": json.dumps(result)}]}]}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "state.sqlite3")
        self.csv = self.root / "input.csv"

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def setup_run(self, rows):
        write_csv(self.csv, rows, list(FIELDS))
        initialize(self.store, "test", self.csv)

    def client(self, fake, cap=2):
        return ModelClient(self.store, "test", config(), cap, self.root, transport=fake, sleeper=lambda _: None)

    def test_hash_and_multiline_preservation(self):
        r = source(text='café\n"你好"\r\n')
        self.setup_run([r])
        self.assertEqual(source_records(self.csv), [r])
        import hashlib
        self.assertEqual(row_sha(r), hashlib.sha256(canonical([r[k] for k in FIELDS]).encode()).hexdigest())
        self.assertNotEqual(row_sha(r), row_sha(dict(r, review_text=r["review_text"].strip())))

    def test_schema_quotes_entities_and_ids(self):
        r = source()
        good = prediction()
        validate_labels({"records": [good]}, [r])
        for key, value in [("review_id", "foreign"), ("evidence_quote", "invented"), ("entities", ["invented"]),
                           ("severity", True), ("sentiment", float("nan")), ("topic", "made-up")]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_labels({"records": [dict(good, **{key: value})]}, [r])
        for p in ({"records": []}, {"records": [good, good]}, {"records": "bad"}):
            with self.assertRaises(ValueError):
                validate_labels(p, [r])

    def test_code_grounding_preserves_literal_source_and_rejects_foreign_ids(self):
        text = 'spotify Premium\nOffline 音楽 lyrics'
        r = source(text=text)
        model_output = {"records": [dict(prediction(text=text), evidence_quote="", entities=[])]}
        result = ground_labels(model_output, [r])["records"][0]
        self.assertEqual(result["evidence_quote"], text)
        self.assertEqual(result["entities"], ["spotify", "Premium", "Offline", "lyrics"])
        with self.assertRaises(ValueError):
            ground_labels({"records": [dict(prediction(), review_id="foreign")]}, [r])

    def test_global_ledger_applies_across_experiments(self):
        self.setup_run([source()])
        first = FakeProvider()
        enrich(self.store, "test", self.client(first))
        initialize(self.store, "second", self.csv)
        second = FakeProvider()
        client = ModelClient(self.store, "second", config(), self.store.committed_spend(), self.root,
                             transport=second, sleeper=lambda _: None)
        with self.assertRaises(BudgetExceeded):
            enrich(self.store, "second", client)
        self.assertEqual(second.payloads, [])

    def test_empty_text_quarantine_and_direct_exact_reuse(self):
        self.setup_run([source("a"), source("b"), source("c", "\n "), source("d", "I cannot log in at all. ")])
        fake = FakeProvider()
        enrich(self.store, "test", self.client(fake))
        records = {r["review_id"]: r for r in self.store.records("test")}
        self.assertEqual(records["b"]["cache_source_id"], "a")
        self.assertNotIn("cache_source_id", records["a"])
        self.assertNotIn("cache_source_id", records["d"])
        self.assertEqual(records["c"]["reason"], "empty_review_text")
        sent = json.loads(fake.payloads[0]["input"][1]["content"])["reviews"]
        self.assertEqual({r["review_id"] for r in sent}, {"a", "d"})
        self.assertTrue(all(set(r) == {"review_id", "review_text"} for r in sent))

    def test_retry_then_success_and_unknown_charge_reservation(self):
        self.setup_run([source()])
        fake = FakeProvider("transient")
        enrich(self.store, "test", self.client(fake))
        calls = self.store.calls("test")
        self.assertEqual([r["outcome"] for r in calls], ["failed", "succeeded"])
        self.assertIsNone(calls[0]["input_tokens"])
        self.assertGreater(self.store.committed_spend(), Decimal(calls[1]["calculated_api_usd"]))

    def test_one_invalid_retry_then_quarantine(self):
        self.setup_run([source()])
        fake = FakeProvider("always_invalid")
        enrich(self.store, "test", self.client(fake))
        self.assertEqual(len(fake.payloads), 2)
        self.assertEqual(self.store.records("test")[0]["status"], "quarantined")
        self.assertEqual(self.store.records("test")[0]["attempt_count"], 2)

    def test_budget_exhaustion_no_dispatch(self):
        self.setup_run([source()])
        fake = FakeProvider()
        with self.assertRaises(BudgetExceeded):
            enrich(self.store, "test", self.client(fake, cap=0.000001))
        self.assertEqual(fake.payloads, [])
        self.assertEqual(self.store.records("test"), [])
        unsupported = config()
        unsupported["model"] = "not-allowlisted"
        with self.assertRaises(ValueError):
            ModelClient(self.store, "test", unsupported, 2, self.root, transport=fake)

    def test_time_cap_no_dispatch(self):
        self.setup_run([source()])
        fake = FakeProvider()
        client = self.client(fake)
        client.deadline = time.monotonic() - 1
        with self.assertRaises(TimeoutError):
            enrich(self.store, "test", client)
        self.assertEqual(fake.payloads, [])

    def test_id_enum_and_final_recovery_attempt_are_bounded(self):
        self.setup_run([source()])
        cfg = config() | {"schema_version": "spotify-label-v3-id-enum", "routing_schema": "review-id-enum-v1"}
        initialize(self.store, "repair", self.csv, cfg)
        self.store.put("repair", "prior_enrichment_attempt_counts", {"a": 2})
        fake = FakeProvider("always_invalid")
        client = ModelClient(self.store, "repair", cfg, 2, self.root, transport=fake)
        enrich(self.store, "repair", client)
        self.assertEqual(len(fake.payloads), 1)
        actual = fake.payloads[0]["text"]["format"]["schema"]
        self.assertEqual(actual["properties"]["records"]["items"]["properties"]["review_id"]["enum"], ["a"])
        self.assertNotIn("enum", LABEL_SCHEMA["properties"]["records"]["items"]["properties"]["review_id"])
        self.assertEqual(self.store.calls("repair")[0]["attempt"], 3)
        self.assertEqual(self.store.records("repair")[0]["attempt_count"], 3)
        self.assertNotEqual(label_config(cfg), label_config(config()))
        with self.assertRaises(ValueError):
            client.call("enrich", {"reviews": [{"review_id": "a", "review_text": source()["review_text"]}]},
                LABEL_SCHEMA, lambda x: ground_labels(x, [source()]), "initial", label_config(cfg), ["a"])
        self.assertEqual(len(fake.payloads), 1)

    def test_resume_then_warm_and_checker(self):
        rows = [source(str(i), "Blocked login " + str(i)) for i in range(30)]
        self.setup_run(rows)
        fake = FakeProvider()
        enrich(self.store, "test", self.client(fake), stop_after=20)
        before = snapshot(self.store, "test", "checkpoint_before")
        self.assertEqual(len(before["completed_ids"]), 20)
        self.store.close()
        self.store = Store(self.root / "state.sqlite3")
        client = self.client(fake)
        enrich(self.store, "test", client, "resume")
        snapshot(self.store, "test", "checkpoint_after")
        downstream(self.store, "test", client, self.root / "run")
        initial_calls = len(fake.payloads)
        ranking_before = (self.root / "run/ranking.csv").read_bytes()
        enrich(self.store, "test", self.client(fake), "resume")
        downstream(self.store, "test", self.client(fake), self.root / "run")
        rerank(self.store, "test", self.root / "run")
        rerank_exports(self.root / "run")
        self.assertEqual(len(fake.payloads), initial_calls)
        self.assertEqual((self.root / "run/ranking.csv").read_bytes(), ranking_before)
        for call in self.store.calls("test"):
            if call["role"] == "enrich" and call["phase"] == "resume":
                self.assertFalse(set(call["review_ids"]) & set(before["completed_ids"]))
        # Mechanical checker test is explicitly synthetic and isolated in a temp directory.
        write_json(self.root / "run/grading/ingestion.json", profile(self.csv))
        result = audit(self.root / "run/grading", reference(self.csv, self.csv))
        self.assertEqual(result["status"], "pass", result["issue_counts"])
        verify_payload = next(p for p in fake.payloads if p["text"]["format"]["name"] == "spotify_verify")
        self.assertNotIn('"severity"', verify_payload["input"][1]["content"])

    def test_saved_valid_response_recovers_before_record_commit(self):
        self.setup_run([source()])
        fake = FakeProvider()
        client = self.client(fake)
        data = {"reviews": [{"review_id": "a", "review_text": source()["review_text"]}]}
        client.call("enrich", data, LABEL_SCHEMA, lambda x: validate_labels(x, [source()]), "initial", label_config(config()), ["a"])
        enrich(self.store, "test", self.client(fake), "resume")
        self.assertEqual(len(fake.payloads), 1)
        self.assertEqual(self.store.records("test")[0]["status"], "completed")

    def test_ranking_ties_and_rounding(self):
        records = [dict(prediction("a"), status="completed"), dict(prediction("b"), topic="billing", status="completed")]
        membership, ranking, claims = rank_records(records)
        self.assertEqual([r["issue_id"] for r in ranking], ["ISSUE-ACCESS", "ISSUE-BILLING"])
        self.assertEqual(ranking[0]["mean_severity"], "4.000000")
        self.assertEqual(ranking[0]["priority_score"], ranking[0]["severity_sum"])

    def test_pilot_size_and_changed_config_guard(self):
        self.setup_run([source()])
        changed = config()
        changed["effort"] = "low"
        with self.assertRaises(ValueError):
            initialize(self.store, "test", self.csv, changed)
        write_csv(self.csv, [source(str(i)) for i in range(101)], list(FIELDS))
        with self.assertRaises(ValueError):
            initialize(self.store, "large", self.csv)

    def test_memo_unknown_claim_rejected(self):
        _, ranking, claims = rank_records([dict(prediction(), status="completed")])
        memo = {"priority_issue_id": "ISSUE-ACCESS", "rationale": "Restore access.", "alternative_issue_ids": [],
                "claim_ids": ["invented"], "review_ids": ["a"], "limitations": "Historical reviews."}
        with self.assertRaises(ValueError):
            validate_memo(memo, ranking, claims, [{"review_id": "a"}])

    def test_quota_error_is_not_transient(self):
        error = urllib.error.HTTPError("https://api.openai.com/v1/responses", 429, "error", {},
            io.BytesIO(b'{"error":{"code":"insufficient_quota","message":"private message not logged"}}'))
        with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic-test-value"}), patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(AccountError) as raised:
                https_response({})
        self.assertIn("insufficient_quota", str(raised.exception))
        self.assertNotIn("private", str(raised.exception))

    def test_retry_after_header_is_respected(self):
        error = urllib.error.HTTPError("https://api.openai.com/v1/responses", 429, "error", {"Retry-After": "12"},
            io.BytesIO(b'{"error":{"code":"rate_limit_exceeded"}}'))
        with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic-test-value"}), patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(TransientError) as raised:
                https_response({})
        self.assertEqual(raised.exception.retry_after, 12)

    def test_repair_window_retains_successful_task_cache(self):
        self.setup_run([source()])
        fake = FakeProvider()
        data = {"reviews": [{"review_id": "a", "review_text": source()["review_text"]}]}
        validator = lambda x: validate_labels(x, [source()])
        self.client(fake).call("enrich", data, LABEL_SCHEMA, validator, review_ids=["a"])
        self.store.put("test", "attempt_window", 1)
        self.client(fake).call("enrich", data, LABEL_SCHEMA, validator, review_ids=["a"])
        self.assertEqual(len(fake.payloads), 1)

    def test_task_attempt_limit_survives_restart(self):
        self.setup_run([source()])
        fake = FakeProvider("always_invalid")
        data = {"reviews": [{"review_id": "a", "review_text": source()["review_text"]}]}
        validator = lambda x: validate_labels(x, [source()])
        with self.assertRaises(RuntimeError):
            self.client(fake).call("enrich", data, LABEL_SCHEMA, validator, review_ids=["a"])
        with self.assertRaises(ValueError):
            self.client(fake).call("enrich", data, LABEL_SCHEMA, validator, review_ids=["a"])
        self.assertEqual(len(fake.payloads), 2)

    def test_golden_cannot_enter_development_run(self):
        first = source_records("golden_50_to_label.csv")[0]
        write_csv(self.csv, [first], list(FIELDS))
        with self.assertRaisesRegex(ValueError, "held out"):
            initialize(self.store, "test", self.csv)

    def test_500_extension_reuses_originals_and_historical_evidence(self):
        rows=[source(str(i),"Blocked login " + str(i)) for i in range(500)]
        for i in range(100,121):
            rows[i]["review_text"]=rows[i-100]["review_text"]
        self.setup_run(rows[:100])
        fake=FakeProvider()
        enrich(self.store,"test",self.client(fake),stop_after=20)
        snapshot(self.store,"test","checkpoint_before")
        enrich(self.store,"test",self.client(fake),"resume")
        snapshot(self.store,"test","checkpoint_after")
        original_calls=len(fake.payloads)
        original_spend=self.store.committed_spend()
        write_csv(self.csv,rows,list(FIELDS))
        initialize(self.store,"checkpoint",self.csv,kind="checkpoint_500",max_records=500)
        directory=self.root/"checkpoint"
        inherit_previous(self.store,"checkpoint","test",directory)
        self.assertEqual(len(self.store.records("checkpoint")),100)
        self.assertEqual(self.store.committed_spend(),original_spend)
        self.assertEqual(self.store.calls("checkpoint"),[])
        inherit_previous(self.store,"checkpoint","test",directory) # Idempotent restart.
        client=ModelClient(self.store,"checkpoint",config(),2,directory,transport=fake,sleeper=lambda _:None)
        enrich(self.store,"checkpoint",client,"resume")
        snapshot(self.store,"checkpoint","checkpoint_after")
        downstream(self.store,"checkpoint",client,directory)
        new_enrich=[c for c in self.store.calls("checkpoint") if c["role"]=="enrich"]
        sent={rid for c in new_enrich for rid in c["review_ids"]}
        self.assertEqual(len(sent),379)
        self.assertFalse(sent.intersection(str(i) for i in range(100)))
        records=self.store.records("checkpoint")
        self.assertEqual(len(records),500)
        self.assertEqual(sum(bool(r.get("cache_source_id")) for r in records),21)
        self.assertEqual(sum(bool(r.get("reused_from_run")) for r in records),100)
        self.assertEqual(len(self.store.calls("test")),original_calls)
        write_json(directory/"grading/ingestion.json",profile(self.csv))
        checked=audit(directory/"grading",reference(self.csv,self.csv))
        self.assertEqual(checked["status"],"pass",checked["issue_counts"])
        requests=len(fake.payloads)
        enrich(self.store,"checkpoint",client,"resume")
        downstream(self.store,"checkpoint",client,directory)
        self.assertEqual(len(fake.payloads),requests)

    def test_nested_checkpoint_keeps_all_historical_calls_without_rebilling(self):
        rows = [source(str(i), "Blocked login " + str(i)) for i in range(60)]
        self.setup_run(rows[:20])
        fake = FakeProvider()
        enrich(self.store, "test", self.client(fake))
        snapshot(self.store, "test", "checkpoint_before")
        write_csv(self.csv, rows[:40], list(FIELDS))
        initialize(self.store, "middle", self.csv, kind="checkpoint_500", max_records=500)
        inherit_previous(self.store, "middle", "test", self.root / "middle")
        client = ModelClient(self.store, "middle", config(), 2, self.root, transport=fake)
        enrich(self.store, "middle", client, "resume")
        spend = self.store.committed_spend()
        write_csv(self.csv, rows, list(FIELDS))
        initialize(self.store, "large", self.csv, kind="checkpoint_10000", max_records=10000)
        inherit_previous(self.store, "large", "middle", self.root / "large")
        history = self.store.get("large", "inherited_call_evidence")
        self.assertEqual(len(history), 4)
        self.assertEqual(len({c["local_call_id"] for c in history}), 4)
        self.assertEqual(self.store.committed_spend(), spend)
        self.assertEqual(len(self.store.records("large")), 40)
        self.assertEqual(self.store.calls("large"), [])
        client = ModelClient(self.store, "large", config(), 2, self.root, transport=fake)
        enrich(self.store, "large", client, "resume")
        sent = {rid for c in self.store.calls("large") for rid in c["review_ids"]}
        self.assertEqual(sent, {str(i) for i in range(40, 60)})
        write_csv(self.csv, [source(str(i)) for i in range(10001)], list(FIELDS))
        with self.assertRaises(ValueError):
            initialize(self.store, "too-large", self.csv, max_records=10000)

    def test_checkpoint_ceiling_and_changed_inheritance_config(self):
        self.setup_run([source()])
        changed=config(); changed["schema_version"]="changed"
        initialize(self.store,"different",self.csv,changed)
        with self.assertRaises(ValueError):
            inherit_previous(self.store,"different","test",self.root)
        write_csv(self.csv,[source(str(i)) for i in range(501)],list(FIELDS))
        with self.assertRaises(ValueError):
            initialize(self.store,"too-large",self.csv,max_records=500)

    def test_superseded_checkpoint_cannot_rebill_legacy_work(self):
        from spotify_pipeline.checkpoint import checkpoint
        self.store.new_run("pilot-10000-v3", "synthetic", config(), {"kind": "test-only"})
        with self.assertRaisesRegex(ValueError, "supersedes"):
            checkpoint(self.root / "state.sqlite3", "analysis_10000.csv", max_active_minutes=180)
        self.assertEqual(self.store.calls(), [])


class CalculatorTests(unittest.TestCase):
    def fixture(self):
        calls = [{"local_call_id": role, "role": role, "outcome": "succeeded", "synthetic": False,
            "duration_seconds": 1, "usage": {"input_tokens": 1000, "output_tokens": 100,
            "input_tokens_details": {"cached_tokens": 200}}} for role in ("enrich", "verify", "group", "memo")]
        summary = {"status": "completed", "input_count": 100, "completed": 100, "unique_nonempty_texts": 100,
                   "verification_sample_count": 20, "cold_seconds": 6, "warm_seconds": 0.1}
        return calls, summary

    def test_rates_double_volume_independence(self):
        calls, summary = self.fixture()
        card = rates()
        normal, _ = calculate(calls, summary, card)
        double, _ = calculate(calls, summary, {k: v*2 for k,v in card.items()})
        self.assertEqual(Decimal(double["measured"]["known_api_usd"]), Decimal(normal["measured"]["known_api_usd"])*2)
        self.assertEqual(normal["measured"]["cold_seconds"], double["measured"]["cold_seconds"])
        self.assertEqual(normal["measured"]["local_compute_usd"], double["measured"]["local_compute_usd"])
        reduced, _ = calculate(calls, summary, card, volume=1000)
        self.assertEqual(normal["measured"], reduced["measured"])
        self.assertEqual(normal["projections"][0]["stage_work"]["memo"], 1)
        self.assertEqual(normal["projections"][0]["stage_work"]["enrich"], 484189)

    def test_input_not_double_counted_reasoning_not_added(self):
        usage = {"input_tokens": 100, "output_tokens": 20, "input_tokens_details": {"cached_tokens": 40},
                 "output_tokens_details": {"reasoning_tokens": 10}}
        units = billing_units(usage)
        self.assertEqual(units, {"input": 60, "cached_input": 40, "cache_write": 0, "output": 20})
        with self.assertRaises(ValueError):
            billing_units({"input_tokens": 5, "output_tokens": 1, "input_tokens_details": {"cached_tokens": 6}})

    def test_unknown_usage_not_free_and_synthetic_excluded(self):
        calls, summary = self.fixture()
        calls[0]["usage"] = None
        result, _ = calculate(calls, summary, rates())
        self.assertFalse(result["measured"]["usage_complete"])
        self.assertEqual(len(result["measured"]["unresolved_calls"]), 1)
        calls[0]["synthetic"] = True
        with self.assertRaises(ValueError):
            calculate(calls, summary, rates())

    def test_incremental_projection_uses_new_work_and_source_row_verification(self):
        calls,summary=self.fixture()
        summary.update(input_count=500,completed=500,unique_nonempty_texts=479,enrichment_work_count=379,
            verification_sample_count=100,verification_sampling_unit="source_rows",
            measurement_kind="incremental_checkpoint",cold_seconds=None,incremental_seconds=6,
            inherited_completed_records=100,new_completed_records=400)
        result,_=calculate(calls,summary,rates())
        base=result["projections"][0]
        expected=(Decimal(result["stages"]["enrich"]["known_api_usd"])*Decimal(484189)/Decimal(379)
            +Decimal(result["stages"]["verify"]["known_api_usd"])*Decimal(132122)/Decimal(100)
            +Decimal(result["stages"]["group"]["known_api_usd"])+Decimal(result["stages"]["memo"]["known_api_usd"]))
        self.assertEqual(Decimal(base["estimated_api_usd"]),expected)
        self.assertEqual(base["stage_work"]["verify"],132122)
        self.assertIsNone(result["measured"]["cold_seconds"])
        self.assertEqual(result["measured"]["incremental_seconds"],6)


if __name__ == "__main__":
    unittest.main()
