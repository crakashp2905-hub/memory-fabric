"""Stable classifications for evidence that cannot support an agent decision."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass
from enum import StrEnum
import re


class EvidenceFailureKind(StrEnum):
    MISSING = "EVIDENCE_MISSING"
    WITHHELD = "EVIDENCE_WITHHELD"
    IRRELEVANT = "EVIDENCE_IRRELEVANT"
    STALE = "EVIDENCE_STALE"
    CONTESTED = "EVIDENCE_CONTESTED"
    UNAUTHORIZED = "EVIDENCE_UNAUTHORIZED"
    ERASED = "EVIDENCE_ERASED"
    DUPLICATE = "EVIDENCE_DUPLICATE"
    INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class EvidenceFailure:
    """A stable taxonomy label plus the original refusal code, when supplied."""

    kind: EvidenceFailureKind
    source_reason_code: str | None = None

    @property
    def reason_code(self) -> str:
        """Return the stable taxonomy code suitable for reports and audit rows."""
        return self.kind.value


_ALIASES: dict[EvidenceFailureKind, frozenset[str]] = {
    EvidenceFailureKind.MISSING: frozenset({
        "not_found", "missing", "evidence_missing", "requirement_evidence_missing",
    }),
    EvidenceFailureKind.WITHHELD: frozenset({
        "not_visible", "withheld", "evidence_withdrawn", "content_withheld",
        "withdrawn_on_weak_evidence",
    }),
    EvidenceFailureKind.IRRELEVANT: frozenset({
        "irrelevant", "evidence_off_target", "off_target", "insufficient_chain",
    }),
    EvidenceFailureKind.STALE: frozenset({
        "stale", "version_moved", "evidence_version_moved", "stale_revision_epoch",
        "evidence_not_fresh",
    }),
    EvidenceFailureKind.CONTESTED: frozenset({
        "contested", "claim_evidence_disputed", "disputed", "contradicted",
    }),
    EvidenceFailureKind.UNAUTHORIZED: frozenset({
        "unauthorized", "wrong_tenant", "tool_not_granted", "authority_insufficient",
        "scope_denied", "permission_revoked",
    }),
    EvidenceFailureKind.ERASED: frozenset({
        "erased", "record_erased", "source_erased", "content_erased",
    }),
    EvidenceFailureKind.DUPLICATE: frozenset({
        "duplicate", "duplicate_evidence", "duplicate_source", "copy_correlated",
    }),
    EvidenceFailureKind.INSUFFICIENT: frozenset({
        "insufficient", "insufficient_evidence", "insufficient_independent_support",
    }),
}


def _normalize(code: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", code.strip().casefold()).strip("_")


_KIND_BY_ALIAS = {
    _normalize(alias): kind
    for kind, aliases in _ALIASES.items()
    for alias in aliases | {kind.value}
}


def classify_evidence_failure(reason_code: str | None) -> EvidenceFailure:
    """Map known refusal codes into the fixed taxonomy; preserve unknowns explicitly."""
    if not isinstance(reason_code, str) or not reason_code.strip():
        return EvidenceFailure(EvidenceFailureKind.UNKNOWN, reason_code)
    kind = _KIND_BY_ALIAS.get(_normalize(reason_code), EvidenceFailureKind.UNKNOWN)
    return EvidenceFailure(kind, reason_code)
