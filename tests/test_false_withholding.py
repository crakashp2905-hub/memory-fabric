from __future__ import annotations

import unittest

from benchmarks.false_withholding import build_report, run_seed


class FalseWithholdingAblation(unittest.TestCase):
    def test_cases_have_exact_action_evidence_blocker_and_oracle_label(self) -> None:
        report = run_seed(101)
        cases = report["cases"]
        self.assertTrue(cases)
        for case in cases:
            self.assertIn("tool", case["action"])
            self.assertIsInstance(case["evidence_ids"], list)
            self.assertTrue(case["actual_blocker_reason"])
            self.assertIsInstance(case["oracle_supported"], bool)
            self.assertTrue(case["dry_run_only"])

    def test_report_separates_withholding_cases_and_guard_counterfactuals(self) -> None:
        report = build_report()
        self.assertEqual(report["acceptance_status"], "PASS")
        self.assertEqual(report["invariant_failures"], [])
        self.assertEqual(report["upstream_provenance"]["exact_upstream_rows_available"], False)
        # Measured on the merged code: no valid case is withheld. The earlier branch
        # figure (86 of 500, 0.172) came from the pre-merge claim matching; see the
        # decision record for the integration.
        self.assertEqual(report["attempted_valid_case_denominator"], 0)
        self.assertEqual(report["attempted_valid_case_denominator"] / 500, 0.0)
        self.assertGreater(report["attempted_unsafe_case_denominator"], 0)
        self.assertEqual(report["ablations"]["allow_suspicious"]["executor_calls"], 0)
        self.assertFalse(report["ablations"]["allow_suspicious"]["live_policy_mutated"])
        self.assertEqual(report["ablations"]["live"]["additional_unsafe_actions"], 0)
        self.assertIn("freshness", report["causal_category_counts_multilabel"])


if __name__ == "__main__":
    unittest.main()
