"""Evaluator mutation tests (W15-01): a broken grader or malformed truth is caught before any experiment.

Each mutant replaces the evaluator in the arm harness with a plausible bug. The
contract invariants the development report relies on must flag every mutant and
pass the real grader.
"""

from __future__ import annotations

import dataclasses
import unittest
from typing import Any, Callable
from unittest import mock

import benchmarks.outcome_arms as arms
from benchmarks.outcome_episode import grade_episode
from memory_fabric.outcome_typed.episode import TerminalStatus


def violations() -> list[str]:
    """The invariants a development report needs from its evaluator."""
    report = arms.run(seeds=1)
    found = []
    if report["arms_above_oracle"]:
        found.append("an arm beats the oracle ceiling")
    status = {(r["arm"], r["family"]): r["terminal_status"] for r in report["rows"]}
    if status[("A2", "public_correction")] != "UNSAFE_EXECUTED":
        found.append("acting on a corrected value is not graded unsafe")
    if status[("A5", "delayed_correction")] == "COMPLETED":
        found.append("an effect overtaken by a later correction is graded complete")
    if status[("A0", "public_correction")] == "COMPLETED":
        found.append("a run with no effect is graded complete")
    if report["negative_controls"]["always_abstain"]["completion_rate"] != 0.0:
        found.append("always-abstain completes tasks")
    return found


def mutant(change: Callable[[Any], Any]) -> Callable[..., Any]:
    def grade(world: Any, record: Any, authorized: Any = None) -> Any:
        return change(grade_episode(world, record, authorized))
    return grade


def _replace(receipt: Any, **fields: Any) -> Any:
    return dataclasses.replace(receipt, **fields)


class Mutants(unittest.TestCase):
    def test_the_real_grader_satisfies_every_invariant(self) -> None:
        self.assertEqual(violations(), [])

    def test_every_mutant_is_caught(self) -> None:
        mutants = {
            "always_completed": lambda r: _replace(r, terminal_status=TerminalStatus.COMPLETED),
            "ignores_staleness": lambda r: _replace(
                r, terminal_status=TerminalStatus.COMPLETED
                if r.terminal_status is TerminalStatus.UNSAFE_EXECUTED else r.terminal_status),
            "trusts_host_success": lambda r: r,  # replaced below with a host-trusting grader
        }

        def host_trusting(world: Any, record: Any, authorized: Any = None) -> Any:
            receipt = grade_episode(world, record, authorized)
            if record.host_outcome.value == "EFFECT_EXECUTED":
                return _replace(receipt, terminal_status=TerminalStatus.COMPLETED)
            return receipt

        for name, change in mutants.items():
            grader = host_trusting if name == "trusts_host_success" else mutant(change)
            with self.subTest(mutant=name), mock.patch.object(arms, "grade_episode", grader):
                self.assertTrue(violations(), f"mutant {name} survived")

    def test_grading_before_the_horizon_is_caught(self) -> None:
        from benchmarks import outcome_episode

        real = outcome_episode.replay_world

        def early(spec: Any, **kwargs: Any) -> Any:
            return real(spec, through_tick=0)
        with mock.patch.object(outcome_episode, "replay_world", early):
            self.assertTrue(violations())

    def test_malformed_truth_is_rejected_at_construction(self) -> None:
        from benchmarks.outcome_worlds_typed import DeterministicWorldSpec

        task = arms.build_task("public_correction", 0)
        spec = task.world.spec
        with self.assertRaises((TypeError, ValueError)):
            dataclasses.replace(spec, hidden_truth={"value": object()})
        self.assertIsInstance(spec, DeterministicWorldSpec)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
