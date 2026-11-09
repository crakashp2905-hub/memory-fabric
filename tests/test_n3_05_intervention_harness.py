from __future__ import annotations

import unittest

from benchmarks.intervention_harness import RandomizedInterventionHarness
from benchmarks.n3_05_intervention_harness import run


class TestN305InterventionHarness(unittest.TestCase):
    def test_seeded_assignment_and_observation_are_inspectable(self) -> None:
        result = run()
        self.assertTrue(result["same_seed_replay_identical"])
        self.assertTrue(result["different_seed_changes_sequence"])
        self.assertTrue(result["all_realized_assignment_propensities_correct"])
        self.assertTrue(result["all_assignment_and_observation_rates_within_tolerance"])
        self.assertEqual(result["unit_count"], 10_000)
        self.assertEqual(len(result["rows"]), 10_000)

    def test_probability_validation_and_order_independent_draws(self) -> None:
        harness = RandomizedInterventionHarness(77)
        expected = harness.assign_and_observe(
            "unit-x", probability_treated=0.4,
            probability_observed_treated=0.8, probability_observed_control=0.9,
        )
        harness.assign_and_observe(
            "unit-y", probability_treated=0.7,
            probability_observed_treated=0.8, probability_observed_control=0.9,
        )
        replay = RandomizedInterventionHarness(77).assign_and_observe(
            "unit-x", probability_treated=0.4,
            probability_observed_treated=0.8, probability_observed_control=0.9,
        )
        self.assertEqual(expected, replay)
        for probability in (-0.1, 0.0, 1.0, 1.1):
            with self.assertRaises(ValueError):
                harness.assign_and_observe(
                    "invalid", probability_treated=probability,
                    probability_observed_treated=0.8, probability_observed_control=0.9,
                )
        for probability in (-0.1, 1.1):
            with self.assertRaises(ValueError):
                harness.assign_and_observe(
                    "invalid", probability_treated=0.5,
                    probability_observed_treated=probability, probability_observed_control=0.9,
                )
            with self.assertRaises(ValueError):
                harness.assign_and_observe(
                    "invalid", probability_treated=0.5,
                    probability_observed_treated=0.8, probability_observed_control=probability,
                )


if __name__ == "__main__":
    unittest.main()
