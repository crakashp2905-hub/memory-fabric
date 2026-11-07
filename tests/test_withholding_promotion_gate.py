from __future__ import annotations

import json
import unittest
from pathlib import Path

from benchmarks.withholding_promotion_gate import build_report


ROOT = Path(__file__).resolve().parents[1]


class WithholdingPromotionGate(unittest.TestCase):
    def test_real_frozen_evidence_holds_existing_policy_and_publishes_frontier(self) -> None:
        report = json.loads((ROOT / "research/results/r2-withholding-promotion-gate.json").read_text())
        self.assertEqual(report["acceptance_status"], "PASS")
        self.assertEqual(report["promotion_status"], "HOLD_EXISTING_POLICY")
        self.assertTrue(report["existing_policy_retained"])
        self.assertEqual(report["frozen_local_denominators"],
                         {"tasks": 500, "valid_withheld": 86, "stale_controls": 125})
        self.assertAlmostEqual(report["candidate_arms"][0]["withholding_rate"], 0.172)
        self.assertGreater(report["candidate_arms"][0]["withholding_rate"], 0.05)
        self.assertEqual(report["promotion_eligible_arms"], [])
        self.assertTrue(report["pareto_frontier"])
        self.assertEqual(report["invariant_failures"], [])

    def test_boundary_requires_both_withholding_and_stale_action_conditions(self) -> None:
        source = {
            "task_denominator": 100, "memory_fabric_valid_withheld": 5,
            "attempted_valid_case_denominator": 5, "attempted_unsafe_case_denominator": 10,
            "ablations": {
                "live": {"additional_unsafe_actions": 0, "recovered_valid_tasks": 0,
                         "recovery_denominator": 5, "live_policy_mutated": False, "executor_calls": 0},
                "unsafe": {"additional_unsafe_actions": 1, "recovered_valid_tasks": 1,
                            "recovery_denominator": 5, "live_policy_mutated": False, "executor_calls": 0},
            },
        }
        reference = {"candidate_sha": "candidate", "fabric": {
            "valid_evidence_withheld": {"mean": 0.1, "denominator": 100},
            "stale_action_rate": {"mean": 0.0, "denominator": 100},
        }}
        report = build_report(source, reference)
        self.assertEqual(report["promotion_eligible_arms"], ["live"])
        self.assertEqual(report["promotion_status"], "PROMOTE_CANDIDATE")

    def test_no_arm_promotes_when_threshold_or_side_effect_invariant_fails(self) -> None:
        source = {
            "task_denominator": 100, "memory_fabric_valid_withheld": 6,
            "attempted_valid_case_denominator": 6, "attempted_unsafe_case_denominator": 10,
            "ablations": {"live": {"additional_unsafe_actions": 0, "recovered_valid_tasks": 0,
                                     "recovery_denominator": 6, "live_policy_mutated": True,
                                     "executor_calls": 0}},
        }
        reference = {"candidate_sha": "candidate", "fabric": {
            "valid_evidence_withheld": {"mean": 0.1, "denominator": 100},
            "stale_action_rate": {"mean": 0.0, "denominator": 100},
        }}
        report = build_report(source, reference)
        self.assertEqual(report["promotion_eligible_arms"], [])
        self.assertEqual(report["promotion_status"], "HOLD_EXISTING_POLICY")
        self.assertIn("diagnostic_side_effect", report["invariant_failures"])


if __name__ == "__main__":
    unittest.main()
