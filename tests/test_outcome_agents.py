from __future__ import annotations

import json

import pytest

from benchmarks.outcome_agents import (
    ActorRole,
    ExecutorActor,
    OllamaOutcomePlanner,
    ObserverActor,
    PlannerActor,
    ToolDeclaration,
)
from memory_fabric import MemoryFabric
from memory_fabric.service import MemoryService


def test_three_roles_use_distinct_sessions_tools_and_logged_steps() -> None:
    service = MemoryService(MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False))
    try:
        for actor_id in ("observer", "planner", "executor", "writer"):
            service.register_agent(actor_id, key=f"key-{actor_id}".encode(), tenant_id="plant-a")
        observer_session = service.session(service.issue("observer"))
        planner_session = service.session(service.issue("planner"))
        executor_session = service.session(service.issue("executor"))
        writer = service.session(service.issue("writer"))
        writer.remember("Valve V-8 is in the closed position.", scope="team")

        observer = ObserverActor(observer_session, (
            ToolDeclaration("retrieve", ActorRole.OBSERVER, {"query": str}),
        ))
        planner = PlannerActor(planner_session, (
            ToolDeclaration("propose", ActorRole.PLANNER,
                            {"tool": str, "target": str, "position": str}),
        ))
        executor = ExecutorActor(executor_session, (
            ToolDeclaration("set_valve", ActorRole.EXECUTOR,
                            {"target": str, "position": str}, protected=True),
        ))

        observation = observer.observe(
            task_id="valve-task", instruction="Close valve V-8.", query="Valve V-8",
            permitted_tools=("set_valve",), budget={"steps": 4},
        )
        proposal = planner.plan(
            observation, tool="set_valve", arguments={"target": "V-8", "position": "closed"}
        )
        accepted = executor.accept(observation, proposal)

        assert observer.actor_id == "observer"
        assert planner.actor_id == "planner"
        assert executor.actor_id == "executor"
        assert observer.permitted_tools == ("retrieve",)
        assert planner.permitted_tools == ("propose",)
        assert executor.permitted_tools == ("set_valve",)
        assert [observer.steps[0].intent, proposal.intent, accepted.intent] == [
            "retrieve", "propose", "propose",
        ]
        assert observer.steps[0].evidence_versions
        assert len({step.actor_id for step in (
            observer.steps[0], proposal, accepted,
        )}) == 3
        assert "truth" not in observation.canonical_json()
    finally:
        service.close()


def test_local_model_step_flows_through_observer_planner_executor_identities() -> None:
    class StubOllama:
        host = "http://127.0.0.1:11434"

        def __init__(self) -> None:
            self.calls = []

        def chat(self, model, messages, **kwargs):
            self.calls.append((model, messages, kwargs))
            event = json.loads(messages[1]["content"])["visible_events"][0]
            return {"message": {"content": json.dumps({
                "intent": "propose", "tool": "set_valve",
                "arguments": {"target": "V-8", "position": "closed"},
                "evidence_versions": [[event["memory_id"], event["version"]]],
            })}}

    service = MemoryService(MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False))
    try:
        for actor_id in ("observer", "planner", "executor", "writer"):
            service.register_agent(actor_id, key=f"key-{actor_id}".encode(), tenant_id="plant-a")
        observer = ObserverActor(service.session(service.issue("observer")), (
            ToolDeclaration("retrieve", ActorRole.OBSERVER, {"query": str}),
        ))
        planner = PlannerActor(service.session(service.issue("planner")), (
            ToolDeclaration("propose", ActorRole.PLANNER,
                            {"tool": str, "target": str, "position": str}),
        ))
        executor = ExecutorActor(service.session(service.issue("executor")), (
            ToolDeclaration("set_valve", ActorRole.EXECUTOR,
                            {"target": str, "position": str}),
        ))
        writer = service.session(service.issue("writer"))
        writer.remember("Valve V-8 is in the closed position.", scope="team")
        order = ["observer.retrieve"]
        observation = observer.observe(
            task_id="local-agent-chain", instruction="Inspect Valve V-8 and report its position.",
            query="Valve V-8 position", permitted_tools=("set_valve",), budget={"steps": 3},
        )
        model = StubOllama()
        local_planner = OllamaOutcomePlanner(
            "qwen2.5:3b", model,
            tool_argument_types={"set_valve": {"target": str, "position": str}},
        )
        order.append("planner.model_decide")
        model_step = local_planner.decide(
            observation, actor_id=planner.actor_id, step_id="local-agent-chain:planner:1",
        )
        planner_step = planner.accept_model_step(observation, model_step)
        order.append("executor.accept")
        executor_step = executor.accept(observation, planner_step)

        assert order == ["observer.retrieve", "planner.model_decide", "executor.accept"]
        assert len(model.calls) == 1
        assert planner_step.actor_id == planner.actor_id
        assert executor_step.actor_id == executor.actor_id
        assert len({observer.steps[0].actor_id, planner_step.actor_id,
                    executor_step.actor_id}) == 3
        assert planner_step.evidence_versions == (
            (observation.visible_events[0]["memory_id"], observation.visible_events[0]["version"]),
        )
        assert "truth" not in observation.canonical_json()
    finally:
        service.close()


def test_roles_reject_foreign_tools_and_malformed_declarations() -> None:
    service = MemoryService(MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False))
    try:
        service.register_agent("planner", key=b"planner", tenant_id="plant-a")
        session = service.session(service.issue("planner"))
        planner = PlannerActor(session, (
            ToolDeclaration("propose", ActorRole.PLANNER, {"tool": str}),
        ))
        observation = ObserverActor(
            service.session(service.issue("planner")),
            (ToolDeclaration("retrieve", ActorRole.OBSERVER, {"query": str}),),
        ).observe(task_id="role-check", instruction="Inspect.", query="none",
                  permitted_tools=("known",), budget={"steps": 1})

        with pytest.raises(PermissionError, match="outside the observation"):
            planner.plan(observation, tool="admin_override")
        with pytest.raises(ValueError, match="own role"):
            PlannerActor(session, (
                ToolDeclaration("retrieve", ActorRole.OBSERVER, {"query": str}),
            ))
    finally:
        service.close()


def test_three_agent_correction_demo_reauthorizes_and_completes(capsys) -> None:
    from examples.outcome_recovery_demo import run_demo

    assert run_demo() == 0
    output = capsys.readouterr().out
    assert "Observer: 2 retrievals; planner: 2 proposals." in output
    assert "stale proposal refused by ActionGate" in output
    assert "refreshed proposal authorized and applied in the mock world" in output
    assert "Independent evaluator: COMPLETED" in output
    assert "Actors: observer, planner, executor (distinct verified sessions)." in output
    assert "REAL_AGENT_NOT_RUN" in output
