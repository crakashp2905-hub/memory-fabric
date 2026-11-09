"""Outcome evaluation and calibration diagnostics; never changes authority."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass
from math import isfinite
from typing import Iterable

from .types import CDMError


@dataclass(frozen=True)
class Outcome:
    outcome_id: str
    reward: float | None
    safety: float | None
    observation_complete: bool
    ground_truth_valid: bool = False
    held_out: bool = False

    def __post_init__(self) -> None:
        if not self.outcome_id:
            raise CDMError("outcome id is required")
        for name in ("reward", "safety"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                      or not isfinite(value)):
                raise CDMError(f"{name} must be a finite number or missing")


@dataclass(frozen=True)
class OutcomeAssessment:
    outcome_id: str
    status: str
    reward: float | None
    safety: float | None
    reason: str


@dataclass(frozen=True)
class FidelityAssessment:
    verified: bool
    status: str
    reason: str


@dataclass(frozen=True)
class CalibrationReport:
    sample_count: int
    brier_score: float | None
    expected_calibration_error: float | None
    bin_errors: tuple[float, ...]


@dataclass(frozen=True)
class ContributionAssessment:
    score: float | None
    observations: int
    tag: str = "PREDICTIVE_NOT_CAUSAL"


def assess_outcome(outcome: Outcome) -> OutcomeAssessment:
    """Missing/incomplete outcomes abstain; observed dimensions remain separate."""
    if not outcome.observation_complete or (outcome.reward is None and outcome.safety is None):
        return OutcomeAssessment(outcome.outcome_id, "UNDECIDABLE", None, None,
                                "outcome observation is missing or incomplete")
    return OutcomeAssessment(outcome.outcome_id, "OBSERVED", outcome.reward,
                             outcome.safety, "observed simulator outcome")


def verify_fidelity(expected_digest: str | None, observed_digest: str | None) -> FidelityAssessment:
    """Check replay fidelity independently from the outcome evaluator."""
    if expected_digest is None or observed_digest is None:
        return FidelityAssessment(False, "UNDECIDABLE", "fidelity digest is missing")
    valid = expected_digest == observed_digest
    return FidelityAssessment(valid, "VERIFIED" if valid else "MISMATCH",
                              "digest equality" if valid else "factual replay digest differs")


def calibration_report(predictions: Iterable[float], labels: Iterable[bool], *,
                       outcomes: Iterable[Outcome], bins: int = 10) -> CalibrationReport:
    """Compute Brier/ECE only for valid, held-out, complete outcome records."""
    probs, truth, records = tuple(predictions), tuple(labels), tuple(outcomes)
    if type(bins) is not int or not 1 <= bins <= 100:
        raise CDMError("bins must be in [1, 100]")
    if len(probs) != len(truth) or len(probs) != len(records):
        raise CDMError("prediction, label and outcome counts must match")
    if any(type(label) is not bool for label in truth):
        raise CDMError("calibration labels must be booleans")
    if any(isinstance(p, bool) or not isinstance(p, (int, float)) or not isfinite(p)
           or not 0 <= p <= 1 for p in probs):
        raise CDMError("predictions must be finite probabilities")
    eligible = [(float(p), int(label)) for p, label, record in zip(probs, truth, records)
                if record.ground_truth_valid and record.held_out and record.observation_complete]
    if not eligible:
        return CalibrationReport(0, None, None, ())
    brier = sum((p - y) ** 2 for p, y in eligible) / len(eligible)
    errors: list[float] = []
    ece = 0.0
    for index in range(bins):
        members = [(p, y) for p, y in eligible
                   if min(int(p * bins), bins - 1) == index]
        if members:
            confidence = sum(p for p, _ in members) / len(members)
            frequency = sum(y for _, y in members) / len(members)
            error = abs(confidence - frequency)
            errors.append(error)
            ece += len(members) / len(eligible) * error
    return CalibrationReport(len(eligible), brier, ece, tuple(errors))


def heuristic_contribution(*, exposures: int, positive_feedback: int,
                           negative_feedback: int) -> ContributionAssessment:
    """Predictive feedback-frequency score; never updates source trust or authority."""
    values = (exposures, positive_feedback, negative_feedback)
    if any(type(value) is not int or value < 0 for value in values):
        raise CDMError("heuristic counts must be non-negative integers")
    total = positive_feedback + negative_feedback
    score = ((positive_feedback - negative_feedback) / total) if total else None
    return ContributionAssessment(score, exposures + total)
