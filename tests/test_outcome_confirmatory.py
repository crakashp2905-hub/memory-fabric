"""CDM promotion compares paired outcomes after replay cost and safety."""

from __future__ import annotations

import unittest

from benchmarks.outcome_confirmatory import evaluate_cdm_promotion


def _rows(seeds: int = 5, *, candidate_completion: bool = True,
          candidate_attempts: int = 0, candidate_executed: int = 0,
          candidate_overhead_ms: float = 10.0) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for seed in range(1, seeds + 1):
        task_id = f"case-{seed}"
        rows.extend((
            {"task_id": task_id, "seed": seed, "arm": "A5", "completion": False,
             "unsafe_attempts": 0, "unsafe_executed": 0, "replay_overhead_ms": 0.0},
            {"task_id": task_id, "seed": seed, "arm": "A6",
             "completion": candidate_completion,
             "unsafe_attempts": candidate_attempts,
             "unsafe_executed": candidate_executed,
             "replay_overhead_ms": candidate_overhead_ms},
        ))
    return rows


class TestOutcomeConfirmatory(unittest.TestCase):
    def test_promotion_requires_paired_net_utility_and_non_regressive_safety(self) -> None:
        report = evaluate_cdm_promotion(
            _rows(), thresholds_frozen=True, minimum_net_utility_gain=0.5,
            replay_overhead_weight=0.001, resamples=100,
        )

        self.assertEqual(report["status"], "PROMOTE_CDM")
        self.assertAlmostEqual(report["utility"]["mean_paired_net_gain"], 0.99)
        self.assertEqual(report["safety"]["non_regressive"], True)
        self.assertEqual(report["candidate_arm_id"], "A6")
        self.assertEqual(report["baseline_arm_id"], "A5")

    def test_replay_overhead_can_remove_an_apparent_completion_gain(self) -> None:
        report = evaluate_cdm_promotion(
            _rows(candidate_overhead_ms=10.0), thresholds_frozen=True,
            minimum_net_utility_gain=0.1, replay_overhead_weight=0.2, resamples=100,
        )

        self.assertEqual(report["status"], "DO_NOT_PROMOTE")
        self.assertLess(report["utility"]["mean_paired_net_gain"], 0)

    def test_safety_regression_blocks_promotion_despite_utility_gain(self) -> None:
        report = evaluate_cdm_promotion(
            _rows(candidate_attempts=1, candidate_executed=1), thresholds_frozen=True,
            minimum_net_utility_gain=0.5, replay_overhead_weight=0.001, resamples=100,
        )

        self.assertEqual(report["status"], "DO_NOT_PROMOTE")
        self.assertFalse(report["safety"]["non_regressive"])

    def test_unfrozen_thresholds_or_too_few_seeds_remain_not_ready(self) -> None:
        unfrozen = evaluate_cdm_promotion(
            _rows(), thresholds_frozen=False, minimum_net_utility_gain=0.5,
            replay_overhead_weight=0.001, resamples=100,
        )
        underpowered = evaluate_cdm_promotion(
            _rows(seeds=4), thresholds_frozen=True, minimum_net_utility_gain=0.5,
            replay_overhead_weight=0.001, resamples=100,
        )

        self.assertEqual(unfrozen["status"], "NOT_READY")
        self.assertEqual(underpowered["status"], "NOT_READY")

    def test_unpaired_or_duplicate_task_rows_are_rejected(self) -> None:
        rows = _rows()
        rows.pop()
        with self.assertRaisesRegex(ValueError, "same non-empty task IDs"):
            evaluate_cdm_promotion(
                rows, thresholds_frozen=True, minimum_net_utility_gain=0.5,
                replay_overhead_weight=0.001,
            )

        rows = _rows()
        rows.append(dict(rows[0]))
        with self.assertRaisesRegex(ValueError, "duplicate task"):
            evaluate_cdm_promotion(
                rows, thresholds_frozen=True, minimum_net_utility_gain=0.5,
                replay_overhead_weight=0.001,
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
