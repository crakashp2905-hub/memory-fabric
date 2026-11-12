"""Bounded observe-decide-tool-observe loop with no evaluator capability."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass
import json
from typing import Any, Callable, Mapping

from .boundary import AgentPort
from .observations import AgentObservation, AgentStep, _no_oracle_fields

MAX_TOOL_REQUEST_BYTES = 16_000


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value is forbidden: {value}")


def parse_agent_request(
    payload: str,
    *,
    observation: AgentObservation,
    actor_id: str,
    step_id: str,
    tool_schemas: Mapping[str, Mapping[str, type]],
) -> AgentStep:
    """Parse an exact bounded tool-request shape or an explicit abstention."""
    if not isinstance(payload, str):
        raise ValueError("tool request must be JSON text")
    try:
        encoded = payload.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("tool request contains invalid Unicode") from exc
    if len(encoded) > MAX_TOOL_REQUEST_BYTES:
        raise ValueError("tool request exceeds the byte limit")
    try:
        raw = json.loads(encoded, object_pairs_hook=_unique_object,
                         parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("tool request is not valid JSON") from exc
    expected = {"intent", "tool", "arguments", "evidence_versions"}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValueError("tool request fields do not match the schema")
    intent, tool, arguments, versions = (
        raw["intent"], raw["tool"], raw["arguments"], raw["evidence_versions"]
    )
    if not isinstance(arguments, dict) or not isinstance(versions, list):
        raise ValueError("arguments and evidence_versions have invalid types")
    if intent == "abstain":
        if tool is not None or any(
            not isinstance(item, list) or len(item) != 2 for item in versions
        ):
            raise ValueError("abstention request shape is invalid")
        if arguments and (set(arguments) != {"reason"}
                          or not isinstance(arguments.get("reason"), str)):
            raise ValueError("abstention arguments must contain only a text reason")
        return AgentStep(observation.task_id, actor_id, step_id, "abstain", arguments,
                         tuple((item[0], item[1]) for item in versions))
    if intent != "propose" or not isinstance(tool, str):
        raise ValueError("intent must be propose or abstain")
    if tool not in observation.permitted_tools:
        raise ValueError("tool is not permitted by the current observation")
    schema = tool_schemas.get(tool)
    if schema is None:
        raise ValueError("tool has no registered argument schema")
    if set(arguments) != set(schema):
        raise ValueError("tool arguments do not match the registered schema")
    for name, expected_type in schema.items():
        if not isinstance(expected_type, type) or type(arguments[name]) is not expected_type:
            raise ValueError(f"tool argument {name} has the wrong type")
    if any(not isinstance(item, list) or len(item) != 2 for item in versions):
        raise ValueError("evidence_versions must contain pairs")
    return AgentStep(
        observation.task_id, actor_id, step_id, "propose", {"tool": tool, **arguments},
        tuple((item[0], item[1]) for item in versions),
    )


@dataclass(frozen=True)
class ToolOutput:
    """Only actor-visible output returned by one registered tool handler."""

    visible_events: tuple[dict[str, Any], ...] = ()
    completed: bool = True

    def __post_init__(self) -> None:
        if type(self.completed) is not bool:
            raise ValueError("tool completion flag must be boolean")
        if not all(isinstance(event, dict) for event in self.visible_events):
            raise ValueError("tool visible_events must contain objects")
        _no_oracle_fields(self.visible_events)


@dataclass(frozen=True)
class ToolCallRecord:
    step_id: str
    tool: str
    output: ToolOutput


@dataclass(frozen=True)
class RuntimeTrace:
    task_id: str
    actor_id: str
    observations: tuple[AgentObservation, ...]
    steps: tuple[AgentStep, ...]
    calls: tuple[ToolCallRecord, ...]
    final_observation: AgentObservation
    stop_reason: str


class AgentRuntime:
    """Execute only the tools exposed by each observation, within a fixed step budget."""

    def __init__(self, *, max_steps: int, tools: Mapping[str, Callable[..., ToolOutput]],
                 request_schemas: Mapping[str, Mapping[str, type]] | None = None) -> None:
        if type(max_steps) is not int or max_steps < 1:
            raise ValueError("max_steps must be a positive integer")
        if not isinstance(tools, Mapping) or any(
            not isinstance(name, str) or not name or not callable(handler)
            for name, handler in tools.items()
        ):
            raise ValueError("tools must map non-empty names to callable handlers")
        self.max_steps = max_steps
        self._tools = dict(tools)
        self._request_schemas = dict(request_schemas or {})

    def run(
        self,
        *,
        initial_observation: AgentObservation,
        actor_id: str,
        decide: Callable[[AgentObservation], AgentStep],
        observe_after: Callable[[int, ToolOutput], AgentObservation],
    ) -> RuntimeTrace:
        if not isinstance(initial_observation, AgentObservation):
            raise TypeError("initial_observation must be an AgentObservation")
        if not isinstance(actor_id, str) or not actor_id:
            raise ValueError("actor_id must be non-empty")
        if not callable(decide) or not callable(observe_after):
            raise TypeError("decide and observe_after must be callable")

        observation = initial_observation
        observations = [initial_observation]
        steps: list[AgentStep] = []
        calls: list[ToolCallRecord] = []
        stop_reason = "STEP_BUDGET_EXHAUSTED"
        for index in range(self.max_steps):
            port = AgentPort(observation, actor_id)
            decision = decide(observation)
            if isinstance(decision, str):
                try:
                    decision = parse_agent_request(
                        decision, observation=observation, actor_id=actor_id,
                        step_id=f"{observation.task_id}:runtime:{index + 1}",
                        tool_schemas=self._request_schemas,
                    )
                except (TypeError, ValueError):
                    step = AgentStep(
                        observation.task_id, actor_id,
                        f"{observation.task_id}:runtime:{index + 1}", "abstain",
                        {"reason": "invalid_tool_request"},
                    )
                    steps.append(port.submit(step))
                    stop_reason = "INVALID_REQUEST"
                    break
            step = port.submit(decision)
            steps.append(step)
            if step.intent == "abstain":
                stop_reason = "AGENT_ABSTAINED"
                break

            tool_name = step.arguments.get("tool")
            if not isinstance(tool_name, str) or tool_name not in observation.permitted_tools:
                stop_reason = "TOOL_NOT_PERMITTED"
                break
            handler = self._tools.get(tool_name)
            if handler is None:
                stop_reason = "TOOL_NOT_REGISTERED"
                break
            arguments = {key: value for key, value in step.arguments.items() if key != "tool"}
            try:
                output = handler(arguments, step)
            except Exception as exc:
                output = ToolOutput(({"event": "tool_error",
                                      "error_type": type(exc).__name__},), completed=False)
            if not isinstance(output, ToolOutput):
                calls.append(ToolCallRecord(
                    step.step_id, tool_name,
                    ToolOutput(({"event": "invalid_tool_output"},), completed=False),
                ))
                stop_reason = "INVALID_TOOL_OUTPUT"
                break
            calls.append(ToolCallRecord(step.step_id, tool_name, output))
            try:
                next_observation = observe_after(index + 1, output)
            except Exception as exc:
                stop_reason = f"OBSERVATION_FAILED:{type(exc).__name__}"
                break
            if (not isinstance(next_observation, AgentObservation)
                    or next_observation.task_id != initial_observation.task_id):
                stop_reason = "INVALID_NEXT_OBSERVATION"
                break
            observation = next_observation
            observations.append(observation)

        return RuntimeTrace(initial_observation.task_id, actor_id, tuple(observations),
                            tuple(steps), tuple(calls), observation, stop_reason)
