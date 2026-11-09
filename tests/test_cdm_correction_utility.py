"""CDM-199's frozen utility weights and GO threshold cannot silently drift."""

from __future__ import annotations

import unittest

from benchmarks.cdm_correction_utility import (CONFIDENCE_LEVEL,
    MINIMUM_CONFIRMATORY_PAIRS, MINIMUM_MEAN_PAIRED_GAIN,
    confirmatory_go, score_review_utility)


class TestCorrectionUtility(unittest.TestCase):
    def test_three_strategy_fixture_has_fixed_utility_ordering(self):
        universe = ("depended", "would_stand", "unrelated")
        truth = ("depended",)
        blanket = score_review_utility(universe, truth, universe)
        dependence = score_review_utility(universe, truth, ("depended",))
        cdm = score_review_utility(universe, truth, ("depended", "would_stand"))
        self.assertAlmostEqual(blanket, 2.5666666667)
        self.assertAlmostEqual(dependence, 3.3)
        self.assertAlmostEqual(cdm, 2.9333333333)
        self.assertGreater(dependence, cdm)

    def test_confirmatory_go_requires_all_frozen_thresholds(self):
        self.assertEqual(MINIMUM_CONFIRMATORY_PAIRS, 20)
        self.assertEqual(MINIMUM_MEAN_PAIRED_GAIN, 0.1)
        self.assertEqual(CONFIDENCE_LEVEL, 0.95)
        deltas = (0.2,) * MINIMUM_CONFIRMATORY_PAIRS
        self.assertTrue(confirmatory_go(paired_deltas=deltas,
            lower_confidence_bound=0.01, missed_dependent_decisions=0,
            safety_violations=0))
        self.assertFalse(confirmatory_go(paired_deltas=deltas[:-1],
            lower_confidence_bound=0.01, missed_dependent_decisions=0,
            safety_violations=0))
        self.assertFalse(confirmatory_go(paired_deltas=deltas,
            lower_confidence_bound=0.0, missed_dependent_decisions=0,
            safety_violations=0))
        self.assertFalse(confirmatory_go(paired_deltas=deltas,
            lower_confidence_bound=0.01, missed_dependent_decisions=1,
            safety_violations=0))


if __name__ == "__main__":
    unittest.main()
