from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import fuzz_security_boundaries as fuzz  # noqa: E402


class TestBoundedSecurityFuzz(unittest.TestCase):
    def test_mutations_are_reproducible_and_input_bounded(self) -> None:
        seed, _canary, corpus = fuzz.sources()
        first = fuzz.mutations(seed, corpus)
        second = fuzz.mutations(seed, corpus)
        self.assertEqual(first, second)
        self.assertEqual(len(first), fuzz.MAX_CASES)
        self.assertLessEqual(max(len(text.encode("utf-8")) for _, text in first),
                             fuzz.MAX_INPUT_BYTES)

    def test_checked_in_seeded_run_stays_within_limits_and_denies_dispatch(self) -> None:
        report_path = ROOT / ".test-tmp" / "security-fuzz-test.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        run = subprocess.run(
            [sys.executable, str(ROOT / "tools/fuzz_security_boundaries.py"),
             "--report", str(report_path)], cwd=ROOT, capture_output=True, text=True,
            timeout=fuzz.PARENT_TIMEOUT_SECONDS + 2, check=False)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertTrue(report["passed"])
        self.assertEqual(report["cases"], fuzz.MAX_CASES)
        self.assertLessEqual(report["elapsed_seconds"], fuzz.MAX_SECONDS)
        self.assertLessEqual(report["peak_traced_heap_bytes"], fuzz.MAX_HEAP_BYTES)
        self.assertGreater(report["action_gate_denials"], 0)
        self.assertEqual(report["tool_handler_calls"], 0)
        self.assertEqual(report["findings"], [])

    def test_counterexamples_are_saved_and_replayed_as_regression_seeds(self) -> None:
        regression_path = ROOT / ".test-tmp" / "fuzz-regressions-test.json"
        regression_path.unlink(missing_ok=True)
        source = "lookup(value='regression-seed')"
        digest = hashlib.sha256(source.encode()).hexdigest()
        with patch.object(fuzz, "REGRESSIONS", regression_path):
            fuzz.save_regressions([{"sha256": digest, "kind": "test-fixture", "source": source}])
            fuzz.save_regressions([{"sha256": digest, "kind": "test-fixture", "source": source}])
            self.assertEqual(json.loads(regression_path.read_text(encoding="utf-8"))["cases"],
                             [{"sha256": digest, "kind": "test-fixture", "source": source}])
            self.assertIn(source, fuzz.sources()[2])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
