"""Certificate confusion matrix includes a genuine trace and failure fixtures."""

from __future__ import annotations

import unittest

from benchmarks.cdm_report import run


class TestCDMReport(unittest.TestCase):
    def test_attack_and_truncation_matrix_is_complete(self):
        result = run()
        self.assertEqual(result["confusion_matrix"], {
            "true_accept": 1, "true_reject": 6,
            "false_accept": 0, "false_reject": 0, "attack_cases": 6})
        names = {row["case"] for row in result["cases"]}
        self.assertIn("genuine_truncated", names)
        self.assertIn("forged_action_authority", names)
        ablation = result["verifier_ablation"]
        self.assertEqual(ablation["self_certifying_executor"], {
            "true_accept": 1, "true_reject": 0, "false_accept": 8,
            "false_reject": 0, "cases": 9})
        self.assertEqual(ablation["separate_first_party_verifier"], {
            "true_accept": 1, "true_reject": 8, "false_accept": 0,
            "false_reject": 0, "cases": 9})
        by_case = {row["case"]: row for row in ablation["cases"]}
        self.assertTrue(by_case["fabricated_truncated_exact"][
            "self_certifying_executor_accepts"])
        self.assertFalse(by_case["fabricated_truncated_exact"][
            "separate_verifier_accepts"])


if __name__ == "__main__":
    unittest.main()
