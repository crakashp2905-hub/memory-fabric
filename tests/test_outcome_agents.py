from __future__ import annotations

import pytest

from benchmarks.outcome_agents import (
    ActorRole,
    ExecutorActor,
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
