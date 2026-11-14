from __future__ import annotations

import pytest

from memory_fabric.outcome_protocol import (
    EvidenceFailureKind,
    classify_evidence_failure,
)


@pytest.mark.parametrize(
    ("source_code", "expected"),
    [
        ("not_found", EvidenceFailureKind.MISSING),
        ("content_withheld", EvidenceFailureKind.WITHHELD),
        ("evidence_off_target", EvidenceFailureKind.IRRELEVANT),
        ("STALE_REVISION_EPOCH", EvidenceFailureKind.STALE),
        ("claim_evidence_disputed", EvidenceFailureKind.CONTESTED),
        ("tool_not_granted", EvidenceFailureKind.UNAUTHORIZED),
        ("content_erased", EvidenceFailureKind.ERASED),
        ("duplicate_source", EvidenceFailureKind.DUPLICATE),
        ("insufficient_independent_support", EvidenceFailureKind.INSUFFICIENT),
        ("unmapped_refusal", EvidenceFailureKind.UNKNOWN),
    ],
)
def test_refusal_codes_map_to_stable_taxonomy(source_code, expected) -> None:
    failure = classify_evidence_failure(source_code)

    assert failure.kind is expected
    assert failure.reason_code == expected.value
    assert failure.source_reason_code == source_code


@pytest.mark.parametrize("source_code", [None, "", "   ", 17])
def test_missing_or_non_string_refusal_is_explicitly_unknown(source_code) -> None:
    failure = classify_evidence_failure(source_code)

    assert failure.kind is EvidenceFailureKind.UNKNOWN
    assert failure.reason_code == "UNKNOWN"
