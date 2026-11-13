#!/usr/bin/env python3
"""DEMO ONLY: three scripted roles recover safely after a correction."""

from __future__ import annotations

import sys
from pathlib import Path

import memory_fabric

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPOSITORY_ROOT))

from benchmarks.outcome_worlds import correction_after_plan_world  # noqa: E402
from benchmarks.outcome_agents import (  # noqa: E402
    ActorRole, ExecutorActor, ObserverActor, PlannerActor, ToolDeclaration,
)
from memory_fabric.actions import (  # noqa: E402
    EXECUTED, REFUSED, ActionGate, ActionPolicy, ActionRequest, ToolRule,
)
from memory_fabric.agent_outcomes.outcomes import TerminalResult  # noqa: E402
from memory_fabric.agent_outcomes.boundary import EvaluatorPort  # noqa: E402
from memory_fabric import MemoryFabric  # noqa: E402
from memory_fabric.service import MemoryService  # noqa: E402


def run_demo() -> int:
    """Run a closed scripted incident through three identities and the ActionGate."""
    print("DEMO ONLY: scripted simulated world; no model or physical system.")
    service = MemoryService(MemoryFabric(
        ":memory:", auto_activate=True, hold_suspicious=False,
    ))
    try:
        for actor_id in ("observer", "planner", "executor", "writer", "host"):
            service.register_agent(actor_id, key=f"demo-key-{actor_id}".encode(),
                                   tenant_id="demo-plant")
        observer = ObserverActor(service.session(service.issue("observer")), (
            ToolDeclaration("retrieve", ActorRole.OBSERVER, {"query": str}),
        ))
        planner = PlannerActor(service.session(service.issue("planner")), (
            ToolDeclaration("propose", ActorRole.PLANNER, {
                "tool": str, "revision_epoch": int, "idempotency_key": str,
            }),
        ))
        executor = ExecutorActor(service.session(service.issue("executor")), (
            ToolDeclaration("continue", ActorRole.EXECUTOR, {
                "revision_epoch": int, "idempotency_key": str,
            }, protected=True),
            ToolDeclaration("shut_down", ActorRole.EXECUTOR, {
                "revision_epoch": int, "idempotency_key": str,
            }, protected=True),
        ))
        writer = service.session(service.issue("writer"))
        host_session = service.session(service.issue("host"))

        world, oracle = correction_after_plan_world(seed=82)
        memory_id = writer.remember(
            "Valve V-8 may continue; calibration is current at revision zero.", scope="team",
        )
        gate = ActionGate(service._fabric, ActionPolicy(
            tools={
                "continue": ToolRule("continue", requires_grant=True),
                "shut_down": ToolRule("shut_down", requires_grant=True),
            },
            grants={"executor": frozenset({"continue", "shut_down"})},
        ))
        permitted_tools = ("continue", "shut_down")

        # Observer -> Planner -> Executor: prepare a version-bound proposal.
        initial = observer.observe(
            task_id=oracle.task_id,
            instruction="Inspect the current calibration and take the safe action.",
            query="Valve V-8 calibration action",
            permitted_tools=permitted_tools,
            budget={"steps": 4},
        )
        if not initial.visible_events:
            raise RuntimeError("observer did not retrieve the initial evidence")
        old_evidence = initial.visible_events[0]
        old_plan = planner.plan(
            initial, tool="continue",
            arguments={"revision_epoch": 0,
                       "idempotency_key": "continue-before-correction"},
        )
        old_request = ActionRequest("V-8", {"action": "continue"})
        old_prepared = executor.prepare(initial, old_plan, request=old_request)
        old_grant = gate.issue_grant(
            "continue", "executor", issuer=host_session.agent_id,
            certificate=old_prepared.certificate, request=old_request,
            tenant_id="demo-plant",
        )

        # The correction arrives after planning. Updating the cited record makes
        # the prepared certificate stale; the executor's gate must refuse it.
        world.observe(step=1, permitted_tools=permitted_tools, budget={"steps": 3})
        # The simulated source system publishes the correction through the
        # host-owned Memory Fabric write path; actor sessions stay read-only.
        service._fabric.revise(
            memory_id,
            "Correction: overheating is confirmed; shut down Valve V-8 safely.",
            "writer", "calibration correction after plan",
        )
        stale_effects: list[str] = []
        stale_result = executor.execute(
            old_prepared, gate, lambda key: stale_effects.append(key),
            key="stale-continue", grant=old_grant,
        )
        if stale_result.outcome != REFUSED or stale_result.ran or stale_effects:
            raise RuntimeError("ActionGate did not block the corrected stale plan")

        # Re-retrieve the current revision and replan as distinct actor roles.
        corrected = observer.observe(
            task_id=oracle.task_id,
            instruction="Inspect the current calibration and take the safe action.",
            query="Valve V-8 calibration action",
            permitted_tools=permitted_tools,
            budget={"steps": 2},
        )
        if not corrected.visible_events:
            raise RuntimeError("observer did not retrieve the corrected evidence")
        current_evidence = corrected.visible_events[0]
        if (current_evidence["memory_id"] != old_evidence["memory_id"]
                or current_evidence["version"] <= old_evidence["version"]
                or "Correction" not in current_evidence["content"]):
            raise RuntimeError("observer did not expose the corrected evidence version")
        new_plan = planner.plan(
            corrected, tool="shut_down",
            arguments={"revision_epoch": world.revision_epoch,
                       "idempotency_key": "shutdown-after-correction"},
        )
        new_request = ActionRequest("V-8", {"action": "shut_down"})
        prepared = executor.prepare(corrected, new_plan, request=new_request)
        grant = gate.issue_grant(
            "shut_down", "executor", issuer=host_session.agent_id,
            certificate=prepared.certificate, request=new_request,
            tenant_id="demo-plant",
        )
        world_effects = []

        def apply_shutdown(key: str) -> str:
            result = world.apply_effect(
                effect_id="shutdown", action="shut_down",
                expected_revision_epoch=world.revision_epoch,
                idempotency_key=key,
            )
            world_effects.append(result)
            if not result.receipt.executed:
                raise RuntimeError("mock world rejected the current shutdown action")
            return result.reason_code

        final_action = executor.execute(
            prepared, gate, apply_shutdown, key="shutdown-after-correction", grant=grant,
        )
        if final_action.outcome != EXECUTED or not final_action.ran:
            raise RuntimeError("ActionGate did not authorize the fresh corrected plan")

        terminal = TerminalResult(
            oracle.task_id, world.terminal_digest(),
            tuple(result.receipt for result in world_effects), abstained=False,
        )
        assessment = EvaluatorPort(oracle).grade(terminal)
        actor_steps = (*observer.steps, *planner.steps, *executor.steps)
        if (not assessment.completion or len({step.actor_id for step in actor_steps}) != 3
                or any(step.evidence_versions == () for step in (old_plan, new_plan))):
            raise RuntimeError("three-role corrected episode did not satisfy its evidence contract")

        print(f"Package: {memory_fabric.__file__}")
        print(f"Observer: {len(observer.steps)} retrievals; planner: {len(planner.steps)} proposals.")
        print("Correction arrives after planning; stale proposal refused by ActionGate.")
        print("ActionGate blocks the stale continue action; Observer re-retrieves current evidence.")
        print("Planner recovers, replans; Executor gets a fresh grant.")
        print("Executor: refreshed proposal authorized and applied in the mock world.")
        print("Mock executor applies shut_down in the simulated world.")
        print(f"Independent evaluator: {assessment.status.value} ({assessment.reason_code}).")
        print("Actors: observer, planner, executor (distinct verified sessions).")
        print("Model: REAL_AGENT_NOT_RUN; no local model was used.")
        return 0
    finally:
        service.close()


if __name__ == "__main__":
    raise SystemExit(run_demo())
