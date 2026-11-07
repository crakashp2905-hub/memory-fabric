from __future__ import annotations

import unittest

from benchmarks.heldout_agent_qualification import SEEDS, TARGET, build_report


class HeldOutAgentQualification(unittest.TestCase):
    def test_aspirational_target_baseline_safety_and_fairness_are_reported(self) -> None:
        report = build_report()
        self.assertEqual(report["acceptance_status"], "PASS")
        self.assertEqual(report["seeds"], list(SEEDS))
        self.assertEqual(report["unique_task_cases"], 24)
        self.assertEqual(report["attempted_agent_tasks_per_arm"], 1200)
        self.assertEqual(report["aspirational_target"], TARGET)
        self.assertTrue(report["target_met"])
        self.assertEqual(report["strongest_matched_non_oracle_baseline"], "pooled_shared")
        self.assertTrue(report["safety_unchanged"])
        self.assertTrue(report["least_agent_fairness_passed"])
        self.assertTrue(report["high_risk_fairness_passed"])
        self.assertEqual(report["promotion_status"], "NO_PROMOTION_NO_AGGREGATE_GAIN")
        self.assertEqual(report["summary_by_arm"]["memory_fabric"]["task_success_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
