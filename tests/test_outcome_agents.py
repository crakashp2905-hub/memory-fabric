"""Scripted role actors use distinct sessions, declared tools, and typed steps."""

from __future__ import annotations

import secrets
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ActionRequest, ToolRule
from memory_fabric.agent_outcomes import AgentObservation, AgentStep
from memory_fabric.identity import ROLE_AGENT
from memory_fabric.service import MemoryService

from benchmarks.outcome_agents import (
    ActorToolDenied, ExecutorActor, ObserverActor, PlannerActor,
)


class TestScriptedOutcomeActors(unittest.TestCase):
    def setUp(self) -> None:
        self.service = MemoryService(MemoryFabric(":memory:", auto_activate=True))
        self.addCleanup(self.service.close)
        for name in ("observer", "planner", "executor"):
            self.service.register_agent(name, key=secrets.token_bytes(32),
                                        tenant_id="tenant-outcome-actors",
                                        roles=(ROLE_AGENT,))
        self.observation = AgentObservation(
            task_id="pump-alpha-target",
            instruction="Use the current observations to set pump alpha's target.",
            visible_events=(),
            permitted_tools=(
                "remember_evidence", "retrieve_evidence", "propose_action",
                "certify_evidence", "set_target",
            ),
            budget={"steps": 12, "recoveries": 2},
        )
        self.observer = ObserverActor(
            self.service.session(self.service.issue("observer")), self.observation)
        self.planner = PlannerActor(
            self.service.session(self.service.issue("planner")), self.observation)
        self.executor = ExecutorActor(
            self.service.session(self.service.issue("executor")), self.observation)

    def test_distinct_roles_complete_steps_and_execute_only_through_the_gate(self) -> None:
        first_id, _ = self.observer.remember("Pump alpha target setting is 4.")
        second_id, _ = self.observer.remember(
            "Independent instrument confirms pump alpha target 4.")
        observer_hits, _ = self.observer.retrieve("pump alpha target 4", k=3)
        planner_hits, _ = self.planner.retrieve("pump alpha target 4", k=3)
        self.assertEqual({memory.id for memory in observer_hits}, {first_id, second_id})
        self.assertEqual({memory.id for memory in planner_hits}, {first_id, second_id})

        plan = self.planner.propose(
            "set_target", {"value": 4}, planner_hits,
            claim="Pump alpha should use the currently observed target of 4.",
        )
        fabric = self.service._fabric
        gate = ActionGate(fabric, ActionPolicy(
            tools={"set_target": ToolRule(
                "set_target", requires_grant=True, min_independent_sources=2)},
            grants={"executor": frozenset({"set_target"})},
        ))
        certificate = self.executor.certify(plan)
        request = ActionRequest(plan.tool, plan.parameters)
        grant = gate.issue_grant(
            plan.tool, self.executor.actor_id, issuer="host", certificate=certificate,
            request=request, tenant_id=self.executor.tenant_id,
        )
        effects: list[int] = []
        execution = self.executor.execute(
            plan, certificate, gate, grant,
            lambda _key: effects.append(plan.parameters["value"]),
            key="pump-alpha-target-1",
        )

        self.assertTrue(execution.ran)
        self.assertEqual(effects, [4])
        for actor, expected_id in (
            (self.observer, "observer"), (self.planner, "planner"),
            (self.executor, "executor"),
        ):
            with self.subTest(actor=expected_id):
                self.assertEqual(actor.actor_id, expected_id)
                self.assertGreaterEqual(len(actor.steps), 2)
                self.assertTrue(all(isinstance(step, AgentStep) for step in actor.steps))
                self.assertTrue(all(step.actor_id == expected_id for step in actor.steps))
                self.assertEqual(len({step.step_id for step in actor.steps}), len(actor.steps))
        self.assertNotIn("Pump alpha target setting is 4.",
                         self.observer.steps[0].canonical_json())

    def test_actor_roles_and_task_declarations_reject_undeclared_tools(self) -> None:
        with self.assertRaises(ActorToolDenied):
            self.planner.require_tool("remember_evidence", {"content": "not permitted"})
        with self.assertRaises(ActorToolDenied):
            self.observer.require_tool("set_target", {"value": 4})
        with self.assertRaises(ActorToolDenied):
            self.planner.propose(
                "unknown_privileged_tool", {"value": 4}, (), claim="unsafe",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
