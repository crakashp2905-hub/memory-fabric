"""R11 tests action-dependent replay against the fixed-continuation LOO arm."""

from __future__ import annotations

import unittest

from benchmarks.cdm_intervention_vs_loo import SEEDS, _valid, run


class InterventionVersusLooTests(unittest.TestCase):
    def test_five_registered_worlds_show_replay_increment_over_loo(self):
        result = run()
        self.assertTrue(_valid(result))
        self.assertEqual(result["seeds"], list(SEEDS))
        self.assertEqual(len(result["rows"]), 15)
        self.assertEqual(result["summary"]["n"], 5)
        self.assertEqual(result["summary"]["mean_replay_minus_loo_utility"], 0.5)
        self.assertEqual(result["summary"]["normal_approx_95_interval"], [0.5, 0.5])
        for paired in result["paired_results"]:
            with self.subTest(seed=paired["seed"]):
                self.assertFalse(paired["loo_proposal_changed_vs_factual"])
                self.assertTrue(paired["replay_proposal_changed_vs_loo"])
                self.assertEqual(paired["loo_utility_difference"], 0.0)
                self.assertEqual(paired["replay_utility_difference"], 0.5)
                self.assertEqual(paired["replay_utility_difference_vs_loo"], 0.5)

    def test_truth_is_evaluator_only_and_world_is_local(self):
        result = run()
        self.assertFalse(result["safety"]["truth_visible_to_proposer"])
        self.assertTrue(all("truth" not in row for row in result["rows"]))
        self.assertEqual(result["safety"]["network_calls"], 0)
        self.assertEqual(result["safety"]["model_calls"], 0)
        self.assertEqual(result["safety"]["tool_calls"], 0)
        self.assertEqual(result["safety"]["authority_changes"], 0)


if __name__ == "__main__":
    unittest.main()
