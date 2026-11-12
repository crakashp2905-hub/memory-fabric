"""Scripted role actors use distinct sessions, declared tools, and typed steps."""

from __future__ import annotations

import json
import secrets
import unittest
from unittest.mock import patch

from memory_fabric import MemoryFabric
from memory_fabric.adapters.ollama import OllamaClient
from memory_fabric.actions import ActionGate, ActionPolicy, ActionRequest, ToolRule
from memory_fabric.agent_outcomes import AgentObservation, AgentStep
from memory_fabric.agent_outcomes.observations import SCHEMA_ID
from memory_fabric.identity import ROLE_AGENT
from memory_fabric.service import MemoryService

from benchmarks.outcome_agents import (
    ActorToolDenied, ExecutorActor, ObserverActor, OllamaAgentAdapter, PlannerActor,
)


class StubOllamaClient:
    def __init__(self, content: str, *, truncated: bool = False) -> None:
        self.content = content
        self.truncated = truncated
        self.calls: list[dict[str, object]] = []
        self.metadata = {
            "requested_name": "qwen2.5:3b", "name": "qwen2.5:3b",
            "digest": "sha256:" + "a" * 64, "size": 123,
            "format": "gguf", "family": "qwen2", "parameter_size": "3B",
            "quantization_level": "Q4_K_M",
        }

    def model_metadata(self, model):
        return {**self.metadata, "requested_name": model, "name": model}

    def chat(self, model, messages, tools=None, temperature=0.0, num_predict=256, schema=None,
             think=None, top_p=None, num_ctx=None, seed=None):
        self.calls.append({"model": model, "messages": list(messages), "tools": tools,
                           "temperature": temperature, "num_predict": num_predict,
                           "schema": schema, "truncated": self.truncated, "think": think,
                           "top_p": top_p, "num_ctx": num_ctx, "seed": seed})
        return {"message": {"content": self.content}}


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


class TestOllamaOutcomeAgentAdapter(unittest.TestCase):
    def setUp(self) -> None:
        self.observation = AgentObservation(
            task_id="ollama-task-1",
            instruction="Set the target using the visible instrument reading.",
            visible_events=({"source": "instrument", "reading": 4},),
            permitted_tools=("inspect", "set_target"),
            budget={"steps": 3},
        )

    def _reply(self, **overrides: object) -> str:
        step: dict[str, object] = {
            "schema_id": SCHEMA_ID,
            "task_id": self.observation.task_id,
            "actor_id": "executor",
            "step_id": "executor-step-1",
            "intent": "propose",
            "arguments": {"tool": "set_target", "value": 4},
            "evidence_versions": [],
        }
        step.update(overrides)
        return json.dumps(step, sort_keys=True, separators=(",", ":"))

    def test_ollama_adapter_uses_only_public_observation_and_returns_typed_step(self) -> None:
        client = StubOllamaClient(self._reply())
        adapter = OllamaAgentAdapter("executor", model="qwen2.5:3b", client=client)

        step = adapter.next_step(self.observation)

        self.assertIsInstance(step, AgentStep)
        self.assertEqual((step.task_id, step.actor_id, step.intent),
                         (self.observation.task_id, "executor", "propose"))
        self.assertEqual(step.arguments["tool"], "set_target")
        self.assertFalse(hasattr(adapter, "fabric"))
        self.assertFalse(hasattr(adapter, "oracle"))
        call = client.calls[0]
        self.assertEqual(call["model"], "qwen2.5:3b")
        self.assertEqual(call["tools"], None)
        self.assertEqual((call["temperature"], call["top_p"], call["seed"],
                          call["num_ctx"], call["num_predict"]),
                         (0.0, 0.9, 0, 4096, 256))
        self.assertEqual(len(call["schema"]["required"]), 7)  # type: ignore[index]
        arguments_schema = call["schema"]["properties"]["arguments"]  # type: ignore[index]
        self.assertIn("tool", arguments_schema["required"])
        self.assertEqual(arguments_schema["properties"]["tool"]["enum"],
                         ["inspect", "set_target", "abstain"])
        messages = call["messages"]
        user_messages = [message for message in messages if message["role"] == "user"]  # type: ignore[union-attr]
        self.assertEqual(len(user_messages), 1)
        self.assertEqual(user_messages[0]["content"], self.observation.canonical_json())
        self.assertNotIn("truth", user_messages[0]["content"])

    def test_ollama_adapter_uses_the_existing_client_and_records_call_usage(self) -> None:
        client = OllamaClient(retries=0)
        reply = {"message": {"content": self._reply()},
                 "prompt_eval_count": 17, "eval_count": 9}
        with patch.object(client, "_post", return_value=reply):
            with patch.object(client, "model_metadata", return_value={
                    "requested_name": "qwen2.5:3b", "name": "qwen2.5:3b",
                    "digest": "sha256:" + "a" * 64, "size": 123,
                    "format": "gguf", "family": "qwen2", "parameter_size": "3B",
                    "quantization_level": "Q4_K_M"}):
                adapter = OllamaAgentAdapter("executor", model="qwen2.5:3b", client=client)
                step = adapter.next_step(self.observation)

        self.assertEqual(step.intent, "propose")
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(adapter.calls[0].model, "qwen2.5:3b")
        self.assertEqual(adapter.calls[0].tokens, 26)

    def test_ollama_adapter_rejects_wrong_task_actor_and_unpermitted_tool(self) -> None:
        for override in (
            {"task_id": "another-task"},
            {"actor_id": "planner"},
        ):
            with self.subTest(override=override):
                adapter = OllamaAgentAdapter(
                    "executor", client=StubOllamaClient(self._reply(**override)))
                with self.assertRaises(ValueError):
                    adapter.next_step(self.observation)

        adapter = OllamaAgentAdapter(
            "executor", client=StubOllamaClient(self._reply(
                arguments={"tool": "erase_store", "value": 4},
            )))
        with self.assertRaises(ActorToolDenied):
            adapter.next_step(self.observation)

        malformed = OllamaAgentAdapter(
            "executor", client=StubOllamaClient('{"schema_id":"unknown"}'))
        with self.assertRaisesRegex(ValueError, "fields do not match"):
            malformed.next_step(self.observation)

        truncated = OllamaAgentAdapter(
            "executor", client=StubOllamaClient(self._reply(), truncated=True))
        with self.assertRaisesRegex(ValueError, "output token limit"):
            truncated.next_step(self.observation)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
