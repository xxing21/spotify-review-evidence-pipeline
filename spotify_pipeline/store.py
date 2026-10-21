"""Transactional saved state. A single process lock guards each experiment."""
import json
import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from .common import canonical, digest, now, row_sha


class BudgetExceeded(RuntimeError):
    pass


class Store:
    def __init__(self, path="state/pipeline.sqlite3"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS datasets(id TEXT PRIMARY KEY, info TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sources(dataset TEXT, review_id TEXT, position INTEGER,
          row_json TEXT NOT NULL, source_sha TEXT NOT NULL, text_sha TEXT NOT NULL,
          PRIMARY KEY(dataset, review_id));
        CREATE INDEX IF NOT EXISTS source_text ON sources(dataset,text_sha);
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, dataset TEXT, info TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS records(run_id TEXT, review_id TEXT, result TEXT NOT NULL,
          PRIMARY KEY(run_id,review_id));
        CREATE TABLE IF NOT EXISTS cache(run_id TEXT, text_sha TEXT, label_config TEXT,
          source_id TEXT, text TEXT NOT NULL, result TEXT NOT NULL,
          PRIMARY KEY(run_id,text_sha,label_config));
        CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY, run_id TEXT, task_key TEXT,
          event TEXT NOT NULL, reservation TEXT NOT NULL, actual TEXT, result TEXT);
        CREATE INDEX IF NOT EXISTS call_tasks ON calls(run_id,task_key);
        CREATE TABLE IF NOT EXISTS artifacts(run_id TEXT, name TEXT, value TEXT NOT NULL,
          PRIMARY KEY(run_id,name));
        CREATE TABLE IF NOT EXISTS membership(run_id TEXT, issue_id TEXT, review_id TEXT,
          PRIMARY KEY(run_id,issue_id,review_id));
        """)

    def close(self):
        self.db.close()

    def add_dataset(self, dataset, rows, info):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO datasets VALUES (?,?)", (dataset, canonical(info)))
            self.db.executemany("INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?,?)",
                ((dataset, r["review_id"], i, canonical(r), row_sha(r), digest(r["review_text"])) for i, r in enumerate(rows)))

    def new_run(self, run_id, dataset, cfg, info):
        old = self.run(run_id)
        if old:
            if old["dataset"] != dataset or old["config"] != cfg:
                raise ValueError("Run identity/configuration changed; use a new run ID")
            return old
        info = dict(info, run_id=run_id, dataset=dataset, config=cfg, created_at=now())
        with self.db:
            self.db.execute("INSERT INTO runs VALUES (?,?,?)", (run_id, dataset, canonical(info)))
        return info

    def run(self, run_id):
        row = self.db.execute("SELECT info FROM runs WHERE id=?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def sources(self, dataset):
        return [json.loads(r[0]) for r in self.db.execute(
            "SELECT row_json FROM sources WHERE dataset=? ORDER BY position", (dataset,))]

    def records(self, run_id):
        return [json.loads(r[0]) for r in self.db.execute(
            "SELECT result FROM records WHERE run_id=? ORDER BY review_id", (run_id,))]

    def save_records(self, run_id, records, source_by_id, cfg):
        with self.db:
            for record in records:
                self.db.execute("INSERT OR REPLACE INTO records VALUES (?,?,?)",
                                (run_id, record["review_id"], canonical(record)))
                if record["status"] == "completed" and not record.get("cache_source_id"):
                    text = source_by_id[record["review_id"]]["review_text"]
                    self.db.execute("INSERT OR IGNORE INTO cache VALUES (?,?,?,?,?,?)",
                        (run_id, digest(text), cfg, record["review_id"], text, canonical(record)))

    def cached(self, run_id, text, cfg):
        row = self.db.execute("SELECT result,text FROM cache WHERE run_id=? AND text_sha=? AND label_config=?",
                              (run_id, digest(text), cfg)).fetchone()
        return json.loads(row[0]) if row and row[1] == text else None

    def put(self, run_id, name, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO artifacts VALUES (?,?,?)", (run_id, name, canonical(value)))

    def get(self, run_id, name, default=None):
        row = self.db.execute("SELECT value FROM artifacts WHERE run_id=? AND name=?", (run_id, name)).fetchone()
        return json.loads(row[0]) if row else default

    def calls(self, run_id=None):
        query = "SELECT event FROM calls" + (" WHERE run_id=?" if run_id else "") + " ORDER BY rowid"
        return [json.loads(r[0]) for r in self.db.execute(query, (run_id,) if run_id else ())]

    def committed_spend(self):
        # Unknown/in-flight charges retain their full reservation, including after restart.
        return sum((Decimal(r[0] if r[0] is not None else r[1])
                    for r in self.db.execute("SELECT actual,reservation FROM calls")), Decimal(0))

    def reserve(self, event, task_key, amount, cap, run_cap=None):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.committed_spend() + amount > Decimal(str(cap)):
                raise BudgetExceeded("Spent + unresolved reservations + next call would exceed the pilot cap")
            if run_cap is not None:
                committed = sum((Decimal(r[0] if r[0] is not None else r[1]) for r in
                    self.db.execute("SELECT actual,reservation FROM calls WHERE run_id=?", (event["run_id"],))), Decimal(0))
                if committed + amount > Decimal(str(run_cap)):
                    raise BudgetExceeded("Run spending plus reservations would exceed its separate pilot cap")
            self.db.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?)",
                (event["local_call_id"], event["run_id"], task_key, canonical(event), str(amount), None, None))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def finish_call(self, event, actual, result=None):
        with self.db:
            self.db.execute("UPDATE calls SET event=?,actual=?,result=? WHERE id=?",
                (canonical(event), str(actual) if actual is not None else None,
                 canonical(result) if result is not None else None, event["local_call_id"]))

    def saved_call(self, run_id, task_key):
        row = self.db.execute("SELECT result FROM calls WHERE run_id=? AND task_key=? AND result IS NOT NULL ORDER BY rowid DESC LIMIT 1",
                              (run_id, task_key)).fetchone()
        return json.loads(row[0]) if row else None

    def attempts(self, run_id, task_key):
        return self.db.execute("SELECT COUNT(*) FROM calls WHERE run_id=? AND task_key=?", (run_id, task_key)).fetchone()[0]


@contextmanager
def experiment_lock(directory):
    import fcntl
    Path(directory).mkdir(parents=True, exist_ok=True)
    with (Path(directory) / ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another process is operating on this experiment") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
