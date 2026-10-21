"""Save genuine offline test outcomes; all provider responses here are synthetic."""
import contextlib
import io
import json
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spotify_pipeline.common import atomic_text, now, write_json


class EvidenceResult(unittest.TextTestResult):
    def startTest(self, test):
        self.started = time.monotonic()
        super().startTest(test)

    def addSuccess(self, test):
        outcomes.append({"test": test.id(), "outcome": "passed", "seconds": time.monotonic()-self.started})
        super().addSuccess(test)

    def addFailure(self, test, err):
        outcomes.append({"test": test.id(), "outcome": "failed"})
        super().addFailure(test, err)

    def addError(self, test, err):
        outcomes.append({"test": test.id(), "outcome": "error"})
        super().addError(test, err)


if __name__ == "__main__":
    outcomes = []
    output = io.StringIO()
    start = time.monotonic()
    with contextlib.redirect_stdout(output):
        result = unittest.TextTestRunner(stream=output, verbosity=2, resultclass=EvidenceResult).run(
            unittest.defaultTestLoader.discover("tests"))
    atomic_text("evals/system_checks.txt", output.getvalue())
    write_json("evals/system_checks.json", {"generated_at": now(), "synthetic_provider_tests": True,
        "real_model_execution": False, "tests_run": result.testsRun, "passed": result.wasSuccessful(),
        "duration_seconds": time.monotonic()-start, "cases": outcomes})
    print(output.getvalue())
    raise SystemExit(0 if result.wasSuccessful() else 1)
