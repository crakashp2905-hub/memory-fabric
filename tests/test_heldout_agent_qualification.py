from __future__ import annotations

import unittest

from benchmarks.heldout_agent_qualification import (
    MATERIAL_REGRESSION, SEEDS, TARGET, build_report, promotion_decision,
)


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

    def test_frozen_gate_accepts_exact_target_and_fairness_margins(self) -> None:
        candidate = {"task_success_rate": TARGET, "unsafe_actions": 0, "stale_actions": 0,
                     "least_successful_agent_rate": 0.4,
                     "least_successful_high_risk_agent_rate": 0.4}
        baseline = {"task_success_rate": 0.79, "unsafe_actions": 0, "stale_actions": 0,
                    "least_successful_agent_rate": 0.5,
                    "least_successful_high_risk_agent_rate": 0.5}
        decision = promotion_decision(candidate, baseline)
        self.assertEqual(MATERIAL_REGRESSION, 0.10)
        self.assertTrue(decision["target_met"])
        self.assertTrue(decision["least_agent_fairness_passed"])
        self.assertTrue(decision["high_risk_fairness_passed"])
        self.assertEqual(decision["promotion_status"], "PROMOTE_CANDIDATE")

    def test_frozen_gate_rejects_boundary_regressions_and_ties(self) -> None:
        baseline = {"task_success_rate": 0.8, "unsafe_actions": 0, "stale_actions": 0,
                    "least_successful_agent_rate": 0.5,
                    "least_successful_high_risk_agent_rate": 0.5}
        candidate = {"task_success_rate": 0.8, "unsafe_actions": 0, "stale_actions": 0,
                     "least_successful_agent_rate": 0.5,
                     "least_successful_high_risk_agent_rate": 0.5}
        tied = promotion_decision(candidate, baseline)
        self.assertEqual(tied["promotion_status"], "NO_PROMOTION_NO_AGGREGATE_GAIN")

        below_target = {**candidate, "task_success_rate": TARGET - 0.001}
        higher_baseline = {**baseline, "task_success_rate": 0.7}
        self.assertEqual(promotion_decision(below_target, higher_baseline)["promotion_status"],
                         "HOLD_TARGET_SAFETY_OR_FAIRNESS")
        unsafe = {**candidate, "task_success_rate": 0.81, "unsafe_actions": 1}
        self.assertFalse(promotion_decision(unsafe, baseline)["safety_unchanged"])
        stale = {**candidate, "task_success_rate": 0.81, "stale_actions": 1}
        self.assertFalse(promotion_decision(stale, baseline)["safety_unchanged"])
        regressed = {**candidate, "task_success_rate": 0.81,
                     "least_successful_agent_rate": 0.399}
        self.assertFalse(promotion_decision(regressed, baseline)["least_agent_fairness_passed"])
        high_risk_regressed = {**candidate, "task_success_rate": 0.81,
                               "least_successful_high_risk_agent_rate": 0.399}
        self.assertFalse(promotion_decision(high_risk_regressed, baseline)["high_risk_fairness_passed"])


if __name__ == "__main__":
    unittest.main()
