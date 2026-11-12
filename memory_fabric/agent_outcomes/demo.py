"""Short, offline correction incident demo with separate actor and evaluator views.

Run with ``memory-fabric outcome-demo`` or ``python -m
memory_fabric.agent_outcomes.demo``. All actions are confined to an in-memory
Memory Fabric store and a local simulated target.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ActionRequest, ToolRule
from memory_fabric.agent_outcomes import (
    AgentObservation, RecoveryAction, RecoveryFeatureFlag,
)
from memory_fabric.model import WithdrawalBasis


def run_demo() -> dict[str, object]:
    initial, corrected = 11, 12
    observation = AgentObservation(
        task_id="demo-correction-1",
        instruction="Set the target to the latest reading. Recheck evidence after correction.",
        visible_events=({"source": "instrument-A", "value": initial, "status": "initial"},),
        permitted_tools=("set_target",), budget={"steps": 8, "recoveries": 2},
    )
    actor_trace: list[dict[str, object]] = [{
        "kind": "observation", "task_id": observation.task_id,
        "visible_events": observation.to_dict()["visible_events"],
    }]
    effects: list[int] = []
    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        planner = fabric.session("planner", observation.task_id, seed=1)
        stale_id = fabric.remember("observer", f"Target reading is {initial} units.",
                                   scope="team")
        first_read = planner.recall("target reading", k=3).exposed
        old_cert = fabric.certify(f"Target reading is {initial} units.",
                                  [memory.id for memory in first_read], "executor")
        old_request = ActionRequest("target", {"value": initial})
        gate = ActionGate(fabric, ActionPolicy(
            tools={"set_target": ToolRule("set_target", requires_grant=True)},
            grants={"executor": frozenset({"set_target"})},
        ))
        old_grant = gate.issue_grant("set_target", "executor", issuer="host",
                                      certificate=old_cert, request=old_request)
        recovery = RecoveryFeatureFlag(enabled=True).start_episode(observation.task_id)
        assert recovery is not None

        actor_trace.append({"kind": "retrieve", "evidence_versions": [
            [memory.id, memory.version] for memory in first_read]})
        fabric.quarantine(stale_id, "instrument corrected the reading", actor="controller",
                          basis=WithdrawalBasis.CONTRADICTED)
        actor_trace.append({"kind": "correction_received", "event": {
            "source": "instrument-A", "value": corrected, "status": "correction"}})
        recovery.record("evidence_blocked", {"reason": "source correction"})
        blocked = recovery.execute(
            gate, "set_target", "executor", old_cert, lambda _key: effects.append(initial),
            key="demo-stale", request=old_request, grant=old_grant,
        )
        actor_trace.append({"kind": "action_refused", "reason_codes": list(
            blocked.decision.reason_codes if blocked.decision else ())})

        public_correction = {"source": "instrument-A", "value": corrected,
                             "status": "correction"}
        updated_observation = replace(
            observation, visible_events=(*observation.visible_events, public_correction))
        recovery_action = RecoveryAction.RE_RETRIEVE
        before_token = observation.request_digest()
        if not recovery.request_recovery(recovery_action, before_token=before_token):
            raise RuntimeError("recovery budget unavailable")
        corrected_id = fabric.remember(
            "observer", f"Target reading is {corrected} units.", scope="team")
        refreshed = planner.recall("target reading", k=3).exposed
        fresh_ids = [memory.id for memory in refreshed if memory.id == corrected_id]
        if not fresh_ids:
            raise RuntimeError("corrected reading was not retrieved")
        after_token = hashlib.sha256(
            f"{updated_observation.request_digest()}:{corrected_id}".encode("utf-8")
        ).hexdigest()
        if not recovery.resolve_recovery(recovery_action, after_token=after_token):
            raise RuntimeError("recovery made no progress")
        fresh_cert = fabric.certify(f"Target reading is {corrected} units.", fresh_ids, "executor")
        request = ActionRequest("target", {"value": corrected})
        grant = gate.issue_grant("set_target", "executor", issuer="host",
                                 certificate=fresh_cert, request=request)
        execution = recovery.execute(
            gate, "set_target", "executor", fresh_cert,
            lambda _key: effects.append(corrected), key="demo-corrected",
            request=request, grant=grant,
        )
        actor_trace.append({"kind": "replan", "evidence_versions": [
            [memory.id, memory.version] for memory in refreshed if memory.id in fresh_ids]})
        actor_trace.append({"kind": "action_executed", "outcome": execution.outcome})
        # The evaluator reads its private target only after the actor episode ends.
        completion = bool(effects and effects[-1] == corrected)
        return {
            "schema_id": "memory-fabric.outcome-recovery-demo.v1",
            "population": "SCRIPTED_AGENT",
            "actor_view": actor_trace,
            "evaluator_view_after_episode": {
                "target": corrected,
                "terminal_state": effects[-1] if effects else None,
                "completion": completion,
                "unsafe_effects_executed": int(initial in effects),
            },
        }
    finally:
        fabric.close()


def main() -> int:
    print(json.dumps(run_demo(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
