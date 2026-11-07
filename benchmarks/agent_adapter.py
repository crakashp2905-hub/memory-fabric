"""Transport-neutral interface for deterministic or external-agent benchmark arms.

The core benchmark passes only a task envelope to an adapter and receives an
action-or-abstain response. Network and model clients belong in separately
registered adapter implementations, never in this protocol module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, Sequence


@dataclass(frozen=True)
class TaskEnvelope:
    task_id: str
    tool: str
    target: str
    evidence: tuple[str, ...]
    evidence_usable: bool
    evidence_conflicted: bool = False


@dataclass(frozen=True)
class AgentResponse:
    decision: Literal["act", "abstain"]
    tool: str | None = None
    target: str | None = None
    value: str | None = None
    reason: str = ""


class AgentAdapter(Protocol):
    """One-call adapter contract; a model adapter can implement this unchanged."""

    def decide(self, task: TaskEnvelope) -> AgentResponse: ...


class ScriptedPolicyAdapter:
    """Offline fail-closed policy used by local regression and contract tests."""

    def decide(self, task: TaskEnvelope) -> AgentResponse:
        if not task.evidence or not task.evidence_usable or task.evidence_conflicted:
            return AgentResponse("abstain", reason="evidence_insufficient_or_conflicted")
        return AgentResponse("act", tool=task.tool, target=task.target,
                             value=task.evidence[0], reason="usable_evidence")


def run_adapter(adapter: AgentAdapter, tasks: Sequence[TaskEnvelope]) -> list[AgentResponse]:
    """Run a batch through the adapter without binding it to transport or model SDKs."""
    responses = [adapter.decide(task) for task in tasks]
    if any(not isinstance(response, AgentResponse) for response in responses):
        raise TypeError("adapter must return AgentResponse for every task")
    return responses
