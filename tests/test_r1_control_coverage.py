"""The R1-05 cross-suite regression map must track the runnable registry."""
from __future__ import annotations

import unittest

from tools.r1_control_coverage import COVERAGE, build_report


class ControlCoverageRegistry(unittest.TestCase):
    def test_every_registered_run_suite_has_one_passing_known_failure(self) -> None:
        report = build_report(write=False)
        self.assertEqual(report["registry_run_suite_count"], 11)
        self.assertEqual(report["coverage_count"], report["registry_run_suite_count"])
        self.assertTrue(report["all_registered_run_suites_covered"])
        self.assertTrue(all(row["passed"] for row in report["rows"]))
        self.assertEqual({row["suite_id"] for row in report["rows"]}, set(COVERAGE))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
