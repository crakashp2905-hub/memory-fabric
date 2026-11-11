"""Episode audits retain actor-visible events, evidence use, and actual results."""

from __future__ import annotations

import json
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ActionRequest, ToolRule
from memory_fabric.agent_outcomes import (
    AgentObservation, AgentStep, EffectRecord, EpisodeAudit, FailureCode,
    OutcomeAuditKind, OutcomeStage, TerminalObjective, TerminalSnapshot,
    canonical_step_id, canonical_task_id, grade_terminal,
)
from memory_fabric.agent_outcomes.observations import OracleTask
from memory_fabric.agent_outcomes.outcomes import (
    MAX_AUDIT_EVENTS, OutcomeAuditEvent,
)


class TestEpisodeAudit(unittest.TestCase):
    def _completed_case(self):
        task_id = canonical_task_id("pump_check", 17, 2)
        _, capability = OracleTask.seal_for_evaluator(task_id, {
            "truth": {"target": 6},
            "eligibility": {"set_target": True},
            "reward": {"completion": 1},
        })
        request = ActionRequest("pump-beta", {"value": 6})
        objective = TerminalObjective(task_id, {"target": 6}, "set_target", request)
        effect_step_id = canonical_step_id(task_id, 0)
        fabric = MemoryFabric(":memory:")
        try:
            gate = ActionGate(fabric, ActionPolicy(
                tools={"set_target": ToolRule("set_target", protected=False)},
                grants={"executor": frozenset({"set_target"})},
            ))
            execution = gate.execute(
                "set_target", "executor", lambda _key: None,
                key="effect-audit-1", request=request,
                receipt_context=effect_step_id,
            )
        finally:
            fabric.close()
        effect = EffectRecord(
            task_id, effect_step_id, "set_target", "executor", request,
            execution,
        )
        snapshot = TerminalSnapshot(task_id, {"target": 6})
        grade = grade_terminal(objective, [effect], [snapshot], capability=capability)
        observation = AgentObservation(
            task_id, "Set the pump beta target from the verified reading.",
            ({"source": "instrument", "reading": "6"},),
            ("retrieve_evidence", "set_target"), {"steps": 8},
        )
        step = AgentStep(
            task_id, "executor", effect.step_id, "propose",
            {"tool": "set_target", "target": "pump-beta", "value": 6},
            (("memory-beta-1", 3),),
        )
        return task_id, capability, objective, effect, snapshot, grade, observation, step

    def test_audit_reconstructs_the_episode_memory_failure_effect_and_terminal_state(self) -> None:
        task_id, capability, objective, effect, snapshot, grade, observation, step = (
            self._completed_case())
        audit = EpisodeAudit(task_id, "A5", 17)
        audit = audit.record_observation(observation)
        audit = audit.record_decision(step)
        audit = audit.record_memory_use(
            "executor", step.step_id, (("memory-beta-1", 3),), use="exposed")
        audit = audit.record_failure(
            OutcomeStage.RETRIEVAL, FailureCode.RETRIEVAL_MISS,
            detail_sha256="a" * 64,
        )
        audit = audit.record_effect(effect)
        audit = audit.record_terminal(grade, [snapshot], capability=capability)

        restored = EpisodeAudit.from_json(audit.canonical_json())
        timeline = restored.reconstruct()
        self.assertEqual(timeline[0]["data"]["observation"]["instruction"],
                         observation.instruction)
        self.assertEqual(timeline[1]["data"]["step"]["arguments"]["value"], 6)
        self.assertEqual(
            [event["data"]["use"] for event in timeline
             if event["kind"] == OutcomeAuditKind.MEMORY_USE.value],
            ["relied_on", "exposed"],
        )
        failure = next(event for event in timeline
                       if event["kind"] == OutcomeAuditKind.FAILURE.value)
        self.assertEqual(failure["stage"], OutcomeStage.RETRIEVAL.value)
        self.assertEqual(failure["data"]["code"], FailureCode.RETRIEVAL_MISS.value)
        self.assertEqual(timeline[-1]["kind"], OutcomeAuditKind.TERMINAL_RESULT.value)
        self.assertTrue(timeline[-1]["data"]["grade"]["completion"])
        self.assertEqual(timeline[-1]["data"]["terminal_snapshots"],
                         [{"state": {"target": 6}}])
        self.assertEqual(restored.canonical_json(), audit.canonical_json())

        detached = list(restored.reconstruct())
        detached[0]["data"]["observation"]["visible_events"][0]["reading"] = "changed"
        self.assertIn('"reading":"6"', restored.canonical_json())
        with self.assertRaises(ValueError):
            restored.record_observation(observation)

        tampered = json.loads(restored.canonical_json())
        relied_on = next(event for event in tampered["events"]
                         if event["kind"] == OutcomeAuditKind.MEMORY_USE.value
                         and event["data"]["use"] == "relied_on")
        relied_on["data"]["evidence_versions"][0][1] += 1
        with self.assertRaisesRegex(ValueError, "match the decision"):
            EpisodeAudit.from_json(json.dumps(tampered, sort_keys=True, separators=(",", ":")))

        incomplete_grade = grade_terminal(objective, [], [snapshot], capability=capability)
        incomplete_audit = EpisodeAudit(task_id, "A0", 17).record_decision(step)
        incomplete_audit = incomplete_audit.record_terminal(
            incomplete_grade, [snapshot], capability=capability)
        terminal_failure = next(event for event in incomplete_audit.reconstruct()
                                if event["kind"] == OutcomeAuditKind.FAILURE.value)
        self.assertEqual(terminal_failure["stage"], OutcomeStage.AUTHORIZATION.value)
        self.assertEqual(terminal_failure["data"]["code"],
                         FailureCode.AUTHORIZATION_DENIAL.value)

    def test_runtime_failures_are_recorded_at_their_stage_and_roundtrip(self) -> None:
        from memory_fabric.agent_outcomes import RuntimeTool, run_agent_loop

        task_id = canonical_task_id("runtime_audit", 4, 1)
        observation = AgentObservation(
            task_id, "Inspect the verified target.", (), (), {"steps": 2},
        )
        step = AgentStep(task_id, "planner", canonical_step_id(task_id, 0),
                         "propose", {"tool": "restricted_action"})
        result = run_agent_loop(
            observation, "planner", lambda _observation: step,
            {"restricted_action": RuntimeTool("restricted_action", lambda _args: {})},
        )
        self.assertEqual(result.failure_code, "tool_not_permitted")

        audit = EpisodeAudit(task_id, "A0", 4).record_runtime_result(result)
        restored = EpisodeAudit.from_json(audit.canonical_json())
        failure = next(event for event in restored.reconstruct()
                       if event["kind"] == OutcomeAuditKind.FAILURE.value)
        self.assertEqual(failure["stage"], OutcomeStage.AUTHORIZATION.value)
        self.assertEqual(failure["data"]["code"], FailureCode.AUTHORIZATION_DENIAL.value)
        self.assertEqual(restored.reconstruct()[-1]["data"]["status"], "FAILED")

        def fail_decision(_observation):
            raise RuntimeError("private implementation details stay out of the audit")

        decision_result = run_agent_loop(observation, "planner", fail_decision, {})
        decision_audit = EpisodeAudit(task_id, "A0", 4).record_runtime_result(decision_result)
        decision_failure = next(
            event for event in decision_audit.reconstruct()
            if event["kind"] == OutcomeAuditKind.FAILURE.value
        )
        self.assertEqual(decision_failure["stage"], OutcomeStage.DECISION.value)
        self.assertIsNone(decision_failure["step_id"])
        self.assertEqual(decision_failure["data"]["code"], FailureCode.PLANNING_ERROR.value)

    def test_runtime_audit_binds_tool_output_to_the_next_observation_and_use(self) -> None:
        from memory_fabric.agent_outcomes import RuntimeTool, run_agent_loop

        task_id = canonical_task_id("runtime_trace", 5, 0)
        memory_id = "memory-runtime-1"
        observation = AgentObservation(
            task_id, "Read the public pump target.", (), ("lookup",), {"steps": 3},
        )
        first = AgentStep(
            task_id, "planner", canonical_step_id(task_id, 0), "retrieve",
            {"tool": "lookup", "query": "pump beta target"},
        )
        second = AgentStep(
            task_id, "planner", canonical_step_id(task_id, 1), "abstain", {},
            ((memory_id, 4),),
        )
        decisions = iter((first, second))
        result = run_agent_loop(
            observation, "planner", lambda _observation: next(decisions),
            {"lookup": RuntimeTool(
                "lookup", lambda _args: {
                    "memory_id": memory_id, "version": 4,
                    "snippet": "Pump beta target setting is 6.",
                }, required_fields=frozenset({"query"}),
            )},
        )

        restored = EpisodeAudit(task_id, "A5", 5).record_runtime_result(result)
        restored = EpisodeAudit.from_json(restored.canonical_json())
        timeline = restored.reconstruct()
        self.assertEqual(
            [event["kind"] for event in timeline],
            ["observation", "decision", "tool_call", "observation", "decision",
             "memory_use", "runtime_end"],
        )
        tool_output = timeline[3]["data"]["observation"]["visible_events"][-1]["output"]
        self.assertEqual(tool_output["memory_id"], memory_id)
        self.assertEqual(timeline[5]["data"]["evidence_versions"], [[memory_id, 4]])

        tampered = json.loads(restored.canonical_json())
        tampered["events"][2]["data"]["output_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "output digest"):
            EpisodeAudit.from_json(json.dumps(tampered, sort_keys=True, separators=(",", ":")))

    def test_audit_parser_rejects_ambiguous_unknown_and_oversized_data(self) -> None:
        task_id, _, _, _, _, _, observation, _ = self._completed_case()
        audit = EpisodeAudit(task_id, "A5", 17).record_observation(observation)
        with self.assertRaisesRegex(ValueError, "evaluator"):
            AgentObservation(task_id, "do not expose audit", ({"record": audit},), (), {})
        encoded = audit.canonical_json()
        with self.assertRaisesRegex(ValueError, "duplicate audit field"):
            EpisodeAudit.from_json('{"schema_id":"x","schema_id":"y"}')

        payload = json.loads(encoded)
        payload["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "fields do not match"):
            EpisodeAudit.from_json(json.dumps(payload, sort_keys=True, separators=(",", ":")))

        with self.assertRaisesRegex(ValueError, "size limit"):
            EpisodeAudit.from_json(" " * 1_000_001)

        excess_events = tuple(
            OutcomeAuditEvent(index, OutcomeAuditKind.FAILURE, OutcomeStage.PLANNING, None,
                              {"code": FailureCode.PLANNING_ERROR.value,
                               "detail_sha256": None})
            for index in range(MAX_AUDIT_EVENTS + 1)
        )
        with self.assertRaisesRegex(ValueError, "bounded sequence"):
            EpisodeAudit(task_id, "A5", 17, excess_events)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
