from __future__ import annotations

from memory_fabric import MemoryFabric
from memory_fabric.exposure import AlwaysExposePolicy
from memory_fabric.outcome_protocol import search_alternate_sources


def _fabric() -> MemoryFabric:
    return MemoryFabric(
        ":memory:", auto_activate=True, exposure_policy=AlwaysExposePolicy(),
        hold_suspicious=False,
    )


def test_valid_independent_source_can_recover_a_blocked_evidence_task() -> None:
    fabric = _fabric()
    try:
        original = fabric.remember(
            "operator", "Pump P-7 pressure is 30 psi.", tenant_id="tenant-a", scope="team"
        )
        alternate = fabric.remember(
            "inspector", "P-7 pressure readings were independently captured by the night-shift "
            "telemetry technician, who inspected the remote console and confirmed the "
            "instrument calibration before recording the value as thirty pounds per square "
            "inch.",
            tenant_id="tenant-a", scope="team",
        )

        found = search_alternate_sources(
            fabric, query="P-7 pressure", agent_id="operator",
            tenant_id="tenant-a", existing_evidence_ids=(original,), limit=10,
        )

        assert [(item.memory_id, item.version) for item in found] == [(alternate, 1)]
        assert found[0].source_root == fabric.source_root(alternate)
    finally:
        fabric.close()


def test_duplicate_root_is_not_returned_as_independent_recovery() -> None:
    fabric = _fabric()
    try:
        original = fabric.remember(
            "operator", "Pump P-7 pressure is 30 psi.", tenant_id="tenant-a", scope="team"
        )
        copied = fabric.derive(
            "inspector", "Pump P-7 pressure is 30 psi.", [original],
            tenant_id="tenant-a", scope="team",
        )

        found = search_alternate_sources(
            fabric, query="Pump P-7 pressure psi", agent_id="operator",
            tenant_id="tenant-a", existing_evidence_ids=(original,), limit=10,
        )

        assert copied not in {item.memory_id for item in found}
        assert found == ()
    finally:
        fabric.close()


def test_revoked_and_wrong_tenant_candidates_are_not_returned() -> None:
    fabric = _fabric()
    try:
        revoked = fabric.remember(
            "inspector", "Pump P-7 pressure reads 30 psi after inspection.",
            tenant_id="tenant-a", scope="team",
        )
        foreign = fabric.remember(
            "inspector", "Pump P-7 pressure reads 30 psi from another facility.",
            tenant_id="tenant-b", scope="team",
        )
        fabric.quarantine(revoked, "withdrawn report", actor="reviewer")

        found = search_alternate_sources(
            fabric, query="Pump P-7 pressure psi", agent_id="operator",
            tenant_id="tenant-a", limit=10,
        )

        assert revoked not in {item.memory_id for item in found}
        assert foreign not in {item.memory_id for item in found}
    finally:
        fabric.close()
