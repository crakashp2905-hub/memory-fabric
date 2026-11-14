"""Stable classifications for evidence that cannot support an agent decision."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any

from ..enforcement import RiskLevel, Verdict


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


@dataclass(frozen=True)
class AlternateEvidence:
    """A currently usable alternate source, identified without copying content."""

    memory_id: str
    version: int
    source_root: str


def search_alternate_sources(
    fabric: Any,
    *,
    query: str,
    agent_id: str,
    tenant_id: str,
    existing_evidence_ids: tuple[str, ...] = (),
    limit: int = 5,
) -> tuple[AlternateEvidence, ...]:
    """Retrieve current, authorized evidence from roots independent of existing sources.

    Search goes through MemoryFabric's normal retrieval path, which applies the
    caller's current tenant, visibility, lifecycle, and exposure rules. The
    result is rechecked before return to catch state changes during retrieval.
    Protected effects still require ActionGate's action-time verification. This
    function never grants source or tool access.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if not isinstance(agent_id, str) or not agent_id.strip():
        raise ValueError("agent_id must be a non-empty string")
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("tenant_id must be explicit for alternate-source search")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer from 1 to 100")
    if any(not isinstance(memory_id, str) or not memory_id for memory_id in existing_evidence_ids):
        raise ValueError("existing_evidence_ids must contain non-empty ids")

    existing_roots = {
        fabric.source_root(memory_id)
        for memory_id in existing_evidence_ids
        if memory_id in fabric.state.memories
    }
    result = fabric.retrieve(
        agent_id=agent_id,
        query=query,
        tenant_id=tenant_id,
        k=limit,
        min_relevance=0.0,
        group_by_source_root=True,
    )
    fabric.refresh()

    alternatives: list[AlternateEvidence] = []
    seen_roots = set(existing_roots)
    for memory in result.exposed:
        decision = fabric.enforcer.check(
            memory.id, risk=RiskLevel.HIGH, tenant_id=tenant_id, agent_id=agent_id,
        )
        if decision.verdict is not Verdict.USABLE or decision.version != memory.version:
            continue
        root = fabric.source_root(memory.id)
        if root in seen_roots:
            continue
        seen_roots.add(root)
        alternatives.append(AlternateEvidence(memory.id, memory.version, root))
    return tuple(alternatives)
