from __future__ import annotations

import math
import unittest

from benchmarks.n3_03_estimator_comparison import run


class TestN303EstimatorComparison(unittest.TestCase):
    def test_estimators_are_compared_within_budget_against_exact_shapley(self) -> None:
        result = run()
        self.assertTrue(result["exact_shapley_efficiency_passed"])
        self.assertTrue(result["all_methods_within_budget"])
        self.assertEqual(result["seed_count"], 128)
        self.assertEqual(result["common_oracle_evaluation_budget_per_world_replicate"], 64)
        self.assertEqual(
            set(result["methods"]),
            {"loo", "shapley_approx", "ips", "naive_recency"},
        )
        for metrics in result["methods"].values():
            self.assertEqual(metrics["estimate_count"], 2048)
            self.assertTrue(math.isfinite(metrics["rmse_vs_exact_shapley"]))
            self.assertTrue(math.isfinite(metrics["mean_within_memory_world_variance"]))
            self.assertLessEqual(
                metrics["max_oracle_outcome_queries_per_world_replicate"], 64
            )

    def test_seeded_result_is_reproducible(self) -> None:
        self.assertEqual(run(), run())

if __name__ == "__main__":
    unittest.main()
