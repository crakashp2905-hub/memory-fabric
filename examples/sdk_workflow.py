"""Compose the typed SDK surfaces without bypassing the action gate.

Run from the repository root:

    python examples/sdk_workflow.py

The decision policy is deterministic and the evidence is a fixed fixture; the
example makes no hosted-model or network calls and performs no external effect.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from memory_fabric import MemoryFabric, correction  # noqa: E402
from memory_fabric.actions import ActionGate, ActionPolicy, ActionRequest, ToolRule  # noqa: E402
from memory_fabric.decision_models import (  # noqa: E402
    DecisionContext,
    DecisionOption,
    DeterministicDecisionModel,
)
from memory_fabric.sdk import agent, operator  # noqa: E402


def main() -> int:
    print("DEMO ONLY: deterministic policy and fixture; no hosted model or external effect.")
    fabric = MemoryFabric(":memory:", auto_activate=True, seed=0)
    effects: list[str] = []
    try:
        writer = agent(fabric, "maintenance-agent")
        reviewer = operator(fabric, "reviewer")

        memory_id = writer.remember("Pump P1 purge setting is 30 seconds.")
        reviewer.validate(memory_id)
        reviewer.share(memory_id, "team")
        recalled = writer.recall("Pump P1 purge setting", k=3)
        if not recalled or recalled[0].memory_id != memory_id:
            raise AssertionError("SDK recall did not return the reviewed fixture")
        print(f"add and recall: {recalled[0].content}")

        explanation = reviewer.explain(memory_id)
        print(f"explain: {explanation.narrative().splitlines()[0]}")

        options = (
            DecisionOption("restart", "Restart pump after the purge", action="restart_pump"),
            DecisionOption("wait", "Do not restart yet"),
        )
        context = DecisionContext(
            query="May Pump P1 be restarted?", options=options,
            evidence_ids=(memory_id,),
        )
        proposal = DeterministicDecisionModel({"restart": 1.0, "wait": 0.0}).decide(context)
        if proposal.selected != "restart":
            raise AssertionError("deterministic decision fixture did not select restart")
        print(f"decide: {proposal.selected} ({proposal.model_id}; proposal only)")

        gate = ActionGate(fabric, ActionPolicy(
            tools={"restart_pump": ToolRule("restart_pump")},
            grants={"maintenance-agent": frozenset({"restart_pump"})},
        ))
        certificate = fabric.certify("restart-P1", [memory_id], "maintenance-agent")
        request = ActionRequest("pump/P1", {"purge_seconds": 30})
        first = gate.execute(
            "restart_pump", "maintenance-agent", lambda _key: effects.append("restart"),
            certificate, key="sdk-demo-before-correction", request=request,
        )
        if first.outcome != "executed":
            raise AssertionError(f"expected the certified action to execute: {first.outcome}")
        print(f"safe execute before correction: {first.outcome}")

        replacement = writer.remember("Pump P1 purge setting is 45 seconds.")
        reviewer.validate(replacement)
        reviewer.share(replacement, "team")
        correction.apply(
            fabric, memory_id, reason="revised maintenance instruction", actor="reviewer"
        )
        second = gate.execute(
            "restart_pump", "maintenance-agent", lambda _key: effects.append("stale-restart"),
            certificate, key="sdk-demo-after-correction", request=request,
        )
        if second.outcome != "refused" or effects != ["restart"]:
            raise AssertionError("the stale action was not refused by the execution fence")
        print(f"correct and safe execute after correction: {second.outcome}")
        print(f"remaining effects: {effects}")
        return 0
    finally:
        fabric.close()


if __name__ == "__main__":
    raise SystemExit(main())
