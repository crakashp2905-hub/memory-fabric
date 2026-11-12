from __future__ import annotations

import pytest

from memory_fabric import MemoryFabric
from memory_fabric.actions import REFUSED, ActionGate, ActionPolicy, ToolRule
from memory_fabric.agent_outcomes import RecoveryEpisode


@pytest.mark.parametrize("invalidation", ["cross_tenant", "erased", "stale", "revoked"])
def test_recovery_never_overrides_action_gate_for_invalid_evidence(invalidation: str) -> None:
    fabric = MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False)
    try:
        memory_id = fabric.remember(
            "operator", "Pump P-7 pressure is within the safe range.", tenant_id="tenant-a"
        )
        certificate = fabric.certify(
            "pressure_safe", [memory_id], "operator", tenant_id="tenant-a"
        )
        gate = ActionGate(fabric, ActionPolicy(
            tools={"start_pump": ToolRule("start_pump")},
            grants={"operator": frozenset({"start_pump"})},
        ))
        effects: list[str] = []

        if invalidation == "cross_tenant":
            tenant_id = "tenant-b"
        else:
            tenant_id = "tenant-a"
            if invalidation == "erased":
                fabric.erase_content(memory_id, "subject request")
            elif invalidation == "stale":
                fabric.revise(memory_id, "Pump P-7 pressure is now unknown.", "operator",
                              "reading corrected")
            elif invalidation == "revoked":
                fabric.quarantine(memory_id, "reading withdrawn", actor="reviewer")

        episode = RecoveryEpisode(f"task-{invalidation}", enabled=True)
        assert episode.record("re_retrieve", {"progress_key": f"refresh-{invalidation}"})
        result = episode.execute(
            gate, "start_pump", "operator", certificate,
            lambda key: effects.append(key), key=f"effect-{invalidation}",
            tenant_id=tenant_id,
        )

        assert result.outcome == REFUSED
        assert result.ran is False
        assert effects == []
        assert episode.status.value == "BLOCKED"
        assert episode.trace[-1]["kind"] == "action_gate"
        assert episode.trace[-1]["reason_codes"]
    finally:
        fabric.close()
