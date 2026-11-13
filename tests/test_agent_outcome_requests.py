from __future__ import annotations

import json

import pytest

from memory_fabric.agent_outcomes import (
    MAX_TOOL_REQUEST_BYTES,
    AgentObservation,
    AgentRuntime,
    parse_agent_request,
)


def _observation() -> AgentObservation:
    return AgentObservation("request-task", "Set the target.", (), ("set_target",),
                            {"steps": 2})


def _request(*, tool="set_target", arguments=None, intent="propose") -> str:
    return json.dumps({
        "intent": intent,
        "tool": tool if intent == "propose" else None,
        "arguments": arguments if arguments is not None else {"target": "zone-2", "value": 4},
        "evidence_versions": [],
    })


def test_runtime_rejects_unbounded_tool_call_budget() -> None:
    with pytest.raises(ValueError, match="between 1 and 64"):
        AgentRuntime(max_steps=65, tools={})


def test_valid_structured_request_parses_against_registered_schema() -> None:
    step = parse_agent_request(
        _request(), observation=_observation(), actor_id="planner", step_id="step-1",
        tool_schemas={"set_target": {"target": str, "value": int}},
    )

    assert step.intent == "propose"
    assert step.arguments == {"tool": "set_target", "target": "zone-2", "value": 4}


@pytest.mark.parametrize("payload", [
    "{bad json",
    _request(tool="unknown_tool"),
    _request(arguments={"target": "zone-2", "value": True}),
    _request() + (" " * (MAX_TOOL_REQUEST_BYTES + 1)),
    '{"intent":"propose","intent":"abstain","tool":null,'
    '"arguments":{},"evidence_versions":[]}',
])
def test_invalid_request_becomes_logged_abstention_without_tool_fallthrough(payload: str) -> None:
    calls: list[dict] = []
    trace = AgentRuntime(
        max_steps=2,
        tools={"set_target": lambda arguments, _step: calls.append(arguments)},
        request_schemas={"set_target": {"target": str, "value": int}},
    ).run(
        initial_observation=_observation(), actor_id="planner",
        decide=lambda _observation: payload,
        observe_after=lambda _index, _output: _observation(),
    )

    assert trace.stop_reason == "INVALID_REQUEST"
    assert trace.steps[0].intent == "abstain"
    assert trace.steps[0].arguments == {"reason": "invalid_tool_request"}
    assert trace.calls == ()
    assert calls == []


def test_explicit_abstention_is_valid_and_does_not_call_a_tool() -> None:
    trace = AgentRuntime(
        max_steps=1, tools={"set_target": lambda *_: pytest.fail("must not call")},
        request_schemas={"set_target": {"target": str, "value": int}},
    ).run(
        initial_observation=_observation(), actor_id="planner",
        decide=lambda _observation: _request(intent="abstain", arguments={"reason": "uncertain"}),
        observe_after=lambda _index, _output: _observation(),
    )

    assert trace.steps[0].intent == "abstain"
    assert trace.steps[0].arguments == {"reason": "uncertain"}
    assert trace.stop_reason == "AGENT_ABSTAINED"
    assert trace.calls == ()
