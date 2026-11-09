from __future__ import annotations

import unittest

from benchmarks.n3_08_ood_retention import BUDGET, FAMILIES
from benchmarks.n3_10_policy_graduation import run


class TestN310PolicyGraduation(unittest.TestCase):
    def test_gates_and_per_seed_evidence_are_reported_without_forcing_a_win(self) -> None:
        result = run(seeds=(40, 41))

        self.assertEqual(set(result["heldout_families"]), set(FAMILIES))
        self.assertEqual(result["seeds"], [40, 41])
        self.assertTrue(result["compute_gate"]["passed"])
        self.assertAlmostEqual(result["compute_gate"]["row_work_ratio"], 2.5)
        for family, evidence in result["family_results"].items():
            self.assertEqual(evidence["seed_count"], 2)
            self.assertEqual(len(evidence["regret_reduction_ci_95"]), 2)
            self.assertEqual(len(evidence["unsafe_rate_difference_ci_95"]), 2)
            self.assertTrue(
                all(row["seed"] in (40, 41) for row in evidence["per_seed"])
            )
            for row in evidence["per_seed"]:
                self.assertGreater(row["source_training_seconds"], 0.0)
                self.assertGreater(row["baseline_calibration_and_ranking_seconds"], 0.0)
                self.assertGreater(row["source_rows_processed"], 0)
                self.assertGreater(row["target_rows_processed"], 0)
                for mix in row["selected_kinds"].values():
                    self.assertEqual(sum(mix.values()), BUDGET)
            self.assertGreaterEqual(evidence["causal_unsafe_rate_mean"], 0.0)
            self.assertLessEqual(evidence["causal_unsafe_rate_mean"], 1.0)

        all_gates = result["compute_gate"]["passed"] and all(
            family["regret_gate_passed"] and family["safety_gate_passed"]
            for family in result["family_results"].values()
        )
        self.assertEqual(result["graduation_passed"], all_gates)
        self.assertEqual(
            result["decision"],
            "GRADUATE_FOR_SUPERVISED_RESEARCH" if all_gates else "DO_NOT_GRADUATE",
        )


if __name__ == "__main__":
    unittest.main()
