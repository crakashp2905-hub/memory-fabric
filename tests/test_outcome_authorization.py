from __future__ import annotations

import pytest

from benchmarks.outcome_agents import (
    ActorRole, ExecutorActor, PlannerActor, ToolDeclaration,
)
from memory_fabric import MemoryFabric
from memory_fabric.actions import (
    GRANT_REVOKED, REFUSED, ActionGate, ActionPolicy, ActionRequest, ToolRule,
)
from memory_fabric.agent_outcomes import RecoveryEpisode
from memory_fabric.agent_outcomes.observations import AgentObservation
from memory_fabric.service import MemoryService


@pytest.mark.parametrize("invalidation", ["cross_tenant", "erased", "stale", "revoked"])
def test_recovery_never_overrides_action_gate_for_invalid_evidence(invalidation: str) -> None:
    fabric = MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False)
    try:
        memory_id = fabric.remember(
            "operator", "Pump P-7 pressure is within the safe range.", tenant_id="tenant-a"
        )
        certificate = fabric.certify(
            "pressure_safe", [memory_id], "operator", tenant_id="tenant-a"
        )
        gate = ActionGate(fabric, ActionPolicy(
            tools={"start_pump": ToolRule("start_pump")},
            grants={"operator": frozenset({"start_pump"})},
        ))
        effects: list[str] = []

        if invalidation == "cross_tenant":
            tenant_id = "tenant-b"
        else:
            tenant_id = "tenant-a"
            if invalidation == "erased":
                fabric.erase_content(memory_id, "subject request")
            elif invalidation == "stale":
                fabric.revise(memory_id, "Pump P-7 pressure is now unknown.", "operator",
                              "reading corrected")
            elif invalidation == "revoked":
                fabric.quarantine(memory_id, "reading withdrawn", actor="reviewer")

        episode = RecoveryEpisode(f"task-{invalidation}", enabled=True)
        assert episode.record("re_retrieve", {"progress_key": f"refresh-{invalidation}"})
        result = episode.execute(
            gate, "start_pump", "operator", certificate,
            lambda key: effects.append(key), key=f"effect-{invalidation}",
            tenant_id=tenant_id,
        )

        assert result.outcome == REFUSED
        assert result.ran is False
        assert effects == []
        assert episode.status.value == "BLOCKED"
        assert episode.trace[-1]["kind"] == "action_gate"
        assert episode.trace[-1]["reason_codes"]
    finally:
        fabric.close()


def _prepared_action():
    service = MemoryService(MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False))
    for actor_id in ("planner", "executor", "writer", "host"):
        service.register_agent(actor_id, key=f"key-{actor_id}".encode(), tenant_id="plant-a")
    writer = service.session(service.issue("writer"))
    planner_session = service.session(service.issue("planner"))
    executor_session = service.session(service.issue("executor"))
    memory_id = writer.remember("Valve V-8 is in the closed position.", scope="team")
    observation = AgentObservation(
        "valve-task", "Set valve V-8 closed.",
        ({"memory_id": memory_id, "version": 1,
          "content": "Valve V-8 is in the closed position."},),
        ("set_valve",), {"steps": 3},
    )
    planner = PlannerActor(planner_session, (
        ToolDeclaration("propose", ActorRole.PLANNER,
                        {"tool": str, "target": str, "position": str}),
    ))
    executor = ExecutorActor(executor_session, (
        ToolDeclaration("set_valve", ActorRole.EXECUTOR,
                        {"target": str, "position": str}, protected=True),
    ))
    plan = planner.plan(
        observation, tool="set_valve", arguments={"target": "V-8", "position": "closed"}
    )
    request = ActionRequest("V-8", {"position": "closed"})
    prepared = executor.prepare(observation, plan, request=request)
    gate = ActionGate(service._fabric, ActionPolicy(
        tools={"set_valve": ToolRule("set_valve", requires_grant=True)},
        grants={"executor": frozenset({"set_valve"})},
    ))
    grant = gate.issue_grant(
        "set_valve", "executor", issuer="host", certificate=prepared.certificate,
        request=request, tenant_id="plant-a",
    )
    return service, executor, gate, prepared, grant, memory_id, request


def test_executor_binds_action_to_planned_evidence_and_exact_typed_grant() -> None:
    service, executor, gate, prepared, grant, _memory_id, _request = _prepared_action()
    try:
        effects: list[str] = []
        result = executor.execute(
            prepared, gate, lambda key: effects.append(key), key="valve-once", grant=grant,
        )

        assert result.ran is True
        assert effects == ["valve-once"]
        assert executor.executions[-1].ran is True
        assert executor.executions[-1].step.evidence_versions == prepared.evidence_versions
    finally:
        service.close()


def test_gate_refuses_evidence_changed_after_executor_preparation() -> None:
    service, executor, gate, prepared, grant, memory_id, _request = _prepared_action()
    try:
        service._fabric.revise(memory_id, "Valve V-8 is now open.", "writer", "state changed")
        effects: list[str] = []
        result = executor.execute(
            prepared, gate, lambda key: effects.append(key), key="stale-plan", grant=grant,
        )

        assert result.outcome == REFUSED
        assert result.ran is False
        assert effects == []
        assert executor.executions[-1].reason_codes
    finally:
        service.close()


def test_revoked_typed_grant_is_refused_and_strings_are_not_accepted() -> None:
    service, executor, gate, prepared, grant, _memory_id, _request = _prepared_action()
    try:
        with pytest.raises(TypeError, match="typed Grant"):
            executor.execute(prepared, gate, lambda _key: None, key="string-grant",
                             grant=grant.grant_id)
        gate.revoke_grant(grant.grant_id, issuer="host")
        effects: list[str] = []
        result = executor.execute(
            prepared, gate, lambda key: effects.append(key), key="revoked-grant", grant=grant,
        )

        assert result.outcome == REFUSED
        assert result.decision is not None
        assert result.decision.reason_code == GRANT_REVOKED
        assert effects == []
    finally:
        service.close()
