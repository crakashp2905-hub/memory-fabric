"""Opt-in high-level outcome API (W20-01, W20-03, W20-04, W20-05, W20-06, W20-07, W20-09)."""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
import unittest
from pathlib import Path

from benchmarks.outcome_arms import build_task
from benchmarks.outcome_episode import ScriptedTeam
from memory_fabric import MemoryFabric
from memory_fabric.outcome_typed.api import (
    AUTHORITY_FIELDS, ERRORS, OutcomeAPI, OutcomeApiError, _diagnose, validate_request,
)
from memory_fabric.outcome_typed.episode import AgentStep, HostOutcome

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "docs" / "schemas" / "outcome-api.v1.json").read_text())


def api_for(family: str = "public_correction", seed: int = 0, team=None):
    task = build_task(family, seed)
    fabric = MemoryFabric(":memory:", auto_activate=True)
    api = OutcomeAPI(fabric, effects={"set_target": task.world.effect("set_target")},
                     team=team or ScriptedTeam())
    return api, task, fabric


def request(task, **extra):
    return {"task_id": task.envelope.task_id, "objective": "set the actuator", **extra}


class Schema(unittest.TestCase):
    def test_the_schema_file_and_the_validator_agree(self) -> None:
        self.assertEqual(set(SCHEMA["refused_fields"]), set(AUTHORITY_FIELDS))
        self.assertEqual(SCHEMA["errors"], ERRORS)
        self.assertEqual(set(SCHEMA["properties"]), {"task_id", "objective", "objective_id",
                                                     "recovery", "limits"})
        for example in SCHEMA["examples"]:
            validate_request(example)

    def test_unknown_and_authority_bearing_fields_are_refused(self) -> None:
        for bad in ({"task_id": "t", "objective": "o", "callback": "os.system"},
                    {"task_id": "t", "objective": "o", "code": "import os"},
                    {"task_id": "t", "objective": "o", "grant": "g"},
                    {"task_id": "t", "objective": "o", "surprise": 1},
                    {"task_id": "t"}, {"task_id": 3, "objective": "o"},
                    {"task_id": "t", "objective": "o", "limits": {"max_steps": "many"}}):
            with self.subTest(bad=bad), self.assertRaises(OutcomeApiError) as caught:
                validate_request(bad)
            self.assertEqual(caught.exception.code, "INVALID_REQUEST")

    def test_effects_are_host_registered_never_supplied(self) -> None:
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        with self.assertRaises(ValueError):
            OutcomeAPI(fabric, effects={})


class Operations(unittest.TestCase):
    def test_run_task_end_to_end_and_the_outcome_hides_the_evaluator(self) -> None:
        api, task, fabric = api_for()
        self.addCleanup(fabric.close)
        result = api.run_task(request(task), feed=task.world.feed)
        self.assertEqual(result.status, "EFFECT_EXECUTED")
        outcome = api.get_outcome(task.envelope.task_id)
        self.assertEqual(outcome["evaluator_grade"], "NOT_AVAILABLE_TO_ACTORS")
        self.assertEqual(api.inspect_failure(task.envelope.task_id)["failure"], None)
        evidence = api.get_evidence(task.envelope.task_id)
        self.assertEqual([e["status"] for e in evidence], ["current"])

    def test_no_incomplete_task_is_reported_as_success(self) -> None:
        api, task, fabric = api_for()
        self.addCleanup(fabric.close)
        tight = api.run_task(request(task, limits={"max_steps": 2}), feed=task.world.feed)
        self.assertEqual((tight.status, tight.diagnosis), ("BUDGET_EXCEEDED", "budget"))
        self.assertTrue(tight.next_steps)

    def test_resume_refuses_what_rerunning_cannot_fix(self) -> None:
        api, task, fabric = api_for()
        self.addCleanup(fabric.close)
        api.run_task(request(task, limits={"max_steps": 2}), feed=task.world.feed)
        with self.assertRaises(OutcomeApiError) as caught:
            api.resume_recovery(task.envelope.task_id, feed=task.world.feed)
        self.assertEqual(caught.exception.code, "BUDGET_EXCEEDED")
        with self.assertRaises(OutcomeApiError) as unknown:
            api.get_outcome("never-ran")
        self.assertEqual(unknown.exception.code, "UNKNOWN_TASK")
        record = api._records[task.envelope.task_id]
        api._records[task.envelope.task_id] = dataclasses.replace(record, trace={"events": []})
        with self.assertRaises(OutcomeApiError) as partial:
            api.resume_recovery(task.envelope.task_id, feed=task.world.feed)
        self.assertEqual(partial.exception.code, "NON_REPLAYABLE")

    def test_a_blocked_task_resumes_with_recovery_on(self) -> None:
        api, task, fabric = api_for()
        self.addCleanup(fabric.close)
        first = api.run_task(request(task, recovery=False), feed=task.world.feed)
        self.assertEqual((first.status, first.diagnosis), ("BLOCKED", "withdrawn"))
        api._requests[task.envelope.task_id]["recovery"] = True
        resumed = api.resume_recovery(task.envelope.task_id, feed=task.world.feed)
        self.assertNotEqual(resumed.task_id, task.envelope.task_id)
        self.assertIn(resumed.status, {"EFFECT_EXECUTED", "BLOCKED"})


class Diagnostics(unittest.TestCase):
    """A developer can tell retrieval, permission, stale-data and tool failures apart (W20-04)."""

    def record_with(self, **changes):
        api, task, fabric = api_for()
        self.addCleanup(fabric.close)
        api.run_task(request(task), feed=task.world.feed)
        return dataclasses.replace(api._records[task.envelope.task_id], **changes)

    def test_each_failure_kind_has_its_own_diagnosis_and_next_step(self) -> None:
        cases = {
            "tool_not_declared": "tool",
            "tool_not_granted": "no_permission",
            "planner_abstained:no_evidence": "no_evidence",
            "evidence_withdrawn": "withdrawn",
            "wrong_tenant": "not_available",
        }
        for reason, expected in cases.items():
            with self.subTest(reason=reason):
                record = self.record_with(host_outcome=HostOutcome.FAILED, reason=reason)
                self.assertEqual(_diagnose(record), expected)

    def test_an_invalid_tool_from_the_actor_is_a_tool_failure(self) -> None:
        def bad(role, observation):
            step = ScriptedTeam()(role, observation)
            if role == "planner" and step.intent == "retrieve":
                return AgentStep(observation.task_id, role, step.step_id, "retrieve",
                                 {"tool": "delete_everything"})
            return step

        api, task, fabric = api_for(team=bad)
        self.addCleanup(fabric.close)
        result = api.run_task(request(task), feed=task.world.feed)
        self.assertEqual((result.status, result.diagnosis), ("BLOCKED", "tool"))


class TransportParity(unittest.TestCase):
    def test_direct_mcp_and_utcp_calls_return_the_same_answers(self) -> None:
        from benchmarks.outcome_episode import seeded_ids

        answers = []
        for mode in ("direct", "mcp", "utcp"):
            with seeded_ids(7):  # identical stores, so ids match across the three runs
                api, task, fabric = api_for()
                self.addCleanup(fabric.close)
                payload = request(task)
                if mode == "direct":
                    run = api.handle("run_task", payload, feed=task.world.feed)
                elif mode == "mcp":
                    run = api.mcp_call({"name": "run_task", "arguments": payload},
                                       feed=task.world.feed)
                else:
                    run = api.utcp_call("outcome.run_task", payload, feed=task.world.feed)
                ask = {"task_id": task.envelope.task_id}
                answers.append((run, api.handle("get_outcome", ask), api.mcp_call(
                    {"name": "inspect_failure", "arguments": ask}),
                    api.utcp_call("outcome.get_evidence", ask)))
        self.assertEqual(answers[0], answers[1])
        self.assertEqual(answers[1], answers[2])

    def test_errors_are_the_same_shape_on_every_surface(self) -> None:
        api, task, fabric = api_for()
        self.addCleanup(fabric.close)
        bad = {"task_id": "t", "objective": "o", "callback": "x"}
        expected = api.handle("run_task", bad, feed=task.world.feed)
        self.assertEqual(expected["error"], "INVALID_REQUEST")
        self.assertEqual(api.mcp_call({"name": "run_task", "arguments": bad}, feed=task.world.feed),
                         expected)
        self.assertEqual(api.utcp_call("outcome.run_task", bad, feed=task.world.feed), expected)


class TenantSetupExample(unittest.TestCase):
    def test_fresh_machine_example_denies_the_unauthorized_action(self) -> None:
        done = subprocess.run([sys.executable, "-W", "ignore", "examples/agent_outcome_tenant_setup.py"],
                              cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("ops: allowed", done.stdout)
        self.assertIn("intern: refused (tool_not_granted)", done.stdout)
        source = (ROOT / "examples" / "agent_outcome_tenant_setup.py").read_text()
        self.assertIn("os.urandom(32)", source)
        self.assertNotRegex(source, r"key\s*=\s*b[\"']")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
