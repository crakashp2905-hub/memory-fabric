from __future__ import annotations

import unittest

from experiments.n5_10_false_consensus_recovery import analyze, fork_seed


class FalseConsensusRecoveryTests(unittest.TestCase):
    def test_counterfactual_arms_share_the_same_checkpoint_and_are_reproducible(self) -> None:
        first = fork_seed(112)
        second = fork_seed(112)
        self.assertIsNotNone(first)
        self.assertEqual(first, second)
        assert first is not None
        self.assertEqual(set(first["arms"]), {
            "complete_collapse", "complete_preserve", "ring_collapse", "ring_preserve",
        })

    def test_preregistered_rule_requires_incremental_uplift_over_both_comparators(self) -> None:
        rows = [{"seed": seed, "arms": {
            "complete_preserve": {"recovered": True, "recovery_round": 30,
                                   "bad_pull_fraction": 0.1},
            "complete_collapse": {"recovered": False, "recovery_round": None,
                                  "bad_pull_fraction": 0.2},
            "ring_collapse": {"recovered": False, "recovery_round": None,
                              "bad_pull_fraction": 0.2},
            "ring_preserve": {"recovered": True, "recovery_round": 35,
                              "bad_pull_fraction": 0.15},
        }} for seed in range(200)]
        report = analyze(rows)
        self.assertEqual(report["verdict"], "SUPPORTED")
        self.assertEqual(report["contrasts"][
            "h1_complete_preserve_minus_complete_collapse"]["mean_recovery_uplift"], 1.0)

    def test_analysis_labels_below_preregistered_minimum_underpowered(self) -> None:
        rows = [{"seed": seed, "arms": {
            "complete_preserve": {"recovered": True, "recovery_round": 30,
                                   "bad_pull_fraction": 0.1},
            "complete_collapse": {"recovered": False, "recovery_round": None,
                                  "bad_pull_fraction": 0.2},
            "ring_collapse": {"recovered": False, "recovery_round": None,
                              "bad_pull_fraction": 0.2},
            "ring_preserve": {"recovered": True, "recovery_round": 35,
                              "bad_pull_fraction": 0.15},
        }} for seed in range(112)]
        report = analyze(rows)
        self.assertFalse(report["preregistered_minimum_met"])
        self.assertEqual(report["verdict"], "INCONCLUSIVE_UNDERPOWERED")
        with self.assertRaisesRegex(ValueError, "at least two eligible seeds"):
            analyze([])


if __name__ == "__main__":
    unittest.main()
