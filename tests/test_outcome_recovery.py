from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule, reconciliation_ledger
from memory_fabric.decision_records import (
    DecisionEdge, DecisionLedger, DecisionOption, DecisionReevaluationReceipt,
    DecisionRecord, EvidenceVersion,
)
from memory_fabric.agent_outcomes import (
    RecoveryEpisode,
    classify_evidence_failure,
    classify_recovery_failure,
    RecoveryFailureClass,
)
from memory_fabric.exposure import AlwaysExposePolicy

ROOT = Path(__file__).resolve().parents[1]


def test_correction_receipt_drives_an_advisory_replan_transition() -> None:
    episode = RecoveryEpisode("replan-task", enabled=True)
    assert episode.record("evidence_blocked", {"cause_code": "EVIDENCE_STALE"})
    receipt = DecisionReevaluationReceipt(
        receipt_id="receipt-1", trigger_event_id="event-correction-1",
        decision_id="decision-1", changed_premise=EvidenceVersion("memory-1", 2),
        current_decision_status="proposed", proof_edge_ids=("edge-relied-on",),
        affected_effect_ids=("edge-execution",),
    )

    assert episode.replan_from_reevaluation(
        receipt, plan_sha256="a" * 64, progress_key="correction-replan-1",
    )
    assert episode.status.value == "RECOVERED"
    assert episode.trace[-1]["kind"] == "replan"
    assert episode.trace[-1]["detail"]["receipt_id"] == "receipt-1"
    assert episode.trace[-1]["detail"]["action_authorized"] is False
    steps = episode.steps
    assert episode.replan_from_reevaluation(
        receipt, plan_sha256="a" * 64, progress_key="correction-replan-1",
    )
    assert episode.steps == steps


def test_replan_rejects_unlinked_or_malformed_correction_transitions() -> None:
    receipt = DecisionReevaluationReceipt(
        receipt_id="receipt-1", trigger_event_id="event-correction-1",
        decision_id="decision-1", changed_premise=EvidenceVersion("memory-1", 2),
        current_decision_status="proposed", proof_edge_ids=("edge-relied-on",),
        affected_effect_ids=(),
    )
    episode = RecoveryEpisode("replan-task", enabled=True)
    with pytest.raises(RuntimeError, match="evidence-blocked"):
        episode.replan_from_reevaluation(
            receipt, plan_sha256="a" * 64, progress_key="replan-1",
        )
    assert episode.record("evidence_blocked", {"cause_code": "EVIDENCE_STALE"})
    with pytest.raises(ValueError, match="SHA-256"):
        episode.replan_from_reevaluation(
            receipt, plan_sha256="not-a-digest", progress_key="replan-1",
        )
    with pytest.raises(TypeError, match="DecisionReevaluationReceipt"):
        episode.replan_from_reevaluation(
            {"action_authorized": False}, plan_sha256="a" * 64,
            progress_key="replan-1",
        )


def test_correction_preserves_historical_decision_but_revokes_old_authorization() -> None:
    fabric = MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False)
    try:
        memory_id = fabric.remember("reviewer", "Current pressure is 42.", scope="team")
        fabric.elevate(memory_id, approver="operator", reason="source checked")
        premise = EvidenceVersion(memory_id, 1)
        ledger = DecisionLedger(fabric.log, lambda: 1_800_000_000_000)
        decision = DecisionRecord(
            "decision-1", "tn_default", "agent-1", "2026-11-13T10:00:00Z",
            "set threshold from the observed pressure",
            (DecisionOption("option-42", "Use 42", (premise,)),),
            "option-42", (premise,), {},
        )
        ledger.record(decision)
        ledger.link(DecisionEdge(
            "relied-1", "decision-1", "relied_on", "claim-42", "agent-1",
            "2026-11-13T10:01:00Z", premise,
        ))
        certificate = fabric.certify("decision-1", [memory_id], "agent-1")
        gate = ActionGate(fabric, ActionPolicy(
            tools={"publish": ToolRule("publish")},
            grants={"agent-1": frozenset({"publish"})},
        ))
        assert gate.authorize("publish", "agent-1", certificate).allowed

        fabric.revise(memory_id, "Current pressure is 40.", agent_id="reviewer",
                      reason="verified correction", expected_version=1)
        event = next(item for item in reversed(list(fabric.log.read()))
                     if item.type == "MemoryVersioned"
                     and item.payload.get("memory", {}).get("id") == memory_id)
        receipt, = ledger.reevaluation_receipts_from_event(event.event_id)

        assert ledger.get("decision-1") == decision
        assert receipt.changed_premise == premise
        assert receipt.action_authorized is False
        assert fabric.get(memory_id).content == "Current pressure is 40."
        denied = gate.authorize("publish", "agent-1", certificate)
        assert denied.allowed is False
    finally:
        fabric.close()


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


def test_checkpoint_survives_process_crash_and_reconciles_idempotently(tmp_path: Path) -> None:
    database = tmp_path / "recovery.db"
    checkpoint = tmp_path / "episode.json"
    side_effect = tmp_path / "effect.txt"
    fabric = MemoryFabric(str(database), auto_activate=True, hold_suspicious=False)
    memory_id = fabric.remember("operator", "Pressure is within range.", scope="team")
    fabric.close()

    episode = RecoveryEpisode("crash-recovery", enabled=True)
    assert episode.record("evidence_blocked", {
        "cause_code": "EVIDENCE_STALE", "source_id": "sensor:pressure",
    })
    assert episode.record("replan", {"progress_key": "fresh-reading"})
    episode.save_checkpoint(checkpoint)

    crash_script = textwrap.dedent(f"""
        import os, sys
        from pathlib import Path
        sys.path.insert(0, {str(ROOT / 'src')!r})
        from memory_fabric import MemoryFabric
        from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
        from memory_fabric.agent_outcomes import RecoveryEpisode
        fabric = MemoryFabric({str(database)!r})
        certificate = fabric.certify("pressure_safe", [{memory_id!r}], "operator")
        gate = ActionGate(fabric, ActionPolicy(
            tools={{"start_pump": ToolRule("start_pump")}},
            grants={{"operator": frozenset({{"start_pump"}})}},
        ))
        episode = RecoveryEpisode.load_checkpoint({str(checkpoint)!r})
        def effect(key):
            Path({str(side_effect)!r}).write_text(key, encoding="utf-8")
            os._exit(23)
        episode.execute(gate, "start_pump", "operator", certificate, effect,
                        key="recovery-effect")
    """)
    crashed = subprocess.run([sys.executable, "-c", crash_script], capture_output=True,
                             text=True, timeout=30, check=False)
    assert crashed.returncode == 23, crashed.stderr
    assert side_effect.read_text(encoding="utf-8") == "recovery-effect"

    reopened = MemoryFabric(str(database))
    try:
        assert [row["status"] for row in reconciliation_ledger(reopened)
                if row["key"] == "recovery-effect"] == ["unknown"]
        restored = RecoveryEpisode.load_checkpoint(checkpoint)
        assert restored.status.name == "RECOVERED"
        assert restored.steps == 2
        certificate = reopened.certify("pressure_safe", [memory_id], "operator")
        gate = ActionGate(reopened, ActionPolicy(
            tools={"start_pump": ToolRule("start_pump")},
            grants={"operator": frozenset({"start_pump"})},
        ))

        def idempotent_effect(key: str) -> str:
            if not side_effect.exists():
                side_effect.write_text(key, encoding="utf-8")
            return "already-applied" if side_effect.exists() else "applied"

        execution = restored.execute(
            gate, "start_pump", "operator", certificate, idempotent_effect,
            key="recovery-effect", retry=True,
        )
        assert execution.ran
        assert restored.status.name == "COMPLETE"
        assert side_effect.read_text(encoding="utf-8") == "recovery-effect"
        assert [row["status"] for row in reconciliation_ledger(reopened)
                    if row["key"] == "recovery-effect"] == ["completed"]
    finally:
        reopened.close()
