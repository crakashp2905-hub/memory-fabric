"""Qualify per-effect authorization, retries and payload binding for Code Mode."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric import MemoryFabric  # noqa: E402
from memory_fabric.actions import (  # noqa: E402
    ALREADY_EXECUTED,
    EXECUTED,
    FAILED,
    IDEMPOTENCY_CONFLICT,
    REFUSED,
    ActionGate,
    ActionPolicy,
    ToolRule,
)
from memory_fabric.service import MemoryService  # noqa: E402
from memory_fabric.tool_protocol import (  # noqa: E402
    CodeModePlan,
    GovernedToolCall,
    GovernedToolRuntime,
)


def _fixture() -> tuple[MemoryFabric, MemoryService, Any, ActionGate, str, Any]:
    fabric = MemoryFabric(":memory:", auto_activate=True)
    service = MemoryService(fabric=fabric)
    service.register_agent("operator", key=b"n6-08-integration-key", tenant_id="tenant-1")
    session = service.session(service.issue("operator"))
    evidence_id = fabric.remember("reviewer", "Dispatch authorization evidence is valid.",
                                  tenant_id="tenant-1", scope="team")
    fabric.validate(evidence_id, actor="reviewer")
    certificate = fabric.certify("dispatch-approved", [evidence_id], "operator",
                                 tenant_id="tenant-1")
    gate = ActionGate(fabric, ActionPolicy(
        tools={"dispatch": ToolRule("dispatch")},
        grants={"operator": frozenset({"dispatch"})},
    ))
    return fabric, service, session, gate, evidence_id, certificate


def evaluate() -> dict[str, Any]:
    # A failed external effect is an uncertain outcome. Retrying the exact
    # plan after its evidence is withdrawn must reauthorize and refuse.
    fabric, service, session, gate, evidence_id, certificate = _fixture()
    events: list[str] = []
    fail_plan = CodeModePlan.parse('dispatch(target="pump-7", setpoint=40)')
    runtime = GovernedToolRuntime(gate, {
        "dispatch": lambda **_args: (events.append("attempt"),
                                      (_ for _ in ()).throw(RuntimeError("lost reply")))[1],
    })
    try:
        first = fail_plan.execute(runtime, agent_id="operator", session=session,
                                  certificate=certificate, tenant_id="tenant-1")[0]
        fabric.quarantine(evidence_id, actor="reviewer", reason="evidence withdrawn")
        retry = fail_plan.execute(runtime, agent_id="operator", session=session,
                                  certificate=certificate, tenant_id="tenant-1",
                                  retry=True)[0]
        retry_case = {
            "first_outcome": first.outcome,
            "retry_outcome": retry.outcome,
            "retry_reason_codes": list(retry.decision.reason_codes) if retry.decision else [],
            "effects": len(events),
            "same_key": fail_plan.calls[0].idempotency_key ==
                        CodeModePlan.parse('dispatch(target="pump-7", setpoint=40)').calls[0].idempotency_key,
        }
    finally:
        service.close()

    # An injected argument value paired with the old key cannot inherit the
    # original authorization; ActionGate binds the canonical ActionRequest.
    fabric, service, session, gate, _evidence_id, certificate = _fixture()
    effects: list[dict[str, Any]] = []
    runtime = GovernedToolRuntime(gate, {"dispatch": lambda **args: effects.append(args) or "ok"})
    plan = CodeModePlan.parse('dispatch(target="pump-7", setpoint=40)')
    try:
        executed = plan.execute(runtime, agent_id="operator", session=session,
                                certificate=certificate, tenant_id="tenant-1")[0]
        replay = plan.execute(runtime, agent_id="operator", session=session,
                              certificate=certificate, tenant_id="tenant-1")[0]
        original = plan.calls[0]
        injected = GovernedToolCall(original.tool,
                                    {**original.arguments, "setpoint": 99},
                                    original.idempotency_key,
                                    original.program_digest)
        changed = runtime.execute(injected, agent_id="operator", session=session,
                                  certificate=certificate, tenant_id="tenant-1")
        argument_case = {
            "first_outcome": executed.outcome,
            "identical_replay_outcome": replay.outcome,
            "injected_argument_outcome": changed.outcome,
            "injected_argument_error": changed.error,
            "effects": effects,
        }
    finally:
        service.close()

    passed = (
        retry_case["first_outcome"] == FAILED
        and retry_case["retry_outcome"] == REFUSED
        and retry_case["effects"] == 1
        and argument_case["first_outcome"] == EXECUTED
        and argument_case["identical_replay_outcome"] == ALREADY_EXECUTED
        and argument_case["injected_argument_outcome"] == REFUSED
        and argument_case["injected_argument_error"] == IDEMPOTENCY_CONFLICT
        and len(argument_case["effects"]) == 1
    )
    return {
        "schema": "memory-fabric-n6-08-code-mode-effect-authorization/1",
        "task_id": "N6-08", "acceptance_passed": passed, "evidence_level": "INTERNAL_INTEGRATION",
        "retry_after_evidence_change": retry_case,
        "injected_argument_binding": argument_case,
        "source": {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                check=True, capture_output=True,
                                                text=True).stdout.strip(),
                   "experiment_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "limitations": [
            "External effects are represented by deterministic in-memory handlers; no production service is called.",
            "A failed handler has an uncertain external outcome; retry safety still depends on the external system honoring the idempotency key.",
            "An already executed identical replay is suppressed as ALREADY_EXECUTED and does not execute a second effect.",
        ],
    }


if __name__ == "__main__":
    report = evaluate()
    (ROOT / "research" / "results" / "n6-08-code-mode-effect-authorization.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"task_id": report["task_id"],
                      "retry": report["retry_after_evidence_change"]["retry_outcome"],
                      "injected": report["injected_argument_binding"]["injected_argument_outcome"],
                      "acceptance_passed": report["acceptance_passed"]}, indent=2))
