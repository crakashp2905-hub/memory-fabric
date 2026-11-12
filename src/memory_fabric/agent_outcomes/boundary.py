"""Narrow actor and evaluator ports for an in-process scripted episode.

The world constructor retains the evaluator capability. Agent code receives
only ``AgentPort`` and cannot grade outcomes through that port.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable

from memory_fabric.agent_outcomes.observations import AgentObservation, AgentStep
from memory_fabric.agent_outcomes.outcomes import (
    OracleTask, OutcomeAssessment, TerminalResult, _grade_terminal_outcome,
)


class AgentPort:
    """Agent identity view; contains no oracle object or grading method."""

    __slots__ = ("_observation", "_actor_id")

    def __init__(self, observation: AgentObservation, actor_id: str) -> None:
        if not isinstance(observation, AgentObservation):
            raise TypeError("observation must be an AgentObservation")
        if not isinstance(actor_id, str) or not actor_id:
            raise ValueError("actor_id must be non-empty text")
        self._observation = observation
        self._actor_id = actor_id

    def observe(self) -> AgentObservation:
        """Return the truth-free observation bound to this actor identity."""
        return self._observation

    def submit(self, step: AgentStep) -> AgentStep:
        """Validate a proposal's identity and task binding; perform no effect."""
        if not isinstance(step, AgentStep):
            raise TypeError("step must be an AgentStep")
        if step.task_id != self._observation.task_id:
            raise ValueError("step belongs to a different task")
        if step.actor_id != self._actor_id:
            raise ValueError("step belongs to a different actor identity")
        return step


class EvaluatorPort:
    """Capability held by the world/evaluator, never supplied to an actor."""

    __slots__ = ("_oracle_task",)

    def __init__(self, oracle_task: OracleTask) -> None:
        if not isinstance(oracle_task, OracleTask):
            raise TypeError("oracle_task must be an OracleTask")
        self._oracle_task = oracle_task

    def grade(self, result: TerminalResult) -> OutcomeAssessment:
        if not isinstance(result, TerminalResult):
            raise TypeError("result must be a TerminalResult")
        return _grade_terminal_outcome(self._oracle_task, result)


@dataclass(frozen=True)
class EvaluatorCallbackNotice:
    """Serialized post-run summary; contains no actor, world, gate, or oracle handle."""

    task_id: str
    actor_id: str
    trace_digest: str
    stop_reason: str


@dataclass(frozen=True)
class EvaluatorDispatch:
    assessment: OutcomeAssessment
    callback_error_type: str | None = None


def grade_after_episode(
    evaluator: EvaluatorPort,
    result: TerminalResult,
    trace: Any,
    callback: Callable[[EvaluatorCallbackNotice], Any] | None = None,
) -> EvaluatorDispatch:
    """Grade completed evidence, then notify an evaluator callback with a value copy only.

    Callback return values are discarded. The callback receives no runtime,
    world, session, action gate, approval, or oracle capability and runs after
    every actor and tool decision is complete.
    """
    if not isinstance(evaluator, EvaluatorPort):
        raise TypeError("evaluator must be an EvaluatorPort")
    if not isinstance(result, TerminalResult):
        raise TypeError("result must be a TerminalResult")
    if not all(hasattr(trace, name) for name in (
        "task_id", "actor_id", "observations", "steps", "calls", "stop_reason",
    )):
        raise TypeError("trace must contain runtime observations")
    if callback is not None and not callable(callback):
        raise TypeError("callback must be callable")
    payload = {
        "task_id": trace.task_id,
        "actor_id": trace.actor_id,
        "observations": [item.to_dict() for item in trace.observations],
        "steps": [item.to_dict() for item in trace.steps],
        "calls": [{"step_id": call.step_id, "tool": call.tool,
                   "completed": call.output.completed,
                   "visible_events": list(call.output.visible_events)}
                  for call in trace.calls],
        "stop_reason": trace.stop_reason,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    notice = EvaluatorCallbackNotice(
        task_id=trace.task_id,
        actor_id=trace.actor_id,
        trace_digest=hashlib.sha256(encoded).hexdigest(),
        stop_reason=trace.stop_reason,
    )
    assessment = evaluator.grade(result)
    callback_error_type = None
    if callback is not None:
        try:
            callback(notice)
        except Exception as exc:
            callback_error_type = type(exc).__name__
    return EvaluatorDispatch(assessment, callback_error_type)


def build_episode_boundary(
    observation: AgentObservation,
    oracle_task: OracleTask,
    *,
    actor_id: str,
) -> tuple[AgentPort, EvaluatorPort]:
    """Build separate ports; the caller must give only the first to agent code."""
    if observation.task_id != oracle_task.task_id:
        raise ValueError("observation and oracle task IDs must match")
    return AgentPort(observation, actor_id), EvaluatorPort(oracle_task)
