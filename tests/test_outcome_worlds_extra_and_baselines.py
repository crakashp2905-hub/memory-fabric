"""Temporal-validity and multi-hop worlds (W05-07, W05-09); first-party baselines (W11-05)."""

from __future__ import annotations

import unittest

from benchmarks import outcome_retrieval_baselines as baselines
from benchmarks.outcome_worlds_extra import run_multihop, run_temporal


class TemporalValidity(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_temporal(2)["policies"]

    def test_valid_time_answers_both_the_historical_fact_and_the_action_now(self) -> None:
        self.assertEqual(self.report["temporal"]["by_question"], {"action_now": 1.0, "historical": 1.0})

    def test_a_timeless_contradiction_reading_fails(self) -> None:
        self.assertEqual(self.report["timeless"]["accuracy"], 0.0)

    def test_latest_known_gets_the_action_right_and_history_wrong(self) -> None:
        self.assertEqual(self.report["latest_known"]["by_question"],
                         {"action_now": 1.0, "historical": 0.0})


class MultiHop(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_multihop(2)["policies"]

    def test_two_hops_answer_before_and_after_the_rewiring(self) -> None:
        self.assertEqual(self.report["two_hop"]["by_phase"], {"after": 1.0, "before": 1.0})

    def test_single_record_and_exact_match_shortcuts_fail(self) -> None:
        self.assertEqual(self.report["single_record"]["accuracy"], 0.0)
        self.assertEqual(self.report["exact_match"]["accuracy"], 0.0)


class FirstPartyBaselines(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = baselines.run(2)

    def test_all_six_strategies_run_under_the_same_caps(self) -> None:
        summary = self.report["summary"]
        self.assertEqual(set(summary), {"recency", "lexical", "fixed_top_k", "full_context",
                                        "summary", "governed"})
        for name, row in summary.items():
            self.assertLessEqual(row["max_chars"], baselines.CHARS, name)
            if name != "full_context":
                self.assertLessEqual(row["max_items"], baselines.K, name)
        self.assertTrue(self.report["first_party"])

    def test_no_baseline_gets_less_context_than_the_governed_arm(self) -> None:
        summary = self.report["summary"]
        governed = summary["governed"]["max_chars"]
        for name, row in summary.items():
            self.assertGreaterEqual(row["max_chars"], governed, name)

    def test_fair_baselines_tie_on_accuracy_and_the_query_blind_one_fails(self) -> None:
        summary = self.report["summary"]
        self.assertEqual(summary["fixed_top_k"]["accuracy"], 0.0)
        for name in ("recency", "lexical", "full_context", "summary", "governed"):
            self.assertEqual(summary[name]["accuracy"], 1.0, name)

    def test_the_reader_is_shared_and_prefers_a_correction(self) -> None:
        context = [("a", "instrument-A reading is 5 units (initial)."),
                   ("b", "instrument-A reading is 9 units (correction).")]
        self.assertEqual(baselines.reader(context), 9)
        self.assertEqual(baselines.reader(list(reversed(context))), 9)
        self.assertIsNone(baselines.reader([("c", "no reading here")]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
