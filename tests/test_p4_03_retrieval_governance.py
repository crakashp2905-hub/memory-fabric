from __future__ import annotations

import unittest

from experiments.p4_03_retrieval_governance import build_report


class RetrievalGovernanceComparison(unittest.TestCase):
    def test_matched_synthetic_runs_are_deterministic_and_report_joint_outcomes(self) -> None:
        first = build_report()
        second = build_report()
        self.assertEqual(first, second)
        self.assertTrue(first["passed"])
        self.assertTrue(first["matched_inputs_per_case"])
        self.assertEqual(first["scenario_count"], 20)
        ordinary = first["arms"]["ordinary_retrieval"]
        governed = first["arms"]["governed_memory"]
        self.assertEqual(ordinary["task_completed"], ordinary["task_denominator"])
        self.assertEqual(governed["task_completed"], governed["task_denominator"])
        self.assertEqual(ordinary["stale_actions_would_execute"], 20)
        self.assertEqual(governed["stale_actions_executed"], 0)
        self.assertIn("counterfactual WOULD EXECUTE", first["limitations"][1])


if __name__ == "__main__":
    unittest.main()
