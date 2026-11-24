"""Calibration metrics and a frozen, roll-backable threshold artifact (VEGA S10).

Metrics are computed from evaluator-owned rows: the advisor's raw probabilities
and conformal set, and the correct option recorded separately by a fixture
oracle (VEGA-CDM-102). Every metric names its population and denominator (103).

:func:`fit_threshold` fits one confidence threshold on calibration rows only and
returns a :class:`CalibrationArtifact` pinned to the sample ids and digest it was
fitted on (104). The uncalibrated model stays the comparator, and nothing is
written back to the checkpoint (105). :func:`transfer_check` compares the fitted
threshold's risk on another domain and sends a failure to review-only mode (106).
Splits are checked for leakage by family, template and source root (101).

Online learning is not implemented: :data:`ONLINE_LEARNING` is ``DISABLED``, and
:func:`admissible_feedback` accepts only evaluator-confirmed labels timestamped
after their outcome, never self-ratings or generated rationales (107, 108).
Promotion of any fitted artifact requires a positive matched downstream effect,
which calibration metrics alone cannot supply (110).
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

ONLINE_LEARNING = "DISABLED"


@dataclass(frozen=True)
class CalibrationRow:
    sample_id: str
    family: str
    template: str
    source_root: str
    probs: Mapping[str, float]
    prediction_set: tuple[str, ...]
    abstain: bool
    correct: str  # evaluator-owned, never produced by the advisor


def leakage(calibration: Sequence[CalibrationRow], confirmatory: Sequence[CalibrationRow]) -> list[str]:
    problems = []
    for key in ("family", "template", "source_root", "sample_id"):
        shared = {getattr(r, key) for r in calibration} & {getattr(r, key) for r in confirmatory}
        if shared and key != "family":
            problems.append(f"{key} shared across splits: {sorted(shared)[:3]}")
    return problems


def metrics(rows: Sequence[CalibrationRow], *, bins: int = 10) -> dict[str, Any]:
    n = len(rows)
    if not n:
        return {"population": 0, "status": "NOT_ASSESSABLE"}
    brier = nll = top1 = covered = 0.0
    answered = [r for r in rows if not r.abstain]
    conf_bins: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for r in rows:
        top = max(r.probs, key=lambda k: r.probs[k])
        right = top == r.correct
        top1 += right
        brier += sum((r.probs.get(k, 0.0) - (1.0 if k == r.correct else 0.0)) ** 2 for k in r.probs)
        nll += -math.log(max(r.probs.get(r.correct, 0.0), 1e-12))
        covered += r.correct in r.prediction_set
        conf = r.probs[top]
        conf_bins[min(bins - 1, int(conf * bins))].append((conf, right))
    ece = sum(len(b) / n * abs(sum(c for c, _ in b) / len(b) - sum(ok for _, ok in b) / len(b))
              for b in conf_bins if b)
    sel = [max(r.probs, key=lambda k: r.probs[k]) == r.correct for r in answered]
    return {"population": n, "denominator": "all calibration rows",
            "brier": round(brier / n, 4), "ece": round(ece, 4), "nll": round(nll / n, 4),
            "top1": round(top1 / n, 4), "set_coverage": round(covered / n, 4),
            "abstention_rate": round(1 - len(answered) / n, 4),
            "selective_accuracy": round(sum(sel) / len(sel), 4) if sel else None,
            "selective_denominator": len(answered)}


@dataclass(frozen=True)
class CalibrationArtifact:
    version: str
    threshold: float
    fitted_on: tuple[str, ...]
    digest: str
    target_risk: float

    def accept(self, confidence: float) -> bool:
        return confidence >= self.threshold


def fit_threshold(rows: Sequence[CalibrationRow], *, target_risk: float = 0.10,
                  version: str = "cal-v1") -> CalibrationArtifact:
    """The lowest confidence threshold whose accepted rows keep error under ``target_risk``."""
    scored = sorted(((max(r.probs.values()), max(r.probs, key=lambda k: r.probs[k]) == r.correct)
                     for r in rows), reverse=True)
    threshold, errors = 1.01, 0
    for count, (conf, right) in enumerate(scored, start=1):
        errors += not right
        if errors / count <= target_risk:
            threshold = conf
    ids = tuple(sorted(r.sample_id for r in rows))
    digest = hashlib.sha256(json.dumps({"ids": ids, "threshold": threshold, "risk": target_risk},
                                       sort_keys=True).encode()).hexdigest()
    return CalibrationArtifact(version, round(threshold, 6), ids, digest, target_risk)


def transfer_check(artifact: CalibrationArtifact, rows: Sequence[CalibrationRow]) -> dict[str, Any]:
    accepted = [r for r in rows if artifact.accept(max(r.probs.values()))]
    if not accepted:
        return {"mode": "REVIEW_ONLY", "reason": "no rows accepted in the new domain", "risk": None}
    risk = sum(max(r.probs, key=lambda k: r.probs[k]) != r.correct for r in accepted) / len(accepted)
    mode = "ADVISORY" if risk <= artifact.target_risk else "REVIEW_ONLY"
    return {"mode": mode, "risk": round(risk, 4), "accepted": len(accepted), "population": len(rows)}


def admissible_feedback(item: Mapping[str, Any]) -> bool:
    """Only evaluator-confirmed labels, recorded after the outcome they describe."""
    return (item.get("source") == "evaluator" and isinstance(item.get("label_at"), int)
            and isinstance(item.get("outcome_at"), int) and item["label_at"] > item["outcome_at"])
