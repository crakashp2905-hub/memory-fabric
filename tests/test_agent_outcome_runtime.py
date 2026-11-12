from __future__ import annotations

import pytest

from memory_fabric.agent_outcomes.observations import AgentObservation, AgentStep
from memory_fabric.agent_outcomes.runtime import AgentRuntime, ToolOutput


def observation(events=(), tools=("inspect", "isolate")) -> AgentObservation:
    return AgentObservation("runtime-task", "Inspect then respond.", tuple(events),
                            tuple(tools), {"steps": 4})


def test_tool_output_changes_the_next_decision_without_oracle_access() -> None:
    calls: list[str] = []
    decisions: list[str] = []
    initial = observation()

    def decide(current: AgentObservation) -> AgentStep:
        decisions.append(str(len(current.visible_events)))
        if not current.visible_events:
            return AgentStep("runtime-task", "planner", "step-1", "inspect",
                             {"tool": "inspect"})
        if len(decisions) == 2:
            assert current.visible_events[-1]["reading"] == "high"
            return AgentStep("runtime-task", "planner", "step-2", "propose",
                             {"tool": "isolate", "zone": "north"})
        assert current.visible_events[-1]["isolated"] == "north"
        return AgentStep("runtime-task", "planner", "step-3", "abstain", {})

    def inspect(_arguments, _step):
        calls.append("inspect")
        return ToolOutput(({"reading": "high"},))

    def isolate(arguments, _step):
        calls.append(f"isolate:{arguments['zone']}")
        return ToolOutput(({"isolated": "north"},))

    def observe_after(step_index: int, output: ToolOutput) -> AgentObservation:
        return observation(
            ({"event": "tool_result", "step": step_index, **output.visible_events[0]},),
        )

    trace = AgentRuntime(max_steps=3, tools={"inspect": inspect, "isolate": isolate}).run(
        initial_observation=initial, actor_id="planner", decide=decide,
        observe_after=observe_after,
    )

    assert decisions == ["0", "1", "1"]
    assert calls == ["inspect", "isolate:north"]
    assert [step.intent for step in trace.steps] == ["inspect", "propose", "abstain"]
    assert [call.tool for call in trace.calls] == ["inspect", "isolate"]
    assert trace.stop_reason == "AGENT_ABSTAINED"
    assert trace.final_observation.visible_events[-1]["isolated"] == "north"


def test_unpermitted_tool_never_falls_through_to_a_handler() -> None:
    calls: list[str] = []
    trace = AgentRuntime(max_steps=2, tools={
        "admin_override": lambda *_: calls.append("unsafe") or ToolOutput(),
    }).run(
        initial_observation=observation(tools=("inspect",)), actor_id="planner",
        decide=lambda _obs: AgentStep(
            "runtime-task", "planner", "step-1", "propose", {"tool": "admin_override"}
        ),
        observe_after=lambda _index, _output: observation(),
    )

    assert trace.stop_reason == "TOOL_NOT_PERMITTED"
    assert calls == []
    assert trace.calls == ()


def test_invalid_oracle_shaped_tool_output_is_rejected() -> None:
    with pytest.raises(ValueError, match="evaluator-only"):
        ToolOutput(({"truth": {"safe": True}},))

    trace = AgentRuntime(max_steps=1, tools={"inspect": lambda *_: {"truth": "hidden"}}).run(
        initial_observation=observation(), actor_id="planner",
        decide=lambda _obs: AgentStep(
            "runtime-task", "planner", "step-1", "inspect", {"tool": "inspect"}
        ),
        observe_after=lambda _index, _output: observation(),
    )
    assert trace.stop_reason == "INVALID_TOOL_OUTPUT"
    assert trace.calls[0].output.visible_events == ({"event": "invalid_tool_output"},)


def test_step_budget_and_task_binding_are_enforced() -> None:
    trace = AgentRuntime(max_steps=1, tools={"inspect": lambda *_: ToolOutput()}).run(
        initial_observation=observation(), actor_id="planner",
        decide=lambda _obs: AgentStep(
            "runtime-task", "planner", "step-1", "inspect", {"tool": "inspect"}
        ),
        observe_after=lambda _index, _output: observation(),
    )
    assert len(trace.steps) == 1
    assert len(trace.calls) == 1
    assert trace.stop_reason == "STEP_BUDGET_EXHAUSTED"

    with pytest.raises(ValueError, match="different task"):
        AgentRuntime(max_steps=1, tools={}).run(
            initial_observation=observation(), actor_id="planner",
            decide=lambda _obs: AgentStep("another-task", "planner", "step-1", "abstain", {}),
            observe_after=lambda _index, _output: observation(),
        )
