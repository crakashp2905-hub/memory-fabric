"""Policy-controlled, read-only degradation for insufficient evidence.

This module only assesses whether an advisory may be presented. It never
authorizes, executes, or implies permission for an action; protected tools must
still pass through :mod:`memory_fabric.actions`.
"""

from __future__ import annotations

__stability__ = "beta"

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .evidence_status import (
    DecisionReadiness,
    RetrievalAssessment,
    assess as assess_evidence,
)

if TYPE_CHECKING:  # pragma: no cover
    from ._fabric.common import RetrievalResult


@dataclass(frozen=True)
class ReadOnlyAdvisoryPolicy:
    """Host policy for presenting a read-only advisory.

    Insufficient evidence and evidence requiring review are denied by default.
    A host may separately opt into showing either state as an advisory, with
    the returned result carrying a mandatory disclosure. This policy cannot
    grant action authority.
    """

    policy_id: str
    allow_insufficient: bool = False
    allow_review: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or not self.policy_id.strip():
            raise ValueError("policy_id must be a non-empty string")
        if type(self.allow_insufficient) is not bool or type(self.allow_review) is not bool:
            raise TypeError("advisory policy flags must be bool")


@dataclass(frozen=True)
class ReadOnlyAdvisoryDecision:
    """Presentation decision and disclosure; never a tool authorization."""

    policy_id: str
    presentation_allowed: bool
    evidence: RetrievalAssessment
    disclosure: str | None

    @property
    def action_authorized(self) -> bool:
        """Always false: this result cannot authorize a consequential action."""
        return False

    def to_json(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "presentation_allowed": self.presentation_allowed,
            "action_authorized": False,
            "evidence": self.evidence.to_json(),
            "disclosure": self.disclosure,
        }


def assess_read_only_advisory(
    result: "RetrievalResult",
    question: str,
    policy: ReadOnlyAdvisoryPolicy,
    *,
    judge: Any = None,
) -> ReadOnlyAdvisoryDecision:
    """Assess a read-only presentation under an explicit host policy.

    A ready answer may be presented without a degradation disclosure. An
    abstain or review state is presented only when the matching policy flag is
    enabled, and then includes a machine-visible reason plus a human-readable
    warning. No content is generated and no action capability is returned.
    """
    if not isinstance(policy, ReadOnlyAdvisoryPolicy):
        raise TypeError("policy must be ReadOnlyAdvisoryPolicy")

    evidence = assess_evidence(result, question, judge=judge)
    readiness = evidence.decision_readiness
    if readiness is DecisionReadiness.READY:
        return ReadOnlyAdvisoryDecision(policy.policy_id, True, evidence, None)

    if readiness is DecisionReadiness.ABSTAIN:
        allowed = policy.allow_insufficient
        status = "insufficient or undetermined"
        reasons = "; ".join(evidence.reasons) or "no sufficient evidence was found"
    elif readiness is DecisionReadiness.REVIEW:
        allowed = policy.allow_review
        status = "invalid, conflicting, or review-required"
        reasons = "; ".join(evidence.reasons) or "the evidence requires review"
    else:  # defensive if a readiness enum is extended
        allowed = False
        status = "unknown"
        reasons = "the evidence status is not recognized"

    disclosure = (
        f"Evidence is {status}: {reasons}. This is a read-only advisory and "
        "does not authorize action."
    )
    return ReadOnlyAdvisoryDecision(policy.policy_id, allowed, evidence, disclosure)
