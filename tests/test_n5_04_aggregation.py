from __future__ import annotations

import unittest

from experiments.n5_04_aggregation import (
    POLICIES,
    ARMS,
    Report,
    generate,
    pilot_is_degenerate,
    predict,
    score,
)


class AggregationBenchmarkTests(unittest.TestCase):
    def test_generator_is_deterministic_and_balanced(self) -> None:
        first = generate(17, 20)
        replay = generate(17, 20)
        self.assertEqual(first, replay)
        self.assertEqual(sum(task.truth for task in first.tasks), 10)

    def test_reporter_calibration_is_separate_from_evaluation_draw_count(self) -> None:
        short = generate(18, 20)
        longer = generate(18, 40)
        self.assertEqual(short.reputation, longer.reputation)
        self.assertEqual(short.calibration_correct, longer.calibration_correct)

    def test_report_copy_volume_does_not_increase_independent_root_weight(self) -> None:
        left = Report(0, 0, 0, "medium", 0, 0)
        right = Report(0, 1, 1, "medium", 1, 0)
        reputation = (0.7,) * 16
        self.assertIsNone(predict((left, right), "independent_root", reputation))
        self.assertIsNone(
            predict((left,) * 12 + (right,), "independent_root", reputation)
        )
        self.assertEqual(predict((left,) * 12 + (right,), "majority", reputation), 0)

    def test_evidence_quality_and_independent_root_use_distinct_frozen_weights(self) -> None:
        reports = (
            Report(0, 0, 0, "high", 0, 0),
            Report(0, 1, 1, "low", 1, 0),
        )
        reputation = (0.7,) * 16
        self.assertIsNone(predict(reports, "independent_root", reputation))
        self.assertEqual(predict(reports, "evidence_quality", reputation), 0)

    def test_prediction_api_has_no_ground_truth_input(self) -> None:
        reports = (Report(0, 0, 0, "high", 1, 0),)
        action = predict(reports, "majority", (0.7,) * 16)
        self.assertEqual(action, 1)

    def test_tie_abstains_and_utility_is_not_hidden(self) -> None:
        reports = (
            Report(0, 0, 0, "medium", 0, 0),
            Report(0, 1, 1, "medium", 1, 0),
        )
        self.assertIsNone(predict(reports, "majority", (0.7,) * 16))

    def test_pilot_metric_saturation_triggers_stop(self) -> None:
        self.assertTrue(pilot_is_degenerate({"majority": {"mean_utility": 1.0, "action_errors": 0}}))
        self.assertFalse(pilot_is_degenerate({"majority": {"mean_utility": 0.5, "action_errors": 0}}))

    def test_scoring_reports_policy_metrics_and_respects_oracle_ceiling(self) -> None:
        result = score(generate(19, 20))
        summaries = result["summary"]
        tasks = result["tasks"]
        self.assertEqual(set(summaries), set(ARMS))
        self.assertEqual(len(tasks["majority"]), 20)
        for summary in summaries.values():
            self.assertLessEqual(float(summary["mean_utility"]), 1.0)
            self.assertIn("minority_recovery", summary)
            self.assertIn("mean_convergence_wave", summary)


if __name__ == "__main__":
    unittest.main()
