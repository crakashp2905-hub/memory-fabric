"""Content-free evidence failure diagnosis for experimental agent recovery.

The diagnoses classify existing, authoritative refusal signals. They do not
grant access, decide truth, or execute a suggested recovery; consequential
effects still pass through the host's ActionGate.
"""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from .. import answerability as answerability_codes
from .. import certificates as certificate_codes
from .. import enforcement as access_codes
from ..answerability import Answerability
from ..certificates import CertificateVerification
from ..enforcement import AccessDecision, Verdict
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
    certificate_codes.DEPENDENCY_NOT_FOUND: EvidenceFailureCode.MISSING,
    certificate_codes.EVIDENCE_WITHDRAWN: EvidenceFailureCode.WITHHELD,
    certificate_codes.DEPENDENCY_WITHDRAWN: EvidenceFailureCode.WITHHELD,
    certificate_codes.EVIDENCE_VERSION_MOVED: EvidenceFailureCode.STALE,
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


def diagnose_relevance(reason: ReasonCode | str) -> EvidenceDiagnosis:
    """Classify a typed ranking/gate reason; unrecognized values stay unknown."""
    if isinstance(reason, ReasonCode) and reason in _RELEVANCE_SUCCESS:
        return _diagnosis(DiagnosisSource.RELEVANCE, ())
    code = _RELEVANCE_FAILURES.get(reason) if isinstance(reason, ReasonCode) else None
    return _diagnosis(DiagnosisSource.RELEVANCE,
                      (code if code is not None else EvidenceFailureCode.UNKNOWN,))
