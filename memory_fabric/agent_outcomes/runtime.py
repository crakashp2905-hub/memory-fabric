"""Truth-free, bounded observe-decide-call-observe agent loop contracts.

The loop receives one public ``AgentObservation``, a decision callback, and
host-declared tools. It never accepts an evaluator task or a world object. Tool
handlers are trusted host integrations and must return only actor-visible data.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Mapping

from .observations import AgentObservation, AgentStep

MAX_RUNTIME_STEPS = 128
MAX_TOOL_ARGUMENT_BYTES = 16_000
MAX_TOOL_OUTPUT_BYTES = 16_000


class RuntimeStatus(StrEnum):
    ABSTAINED = "ABSTAINED"
    FAILED = "FAILED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


@dataclass(frozen=True)
class RuntimeTool:
    """Host-owned handler declaration with strict JSON argument and output bounds."""

    name: str
    handler: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    required_fields: frozenset[str] = frozenset()
    optional_fields: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", self.name):
            raise ValueError("tool names must be stable identifiers")
        if not callable(self.handler):
            raise ValueError("tool handler must be callable")
        if (self.required_fields & self.optional_fields
                or any(not isinstance(key, str) for key in (
                    self.required_fields | self.optional_fields))):
            raise ValueError("tool argument declarations must be disjoint string fields")


@dataclass(frozen=True)
class ToolCallRecord:
    step_id: str
    tool: str
    status: str
    output_sha256: str


@dataclass(frozen=True)
class RuntimeResult:
    status: RuntimeStatus
    steps: tuple[AgentStep, ...]
    calls: tuple[ToolCallRecord, ...]
    observations: tuple[AgentObservation, ...]
    failure_code: str | None = None


DecisionFunction = Callable[[AgentObservation], AgentStep]


def _canonical_object(value: Any, *, max_bytes: int, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be a JSON object with string keys")
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(encoded) > max_bytes:
            raise ValueError(f"{label} exceeds its byte limit")
        decoded = json.loads(encoded)
    except (RecursionError, TypeError, UnicodeEncodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must contain finite canonical JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must be a JSON object")
    return decoded


def run_agent_loop(
    initial: AgentObservation,
    actor_id: str,
    decide: DecisionFunction,
    tools: Mapping[str, RuntimeTool],
    *,
    max_steps: int | None = None,
) -> RuntimeResult:
    """Run bounded steps, exposing each tool result to the next decision only.

    A step with intent ``abstain`` stops the loop. Other intents must name one
    declared tool in ``arguments.tool``; invalid or unauthorized calls stop
    fail-closed without invoking a handler. A handler error becomes a generic
    visible result so the actor can decide what to do next.
    """
    if not isinstance(initial, AgentObservation):
        raise TypeError("initial input must be AgentObservation")
    if not isinstance(actor_id, str) or not actor_id:
        raise ValueError("actor_id must be non-empty text")
    if not callable(decide):
        raise ValueError("decide must be callable")
    if max_steps is not None and (
            isinstance(max_steps, bool) or not isinstance(max_steps, int)
            or not 0 <= max_steps <= MAX_RUNTIME_STEPS):
        raise ValueError(f"max_steps must be between 0 and {MAX_RUNTIME_STEPS}")
    if any(name != tool.name for name, tool in tools.items()):
        raise ValueError("tool registry keys must match declarations")
    budget_steps = initial.budget.get("steps", 0)
    if isinstance(budget_steps, bool) or not isinstance(budget_steps, int):
        raise ValueError("observation step budget must be an integer")
    step_limit = min(budget_steps, MAX_RUNTIME_STEPS)
    if max_steps is not None:
        step_limit = min(step_limit, max_steps)

    observation = initial
    observations = [initial]
    steps: list[AgentStep] = []
    calls: list[ToolCallRecord] = []
    seen_step_ids: set[str] = set()

    for call_index in range(step_limit):
        try:
            step = decide(observation)
        except Exception:
            return RuntimeResult(RuntimeStatus.FAILED, tuple(steps), tuple(calls),
                                 tuple(observations), "decision_failed")
        if (not isinstance(step, AgentStep) or step.task_id != initial.task_id
                or step.actor_id != actor_id or step.step_id in seen_step_ids):
            return RuntimeResult(RuntimeStatus.FAILED, tuple(steps), tuple(calls),
                                 tuple(observations), "invalid_agent_step")
        seen_step_ids.add(step.step_id)
        steps.append(step)
        if step.intent == "abstain":
            return RuntimeResult(RuntimeStatus.ABSTAINED, tuple(steps), tuple(calls),
                                 tuple(observations))

        try:
            arguments = json.loads(step.canonical_json())["arguments"]
            tool_name = arguments.get("tool")
            if not isinstance(tool_name, str) or tool_name not in initial.permitted_tools:
                raise ValueError("tool_not_permitted")
            declaration = tools.get(tool_name)
            if declaration is None:
                raise ValueError("tool_not_declared")
            tool_arguments = dict(arguments)
            tool_arguments.pop("tool")
            if (not declaration.required_fields <= set(tool_arguments)
                    or set(tool_arguments) - declaration.required_fields
                    - declaration.optional_fields):
                raise ValueError("invalid_tool_arguments")
            tool_arguments = _canonical_object(
                tool_arguments, max_bytes=MAX_TOOL_ARGUMENT_BYTES, label="tool arguments")
        except ValueError as exc:
            code = str(exc)
            if code not in {"tool_not_permitted", "tool_not_declared", "invalid_tool_arguments"}:
                code = "invalid_tool_arguments"
            return RuntimeResult(RuntimeStatus.FAILED, tuple(steps), tuple(calls),
                                 tuple(observations), code)

        try:
            output = declaration.handler(tool_arguments)
            safe_output = _canonical_object(
                output, max_bytes=MAX_TOOL_OUTPUT_BYTES, label="tool output")
            status = "ok"
        except Exception:
            safe_output = {"ok": False, "reason": "tool_failed"}
            status = "failed"
        event = {"source": "tool", "tool": tool_name,
                 "call_index": call_index + 1, "output": safe_output}
        try:
            observation = AgentObservation(
                task_id=initial.task_id, instruction=initial.instruction,
                visible_events=(*observation.visible_events, event),
                permitted_tools=initial.permitted_tools, budget=initial.budget,
            )
        except (TypeError, ValueError):
            return RuntimeResult(RuntimeStatus.FAILED, tuple(steps), tuple(calls),
                                 tuple(observations), "tool_output_not_actor_visible")
        output_bytes = json.dumps(safe_output, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False, allow_nan=False).encode("utf-8")
        calls.append(ToolCallRecord(
            step_id=step.step_id, tool=tool_name, status=status,
            output_sha256=hashlib.sha256(output_bytes).hexdigest(),
        ))
        observations.append(observation)

    return RuntimeResult(RuntimeStatus.BUDGET_EXHAUSTED, tuple(steps), tuple(calls),
                         tuple(observations), "step_budget_exhausted")
