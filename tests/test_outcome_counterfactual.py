from __future__ import annotations

import time

from memory_fabric import MemoryFabric
from memory_fabric import events as ev
from memory_fabric.actions import REFUSED, ActionGate, ActionPolicy, ToolRule
from memory_fabric.outcome_protocol.outcomes import OutcomeAssessment, OutcomeStatus
from memory_fabric.outcome_protocol.runtime import schedule_counterfactual_replays
from memory_fabric.causal_replay.bayes import BinaryNode
from memory_fabric.causal_replay.capture import capture, record_decision
from memory_fabric.causal_replay.certificates import issue as issue_replay_certificate
from memory_fabric.causal_replay.executor import execute_recorded
from memory_fabric.causal_replay.policy import ThresholdPolicy
from memory_fabric.causal_replay.replay import deterministic_simulator
from memory_fabric.causal_replay.types import (
    ModelProvenance, NonReplayable, ReplayContext,
)
from memory_fabric.service import MemoryService


def _verified_cdm_certificate():
    return issue_replay_certificate(
        capture_digest="a" * 64, intervention_digest="b" * 64,
        factual_fingerprint="c" * 64, counterfactual_fingerprint="d" * 64,
        updater_id="registered-updater-v1", policy_id="registered-policy-v1",
        status="EXACT", factual_proposal="monitor",
        counterfactual_proposal="investigate", complete=True,
    )


def _isolated_valid_replay(_decision, _remaining):
    return _verified_cdm_certificate()


def _isolated_forged_replay(_decision, _remaining):
    return {"status": "EXACT", "positive_reward": 1.0, "action_authorized": True}


def _isolated_slow_replay(_decision, _remaining):
    time.sleep(5)
    return _verified_cdm_certificate()


def test_cdm_runs_only_after_dependence_check_and_material_alternative(monkeypatch) -> None:
    order: list[tuple[str, int | None]] = []

    def dependence_check(_fabric, memory_id):
        order.append(("dependence", None))
        assert memory_id == "corrected-source"
        return {
            "depended": [{"seq": 10, "remaining": []}],
            "would_stand": [
                {"seq": 20, "remaining": ["independent-source"]},
                {"seq": 30, "remaining": ["independent-source"]},
            ],
            "exposed_only": [],
        }

    monkeypatch.setattr(
        "memory_fabric.outcome_protocol.runtime.dependence.decisions_depending_on",
        dependence_check,
    )

    report = schedule_counterfactual_replays(
        object(), "corrected-source",
        material_alternatives={20: ("continue-with-backup",), 30: ()},
        replay=_isolated_valid_replay,
    )

    assert order == [("dependence", None)]
    assert report["dependence_check"] == "COMPLETED"
    assert report["cdm_invocations"] == 1
    assert report["action_authorized"] is False
    worker_isolation = report["decisions"][1].pop("isolation_status")
    assert worker_isolation in {
        "SUBPROCESS_CPU_MEMORY_LIMITED", "SUBPROCESS_CPU_LIMITED",
        "SUBPROCESS_WALL_LIMIT_ONLY",
    }
    assert report["worker_isolation_statuses"] == [worker_isolation]
    assert report["isolation_gap"] is (worker_isolation != "SUBPROCESS_CPU_MEMORY_LIMITED")
    assert report["decisions"] == [
        {
            "decision_sequence": 10,
            "dependence_verdict": "depended",
            "material_alternative_ids": [],
            "replay_status": "SKIPPED",
            "reason_code": "CORRECTED_EVIDENCE_REQUIRED_BY_POLICY",
        },
        {
            "decision_sequence": 20,
            "dependence_verdict": "would_stand",
            "material_alternative_ids": ["continue-with-backup"],
            "replay_status": "INVOKED",
            "reason_code": "INDEPENDENT_EVIDENCE_AND_MATERIAL_ALTERNATIVE",
            "replay_receipt": {
                "status": "EXACT",
                "certificate_digest": _verified_cdm_certificate().certificate_digest,
                "proposal_changed": True,
                "action_authorized": False,
            },
        },
        {
            "decision_sequence": 30,
            "dependence_verdict": "would_stand",
            "material_alternative_ids": [],
            "replay_status": "SKIPPED",
            "reason_code": "NO_MATERIAL_ALTERNATIVE",
        },
    ]


def test_unaffected_correction_never_invokes_cdm(monkeypatch) -> None:
    monkeypatch.setattr(
        "memory_fabric.outcome_protocol.runtime.dependence.decisions_depending_on",
        lambda *_args: {"depended": [], "would_stand": [], "exposed_only": []},
    )
    calls: list[object] = []

    report = schedule_counterfactual_replays(
        object(), "unrelated-source", material_alternatives={4: ("alternative",)},
        replay=lambda *_args: calls.append("unexpected"),
    )

    assert report["decisions"] == []
    assert report["cdm_invocations"] == 0
    assert calls == []


def test_untrusted_reward_or_authority_claim_is_not_returned_as_cdm_result(monkeypatch) -> None:
    monkeypatch.setattr(
        "memory_fabric.outcome_protocol.runtime.dependence.decisions_depending_on",
        lambda *_args: {
            "depended": [],
            "would_stand": [{"seq": 5, "remaining": ["backup-source"]}],
            "exposed_only": [],
        },
    )
    report = schedule_counterfactual_replays(
        object(), "corrected-source", material_alternatives={5: ("switch-plan",)},
        replay=_isolated_forged_replay,
    )

    decision = report["decisions"][0]
    assert report["action_authorized"] is False
    assert decision["replay_status"] == "FAILED"
    assert decision["error_type"] == "ValueError"
    assert "replay_receipt" not in decision


def test_nonimportable_callback_is_not_run_inline(monkeypatch) -> None:
    monkeypatch.setattr(
        "memory_fabric.outcome_protocol.runtime.dependence.decisions_depending_on",
        lambda *_args: {
            "depended": [],
            "would_stand": [{"seq": 7, "remaining": ["backup-source"]}],
            "exposed_only": [],
        },
    )
    calls: list[str] = []

    def local_callback(*_args):
        calls.append("ran")

    report = schedule_counterfactual_replays(
        object(), "corrected-source", material_alternatives={7: ("alternative",)},
        replay=local_callback,
    )
    decision = report["decisions"][0]
    assert decision["replay_status"] == "FAILED"
    assert decision["error_type"] == "ReplayCallbackNotImportable"
    assert decision["isolation_status"] == "NOT_STARTED"
    assert calls == []


def test_long_running_replay_worker_is_terminated_by_wall_budget(monkeypatch) -> None:
    from memory_fabric.causal_replay.scheduler import ReplayBudget

    monkeypatch.setattr(
        "memory_fabric.outcome_protocol.runtime.dependence.decisions_depending_on",
        lambda *_args: {
            "depended": [],
            "would_stand": [{"seq": 8, "remaining": ["backup-source"]}],
            "exposed_only": [],
        },
    )
    report = schedule_counterfactual_replays(
        object(), "corrected-source", material_alternatives={8: ("alternative",)},
        replay=_isolated_slow_replay,
        replay_budget=ReplayBudget(max_wall_seconds=1.0, max_cpu_seconds=1.0),
    )
    decision = report["decisions"][0]
    assert decision["replay_status"] == "FAILED"
    assert decision["error_type"] == "ReplayWorkerTimeout"
    assert decision["isolation_status"] == "SUBPROCESS_WALL_LIMIT_ONLY"


def test_cdm_certificate_and_positive_outcome_cannot_authorize_an_action() -> None:
    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        memory_id = fabric.remember("operator", "Valve V-10 safe to open.", scope="team")
        evidence_certificate = fabric.certify("open-v10", [memory_id], "operator")
        gate = ActionGate(fabric, ActionPolicy(
            tools={"open": ToolRule("open")},
            grants={"operator": frozenset({"open"})},
        ))
        positive_assessment = OutcomeAssessment(
            task_id="case-10", status=OutcomeStatus.COMPLETED,
            completion=True, safety_violations=0,
            reason_code="VERIFIED_TERMINAL_STATE", result_digest="e" * 64,
        )
        effects: list[str] = []
        for key, non_authority_input in (
            ("cdm-certificate", _verified_cdm_certificate()),
            ("positive-evaluator", positive_assessment),
        ):
            result = gate.execute(
                "open", "operator", effects.append, non_authority_input,
                key=key,
            )
            assert result.outcome == REFUSED
        assert effects == []
        # Passing the actual evidence certificate still requires live ActionGate checks.
        allowed = gate.execute(
            "open", "operator", effects.append, evidence_certificate, key="host-evidence",
        )
        assert allowed.ran is True
        assert effects == ["host-evidence"]
    finally:
        fabric.close()


def test_real_dependence_check_filters_before_registered_replay() -> None:
    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        service = MemoryService(fabric)
        service.register_agent("alice", b"outcome-counterfactual-key", tenant_id="plant-a")
        session = service.session(service.issue("alice"))
        target = session.remember("Primary calibration report from sensor Alpha.")
        backup_a = session.remember("Independent calibration report from sensor Bravo.")
        backup_b = session.remember("Independent calibration report from sensor Charlie.")
        gate = ActionGate(fabric, ActionPolicy(
            tools={"inspect": ToolRule("inspect", min_independent_sources=2)},
            grants={"alice": frozenset({"inspect"})},
        ))
        for claim, evidence in (
            ("dependent", (target, backup_a)),
            ("independent", (target, backup_a, backup_b)),
        ):
            certificate = fabric.certify(
                claim, evidence, "alice", tenant_id="plant-a",
                min_independent_sources=2,
            )
            decision = gate.authorize("inspect", "alice", certificate, session=session)
            assert decision.allowed
        action_rows = [
            event for event in fabric.log.read_types([ev.EventType.ACTION_GATED])
            if event.payload.get("allowed")
        ]
        independent_sequence = max(event.seq for event in action_rows)
        fabric.revise(
            target, "Sensor Alpha report corrected; reading withdrawn.",
            "alice", "calibration correction",
        )
        report = schedule_counterfactual_replays(
            fabric, target,
            material_alternatives={independent_sequence: ("use-backup-plan",)},
            replay=_isolated_forged_replay,
        )

        assert report["cdm_invocations"] == 1
        by_sequence = {row["decision_sequence"]: row for row in report["decisions"]}
        assert by_sequence[action_rows[0].seq]["reason_code"] == (
            "CORRECTED_EVIDENCE_REQUIRED_BY_POLICY"
        )
        assert by_sequence[independent_sequence]["reason_code"] == (
            "INDEPENDENT_EVIDENCE_AND_MATERIAL_ALTERNATIVE"
        )
    finally:
        fabric.close()


def test_model_replay_contract_binds_versions_and_fails_closed_without_runner() -> None:
    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        service = MemoryService(fabric)
        service.register_agent("model-agent", b"counterfactual-model-key", tenant_id="plant-b")
        session = service.session(service.issue("model-agent"))
        memory_id = session.remember("historical observation")
        captured = capture(
            fabric, session, [memory_id], context=ReplayContext(fabric.log.head_seq),
        )
        model = ModelProvenance(
            "agent-model", "checkpoint-2026-11", "c" * 64,
            "local-runtime", "runtime-3", "d" * 64,
        )
        record = record_decision(
            fabric, session, options=("monitor", "investigate"), selected="monitor",
            evidence=captured.evidence, policy_id="host-policy-v2",
            policy_digest="a" * 64, execution_mode="model", model_provenance=model,
        )
        replay_policy = ThresholdPolicy("fault")
        simulator = deterministic_simulator((BinaryNode("fault", (), {(): 0.2}),))

        try:
            execute_recorded(
                fabric, (), simulator=simulator, policy=replay_policy,
                decision_record=record,
            )
        except NonReplayable as exc:
            assert exc.code == "NON_REPLAYABLE"
            assert "exact registered replay runner" in str(exc)
        else:
            raise AssertionError("model trace replayed without its exact registered runner")
    finally:
        fabric.close()
