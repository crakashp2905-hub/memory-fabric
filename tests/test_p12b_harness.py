"""The HTTP load harness runs from a clean source checkout."""

from __future__ import annotations

import os
import unittest

from experiments.p12b_api_load import ROOT, subprocess_env, to_markdown


class SourceCheckoutEnvironment(unittest.TestCase):
    def test_subprocess_can_import_the_src_layout(self) -> None:
        paths = subprocess_env()["PYTHONPATH"].split(os.pathsep)
        self.assertEqual(paths[0], str(ROOT / "src"))

    def test_report_is_utf8_encodable_on_windows(self) -> None:
        row = {
            "agents": 1, "ok": 1, "ops": 1, "ops_per_s": 1.0,
            "errors": {},
            "latency_ms": {
                name: {"p50": 1.0, "p95": 1.0, "p99": 1.0}
                for name in ("all", "remember", "recall", "fetch+verify")
            },
        }
        report = to_markdown([row], "sha", "machine", "custom-result")
        encoded = report.encode("utf-8")
        self.assertIn("→".encode("utf-8"), encoded)
        self.assertIn("custom-result.json", report)
        self.assertIn("Capacity curve across trials", report)


if __name__ == "__main__":
    unittest.main()
