"""Capability and mutation checks for actor/evaluator separation."""

from __future__ import annotations

import copy
import json
import pickle
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import (
    ActionDecision, ActionExecution, ActionGate, ActionPolicy, ActionRequest, ToolRule,
)
from memory_fabric.agent_outcomes.observations import (
    AgentObservation,
    AgentStep,
    EvaluatorCapability,
    OracleTask,
)
from memory_fabric.agent_outcomes.outcomes import (
    EffectRecord,
    TerminalObjective,
    TerminalSnapshot,
    canonical_step_id,
    canonical_task_id,
    grade_terminal,
)


def _bundle():
    task_id = canonical_task_id("isolation", 17, 2)
    request = ActionRequest("target", {"value": "sealed-value-42"})
    objective = TerminalObjective(
        task_id, {"target": "sealed-value-42"}, "set_target", request,
    )
    world = {"target": "before"}
    fabric = MemoryFabric(":memory:")
    try:
        gate = ActionGate(fabric, ActionPolicy(
            tools={"set_target": ToolRule("set_target", protected=False)},
            grants={"executor": frozenset({"set_target"})},
        ))
        execution = gate.execute(
            "set_target", "executor", lambda _key: world.update(request.parameters),
            key="effect-isolation-1", request=request,
            receipt_context=canonical_step_id(task_id, 0),
        )
    finally:
        fabric.close()
    effect = EffectRecord(
        task_id, canonical_step_id(task_id, 0), "set_target", "executor", request,
        execution,
    )
    snapshot = TerminalSnapshot(task_id, {"target": "sealed-value-42"})
    oracle, capability = OracleTask.seal_for_evaluator(task_id, {
        "truth": {"target": "sealed-value-42"},
        "eligibility": {"action_authorized": True},
        "reward": {"completion": 1},
    })
    return task_id, oracle, capability, objective, effect, snapshot


class TestOutcomeOracleIsolation(unittest.TestCase):
    def test_actor_identity_cannot_call_or_serialize_evaluator_outputs(self) -> None:
        task_id, oracle, capability, objective, effect, snapshot = _bundle()
        actor_step = AgentStep(task_id, "planner", "step-1", "propose", {"tool": "set_target"})

        with self.assertRaises(TypeError):
            grade_terminal(objective, [effect], [snapshot])
        with self.assertRaises(PermissionError):
            grade_terminal(objective, [effect], [snapshot], capability=actor_step)
        with self.assertRaises(PermissionError):
            oracle.open_payload(actor_step)
        with self.assertRaises(PermissionError):
            oracle.open_payload(object())

        grade = grade_terminal(objective, [effect], [snapshot], capability=capability)
        self.assertNotIn("sealed-value-42", repr(grade))
        with self.assertRaises(TypeError):
            grade.to_json()
        _, other_capability = OracleTask.seal_for_evaluator(task_id + ".other", {
            "truth": {}, "eligibility": {}, "reward": {},
        })
        with self.assertRaises(PermissionError):
            grade.to_json(other_capability)
        _, same_task_other_capability = OracleTask.seal_for_evaluator(task_id, {
            "truth": {"target": "different sealed target"},
            "eligibility": {},
            "reward": {},
        })
        with self.assertRaises(PermissionError):
            grade.to_json(same_task_other_capability)

        with self.assertRaisesRegex(ValueError, "evaluator handle"):
            AgentStep(task_id, "planner", "step-grade", "propose", {"result": grade})
        with self.assertRaisesRegex(ValueError, "evaluator handle"):
            AgentStep(task_id, "planner", "step-2", "propose", {"handle": capability})
        with self.assertRaisesRegex(ValueError, "evaluator handle"):
            AgentStep(task_id, "planner", "step-3", "propose", {"callback": lambda: grade})
        with self.assertRaisesRegex(ValueError, "evaluator handle"):
            AgentObservation(task_id, "Do the task", ({"handle": oracle},), (), {})

    def test_adversarial_evaluator_cannot_forge_a_gate_outcome_or_mutate_episode_state(self) -> None:
        task_id, _, capability, objective, effect, snapshot = _bundle()
        actor_step = AgentStep(task_id, "planner", canonical_step_id(task_id, 0),
                               "propose", {"tool": "set_target"})
        state_before = dict(snapshot.state)

        def adversarial_evaluator(step, terminal):
            with self.assertRaises(AttributeError):
                step.kind = "approve"  # type: ignore[misc]
            with self.assertRaises(TypeError):
                terminal.state["target"] = "attacker-controlled"  # type: ignore[index]
            forged_decision = ActionDecision(
                True, "set_target", "executor", ("allowed",),
            )
            forged_execution = ActionExecution(
                "executed", forged_decision, "evaluator-minted-effect",
            )
            return EffectRecord(
                task_id, canonical_step_id(task_id, 0), "set_target", "executor",
                effect.request, forged_execution,
            )

        forged = adversarial_evaluator(actor_step, snapshot)
        grade = grade_terminal(objective, [forged], [snapshot], capability=capability)
        self.assertEqual(grade.status.value, "INCOMPLETE")
        self.assertEqual(grade.reason.value, "unauthorized_effect")
        self.assertEqual(grade.executed_effects, 0)
        self.assertEqual(dict(snapshot.state), state_before)

    def test_gate_receipt_cannot_be_replayed_for_another_request_or_edited(self) -> None:
        task_id, _, capability, objective, effect, snapshot = _bundle()
        other_request = ActionRequest("different-target", {"value": "sealed-value-42"})
        replayed = EffectRecord(
            task_id, effect.step_id, effect.tool, effect.actor_id, other_request,
            effect.execution,
        )
        replay_grade = grade_terminal(objective, [replayed], [snapshot], capability=capability)
        self.assertEqual(replay_grade.reason.value, "unauthorized_effect")
        self.assertEqual(replay_grade.executed_effects, 0)

        relabeled = EffectRecord(
            task_id, canonical_step_id(task_id, 1), effect.tool, effect.actor_id,
            effect.request, effect.execution,
        )
        relabeled_grade = grade_terminal(objective, [relabeled], [snapshot],
                                         capability=capability)
        self.assertEqual(relabeled_grade.reason.value, "unauthorized_effect")
        self.assertEqual(relabeled_grade.executed_effects, 0)

        edited_execution = copy.copy(effect.execution)
        object.__setattr__(edited_execution, "outcome", "refused")
        edited = EffectRecord(
            task_id, effect.step_id, effect.tool, effect.actor_id, effect.request,
            edited_execution,
        )
        edited_grade = grade_terminal(objective, [edited], [snapshot], capability=capability)
        self.assertEqual(edited_grade.reason.value, "unauthorized_effect")
        self.assertEqual(edited_grade.refused_effects, 0)

    def test_capability_is_task_bound_opaque_and_not_serializable(self) -> None:
        task_id, oracle, capability, *_ = _bundle()
        other_oracle, other_capability = OracleTask.seal_for_evaluator(task_id + ".other", {
            "truth": {"target": "different"},
            "eligibility": {},
            "reward": {},
        })
        self.assertTrue(oracle.verify_seal(capability))
        self.assertEqual(oracle.open_payload(capability)["truth"]["target"], "sealed-value-42")
        sealed_without_capability = OracleTask.seal(task_id, {
            "truth": {"target": "sealed-value-42"},
            "eligibility": {"action_authorized": True},
            "reward": {"completion": 1},
        })
        with self.assertRaises(PermissionError):
            sealed_without_capability.open_payload(capability)
        with self.assertRaises(PermissionError):
            oracle.open_payload(other_capability)
        with self.assertRaises(PermissionError):
            other_oracle.open_payload(capability)
        with self.assertRaises(PermissionError):
            EvaluatorCapability("actor", task_id, b"x" * 32, oracle.seal_sha256)
        with self.assertRaises(TypeError):
            json.dumps(capability)
        with self.assertRaises(TypeError):
            capability.__reduce__()
        with self.assertRaises(TypeError):
            pickle.dumps(capability)
        self.assertNotIn(capability._nonce.hex(), repr(capability))

    def test_nested_mutation_is_detached_frozen_and_revalidated(self) -> None:
        task_id = "mutation-task"
        source = {"sensor": {"reading": 7}, "samples": [1, 2]}
        budget = {"steps": 3}
        permitted_tools = ["inspect"]
        observation = AgentObservation(task_id, "Inspect the public reading.",
                                       (source,), permitted_tools, budget)
        original = observation.canonical_json()
        source["sensor"]["reading"] = "mutated source"
        source["samples"].append(99)
        budget["steps"] = 99
        permitted_tools.append("mutated-tool-list")
        self.assertEqual(observation.canonical_json(), original)
        self.assertEqual(observation.permitted_tools, ("inspect",))
        with self.assertRaises(TypeError):
            observation.visible_events[0]["sensor"]["reading"] = "direct mutation"
        with self.assertRaises(TypeError):
            observation.budget["steps"] = 99
        copied = observation.to_dict()
        copied["visible_events"][0]["sensor"]["reading"] = "output copy mutation"
        self.assertEqual(observation.canonical_json(), original)

        input_arguments = {"proposal": {"tool": "inspect"}}
        evidence_versions = [("memory-1", 1)]
        step = AgentStep(task_id, "planner", "step-1", "propose", input_arguments,
                         evidence_versions)
        input_arguments["proposal"]["tool"] = "leaked mutation"
        evidence_versions.append(("memory-2", 2))
        self.assertEqual(step.to_dict()["arguments"]["proposal"]["tool"], "inspect")
        self.assertEqual(step.evidence_versions, (("memory-1", 1),))
        with self.assertRaises(TypeError):
            step.arguments["proposal"]["tool"] = "direct mutation"

        object.__setattr__(observation, "visible_events", ({"hidden_answer": "mutated"},))
        with self.assertRaisesRegex(ValueError, "evaluator-only field"):
            observation.canonical_json()
        object.__setattr__(step, "arguments", {"evaluator_capability": "injected"})
        with self.assertRaisesRegex(ValueError, "evaluator-only field"):
            json.dumps(step.to_dict())

    def test_cyclic_deep_and_corrupted_payloads_fail_closed(self) -> None:
        task_id, oracle, capability, *_ = _bundle()
        cycle: dict[str, object] = {}
        cycle["self"] = cycle
        with self.assertRaisesRegex(ValueError, "cyclic actor payload"):
            AgentObservation(task_id, "Check input", (cycle,), (), {})

        deep: object = "leaf"
        for _ in range(70):
            deep = {"nested": deep}
        with self.assertRaisesRegex(ValueError, "nesting exceeds"):
            AgentObservation(task_id, "Check input", ({"data": deep},), (), {})

        object.__setattr__(oracle, "_sealed_payload", b"tampered evaluator payload")
        with self.assertRaisesRegex(ValueError, "does not match its seal"):
            oracle.open_payload(capability)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
