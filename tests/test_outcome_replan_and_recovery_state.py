"""Partial replan, recovery-state binding and observation edge cases (W07-03, W07-07, W07-08)."""

from __future__ import annotations

import unittest

from benchmarks.outcome_arms import ARMS, build_task, run_arm
from benchmarks.outcome_episode import PooledMemoryPort, ScriptedTeam
from memory_fabric.outcome_typed.episode import HostOutcome, run_episode
from memory_fabric.outcome_typed.replan import PlanStep, affected_steps, full_replan, partial_replan

CURRENT = {"m1": 2, "m2": 1, "m3": 1}


def plan() -> list[PlanStep]:
    return [PlanStep("read", "read-sensor", frozenset({("m1", 1)})),
            PlanStep("calc", "compute-setpoint", frozenset(), after=("read",)),
            PlanStep("notify", "notify-ops", frozenset({("m2", 1)})),
            PlanStep("log", "write-log", frozenset({("m3", 1)})),
            PlanStep("apply", "set-target", frozenset(), after=("calc",))]


def redo(step: PlanStep) -> PlanStep:
    """The oracle planner: rebuild a step on the current version of its evidence."""
    evidence = frozenset((memory_id, CURRENT[memory_id]) for memory_id, _ in step.evidence)
    return PlanStep(step.step_id, step.action + "@current", evidence, step.after)


class PartialReplan(unittest.TestCase):
    def test_only_changed_steps_and_their_dependents_are_redone(self) -> None:
        self.assertEqual(affected_steps(plan(), {"m1"}), {"read", "calc", "apply"})
        result = partial_replan(plan(), {"m1"}, redo)
        self.assertEqual(result.redone, ("read", "calc", "apply"))
        self.assertEqual(result.kept, ("notify", "log"))

    def test_partial_replan_matches_the_oracle_on_every_affected_step_with_less_work(self) -> None:
        partial = partial_replan(plan(), {"m1"}, redo)
        oracle = full_replan(plan(), redo)
        for got, want in zip(partial.plan, oracle.plan):
            if got.step_id in partial.redone:
                self.assertEqual(got, want)
        self.assertLess(len(partial.redone), len(oracle.redone))

    def test_unknown_dependencies_and_duplicate_ids_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            affected_steps([PlanStep("a", "x", frozenset(), after=("ghost",))], set())
        with self.assertRaises(ValueError):
            affected_steps([PlanStep("a", "x", frozenset()), PlanStep("a", "y", frozenset())], set())


class RecoveryState(unittest.TestCase):
    def test_recovery_fingerprints_are_bound_to_the_task(self) -> None:
        prints = []
        for seed in (0, 1):
            row = run_arm(ARMS["A5"], build_task("public_correction", seed))
            self.assertEqual(row["terminal_status"], "COMPLETED")
            prints.append(row["trace_digest"])
        self.assertNotEqual(prints[0], prints[1])

    def test_the_fingerprint_names_the_task_and_the_last_failure(self) -> None:
        from benchmarks.outcome_episode import build_correction_task

        world, envelope = build_correction_task(0)
        record = run_episode(envelope, ScriptedTeam(), PooledMemoryPort(recheck=True),
                             feed=world.feed, effects={"set_target": world.effect("set_target")})
        recoveries = [e for e in record.trace["events"] if e["kind"] == "recovery"]
        self.assertTrue(recoveries)
        self.assertTrue(all(len(e["payload"]["fingerprint"]) == 64 for e in recoveries))


def feed_of(*observations):
    def feed(tick: int):
        return [dict(item) for item in observations]
    return feed


def reading(event_id: str, value: int, status: str) -> dict:
    return {"event_id": event_id, "kind": "observation", "revision_epoch": 1,
            "data": {"source": "instrument-A", "value": value, "status": status}}


class ObservationEdgeCases(unittest.TestCase):
    def episode(self, feed):
        from benchmarks.outcome_episode import build_correction_task

        world, envelope = build_correction_task(0)
        return run_episode(envelope, ScriptedTeam(), PooledMemoryPort(recheck=True), feed=feed,
                           effects={"set_target": world.effect("set_target")})

    def test_a_missing_observation_ends_in_a_reasoned_abstention(self) -> None:
        record = self.episode(feed_of())
        self.assertEqual((record.host_outcome, record.reason),
                         (HostOutcome.ABSTAINED, "planner_abstained:no_evidence"))

    def test_contradictory_observations_end_in_a_reasoned_abstention(self) -> None:
        record = self.episode(feed_of(reading("r1", 40, "initial"), reading("r2", 55, "second report")))
        self.assertEqual((record.host_outcome, record.reason),
                         (HostOutcome.ABSTAINED, "planner_abstained:contradictory_observations"))
        self.assertIsNone(record.effect_outcome)

    def test_a_fresh_correction_during_recovery_ends_in_the_corrected_plan(self) -> None:
        row = run_arm(ARMS["A5"], build_task("public_correction", 0))
        self.assertEqual(row["terminal_status"], "COMPLETED")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
