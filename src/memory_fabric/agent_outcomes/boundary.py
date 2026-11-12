"""Narrow actor and evaluator ports for an in-process scripted episode.

The world constructor retains the evaluator capability. Agent code receives
only ``AgentPort`` and cannot grade outcomes through that port.
"""

from __future__ import annotations

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
