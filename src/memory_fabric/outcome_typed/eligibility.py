"""Content-free evidence failure diagnosis for experimental agent recovery.

The diagnoses classify existing, authoritative refusal signals. They do not
grant access, decide truth, or execute a suggested recovery; consequential
effects still pass through the host's ActionGate.
"""

from __future__ import annotations

__stability__ = "experimental"

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar, Mapping, Sequence

from .. import answerability as answerability_codes
from .. import certificates as certificate_codes
from .. import enforcement as access_codes
from ..answerability import Answerability
from ..certificates import CertificateVerification, EvidenceRef
from ..enforcement import AccessDecision, RiskLevel, Verdict
from ..relevance import ReasonCode
from .recovery import RecoveryAction


class EvidenceFailureCode(StrEnum):
    """Closed taxonomy of evidence states an actor can respond to."""

    MISSING = "missing"
    WITHHELD = "withheld"
    IRRELEVANT = "irrelevant"
    STALE = "stale"
    CONTESTED = "contested"
    UNAUTHORIZED = "unauthorized"
    ERASED = "erased"
    DUPLICATE = "duplicate"
    INSUFFICIENT = "insufficient"
    UNKNOWN = "unknown"


class DiagnosisSource(StrEnum):
    ACCESS = "access"
    CERTIFICATE = "certificate"
    ANSWERABILITY = "answerability"
    RELEVANCE = "relevance"


class ReportedTaskStatus(StrEnum):
    """Evaluator-provided terminal task state for a plain-language report."""

    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    UNVERIFIED = "unverified"


_RECOVERY_ADVICE: dict[EvidenceFailureCode, tuple[RecoveryAction, ...]] = {
    EvidenceFailureCode.MISSING: (RecoveryAction.RE_RETRIEVE,
                                  RecoveryAction.ASK_CLARIFICATION),
    EvidenceFailureCode.WITHHELD: (RecoveryAction.INSPECT_PROVENANCE,
                                   RecoveryAction.ASK_CLARIFICATION),
    EvidenceFailureCode.IRRELEVANT: (RecoveryAction.RE_RETRIEVE,
                                     RecoveryAction.REPLAN),
    EvidenceFailureCode.STALE: (RecoveryAction.REFRESH, RecoveryAction.RE_RETRIEVE),
    EvidenceFailureCode.CONTESTED: (RecoveryAction.INSPECT_PROVENANCE,
                                    RecoveryAction.ASK_CLARIFICATION),
    EvidenceFailureCode.UNAUTHORIZED: (),
    EvidenceFailureCode.ERASED: (),
    EvidenceFailureCode.DUPLICATE: (RecoveryAction.RE_RETRIEVE,
                                    RecoveryAction.INSPECT_PROVENANCE),
    EvidenceFailureCode.INSUFFICIENT: (RecoveryAction.RE_RETRIEVE,
                                       RecoveryAction.ASK_CLARIFICATION),
    EvidenceFailureCode.UNKNOWN: (),
}


@dataclass(frozen=True)
class EvidenceDiagnosis:
    """A stable, privacy-safe diagnosis and read-only recovery suggestions."""

    SCHEMA_ID: ClassVar[str] = "memory-fabric.evidence-diagnosis.v1"

    source: DiagnosisSource
    failure_codes: tuple[EvidenceFailureCode, ...]
    suggested_actions: tuple[RecoveryAction, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source, DiagnosisSource):
            raise ValueError("source must be a known diagnosis signal")
        if (any(not isinstance(code, EvidenceFailureCode) for code in self.failure_codes)
                or len(set(self.failure_codes)) != len(self.failure_codes)):
            raise ValueError("failure_codes must be unique known taxonomy values")
        if (any(not isinstance(action, RecoveryAction) for action in self.suggested_actions)
                or len(set(self.suggested_actions)) != len(self.suggested_actions)):
            raise ValueError("suggested_actions must be unique read-only catalog values")

    def to_json(self) -> dict[str, object]:
        """Serialize only closed enums; raw evidence and natural-language details are omitted."""
        return {
            "schema_id": self.SCHEMA_ID,
            "source": self.source.value,
            "failure_codes": [code.value for code in self.failure_codes],
            "suggested_actions": [action.value for action in self.suggested_actions],
        }


_FAILURE_EXPLANATIONS: Mapping[EvidenceFailureCode, str] = {
    EvidenceFailureCode.MISSING: "required evidence could not be found",
    EvidenceFailureCode.WITHHELD: "evidence was withheld by an access or trust rule",
    EvidenceFailureCode.IRRELEVANT: "the available evidence did not support this task",
    EvidenceFailureCode.STALE: "the evidence was expired or had changed",
    EvidenceFailureCode.CONTESTED: "the evidence has unresolved conflicting support",
    EvidenceFailureCode.UNAUTHORIZED: "the current agent is not authorized to use this source",
    EvidenceFailureCode.ERASED: "the evidence was erased and cannot be used",
    EvidenceFailureCode.DUPLICATE: "the available evidence was duplicate support",
    EvidenceFailureCode.INSUFFICIENT: "there was not enough independent evidence",
    EvidenceFailureCode.UNKNOWN: "the system could not safely classify the evidence failure",
}
_ACTION_EXPLANATIONS: Mapping[RecoveryAction, str] = {
    RecoveryAction.REFRESH: "request a current version from the authorized source",
    RecoveryAction.RE_RETRIEVE: "search approved sources again for current evidence",
    RecoveryAction.INSPECT_PROVENANCE: "review the source and its lineage before relying on it",
    RecoveryAction.REQUEST_OBSERVATION: "request a new observation from an approved source",
    RecoveryAction.ASK_CLARIFICATION: "ask the task owner which evidence or condition is required",
    RecoveryAction.REPLAN: "choose another authorized plan and verify its evidence",
}
_FALLBACK_NEXT_STEPS: Mapping[EvidenceFailureCode, str] = {
    EvidenceFailureCode.UNAUTHORIZED:
        "ask the source owner for access; do not bypass the access rule",
    EvidenceFailureCode.ERASED:
        "use an authorized independent replacement if available; otherwise stop",
    EvidenceFailureCode.UNKNOWN:
        "stop and ask an operator to review the evidence path",
}
_PUBLIC_SOURCE_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


def explain_task_failure(
    diagnosis: EvidenceDiagnosis,
    *,
    blocked_source_alias: str,
    task_status: ReportedTaskStatus,
) -> dict[str, object]:
    """Render a content-free, human-readable failure explanation.

    ``blocked_source_alias`` must be a public label already visible to the
    operator, never a memory ID, private source text, or credential. The task
    status must come from the independent terminal evaluator.
    """
    if not isinstance(diagnosis, EvidenceDiagnosis):
        raise ValueError("diagnosis must be an EvidenceDiagnosis")
    if not isinstance(task_status, ReportedTaskStatus):
        raise ValueError("task_status must come from the closed evaluator status set")
    if (not isinstance(blocked_source_alias, str)
            or _PUBLIC_SOURCE_ALIAS.fullmatch(blocked_source_alias) is None):
        raise ValueError("blocked_source_alias must be a short public display label")
    if not diagnosis.failure_codes:
        raise ValueError("a failure explanation requires at least one diagnosed failure")

    explanations = [_FAILURE_EXPLANATIONS[code] for code in diagnosis.failure_codes]
    actions = [_ACTION_EXPLANATIONS[action] for action in diagnosis.suggested_actions]
    next_step = (actions[0] if actions else
                 _FALLBACK_NEXT_STEPS.get(
                     diagnosis.failure_codes[0],
                     "stop and ask an operator to review the evidence path"))
    outcome = {
        ReportedTaskStatus.COMPLETED: "The task completed after recovery.",
        ReportedTaskStatus.INCOMPLETE: "The task did not complete.",
        ReportedTaskStatus.UNVERIFIED: "The final task outcome has not been verified.",
    }[task_status]
    return {
        "schema_id": "memory-fabric.why-task-failed.v1",
        "blocked_source": blocked_source_alias,
        "why": "; ".join(explanations),
        "legal_next_step": next_step,
        "task_outcome": outcome,
    }


def _diagnosis(source: DiagnosisSource,
               codes: tuple[EvidenceFailureCode, ...]) -> EvidenceDiagnosis:
    unique = tuple(dict.fromkeys(codes))
    actions = tuple(dict.fromkeys(action for code in unique
                                  for action in _RECOVERY_ADVICE[code]))
    return EvidenceDiagnosis(source, unique, actions)


def _access_code(decision: AccessDecision) -> EvidenceFailureCode | None:
    code = decision.reason_code
    if code == access_codes.ACTIVE and decision.verdict is Verdict.USABLE:
        return None
    if code == access_codes.NOT_FOUND:
        # NOT_FOUND intentionally also covers concealed cross-tenant ids.
        return EvidenceFailureCode.MISSING
    if code in {access_codes.WRONG_AGENT, access_codes.WRONG_STORE,
                access_codes.WRONG_TENANT, access_codes.NOT_VISIBLE}:
        return EvidenceFailureCode.UNAUTHORIZED
    if code in {access_codes.CANDIDATE_UNVALIDATED,
                access_codes.WITHDRAWN_ON_WEAK_EVIDENCE}:
        return EvidenceFailureCode.WITHHELD
    if code == access_codes.BLOCKED_LIFECYCLE:
        if decision.verdict is Verdict.UNKNOWN:
            return EvidenceFailureCode.UNKNOWN
        if decision.lifecycle_state == "deleted":
            return EvidenceFailureCode.ERASED
        return EvidenceFailureCode.WITHHELD
    if code == access_codes.CONTESTED:
        return EvidenceFailureCode.CONTESTED
    if code in {access_codes.VERSION_MOVED, access_codes.TOKEN_EXPIRED,
                access_codes.INTEGRITY_MOVED}:
        return EvidenceFailureCode.STALE
    return EvidenceFailureCode.UNKNOWN


def diagnose_access(decision: AccessDecision) -> EvidenceDiagnosis:
    """Classify one enforcer decision without copying its detail or memory id."""
    code = _access_code(decision)
    return _diagnosis(DiagnosisSource.ACCESS,
                      () if code is None else (code,))


_CERTIFICATE_FAILURES: dict[str, EvidenceFailureCode] = {
    certificate_codes.WRONG_STORE: EvidenceFailureCode.UNAUTHORIZED,
    certificate_codes.WRONG_AGENT: EvidenceFailureCode.UNAUTHORIZED,
    certificate_codes.WRONG_TENANT: EvidenceFailureCode.UNAUTHORIZED,
    certificate_codes.EXPIRED: EvidenceFailureCode.STALE,
    certificate_codes.POLICY_CHANGED: EvidenceFailureCode.STALE,
    certificate_codes.NO_SUPPORTING_EVIDENCE: EvidenceFailureCode.INSUFFICIENT,
    certificate_codes.EVIDENCE_NOT_FOUND: EvidenceFailureCode.MISSING,
    certificate_codes.EVIDENCE_ERASED: EvidenceFailureCode.ERASED,
    certificate_codes.DEPENDENCY_NOT_FOUND: EvidenceFailureCode.MISSING,
    certificate_codes.EVIDENCE_WITHDRAWN: EvidenceFailureCode.WITHHELD,
    certificate_codes.DEPENDENCY_WITHDRAWN: EvidenceFailureCode.WITHHELD,
    certificate_codes.EVIDENCE_VERSION_MOVED: EvidenceFailureCode.STALE,
    certificate_codes.EVIDENCE_OUTSIDE_CURRENT_VALIDITY: EvidenceFailureCode.STALE,
    certificate_codes.DEPENDENCY_VERSION_MOVED: EvidenceFailureCode.STALE,
    certificate_codes.EVIDENCE_NOT_USABLE: EvidenceFailureCode.WITHHELD,
    certificate_codes.INSUFFICIENT_INDEPENDENT_SUPPORT: EvidenceFailureCode.INSUFFICIENT,
    certificate_codes.STATE_UNAVAILABLE: EvidenceFailureCode.UNKNOWN,
    certificate_codes.MALFORMED: EvidenceFailureCode.UNKNOWN,
    certificate_codes.UNKNOWN_VERSION: EvidenceFailureCode.UNKNOWN,
    certificate_codes.TOO_LARGE: EvidenceFailureCode.UNKNOWN,
    certificate_codes.UNKNOWN_CHECK: EvidenceFailureCode.UNKNOWN,
}


def diagnose_certificate(verification: CertificateVerification) -> EvidenceDiagnosis:
    """Map verifier reason codes to the closed taxonomy, defaulting to unknown."""
    if verification.ok and verification.reason_codes == (certificate_codes.OK,):
        codes: tuple[EvidenceFailureCode, ...] = ()
    elif not verification.reason_codes:
        codes = (EvidenceFailureCode.UNKNOWN,)
    else:
        codes = tuple(_CERTIFICATE_FAILURES.get(reason, EvidenceFailureCode.UNKNOWN)
                      for reason in verification.reason_codes
                      if reason != certificate_codes.OK)
        if not codes:
            codes = (EvidenceFailureCode.UNKNOWN,)
    return _diagnosis(DiagnosisSource.CERTIFICATE, codes)


def diagnose_answerability(assessment: Answerability, *, exposed_count: int) -> EvidenceDiagnosis:
    """Classify coverage using only verdict and a count, never claim or memory text."""
    if exposed_count < 0:
        raise ValueError("exposed_count cannot be negative")
    verdict = assessment.verdict
    if verdict == answerability_codes.ANSWERABLE:
        codes: tuple[EvidenceFailureCode, ...] = ()
    elif verdict == answerability_codes.CONFLICTING:
        codes = (EvidenceFailureCode.CONTESTED,)
    elif verdict == answerability_codes.INSUFFICIENT:
        code = (EvidenceFailureCode.IRRELEVANT if exposed_count > 0
                else EvidenceFailureCode.INSUFFICIENT)
        codes = (code,)
    else:
        codes = (EvidenceFailureCode.UNKNOWN,)
    return _diagnosis(DiagnosisSource.ANSWERABILITY, codes)


_RELEVANCE_FAILURES: dict[ReasonCode, EvidenceFailureCode] = {
    ReasonCode.LOW_RELEVANCE: EvidenceFailureCode.IRRELEVANT,
    ReasonCode.CONTEXT_MISMATCH: EvidenceFailureCode.IRRELEVANT,
    ReasonCode.DUPLICATE_OR_REDUNDANT: EvidenceFailureCode.DUPLICATE,
    ReasonCode.OVER_BUDGET: EvidenceFailureCode.INSUFFICIENT,
    ReasonCode.INSUFFICIENT_EVIDENCE: EvidenceFailureCode.INSUFFICIENT,
    ReasonCode.SUPERSEDED: EvidenceFailureCode.STALE,
    ReasonCode.RETRACTED: EvidenceFailureCode.WITHHELD,
    ReasonCode.BLOCKED_LIFECYCLE: EvidenceFailureCode.WITHHELD,
    ReasonCode.UNAUTHORIZED: EvidenceFailureCode.UNAUTHORIZED,
    ReasonCode.WRONG_TENANT: EvidenceFailureCode.UNAUTHORIZED,
}

_RELEVANCE_SUCCESS = frozenset({
    ReasonCode.DIRECT_MATCH,
    ReasonCode.ENTITY_LINK,
    ReasonCode.TEMPORAL_APPLICABILITY,
    ReasonCode.SUPPORTS_HYPOTHESIS,
    ReasonCode.CONTRADICTS_HYPOTHESIS,
    ReasonCode.DEPENDENCY_REQUIRED,
    ReasonCode.CRITICAL_FACT,
})

MAX_ALTERNATE_SOURCE_RESULTS = 32
MAX_ALTERNATE_SOURCE_CANDIDATES = 128
MAX_ALTERNATE_SOURCE_BASES = 64
MAX_ALTERNATE_SOURCE_QUERY_CHARS = 4096


def find_alternate_sources(
    session: Any,
    query: str,
    existing_evidence: Sequence[EvidenceRef] = (),
    *,
    limit: int = 5,
) -> tuple[EvidenceRef, ...]:
    """Find current, authorized evidence from roots absent in the given basis.

    A live ``service.Session`` is required so retrieval and the follow-up read
    both recheck the caller's credential, tenant, scope, and collection grants.
    Same-root candidates are filtered internally and never returned as new
    support. This is a bounded read-only helper; the caller must still certify
    its chosen evidence and use ActionGate for any protected effect.
    """
    if (not isinstance(query, str) or not query.strip()
            or len(query) > MAX_ALTERNATE_SOURCE_QUERY_CHARS):
        raise ValueError("query must be non-empty and within the alternate-search limit")
    if (isinstance(limit, bool) or not isinstance(limit, int)
            or not 1 <= limit <= MAX_ALTERNATE_SOURCE_RESULTS):
        raise ValueError(f"limit must be between 1 and {MAX_ALTERNATE_SOURCE_RESULTS}")
    if (not isinstance(existing_evidence, Sequence)
            or len(existing_evidence) > MAX_ALTERNATE_SOURCE_BASES
            or any(not isinstance(ref, EvidenceRef) for ref in existing_evidence)):
        raise ValueError("existing_evidence must contain at most 64 typed evidence references")

    principal = session.principal()
    retrieved = session.retrieve(
        query, k=min(MAX_ALTERNATE_SOURCE_CANDIDATES,
                     limit + len(existing_evidence)),
        group_by_source_root=True,
    )
    fabric = session.service._fabric
    roots = {
        fabric.source_root(ref.memory_id)
        for ref in existing_evidence
        if (memory := fabric.state.memories.get(ref.memory_id)) is not None
        and memory.tenant_id == principal.tenant_id
    }

    alternates: list[EvidenceRef] = []
    for candidate in retrieved.exposed:
        if candidate.id in fabric.state.erased:
            continue
        current = session.use(candidate.id, risk=RiskLevel.HIGH)
        if not current.usable or current.memory is None:
            continue
        if current.memory.version != candidate.version:
            continue
        root = fabric.source_root(candidate.id)
        if root in roots:
            continue
        roots.add(root)
        alternates.append(EvidenceRef(candidate.id, current.memory.version))
        if len(alternates) >= limit:
            break
    return tuple(alternates)


def diagnose_relevance(reason: ReasonCode | str) -> EvidenceDiagnosis:
    """Classify a typed ranking/gate reason; unrecognized values stay unknown."""
    if isinstance(reason, ReasonCode) and reason in _RELEVANCE_SUCCESS:
        return _diagnosis(DiagnosisSource.RELEVANCE, ())
    code = _RELEVANCE_FAILURES.get(reason) if isinstance(reason, ReasonCode) else None
    return _diagnosis(DiagnosisSource.RELEVANCE,
                      (code if code is not None else EvidenceFailureCode.UNKNOWN,))
