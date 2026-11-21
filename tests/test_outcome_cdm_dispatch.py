"""Dependence-first counterfactual dispatch and its utility ledger (W09-01, W09-09, W07-05, W18-05)."""

from __future__ import annotations

import unittest

from memory_fabric.outcome_typed.cdm_dispatch import (
    NON_REPLAYABLE, REPLAYED, RESOLVED_BY_ALTERNATE_SOURCE, SKIP_BUDGET, SKIP_INDEPENDENT,
    SKIP_NO_ALTERNATIVE, DecisionRecord, always_on, dispatch, utility_ledger,
)


def decision(name: str, memory: str, *, alternatives=("a", "b"), complete=True) -> DecisionRecord:
    return DecisionRecord(name, "a", frozenset({(memory, 1)}), tuple(alternatives), complete)


class Counter:
    def __init__(self, answer: str = "b") -> None:
        self.calls: list[str] = []
        self.answer = answer

    def __call__(self, item: DecisionRecord) -> str:
        self.calls.append(item.decision_id)
        return self.answer


class Dispatch(unittest.TestCase):
    def test_every_skip_has_an_explicit_reason_and_costs_no_replay(self) -> None:
        replay = Counter()
        report = dispatch([decision("independent", "m-other"),
                           decision("no-choice", "m1", alternatives=("a",)),
                           decision("partial", "m1", complete=False),
                           decision("dependent", "m1")], {"m1"}, replay)
        self.assertEqual([r.reason for r in report.rows],
                         [SKIP_INDEPENDENT, SKIP_NO_ALTERNATIVE, NON_REPLAYABLE, REPLAYED])
        self.assertEqual(replay.calls, ["dependent"])
        self.assertEqual((report.replays, report.flips), (1, 1))

    def test_budget_is_respected_and_reported(self) -> None:
        replay = Counter()
        report = dispatch([decision(f"d{i}", "m1") for i in range(3)], {"m1"}, replay, budget=1)
        self.assertEqual([r.reason for r in report.rows], [REPLAYED, SKIP_BUDGET, SKIP_BUDGET])
        self.assertEqual(len(replay.calls), 1)
        with self.assertRaises(ValueError):
            dispatch([], (), replay, budget=-1)

    def test_an_exact_alternate_source_answers_before_replay(self) -> None:
        replay = Counter()
        report = dispatch([decision("d", "m1")], {"m1"}, replay,
                          alternate_source=lambda item: "b")
        self.assertEqual(report.rows[0].reason, RESOLVED_BY_ALTERNATE_SOURCE)
        self.assertEqual(replay.calls, [])

    def test_dependence_first_costs_less_than_always_on_with_the_same_flips(self) -> None:
        decisions = [decision(f"d{i}", "m1" if i == 0 else f"other-{i}") for i in range(5)]
        lazy, eager = Counter(), Counter()
        first = dispatch(decisions, {"m1"}, lazy, budget=5)
        everything = always_on(decisions, eager)
        self.assertEqual((first.replays, everything.replays), (1, 5))
        # A deterministic policy cannot flip on unchanged evidence: the extra four are waste.
        self.assertEqual(first.flips, 1)

    def test_reports_are_advisory_and_never_authorize(self) -> None:
        report = dispatch([decision("d", "m1")], {"m1"}, Counter()).to_dict()
        self.assertTrue(report["advisory"])
        self.assertFalse(report["authorizes_effects"])
        self.assertNotIn("grant", report)
        self.assertNotIn("certificate", report)


class Ledger(unittest.TestCase):
    def test_a_flip_alone_never_earns_utility(self) -> None:
        ledger = utility_ledger(policy_flips=10, completion_difference=0.0, safety_difference=0.0,
                                replays=10)
        self.assertLess(ledger["net_utility"], 0)
        self.assertFalse(ledger["promotable"])

    def test_observed_gains_net_of_cost_and_safety(self) -> None:
        good = utility_ledger(policy_flips=1, completion_difference=0.2, safety_difference=0.0,
                              replays=2)
        self.assertTrue(good["promotable"])
        self.assertAlmostEqual(good["net_utility"], 0.18)
        worse = utility_ledger(policy_flips=1, completion_difference=0.2, safety_difference=0.1,
                               replays=2)
        self.assertFalse(worse["promotable"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
