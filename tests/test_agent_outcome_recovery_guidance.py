from __future__ import annotations

import pytest

from memory_fabric.agent_outcomes import (
    EvidenceFailureKind,
    READ_ONLY_RECOVERY_CATALOG,
    RecoveryDisposition,
    classify_evidence_failure,
    recovery_guidance,
)


@pytest.mark.parametrize("kind", list(EvidenceFailureKind))
def test_every_failure_has_structured_legal_fallback(kind: EvidenceFailureKind) -> None:
    guidance = recovery_guidance(classify_evidence_failure(kind.value))

    assert guidance.cause_code == kind.value
    assert guidance.protected_effect_allowed is False
    if guidance.next_action is not None:
        assert READ_ONLY_RECOVERY_CATALOG.permits(guidance.next_action)


def test_irrecoverable_and_unknown_failures_escalate_or_abstain() -> None:
    unauthorized = recovery_guidance(classify_evidence_failure("tool_not_granted"))
    erased = recovery_guidance(classify_evidence_failure("content_erased"))
    unknown = recovery_guidance(classify_evidence_failure("unexpected_code"))

    assert (unauthorized.disposition, unauthorized.next_action,
            unauthorized.operator_handoff) == (RecoveryDisposition.ESCALATE, None, True)
    assert (erased.disposition, erased.operator_handoff) == (
        RecoveryDisposition.ESCALATE, True,
    )
    assert (unknown.disposition, unknown.operator_handoff) == (
        RecoveryDisposition.ABSTAIN, True,
    )
