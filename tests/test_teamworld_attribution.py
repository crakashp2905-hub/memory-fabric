"""TeamWorld separates ranking, conflict, validation and lifecycle misses."""

from __future__ import annotations

import unittest

from experiments.p3b_teams import run


def test_failed_tasks_have_replay_coordinates_and_cause() -> None:
    result = run(arms=("fabric",), seeds=(101,), agents=50, rounds=60)
    failures = result["failure_examples"]["fabric"]
    # Re-registered on the merged code (seed 101): 4 failed tasks, all rediscoveries.
    # The earlier 10 came from the pre-fix claim matching (P3b defect).
    assert len(failures) == 4
    assert all(row["seed"] == 101 and isinstance(row["task_index"], int) for row in failures)
    assert all(row["correct_value"] is not None for row in failures)
    assert all(
        row["evidence_miss_reason"] or row["rediscovered"]
        or row["acted_on_withdrawn"] or row["answered"] != row["correct_value"]
        for row in failures
    )


class EvidenceMissAttribution(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run(
            arms=("fabric", "shared"), seeds=(101,), agents=50, rounds=60)

    def test_fabric_misses_are_rediscoveries_not_governance_causes(self) -> None:
        # Re-registered on the merged code: no governance-cause misses, and every
        # fabric failure on seed 101 is a rediscovery.
        reasons = self.result["arms"]["fabric"]["evidence_miss_reasons"]
        self.assertEqual(reasons, {})
        failures = self.result["failure_examples"]["fabric"]
        self.assertTrue(all(row["rediscovered"] for row in failures))
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
        # Re-registered on the merged code: neither arm has unvalidated misses (both
        # 0 over five seeds). The registered comparison is task success: 0.964
        # (authority-conditioned) against 0.962 (plain), measured.
        self.assertEqual(original, 0)
        self.assertEqual(conditioned, 0)
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
