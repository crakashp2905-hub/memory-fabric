from __future__ import annotations

import pytest

from memory_fabric import MemoryFabric
from memory_fabric.actions import EXECUTED, ActionGate, ActionPolicy, ToolRule
from memory_fabric.agent_outcomes import (
    RecoveryEpisode,
    RecoveryStatus,
    classify_evidence_failure,
)


def test_recovery_is_off_by_default_and_legacy_gate_behavior_is_unchanged() -> None:
    fabric = MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False)
    try:
        memory_id = fabric.remember("operator", "Pressure is within range.", scope="team")
        certificate = fabric.certify("pressure_safe", [memory_id], "operator")
        gate = ActionGate(fabric, ActionPolicy(
            tools={"start_pump": ToolRule("start_pump")},
            grants={"operator": frozenset({"start_pump"})},
        ))
        episode = RecoveryEpisode("default-off")
        effects: list[str] = []

        assert episode.enabled is False
        assert episode.status is RecoveryStatus.DISABLED
        assert episode.record("replan") is False
        assert episode.search_alternate_sources(
            classify_evidence_failure("not_found"), fabric, query="pressure",
            agent_id="operator", tenant_id="default",
        ) == ()
        with pytest.raises(RuntimeError, match="recovery is disabled"):
            episode.execute(gate, "start_pump", "operator", certificate,
                            lambda key: effects.append(key), key="recovery-disabled")
        assert effects == []

        legacy = gate.execute("start_pump", "operator", lambda key: effects.append(key),
                              certificate, key="legacy-path")
        assert legacy.outcome == EXECUTED
        assert effects == ["legacy-path"]
    finally:
        fabric.close()


def test_feature_flag_requires_a_real_boolean() -> None:
    with pytest.raises(ValueError, match="boolean feature flag"):
        RecoveryEpisode("invalid-flag", enabled=1)
