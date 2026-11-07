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
            "agents": 1, "ops_per_agent": 1, "ok": 1, "ops": 1, "ops_per_s": 1.0,
            "errors": {},
            "latency_ms": {
                name: {"p50": 1.0, "p95": 1.0, "p99": 1.0}
                for name in ("all", "remember", "recall", "fetch+verify")
            },
            "profile": {
                "process_cpu_seconds": 1.0,
                "process_cpu_percent_of_one_core": 50.0,
                "server_read_bytes": 10,
                "server_write_bytes": 20,
                "server_rss_peak_bytes": 100,
                "fabric_profile": {
                    "fabric_lock_wait": {"total": 2_000, "count": 2},
                    "sqlite_append_ns": {"total": 4_000_000, "count": 2},
                },
                "python_allocation_pass": {
                    "server_python_allocation_peak_bytes": 200,
                },
            },
        }
        report = to_markdown([row], "sha", "machine", "custom-result")
        encoded = report.encode("utf-8")
        self.assertIn("→".encode("utf-8"), encoded)
        self.assertIn("custom-result.json", report)
        self.assertIn("Capacity curve across trials", report)
        self.assertIn("Resource profile", report)
        self.assertIn("2.000", report)
        self.assertIn("200 |", report)


if __name__ == "__main__":
    unittest.main()
