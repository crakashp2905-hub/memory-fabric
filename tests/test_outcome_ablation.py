"""Scripted factorial ablation and oracle headroom (W15-03, W15-05)."""

from __future__ import annotations

import unittest

from benchmarks.outcome_ablation import effects, factorial, headroom
from benchmarks.outcome_arms import paired_difference, rows_for

KEYS = [("pooled_recheck", False), ("pooled_recheck", True), ("governed", False), ("governed", True)]


class Factorial(unittest.TestCase):
    def test_known_answer_main_effects_and_interaction(self) -> None:
        cell = dict(zip(KEYS, [0.0, 0.5, 0.25, 1.0]))
        self.assertEqual(effects(cell), {"governance_main": 0.375, "recovery_main": 0.625,
                                         "interaction": 0.25})
        additive = dict(zip(KEYS, [0.0, 0.2, 0.3, 0.5]))
        self.assertEqual(effects(additive)["interaction"], 0.0)

    def test_each_family_credits_only_the_factor_that_moves_it(self) -> None:
        scopes = factorial(seeds=1)["by_scope"]
        self.assertEqual((scopes["public_correction"]["recovery_main"],
                          scopes["public_correction"]["governance_main"]), (1.0, 0.0))
        self.assertEqual((scopes["restricted_source"]["governance_main"],
                          scopes["restricted_source"]["recovery_main"]), (1.0, 0.0))
        for family in ("silent_change", "delayed_correction", "remote_retraction"):
            self.assertEqual(scopes[family]["governance_main"], 0.0, family)
            self.assertEqual(scopes[family]["recovery_main"], 0.0, family)


class Headroom(unittest.TestCase):
    def test_a3_optimal_and_no_headroom_tasks_are_excluded_from_targets(self) -> None:
        report = headroom(seeds=2)
        self.assertEqual(report["improvable_families"], ["restricted_source"])
        self.assertEqual(report["tasks"], report["no_headroom"] + report["a3_already_optimal"]
                         + report["improvable_over_a3"])

    def test_no_measured_contrast_exceeds_the_attainable_headroom(self) -> None:
        report = headroom(seeds=2)
        measured = paired_difference(rows_for(("A3", "A5"), seeds=2), "A5", "A3")["mean_difference"]
        self.assertLessEqual(measured, report["max_attainable_a5_minus_a3"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
