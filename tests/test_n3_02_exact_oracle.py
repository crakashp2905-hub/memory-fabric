from __future__ import annotations

import unittest

from benchmarks.n3_02_exact_oracle import run


class TestN302ExactOracle(unittest.TestCase):
    def test_ips_matches_causal_oracle_in_every_enumerated_world(self) -> None:
        result = run()
        self.assertTrue(result["passed"])
        self.assertEqual(result["world_count"], 4)
        self.assertEqual(result["total_enumerated_subsets"], 64)
        for world in result["worlds"]:
            self.assertEqual(world["enumerated_subsets"], 16)
            for effect in world["effects"]:
                self.assertTrue(effect["contrastive"])
                self.assertTrue(effect["passed"], effect)


if __name__ == "__main__":
    unittest.main()
