"""Scripted role actors use distinct sessions, declared tools, and typed steps."""

from __future__ import annotations

import hashlib
import json
import secrets
import unittest
from dataclasses import replace
from typing import Any
from unittest.mock import patch

from memory_fabric import MemoryFabric
from memory_fabric.adapters.ollama_typed import OllamaClient
from memory_fabric.actions_typed import ActionGate, ActionPolicy, ActionRequest, ToolRule
from memory_fabric.outcome_typed import AgentObservation, AgentStep
from memory_fabric.outcome_typed.observations import SCHEMA_ID
from memory_fabric.identity import ROLE_AGENT
from memory_fabric.service import MemoryService

from benchmarks.outcome_agents_typed import (
    ActorToolDenied, ExecutorActor, ObserverActor, OllamaAgentAdapter, PlannerActor,
    run_sequential_real_agent_team,
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


class SequentialTeamOllamaClient(OllamaClient):
    """Model-shaped responses for the sequential team contract, without HTTP."""

    def __init__(self) -> None:
        super().__init__(retries=0)
        self.actor_calls: dict[str, int] = {}
        self.user_observations: list[dict[str, object]] = []
        self.response_schemas: list[dict[str, Any]] = []

    def model_metadata(self, model):
        return {
            "requested_name": model, "name": model,
            "digest": "sha256:" + "c" * 64, "size": 123,
            "format": "gguf", "family": "qwen2", "parameter_size": "1.5B",
            "quantization_level": "Q4_K_M",
        }

    def _post(self, path, payload):
        if path != "/api/chat":
            raise AssertionError("team decisions must use Ollama chat")
        observation = json.loads(payload["messages"][-1]["content"])
        schema = payload["format"]
        actor_id = schema["properties"]["actor_id"]["const"]
        task_id = schema["properties"]["task_id"]["const"]
        call_number = self.actor_calls.get(actor_id, 0)
        self.actor_calls[actor_id] = call_number + 1
        self.user_observations.append(observation)
        self.response_schemas.append(schema)
        evidence_versions = schema["properties"]["evidence_versions"]["const"]
        if actor_id == "observer":
            intent = "inspect"
            arguments = {
                "tool": "remember_evidence",
                "content": "Instrument reading reports target 4.",
            }
        elif actor_id == "planner" and call_number == 0:
            intent = "retrieve"
            arguments = {"tool": "retrieve_evidence", "query": "target 4", "k": 5}
        elif actor_id == "planner":
            intent = "propose"
            arguments = {
                "tool": "propose_action", "action_tool": "set_target",
                "parameters": {"value": 4},
                "claim": "The visible instrument reports target 4.",
            }
        elif actor_id == "executor" and call_number == 0:
            intent = "inspect"
            arguments = {"tool": "certify_evidence"}
        else:
            intent = "propose"
            arguments = {"tool": "set_target", "parameters": {"value": 4}}
        step = {
            "schema_id": SCHEMA_ID,
            "task_id": task_id,
            "actor_id": actor_id,
            "step_id": schema["properties"]["step_id"]["const"],
            "intent": intent,
            "arguments": arguments,
            "evidence_versions": evidence_versions,
        }
        return {"message": {"content": json.dumps(step, sort_keys=True)},
                "prompt_eval_count": 40, "eval_count": 12}


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
            "step_id": "mf-step-" + hashlib.sha256(
                f"{self.observation.task_id}:executor:1".encode("utf-8")
            ).hexdigest()[:24],
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

        for override, message in (
            ({"step_id": "invented-step"}, "assigned step identifier"),
            ({"evidence_versions": [["invented-memory", 0]]},
             "visible evidence versions"),
        ):
            with self.subTest(override=override):
                adapter = OllamaAgentAdapter(
                    "executor", client=StubOllamaClient(self._reply(**override)))
                with self.assertRaisesRegex(ValueError, message):
                    adapter.next_step(self.observation)

        malformed = OllamaAgentAdapter(
            "executor", client=StubOllamaClient('{"schema_id":"unknown"}'))
        with self.assertRaisesRegex(ValueError, "fields do not match"):
            malformed.next_step(self.observation)

        truncated = OllamaAgentAdapter(
            "executor", client=StubOllamaClient(self._reply(), truncated=True))
        with self.assertRaisesRegex(ValueError, "output token limit"):
            truncated.next_step(self.observation)


class TestSequentialRealAgentTeam(unittest.TestCase):
    def test_three_model_identities_share_one_sequential_memory_backed_run(self) -> None:
        service = MemoryService(MemoryFabric(":memory:", auto_activate=True))
        self.addCleanup(service.close)
        for agent_id in ("observer", "planner", "executor"):
            service.register_agent(
                agent_id, key=secrets.token_bytes(32), tenant_id="team-tenant",
                roles=(ROLE_AGENT,),
            )
        observation = AgentObservation(
            task_id="sequential-team-task",
            instruction="Set the target to the visible instrument reading.",
            visible_events=({"source": "instrument", "reading": 4},),
            permitted_tools=(
                "remember_evidence", "retrieve_evidence", "propose_action",
                "certify_evidence", "set_target",
            ),
            budget={"steps": 5},
        )
        gate = ActionGate(service._fabric, ActionPolicy(
            tools={"set_target": ToolRule(
                "set_target", requires_grant=True, min_independent_sources=1,
            )},
            grants={"executor": frozenset({"set_target"})},
        ))
        client = SequentialTeamOllamaClient()
        effects: list[int] = []

        result = run_sequential_real_agent_team(
            service, observation, gate, lambda _key: effects.append(4),
            model="qwen2.5:1.5b", client=client, key="sequential-team-effect-1",
            seed=42,
        )

        report = json.loads(result.canonical_json())
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.actor_ids, ("observer", "planner", "executor"))
        self.assertEqual({step.actor_id for step in result.model_steps},
                         {"observer", "planner", "executor"})
        self.assertEqual([step.actor_id for step in result.model_steps], [
            "observer", "planner", "planner", "executor", "executor",
        ])
        self.assertEqual(len(client.calls), 5)
        self.assertEqual(report["model_calls"], 5)
        self.assertEqual(report["model_tokens"], 260)
        self.assertEqual(report["model_steps"][4]["arguments"]["parameters"]["value"], 4)
        self.assertTrue(report["shared_model_weights"])
        self.assertEqual(report["max_concurrent_model_calls"], 1)
        self.assertEqual(effects, [4])
        self.assertTrue(result.execution.ran)
        self.assertEqual(result.model_digest, "sha256:" + "c" * 64)
        canary = "private-team-content-canary-39b8"
        private_step = AgentStep(
            observation.task_id, "executor", "privacy-step", "propose",
            {"tool": "set_target", "private_content": canary},
        )
        private_report = json.loads(replace(
            result, model_steps=(*result.model_steps[:-1], private_step),
        ).canonical_json())
        self.assertNotIn(canary, json.dumps(private_report))
        self.assertEqual(
            private_report["model_steps"][-1]["arguments"]["private_content"],
            "[REDACTED]",
        )
        self.assertTrue(any(event.get("source") == "retrieved_memory"
                            for event in client.user_observations[2]["visible_events"]))
        executor_schema = client.response_schemas[4]
        self.assertEqual(
            executor_schema["properties"]["arguments"]["properties"]["parameters"],
            {"const": {"value": 4}},
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
