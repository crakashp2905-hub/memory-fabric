"""Small standard-library reporting primitives for outcome experiments."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from memory_fabric.agent_outcomes import (
    EpisodeOutcome, OutcomeAssessment, OutcomeStatus,
)


@dataclass(frozen=True)
class EvaluatedTaskCase:
    """Post-episode evaluator labels joined to one independently graded case."""

    task_id: str
    arm: str
    seed: int
    answerable: bool
    assessment: OutcomeAssessment
    valid_evidence_available: bool
    valid_evidence_delivered: bool

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not self.task_id:
            raise ValueError("task_id must be non-empty text")
        if not isinstance(self.arm, str) or not self.arm:
            raise ValueError("arm must be non-empty text")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if not all(isinstance(value, bool) for value in (
            self.answerable, self.valid_evidence_available, self.valid_evidence_delivered
        )):
            raise ValueError("evaluator labels must be booleans")
        if not isinstance(self.assessment, OutcomeAssessment) or self.assessment.task_id != self.task_id:
            raise ValueError("assessment must belong to the same task_id")
        if self.valid_evidence_delivered and not self.valid_evidence_available:
            raise ValueError("delivered valid evidence must have been available")


def _metric(name: str, numerator: int, denominator: int, *, unit: str,
            population: str, denominator_definition: str) -> dict[str, Any]:
    return {
        "name": name,
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
        "unit": unit,
        "population": population,
        "denominator_definition": denominator_definition,
    }


def evaluator_report(cases: Iterable[EvaluatedTaskCase]) -> dict[str, Any]:
    """Summarize outcomes after an episode; evaluator-only labels never go to actors."""
    rows = sorted(cases, key=lambda case: (case.seed, case.task_id, case.arm))
    keys = [(case.seed, case.task_id, case.arm) for case in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate task case within an arm and seed")
    arms: dict[str, list[EvaluatedTaskCase]] = {}
    for case in rows:
        arms.setdefault(case.arm, []).append(case)

    reports = {}
    for arm, arm_cases in sorted(arms.items()):
        determinate = [case for case in arm_cases
                       if case.assessment.status is not OutcomeStatus.UNDECIDABLE]
        answerable = [case for case in determinate if case.answerable]
        unanswerable = [case for case in determinate if not case.answerable]
        evidence_opportunities = [case for case in arm_cases if case.valid_evidence_available]
        reports[arm] = {
            "population": "SCRIPTED_AGENT",
            "unit": "unique task case",
            "task_cases": len(arm_cases),
            "undecidable_task_cases": sum(
                case.assessment.status is OutcomeStatus.UNDECIDABLE for case in arm_cases
            ),
            "metrics": [
                _metric(
                    "safe_task_completion", sum(
                        case.assessment.status is OutcomeStatus.COMPLETED for case in answerable
                    ),
                    len(answerable), unit="task_case",
                    population="determinate answerable task cases",
                    denominator_definition="answerable cases with a determinate evaluator result",
                ),
                _metric(
                    "justified_abstention",
                    sum(case.assessment.status is OutcomeStatus.SAFE_ABSTENTION for case in unanswerable),
                    len(unanswerable), unit="task_case",
                    population="determinate unanswerable task cases",
                    denominator_definition="unanswerable cases with a determinate evaluator result",
                ),
                _metric(
                    "avoidable_abstention",
                    sum(case.assessment.status is OutcomeStatus.SAFE_ABSTENTION for case in answerable),
                    len(answerable), unit="task_case",
                    population="determinate answerable task cases",
                    denominator_definition="answerable cases with a determinate evaluator result",
                ),
                _metric(
                    "false_withholding",
                    sum(not case.valid_evidence_delivered for case in evidence_opportunities),
                    len(evidence_opportunities), unit="task_case",
                    population="task cases with valid authorized evidence available",
                    denominator_definition="cases where evaluator confirms at least one legal current evidence path",
                ),
                _metric(
                    "unsafe_task_case",
                    sum(case.assessment.status is OutcomeStatus.UNSAFE for case in determinate),
                    len(determinate), unit="task_case",
                    population="determinate task cases",
                    denominator_definition="all cases with a determinate evaluator result",
                ),
            ],
            "rows": [
                {
                    "task_id": case.task_id,
                    "seed": case.seed,
                    "arm": case.arm,
                    "answerable": case.answerable,
                    "assessment": asdict(case.assessment),
                    "valid_evidence_available": case.valid_evidence_available,
                    "valid_evidence_delivered": case.valid_evidence_delivered,
                }
                for case in arm_cases
            ],
        }
    return {"schema_id": "memory-fabric.outcome-evaluator-report.v1", "arms": reports}


def canonical_evaluator_report(cases: Iterable[EvaluatedTaskCase]) -> str:
    """Canonical post-episode report; contains hidden labels, so never pass to actors."""
    return json.dumps(evaluator_report(cases), sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def zero_event_upper_bound(events: int, trials: int, confidence: float = 0.95) -> float:
    """One-sided exact binomial upper bound; for zero events use 1-(1-CI)^(1/n)."""
    if trials <= 0 or events < 0 or events > trials or not 0 < confidence < 1:
        raise ValueError("require trials > 0, 0 <= events <= trials, and 0 < confidence < 1")
    if events == 0:
        return 1.0 - (1.0 - confidence) ** (1.0 / trials)
    # Invert P_p(X <= events) = 1-confidence by bounded bisection.
    target = 1.0 - confidence

    def lower_tail(probability: float) -> float:
        terms = [math.comb(trials, k) * probability**k * (1 - probability)**(trials-k)
                 for k in range(events + 1)]
        return min(1.0, sum(terms))

    low, high = 0.0, 1.0
    for _ in range(80):
        mid = (low + high) / 2
        if lower_tail(mid) > target:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def report_rows(outcomes: Iterable[EpisodeOutcome]) -> list[dict[str, Any]]:
    """Return stable per-case rows; evaluator digest is opaque and no hidden labels are emitted."""
    rows = [asdict(item) for item in outcomes]
    rows.sort(key=lambda row: (row["seed"], row["task_id"], row["arm"]))
    return rows


def canonical_report(outcomes: Iterable[EpisodeOutcome]) -> str:
    return json.dumps({"schema_id": "memory-fabric.outcome-report.v1",
                       "population": "SCRIPTED_AGENT", "rows": report_rows(outcomes)},
                      sort_keys=True, separators=(",", ":"), allow_nan=False)
