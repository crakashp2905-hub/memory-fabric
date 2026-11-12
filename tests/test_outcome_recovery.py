from __future__ import annotations

from memory_fabric import MemoryFabric
from memory_fabric.agent_outcomes import (
    RecoveryEpisode,
    classify_evidence_failure,
    classify_recovery_failure,
    RecoveryFailureClass,
)
from memory_fabric.exposure import AlwaysExposePolicy


def test_authorization_failure_suppresses_requery_and_records_telemetry(monkeypatch) -> None:
    fabric = MemoryFabric(
        ":memory:", auto_activate=True, exposure_policy=AlwaysExposePolicy(),
        hold_suspicious=False,
    )
    try:
        calls: list[str] = []

        def forbidden_retrieve(**kwargs):
            calls.append("retrieve")
            raise AssertionError("authorization failures must not re-query")

        monkeypatch.setattr(fabric, "retrieve", forbidden_retrieve)
        episode = RecoveryEpisode("authorization-block", enabled=True)
        failure = classify_evidence_failure("tool_not_granted")

        result = episode.search_alternate_sources(
            failure, fabric, query="pump pressure", agent_id="operator",
            tenant_id="tenant-a",
        )

        assert result == ()
        assert calls == []
        assert classify_recovery_failure(failure) is RecoveryFailureClass.AUTHORIZATION
        assert episode.recovery_telemetry() == {
            "alternate_search_attempts": 0,
            "authorization_requeries_suppressed": 1,
            "unauthorized_alternate_source_accesses": 0,
        }
        assert episode.trace[-1]["kind"] == "alternate_search_suppressed"
    finally:
        fabric.close()


def test_retrieval_failure_allows_one_grant_checked_alternate_search() -> None:
    fabric = MemoryFabric(
        ":memory:", auto_activate=True, exposure_policy=AlwaysExposePolicy(),
        hold_suspicious=False,
    )
    try:
        source_id = fabric.remember(
            "inspector", "P-7 pressure readings were independently captured by the night-shift "
            "telemetry technician, who inspected the remote console and confirmed the "
            "instrument calibration before recording the value as thirty pounds per square "
            "inch.", tenant_id="tenant-a", scope="team",
        )
        episode = RecoveryEpisode("retrieval-block", enabled=True)

        found = episode.search_alternate_sources(
            classify_evidence_failure("not_found"), fabric,
            query="P-7 pressure", agent_id="operator", tenant_id="tenant-a",
        )

        assert [item.memory_id for item in found] == [source_id]
        assert episode.recovery_telemetry() == {
            "alternate_search_attempts": 1,
            "authorization_requeries_suppressed": 0,
            "unauthorized_alternate_source_accesses": 0,
        }
    finally:
        fabric.close()
