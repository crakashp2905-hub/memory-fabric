"""Independent retrieval, evidence-validity, and decision-readiness signals."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from .answerability import ANSWERABLE, CONFLICTING
from .model import LifecycleState

if TYPE_CHECKING:  # pragma: no cover
    from ._fabric.common import RetrievalResult


@dataclass(frozen=True)
class RetrievalRanking:
    """A ranking signal only; it does not certify evidence or authorize action."""

    top_score: float | None

    def __post_init__(self) -> None:
        if self.top_score is not None and type(self.top_score) is not float:
            raise TypeError("top_score must be a float or None")


class EvidenceValidity(str, Enum):
    """Whether every exposed item is currently validated evidence."""

    VALID = "valid"
    INVALID = "invalid"
    EMPTY = "empty"


class DecisionReadiness(str, Enum):
    """Whether the evidence supports choosing an answer now."""

    READY = "ready"
    ABSTAIN = "abstain"
    REVIEW = "review"


@dataclass(frozen=True)
class RetrievalAssessment:
    """Three deliberately non-interchangeable retrieval-package fields."""

    ranking: RetrievalRanking
    evidence_validity: EvidenceValidity
    decision_readiness: DecisionReadiness
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.ranking, RetrievalRanking):
            raise TypeError("ranking must be RetrievalRanking")
        if not isinstance(self.evidence_validity, EvidenceValidity):
            raise TypeError("evidence_validity must be EvidenceValidity")
        if not isinstance(self.decision_readiness, DecisionReadiness):
            raise TypeError("decision_readiness must be DecisionReadiness")

    def to_json(self) -> dict[str, Any]:
        return {
            "ranking": {"top_score": self.ranking.top_score},
            "evidence_validity": self.evidence_validity.value,
            "decision_readiness": self.decision_readiness.value,
            "reasons": list(self.reasons),
        }


def assess(result: "RetrievalResult", question: str, judge: Any = None) -> RetrievalAssessment:
    """Assess an exposed package without treating its ranking as a safety gate."""

    ranking = RetrievalRanking(max(result.scores.values()) if result.scores else None)
    if not result.exposed:
        validity = EvidenceValidity.EMPTY
    elif all(memory.lifecycle_state is LifecycleState.ACTIVE for memory in result.exposed):
        validity = EvidenceValidity.VALID
    else:
        validity = EvidenceValidity.INVALID

    answerability = result.answerability(question, judge=judge)
    if validity is not EvidenceValidity.VALID or answerability.verdict == CONFLICTING:
        readiness = DecisionReadiness.REVIEW
    elif answerability.verdict == ANSWERABLE:
        readiness = DecisionReadiness.READY
    else:
        readiness = DecisionReadiness.ABSTAIN
    return RetrievalAssessment(ranking, validity, readiness, answerability.reasons)
