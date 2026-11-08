"""Outcome abstention, independent fidelity and held-out calibration tests."""

from __future__ import annotations

import unittest

from memory_fabric.causal_replay.evaluator import (Outcome, assess_outcome,
    calibration_report, heuristic_contribution, verify_fidelity)


class TestEvaluator(unittest.TestCase):
    def test_missing_outcomes_abstain(self):
        result = assess_outcome(Outcome("missing", None, None, False))
        self.assertEqual(result.status, "UNDECIDABLE")
        self.assertIsNone(result.reward)

    def test_outcome_and_fidelity_are_separate(self):
        observed = assess_outcome(Outcome("case", 0.8, 1.0, True))
        fidelity = verify_fidelity("a" * 64, "b" * 64)
        self.assertEqual(observed.status, "OBSERVED")
        self.assertEqual(fidelity.status, "MISMATCH")
        self.assertFalse(fidelity.verified)

    def test_calibration_uses_only_valid_held_out_outcomes(self):
        outcomes = (Outcome("held", 1.0, 1.0, True, True, True),
                    Outcome("train", 0.0, 1.0, True, True, False),
                    Outcome("invalid", 0.0, 0.0, True, False, True),
                    Outcome("missing", 1.0, 0.0, False, True, True))
        report = calibration_report((0.8, 0.1, 0.1, 0.9),
                                    (True, False, False, True), outcomes=outcomes)
        self.assertEqual(report.sample_count, 1)
        self.assertAlmostEqual(report.brier_score, 0.04)
        self.assertAlmostEqual(report.expected_calibration_error, 0.2)

    def test_no_eligible_calibration_data_is_undefined(self):
        report = calibration_report((0.5,), (True,),
                                    outcomes=(Outcome("train", 1.0, 0.0, True),))
        self.assertEqual(report.sample_count, 0)
        self.assertIsNone(report.brier_score)
        self.assertIsNone(report.expected_calibration_error)

    def test_heuristic_contribution_is_predictive_and_handles_no_feedback(self):
        score = heuristic_contribution(exposures=4, positive_feedback=3,
                                       negative_feedback=1)
        self.assertEqual(score.score, 0.5)
        self.assertEqual(score.tag, "PREDICTIVE_NOT_CAUSAL")
        empty = heuristic_contribution(exposures=0, positive_feedback=0,
                                       negative_feedback=0)
        self.assertIsNone(empty.score)


if __name__ == "__main__":
    unittest.main()
