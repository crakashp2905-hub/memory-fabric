from __future__ import annotations

import unittest

from benchmarks.n3_08_ood_retention import PROMOTION_MARGIN, run


class TestN308HeldoutTransfer(unittest.TestCase):
    def test_source_learned_policy_clears_historical_baseline_gate(self) -> None:
        result = run()
        self.assertEqual(
            set(result["heldout_world_families"]),
            {"supply_chain_dispatch", "incident_response"},
        )
        self.assertEqual(len(result["learned_source_effects_by_seed"]), 10)
        self.assertTrue(result["promotion_gate_passed"])
        for family in result["heldout_world_families"]:
            evidence = result["family_results"][family]
            self.assertEqual(evidence["seed_count"], 10)
            self.assertGreaterEqual(evidence["paired_difference_mean"], PROMOTION_MARGIN)
            self.assertGreater(evidence["paired_difference_ci_95"][0], 0.0)
            self.assertTrue(evidence["promotion_gate_passed"])
            self.assertEqual(
                sum(evidence["policy_memory_mix"]["source_causal_policy"].values()),
                10 * 20,
            )


if __name__ == "__main__":
    unittest.main()
