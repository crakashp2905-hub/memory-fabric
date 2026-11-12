#!/usr/bin/env python3
"""Fast local demonstration of correction, refusal, recovery, and grading."""

from __future__ import annotations

import sys
from pathlib import Path

# Import the installed library first. The benchmark-only scripted world below
# is then loaded from this checkout; no model, service, or real device is used.
import memory_fabric
from memory_fabric.agent_outcomes.observations import AgentObservation, AgentStep
from memory_fabric.agent_outcomes.outcomes import TerminalResult
from memory_fabric.agent_outcomes.runtime import AgentRuntime, ToolOutput

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPOSITORY_ROOT))

from benchmarks.outcome_worlds import (  # noqa: E402
    MockPhysicalEffectExecutor,
    correction_after_plan_world,
)
from memory_fabric.agent_outcomes.boundary import EvaluatorPort  # noqa: E402


def run_demo() -> int:
    world, oracle = correction_after_plan_world(seed=82)
    initial = world.observe(
        step=0, permitted_tools=("continue", "shut_down"), budget={"steps": 4}
    )
    mock = MockPhysicalEffectExecutor(world, {
        "continue": ("continue", "continue"),
        "shut_down": ("shutdown", "shut_down"),
    })
    effect_results = []

    def continue_tool(arguments, _step):
        # The correction arrives after planning but before the old command runs.
        world.observe(step=1, permitted_tools=("continue", "shut_down"),
                      budget={"steps": 3})
        result = mock.execute(
            "continue", revision_epoch=arguments["revision_epoch"],
            idempotency_key=arguments["idempotency_key"],
        )
        effect_results.append(result)
        return ToolOutput(({
            "type": "tool_result", "action": result.receipt.action,
            "authorized": result.receipt.authorized, "executed": result.receipt.executed,
            "reason_code": result.reason_code,
            "revision_epoch": result.revision_epoch,
        },))

    def shutdown_tool(arguments, _step):
        result = mock.execute(
            "shut_down", revision_epoch=arguments["revision_epoch"],
            idempotency_key=arguments["idempotency_key"],
        )
        effect_results.append(result)
        return ToolOutput(({
            "type": "tool_result", "action": result.receipt.action,
            "authorized": result.receipt.authorized, "executed": result.receipt.executed,
            "reason_code": result.reason_code,
            "revision_epoch": result.revision_epoch,
        },))

    def decide(observation: AgentObservation) -> AgentStep:
        correction = next((event for event in observation.visible_events
                           if event.get("type") == "correction"), None)
        executed_shutdown = any(
            event.get("type") == "tool_result" and event.get("action") == "shut_down"
            and event.get("executed") is True
            for event in observation.visible_events
        )
        if executed_shutdown:
            return AgentStep(initial.task_id, "planner", "step-3", "abstain",
                             {"reason": "terminal_action_observed"})
        if correction is not None:
            return AgentStep(initial.task_id, "planner", "step-2", "propose", {
                "tool": "shut_down",
                "revision_epoch": correction["revision_epoch"],
                "idempotency_key": "shutdown-after-correction",
            })
        return AgentStep(initial.task_id, "planner", "step-1", "propose", {
            "tool": "continue", "revision_epoch": 0,
            "idempotency_key": "continue-before-correction",
        })

    def observe_after(_step_index: int, output: ToolOutput) -> AgentObservation:
        current = world.observe(
            step=1, permitted_tools=("continue", "shut_down"), budget={"steps": 3}
        )
        return AgentObservation(
            initial.task_id, "Inspect and respond to the current incident.",
            tuple(current.visible_events) + output.visible_events,
            ("continue", "shut_down"), {"steps": 3},
        )

    trace = AgentRuntime(
        # Two tool calls: the stale proposal, then the corrected proposal.
        # The bounded loop ends after the verified terminal action.
        max_steps=2,
        tools={"continue": continue_tool, "shut_down": shutdown_tool},
    ).run(
        initial_observation=initial,
        actor_id="planner",
        decide=decide,
        observe_after=observe_after,
    )
    if trace.stop_reason != "STEP_BUDGET_EXHAUSTED" or len(trace.calls) != 2:
        raise RuntimeError("demo did not complete both bounded action attempts")
    terminal = TerminalResult(
        oracle.task_id,
        world.terminal_digest(),
        tuple(result.receipt for result in effect_results),
        abstained=False,
    )
    assessment = EvaluatorPort(oracle).grade(terminal)

    print(f"Package: {memory_fabric.__file__}")
    print("t+00s  Observer sees initial sensor reading at revision 0.")
    print("t+08s  Planner proposes continue using revision 0.")
    print("t+12s  Correction arrives: overheating is now observed at revision 1.")
    print("t+13s  ActionGate blocks the stale continue action.")
    print("t+24s  Planner recovers, replans, and proposes shut_down at revision 1.")
    print("t+31s  Mock executor applies shut_down in the simulated world.")
    print(f"t+36s  Independent evaluator: {assessment.status.value} ({assessment.reason_code}).")
    print("Model: REAL_AGENT_NOT_RUN; no local model was used.")
    return 0 if assessment.completion else 1


if __name__ == "__main__":
    raise SystemExit(run_demo())
