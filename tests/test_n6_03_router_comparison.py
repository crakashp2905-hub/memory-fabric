from __future__ import annotations

import unittest

from experiments.n6_03_router_comparison import run


class RouterComparisonTests(unittest.TestCase):
    def test_local_router_handles_overconfident_and_reordered_sources(self) -> None:
        report = run(tasks=200, seed=60_303)
        self.assertTrue(report["acceptance_passed"])
        metrics = report["metrics"]
        local = metrics["deterministic_local_features"]
        calibrated = metrics["simulated_calibrated_probabilities"]
        adversarial = metrics["simulated_overconfident_reversed_probabilities"]
        self.assertEqual(local["unsafe_system1_count"], 0)
        self.assertEqual(local["mean_utility"], calibrated["mean_utility"])
        self.assertGreater(adversarial["unsafe_system1_count"], 0)
        self.assertGreater(local["mean_utility"], adversarial["mean_utility"])
        self.assertTrue(report["paired_differences"]["calibrated_mapping_order_invariant"])

    def test_rejects_empty_task_batch(self) -> None:
        with self.assertRaises(ValueError):
            run(tasks=0)


if __name__ == "__main__":
    unittest.main()
