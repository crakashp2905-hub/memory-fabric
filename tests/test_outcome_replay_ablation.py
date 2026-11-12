"""Replay ablations must match per-task work and answer context."""

from __future__ import annotations

import unittest

from benchmarks.outcome_matched_arms import (
    REPLAY_ABLATION_STRATEGIES, compare_replay_ablation_outcomes,
)


def _rows() -> list[dict[str, object]]:
    return [
        {
            "task_id": f"case-{seed}", "seed": seed, "strategy": strategy,
            "completion": strategy in {"exact_dependence", "budgeted_replay"},
            "work_units": 64, "context_tokens": 128,
        }
        for seed in range(1, 6)
        for strategy in REPLAY_ABLATION_STRATEGIES
    ]


class TestOutcomeReplayAblation(unittest.TestCase):
    def test_reports_completion_only_after_matching_work_and_context(self) -> None:
        report = compare_replay_ablation_outcomes(
            _rows(), work_budget=100, context_token_budget=256,
        )

        self.assertEqual(report["status"], "MATCHED_COSTS_VALIDATED")
        self.assertEqual(report["strategies"], list(REPLAY_ABLATION_STRATEGIES))
        self.assertTrue(report["matched_resource_usage"]["identical_across_strategies"])
        self.assertTrue(report["task_population"]["seed_floor_met"])
        self.assertFalse(report["promotion_eligible"])

    def test_rejects_more_compute_or_more_answer_context_for_one_strategy(self) -> None:
        for field in ("work_units", "context_tokens"):
            rows = _rows()
            rows[-1][field] = 65 if field == "work_units" else 129
            with self.subTest(field=field), self.assertRaisesRegex(
                    ValueError, "match seed, work units, and context"):
                compare_replay_ablation_outcomes(
                    rows, work_budget=100, context_token_budget=256,
                )

    def test_rejects_over_budget_and_unpaired_task_populations(self) -> None:
        rows = _rows()
        rows[0]["work_units"] = 101
        with self.assertRaisesRegex(ValueError, "exceeds its fixed budget"):
            compare_replay_ablation_outcomes(
                rows, work_budget=100, context_token_budget=256,
            )

        rows = _rows()
        rows.pop()
        with self.assertRaisesRegex(ValueError, "same non-empty task IDs"):
            compare_replay_ablation_outcomes(
                rows, work_budget=100, context_token_budget=256,
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
