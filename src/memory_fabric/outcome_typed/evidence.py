"""One status vocabulary for agent-outcome evidence, and the rules that keep it honest.

Checklist W01-04, W01-07 and W01-08. Every gate, report and dashboard that says
what is known about agent outcomes uses :class:`OutcomeEvidenceStatus`, bound to
the kind of evidence that produced it (:class:`EvidenceType`) and the exact
source commit it ran on. The constructors refuse the combinations that would let
one kind of evidence stand in for another: a green CI run cannot be rendered as
a real-agent pass, a scripted pass cannot be rendered as a local-model pass, and
a confirmatory verdict needs a frozen registration.

:func:`validate_paired_comparison` refuses to compare two result populations
unless they were scored on the same task IDs, by the same generator, in the same
outcome unit; it also refuses to pool a retrospective result with a same-commit
reproduction. Filenames are never evidence of pairing.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

_SHA40 = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class OutcomeEvidenceStatus(str, Enum):
    """What is known, never more than the evidence behind it supports."""

    NOT_RUN = "NOT_RUN"
    BLOCKED = "BLOCKED"
    SCRIPTED_PASS = "SCRIPTED_PASS"
    LOCAL_MODEL_PASS = "LOCAL_MODEL_PASS"
    CONFIRMATORY_SUPPORTED = "CONFIRMATORY_SUPPORTED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


class EvidenceType(str, Enum):
    """Where a status came from. A status is only as strong as its type."""

    CI = "ci"
    CONTRACT = "contract"
    SCRIPTED = "scripted"
    MODEL_ATTACK = "model_attack"
    LOCAL_MODEL = "local_model"
    CONFIRMATORY = "confirmatory"
    INDEPENDENT = "independent"


# The only evidence types that can carry each positive status.
_POSITIVE_REQUIRES: dict[OutcomeEvidenceStatus, frozenset[EvidenceType]] = {
    OutcomeEvidenceStatus.SCRIPTED_PASS: frozenset({EvidenceType.SCRIPTED, EvidenceType.CONTRACT,
                                                    EvidenceType.CI}),
    OutcomeEvidenceStatus.LOCAL_MODEL_PASS: frozenset({EvidenceType.LOCAL_MODEL,
                                                       EvidenceType.MODEL_ATTACK}),
    OutcomeEvidenceStatus.CONFIRMATORY_SUPPORTED: frozenset({EvidenceType.CONFIRMATORY}),
}

# A gate may only be reported from evidence of these types.
GATE_EVIDENCE_TYPES: dict[str, frozenset[EvidenceType]] = {
    "main_ci": frozenset({EvidenceType.CI}),
    "synthetic_outcome_gate": frozenset({EvidenceType.SCRIPTED, EvidenceType.CONTRACT}),
    "model_attacks": frozenset({EvidenceType.MODEL_ATTACK}),
    "real_agent": frozenset({EvidenceType.LOCAL_MODEL}),
    "confirmatory": frozenset({EvidenceType.CONFIRMATORY}),
    "independent_review": frozenset({EvidenceType.INDEPENDENT}),
}


class EvidenceBoundaryError(ValueError):
    """Raised when a status would overstate the evidence behind it."""


@dataclass(frozen=True)
class GateEvidence:
    """One gate's status, the evidence type behind it and the commit it ran on."""

    gate_id: str
    status: OutcomeEvidenceStatus
    evidence_type: EvidenceType
    target_sha: str | None
    reason: str
    model_digest: str | None = None
    registration_sha256: str | None = None
    artifacts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, OutcomeEvidenceStatus):
            raise TypeError("status must be OutcomeEvidenceStatus")
        if not isinstance(self.evidence_type, EvidenceType):
            raise TypeError("evidence_type must be EvidenceType")
        if not isinstance(self.gate_id, str) or not self.gate_id:
            raise ValueError("gate_id must be a non-empty string")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("every gate status needs a reason")
        if self.target_sha is not None and not _SHA40.fullmatch(self.target_sha):
            raise ValueError("target_sha must be a 40-hex commit or None")
        allowed = GATE_EVIDENCE_TYPES.get(self.gate_id)
        if allowed is not None and self.evidence_type not in allowed:
            raise EvidenceBoundaryError(
                f"gate {self.gate_id!r} cannot be reported from {self.evidence_type.value} evidence")
        required = _POSITIVE_REQUIRES.get(self.status)
        if required is not None:
            if self.evidence_type not in required:
                raise EvidenceBoundaryError(
                    f"{self.status.value} cannot rest on {self.evidence_type.value} evidence")
            if self.target_sha is None:
                raise EvidenceBoundaryError(f"{self.status.value} requires the exact target SHA")
        if self.status is OutcomeEvidenceStatus.LOCAL_MODEL_PASS and not (
                isinstance(self.model_digest, str) and self.model_digest):
            raise EvidenceBoundaryError("LOCAL_MODEL_PASS requires the pinned model digest")
        if self.status is OutcomeEvidenceStatus.CONFIRMATORY_SUPPORTED and not (
                isinstance(self.registration_sha256, str)
                and _SHA256.fullmatch(self.registration_sha256)):
            raise EvidenceBoundaryError(
                "CONFIRMATORY_SUPPORTED requires the frozen registration SHA-256")
        object.__setattr__(self, "artifacts", tuple(self.artifacts))

    def to_dict(self) -> dict[str, Any]:
        return {"gate_id": self.gate_id, "status": self.status.value,
                "evidence_type": self.evidence_type.value, "target_sha": self.target_sha,
                "reason": self.reason, "model_digest": self.model_digest,
                "registration_sha256": self.registration_sha256,
                "artifacts": list(self.artifacts)}


def from_legacy_gate_status(gate_id: str, legacy: str, evidence_type: EvidenceType,
                            target_sha: str | None, reason: str) -> GateEvidence:
    """Translate a PASS/FAIL/NOT_RUN gate result without upgrading its evidence type."""
    if legacy == "PASS":
        positive = {EvidenceType.LOCAL_MODEL: OutcomeEvidenceStatus.LOCAL_MODEL_PASS,
                    EvidenceType.MODEL_ATTACK: OutcomeEvidenceStatus.LOCAL_MODEL_PASS,
                    EvidenceType.CONFIRMATORY: OutcomeEvidenceStatus.CONFIRMATORY_SUPPORTED}
        status = positive.get(evidence_type, OutcomeEvidenceStatus.SCRIPTED_PASS)
    elif legacy == "FAIL":
        status = OutcomeEvidenceStatus.FAILED
    elif legacy == "NOT_RUN":
        status = OutcomeEvidenceStatus.NOT_RUN
    else:
        raise ValueError(f"unknown legacy gate status {legacy!r}")
    return GateEvidence(gate_id, status, evidence_type, target_sha, reason)


RELEASE_MATRIX_GATES = ("main_ci", "synthetic_outcome_gate", "model_attacks", "real_agent",
                        "confirmatory", "independent_review")


def release_evidence_matrix(entries: Iterable[GateEvidence]) -> dict[str, Any]:
    """Render each gate from its own evidence; an absent gate is NOT_RUN, never inherited.

    The overall engineering status never upgrades a gate: a release candidate with
    a green CI row and a NOT_RUN real-agent row reports exactly that.
    """
    by_gate: dict[str, GateEvidence] = {}
    for entry in entries:
        if not isinstance(entry, GateEvidence):
            raise TypeError("matrix entries must be GateEvidence")
        if entry.gate_id in by_gate:
            raise ValueError(f"duplicate evidence for gate {entry.gate_id!r}")
        by_gate[entry.gate_id] = entry
    rows: list[dict[str, Any]] = []
    for gate in RELEASE_MATRIX_GATES:
        found = by_gate.get(gate)
        if found is None:
            rows.append({"gate_id": gate, "status": OutcomeEvidenceStatus.NOT_RUN.value,
                         "evidence_type": None, "target_sha": None,
                         "reason": "no evidence of this gate's own type was supplied"})
        else:
            rows.append(found.to_dict())
    extra = sorted(set(by_gate) - set(RELEASE_MATRIX_GATES))
    rows.extend(by_gate[gate].to_dict() for gate in extra)
    shas = {row["target_sha"] for row in rows if row["target_sha"]}
    return {"schema_id": "memory-fabric.release-evidence-matrix.v1", "rows": rows,
            "target_shas": sorted(shas),
            "single_target_sha": len(shas) <= 1,
            "production_qualified": False,
            "production_reason": ("in-house evidence cannot self-certify production; "
                                  "independent review and pilot remain separate gates")}


class Population(str, Enum):
    """Whether a result was reproduced at the commit under test."""

    SAME_COMMIT = "same_commit"
    RETROSPECTIVE = "retrospective"


@dataclass(frozen=True)
class ResultPopulation:
    """What a set of outcome rows was measured on; the basis for pairing."""

    task_ids: tuple[str, ...]
    generator_id: str
    generator_revision: str
    outcome_unit: str
    population: Population
    source_sha: str | None = None
    arms: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        ids = tuple(self.task_ids)
        if not ids or not all(isinstance(item, str) and item for item in ids):
            raise ValueError("task_ids must be non-empty strings")
        if len(set(ids)) != len(ids):
            raise ValueError("task_ids must be unique")
        object.__setattr__(self, "task_ids", tuple(sorted(ids)))
        object.__setattr__(self, "arms", tuple(self.arms))
        for name in ("generator_id", "generator_revision", "outcome_unit"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.population, Population):
            raise TypeError("population must be Population")
        if self.population is Population.SAME_COMMIT and not (
                isinstance(self.source_sha, str) and _SHA40.fullmatch(self.source_sha)):
            raise ValueError("a same-commit population must name its 40-hex source SHA")

    @property
    def task_set_digest(self) -> str:
        return hashlib.sha256(json.dumps(list(self.task_ids)).encode("utf-8")).hexdigest()


class UnpairedComparisonError(ValueError):
    """Raised when two populations cannot be compared case by case."""


def validate_paired_comparison(left: ResultPopulation, right: ResultPopulation) -> dict[str, Any]:
    """Refuse a comparison unless task IDs, generator and outcome unit all match."""
    problems: list[str] = []
    if left.task_ids != right.task_ids:
        only_left = sorted(set(left.task_ids) - set(right.task_ids))
        only_right = sorted(set(right.task_ids) - set(left.task_ids))
        problems.append(f"task IDs differ ({len(only_left)} only left, {len(only_right)} only right)")
    if (left.generator_id, left.generator_revision) != (right.generator_id,
                                                        right.generator_revision):
        problems.append("generator or generator revision differs")
    if left.outcome_unit != right.outcome_unit:
        problems.append(f"outcome units differ ({left.outcome_unit!r} vs {right.outcome_unit!r})")
    if left.population is not right.population:
        problems.append("a retrospective result cannot be paired with a same-commit reproduction")
    elif left.population is Population.SAME_COMMIT and left.source_sha != right.source_sha:
        problems.append("same-commit populations ran at different source SHAs")
    if problems:
        raise UnpairedComparisonError("; ".join(problems))
    return {"paired": True, "task_count": len(left.task_ids),
            "task_set_digest": left.task_set_digest, "outcome_unit": left.outcome_unit,
            "population": left.population.value}
