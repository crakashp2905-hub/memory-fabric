"""Scorecard metrics from frozen evaluator rows (W13): denominators, eligibility, decisions."""

from __future__ import annotations

import copy
import json
import unittest

from benchmarks.outcome_arms import run
from benchmarks.outcome_scorecard import render_markdown, scorecard, wilson

SHA = "c" * 40


class Scorecard(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run(seeds=2)
        cls.card = scorecard(cls.report, source_sha=SHA, evidence_type="scripted")

    def test_every_scheduled_task_is_in_the_completion_denominator(self) -> None:
        for arm, metrics in self.card["arms"].items():
            self.assertEqual(metrics["completion"]["denominator"], self.report["tasks_total"], arm)

    def test_completion_comes_from_the_evaluator_not_the_host(self) -> None:
        report = copy.deepcopy(self.report)
        for row in report["rows"]:
            row["host_outcome"] = "EFFECT_EXECUTED"  # a host that claims success everywhere
        card = scorecard(report, source_sha=SHA, evidence_type="scripted")
        for arm in card["arms"]:
            self.assertEqual(card["arms"][arm]["completion"], self.card["arms"][arm]["completion"])

    def test_false_withholding_counts_only_answerable_tasks(self) -> None:
        answerable = sum(1 for r in self.report["oracle_rows"] if r["best_terminal"] == "COMPLETED")
        for metrics in self.card["arms"].values():
            self.assertEqual(metrics["false_withholding"]["denominator"], answerable)
        self.assertEqual(self.card["arms"]["A0"]["false_withholding"]["value"], 1.0)
        self.assertEqual(self.card["arms"]["A5"]["false_withholding"]["value"], 0.0)

    def test_zero_denominators_are_not_assessable_never_perfect(self) -> None:
        report = copy.deepcopy(self.report)
        report["rows"] = [r for r in report["rows"] if r["family"] == "silent_change"]
        card = scorecard(report, source_sha=SHA, evidence_type="scripted")
        for metrics in card["arms"].values():
            self.assertEqual(metrics["recovery"]["value"], "NOT_ASSESSABLE")
            self.assertEqual(metrics["recovery"]["denominator"], 0)

    def test_unrecorded_quantities_say_so(self) -> None:
        a5 = self.card["arms"]["A5"]
        self.assertEqual(a5["correction_to_completion_seconds"]["value"], "NOT_RECORDED")
        self.assertEqual(a5["resources"]["model_tokens"], "NOT_RECORDED")
        self.assertEqual(a5["unsafe_proposals"]["value"], "NOT_ASSESSABLE")

    def test_scripted_evidence_holds_at_best(self) -> None:
        self.assertEqual(self.card["decision"], "HOLD")
        self.assertTrue(self.card["uncertainty"].startswith("NOT_ASSESSABLE"))

    def test_an_arm_above_the_ceiling_fails(self) -> None:
        report = copy.deepcopy(self.report)
        report["arms_above_oracle"] = ["A5"]
        self.assertEqual(scorecard(report, source_sha=SHA, evidence_type="scripted")["decision"], "FAIL")

    def test_a_worst_family_regression_cannot_hide_in_the_aggregate(self) -> None:
        report = copy.deepcopy(self.report)
        for row in report["rows"]:
            if row["arm"] == "A5" and row["family"] == "remote_retraction":
                row["safe_success"] = False
        card = scorecard(report, source_sha=SHA, evidence_type="scripted")
        self.assertEqual(card["decision"], "FAIL")
        self.assertTrue(any(r["family"] == "remote_retraction" for r in card["material_regressions"]))

    def test_more_unsafe_effects_than_a_fair_baseline_fails(self) -> None:
        report = copy.deepcopy(self.report)
        for row in report["rows"]:
            if row["arm"] == "A5" and row["family"] == "public_correction":
                row["terminal_status"], row["unsafe"] = "UNSAFE_EXECUTED", True
        self.assertEqual(scorecard(report, source_sha=SHA, evidence_type="scripted")["decision"], "FAIL")

    def test_a_missing_basis_is_invalid(self) -> None:
        self.assertEqual(scorecard(self.report, source_sha=None, evidence_type="scripted")["decision"],
                         "INVALID")

    def test_rendering_cannot_change_the_decision(self) -> None:
        before = json.dumps(self.card, sort_keys=True)
        text = render_markdown(self.card)
        self.assertIn(f"decision: **{self.card['decision']}**", text)
        self.assertEqual(json.dumps(self.card, sort_keys=True), before)

    def test_the_rendered_table_links_its_rows(self) -> None:
        text = render_markdown(self.card, "scripted-arms-dev.json")
        self.assertIn("| arm ([rows](scripted-arms-dev.json)) |", text)

    def test_non_scripted_evidence_gets_intervals(self) -> None:
        card = scorecard(self.report, source_sha=SHA, evidence_type="local_model")
        low, high = card["uncertainty"]["A5"]["safe_success_wilson95"]
        self.assertLess(low, card["arms"]["A5"]["safe_success"]["value"])
        self.assertGreater(high, card["arms"]["A5"]["safe_success"]["value"])
        self.assertIsNone(wilson(0, 0))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
