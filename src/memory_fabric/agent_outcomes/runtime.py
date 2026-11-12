"""Bounded observe-decide-tool-observe loop with no evaluator capability."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .boundary import AgentPort
from .observations import AgentObservation, AgentStep, _no_oracle_fields


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

    def __init__(self, *, max_steps: int, tools: Mapping[str, Callable[..., ToolOutput]]) -> None:
        if type(max_steps) is not int or max_steps < 1:
            raise ValueError("max_steps must be a positive integer")
        if not isinstance(tools, Mapping) or any(
            not isinstance(name, str) or not name or not callable(handler)
            for name, handler in tools.items()
        ):
            raise ValueError("tools must map non-empty names to callable handlers")
        self.max_steps = max_steps
        self._tools = dict(tools)

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
            step = port.submit(decide(observation))
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
