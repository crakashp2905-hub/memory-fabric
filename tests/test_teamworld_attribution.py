"""TeamWorld separates ranking, conflict, validation and lifecycle misses."""

from __future__ import annotations

import unittest

from experiments.p3b_teams import run


class EvidenceMissAttribution(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run(
            arms=("fabric", "shared"), seeds=(101,), agents=50, rounds=60)

    def test_fabric_misses_name_the_governance_cause(self) -> None:
        reasons = self.result["arms"]["fabric"]["evidence_miss_reasons"]
        self.assertGreater(reasons.get("unvalidated_claim", 0), 0)
        self.assertGreater(reasons.get("unresolved_conflict", 0), 0)
        self.assertNotIn("unknown", reasons)

    def test_plain_shared_store_does_not_claim_governance_reasons(self) -> None:
        self.assertEqual(
            self.result["arms"]["shared"]["evidence_miss_reasons"], {})

    def test_result_preserves_per_seed_values_intervals_and_denominators(self) -> None:
        fabric = self.result["arms"]["fabric"]
        self.assertIn("ci95_low", fabric["task_success"])
        self.assertIn("ci95_high", fabric["task_success"])
        self.assertEqual(self.result["per_seed"]["fabric"][0]["seed"], 101)
        self.assertEqual(
            self.result["metric_denominators"]["wrong_invalidation_rate"],
            "all task decisions",
        )

    def test_authority_conditioned_corrections_reduce_unvalidated_misses(self) -> None:
        improved = run(
            arms=("fabric", "fabric_authority"),
            seeds=(101, 102, 103, 104, 105), agents=50, rounds=60)
        original = improved["arms"]["fabric"]["evidence_miss_reasons"].get(
            "unvalidated_claim", 0)
        conditioned = improved["arms"]["fabric_authority"][
            "evidence_miss_reasons"].get("unvalidated_claim", 0)
        self.assertLess(conditioned, original)
        self.assertGreater(
            improved["arms"]["fabric_authority"]["task_success"]["mean"],
            improved["arms"]["fabric"]["task_success"]["mean"],
        )

    def test_verified_sensor_observations_cannot_remain_candidates(self) -> None:
        result = run(
            arms=("fabric_verified",), seeds=(301,), agents=50, rounds=60)
        reasons = result["arms"]["fabric_verified"]["evidence_miss_reasons"]
        self.assertEqual(reasons.get("unvalidated_claim", 0), 0)
        self.assertEqual(
            result["arms"]["fabric_verified"]["stale_action_rate"]["mean"],
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
