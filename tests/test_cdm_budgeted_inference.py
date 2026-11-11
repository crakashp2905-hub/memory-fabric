"""Matched-budget quality measurement refuses exact work that exceeds budget."""

from __future__ import annotations

import unittest

from benchmarks.cdm_budgeted_inference import run


class TestBudgetedInference(unittest.TestCase):
    def test_exact_refuses_when_over_budget_and_approximation_reports_error(self):
        report = run((17, 29), (32, 256))
        self.assertEqual(report["joint_state_count"], 256)
        small, fitting = report["summary"]
        self.assertEqual(small["exact_status"], "BUDGET_EXCEEDED")
        self.assertIsNone(small["exact_mean_abs_error"])
        self.assertEqual(fitting["exact_status"], "EXACT")
        self.assertEqual(fitting["exact_mean_abs_error"], 0.0)
        for row in report["rows"]:
            self.assertLessEqual(row["approximate_assignment_evaluations"],
                                 row["budget_assignments"])
            self.assertGreaterEqual(row["approximate_effective_sample_size"], 0.0)
            self.assertLessEqual(row["approximate_abs_error"], 1.0)


if __name__ == "__main__":
    unittest.main()
