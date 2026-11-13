from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from benchmarks.outcome_agents import (
    ActorRole, ExecutorActor, PlannerActor, ToolDeclaration,
)
from memory_fabric import MemoryFabric
from memory_fabric.actions import (
    ALREADY_EXECUTED, EXECUTED, GRANT_REVOKED, REFUSED, ActionGate,
    ActionPolicy, ActionRequest, ToolRule, reconciliation_ledger,
)
from memory_fabric.agent_outcomes import RecoveryEpisode
from memory_fabric.agent_outcomes.observations import AgentObservation
from memory_fabric.certificates import EvidenceCertificate
from memory_fabric.events import EventType
from memory_fabric.service import MemoryService


_WORKER = Path(__file__).with_name("outcome_authorization_worker.py")


def _wait_for_file(path: Path, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() >= deadline:
            raise AssertionError(f"subprocess did not create {path.name}")
        time.sleep(0.01)


def _run_worker(
    mode: str, db_path: Path, cert: EvidenceCertificate, key: str, effect_path: Path,
    *barriers: Path, expected_returncode: int = 0,
) -> dict:
    command = [
        sys.executable, str(_WORKER), mode, str(db_path),
        json.dumps(cert.to_json()), key, str(effect_path),
        *(str(path) for path in barriers),
    ]
    completed = subprocess.run(
        command, capture_output=True, text=True, timeout=30,
        cwd=_WORKER.parents[1], check=False,
    )
    assert completed.returncode == expected_returncode, completed.stderr[-2000:]
    if expected_returncode != 0:
        return {}
    return json.loads(completed.stdout)


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


def _prepared_action():
    service = MemoryService(MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False))
    for actor_id in ("planner", "executor", "writer", "host"):
        service.register_agent(actor_id, key=f"key-{actor_id}".encode(), tenant_id="plant-a")
    writer = service.session(service.issue("writer"))
    planner_session = service.session(service.issue("planner"))
    executor_session = service.session(service.issue("executor"))
    memory_id = writer.remember("Valve V-8 is in the closed position.", scope="team")
    observation = AgentObservation(
        "valve-task", "Set valve V-8 closed.",
        ({"memory_id": memory_id, "version": 1,
          "content": "Valve V-8 is in the closed position."},),
        ("set_valve",), {"steps": 3},
    )
    planner = PlannerActor(planner_session, (
        ToolDeclaration("propose", ActorRole.PLANNER,
                        {"tool": str, "target": str, "position": str}),
    ))
    executor = ExecutorActor(executor_session, (
        ToolDeclaration("set_valve", ActorRole.EXECUTOR,
                        {"target": str, "position": str}, protected=True),
    ))
    plan = planner.plan(
        observation, tool="set_valve", arguments={"target": "V-8", "position": "closed"}
    )
    request = ActionRequest("V-8", {"position": "closed"})
    prepared = executor.prepare(observation, plan, request=request)
    gate = ActionGate(service._fabric, ActionPolicy(
        tools={"set_valve": ToolRule("set_valve", requires_grant=True)},
        grants={"executor": frozenset({"set_valve"})},
    ))
    grant = gate.issue_grant(
        "set_valve", "executor", issuer="host", certificate=prepared.certificate,
        request=request, tenant_id="plant-a",
    )
    return service, executor, gate, prepared, grant, memory_id, request


def test_executor_binds_action_to_planned_evidence_and_exact_typed_grant() -> None:
    service, executor, gate, prepared, grant, _memory_id, _request = _prepared_action()
    try:
        effects: list[str] = []
        result = executor.execute(
            prepared, gate, lambda key: effects.append(key), key="valve-once", grant=grant,
        )

        assert result.ran is True
        assert effects == ["valve-once"]
        assert executor.executions[-1].ran is True
        assert executor.executions[-1].step.evidence_versions == prepared.evidence_versions
    finally:
        service.close()


def test_gate_refuses_evidence_changed_after_executor_preparation() -> None:
    service, executor, gate, prepared, grant, memory_id, _request = _prepared_action()
    try:
        service._fabric.revise(memory_id, "Valve V-8 is now open.", "writer", "state changed")
        effects: list[str] = []
        result = executor.execute(
            prepared, gate, lambda key: effects.append(key), key="stale-plan", grant=grant,
        )

        assert result.outcome == REFUSED
        assert result.ran is False
        assert effects == []
        assert executor.executions[-1].reason_codes
    finally:
        service.close()


def test_revoked_typed_grant_is_refused_and_strings_are_not_accepted() -> None:
    service, executor, gate, prepared, grant, _memory_id, _request = _prepared_action()
    try:
        with pytest.raises(TypeError, match="typed Grant"):
            executor.execute(prepared, gate, lambda _key: None, key="string-grant",
                             grant=grant.grant_id)
        gate.revoke_grant(grant.grant_id, issuer="host")
        effects: list[str] = []
        result = executor.execute(
            prepared, gate, lambda key: effects.append(key), key="revoked-grant", grant=grant,
        )

        assert result.outcome == REFUSED
        assert result.decision is not None
        assert result.decision.reason_code == GRANT_REVOKED
        assert effects == []
    finally:
        service.close()


def test_process_correction_race_is_serialized_before_or_after_action(tmp_path: Path) -> None:
    db_path = tmp_path / "fabric.db"
    fabric = MemoryFabric(db_path, auto_activate=True, hold_suspicious=False)
    try:
        memory_id = fabric.remember(
            "operator", "Valve V-8 is safe to start.", scope="team",
        )
        certificate = fabric.certify("start-v8", [memory_id], "operator")
        effect_path = tmp_path / "race-effect"
        entered_path = tmp_path / "action-entered"
        release_path = tmp_path / "release-action"
        process = subprocess.Popen(
            [
                sys.executable, str(_WORKER), "race", str(db_path),
                json.dumps(certificate.to_json()), "race-key", str(effect_path),
                str(entered_path), str(release_path),
            ],
            cwd=_WORKER.parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        _wait_for_file(entered_path)

        correction_attempted = threading.Event()
        correction_done = threading.Event()
        correction_errors: list[BaseException] = []

        def correct() -> None:
            correction_attempted.set()
            try:
                fabric.revise(
                    memory_id, "Valve V-8 must stay stopped.", "operator",
                    "operator correction during action process",
                )
            except BaseException as exc:  # surfaced in the test thread below
                correction_errors.append(exc)
            finally:
                correction_done.set()

        correction_thread = threading.Thread(target=correct)
        correction_thread.start()
        assert correction_attempted.wait(5)
        # The action process owns the SQLite write fence. The correction from
        # this process must wait until the effect receipt commits.
        release_path.write_text("release", encoding="utf-8")
        stdout, stderr = process.communicate(timeout=30)
        correction_thread.join(timeout=15)

        assert process.returncode == 0, stderr[-2000:]
        action_result = json.loads(stdout)
        assert action_result["outcome"] == EXECUTED
        assert effect_path.read_text(encoding="utf-8") == "race-key"
        assert correction_done.is_set()
        assert not correction_thread.is_alive()
        assert correction_errors == []

        # Reopen to observe the commits made through the independent process
        # connection rather than relying on this handle's projection caches.
        with MemoryFabric(db_path) as observer:
            events = observer.log.read_types(
                [EventType.ACTION_EXECUTED, EventType.MEMORY_VERSIONED]
            )
            action_candidates = [
                event for event in events
                if event.type == EventType.ACTION_EXECUTED
                and event.payload.get("key") == "race-key"
            ]
            assert action_candidates, [(event.type, event.payload) for event in events]
            action_event = action_candidates[0]
        correction_event = next(
            event for event in events
            if event.type == EventType.MEMORY_VERSIONED
            and event.payload.get("memory", {}).get("id") == memory_id
        )
        assert action_event.seq < correction_event.seq

        stale_effect = tmp_path / "stale-effect"
        stale_result = _run_worker(
            "once", db_path, certificate, "after-correction", stale_effect,
        )
        assert stale_result["outcome"] == REFUSED
        assert not stale_effect.exists()
    finally:
        fabric.close()


def test_unknown_process_effect_is_never_silently_retried_and_explicit_retry_deduplicates(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "fabric.db"
    fabric = MemoryFabric(db_path, auto_activate=True, hold_suspicious=False)
    memory_id = fabric.remember("operator", "Valve V-9 is safe to start.", scope="team")
    certificate = fabric.certify("start-v9", [memory_id], "operator")
    fabric.close()

    effect_path = tmp_path / "external-effect"
    crashed = subprocess.run(
        [
            sys.executable, str(_WORKER), "crash_after_effect", str(db_path),
            json.dumps(certificate.to_json()), "stable-effect-key", str(effect_path),
        ],
        capture_output=True, text=True, timeout=30,
        cwd=_WORKER.parents[1], check=False,
    )
    assert crashed.returncode == 23, crashed.stderr[-2000:]
    assert effect_path.read_text(encoding="utf-8") == "stable-effect-key"

    with MemoryFabric(db_path) as reopened:
        rows = {row["key"]: row for row in reconciliation_ledger(reopened)}
        assert rows["stable-effect-key"]["status"] == "unknown"

    no_retry_effect = tmp_path / "must-not-run"
    no_retry = _run_worker(
        "once", db_path, certificate, "stable-effect-key", no_retry_effect,
    )
    assert no_retry["outcome"] == REFUSED
    assert "retry_required" in no_retry["error"]
    assert not no_retry_effect.exists()

    retried = _run_worker(
        "retry", db_path, certificate, "stable-effect-key", effect_path,
    )
    assert retried["outcome"] == EXECUTED
    assert effect_path.read_text(encoding="utf-8") == "stable-effect-key"
    with MemoryFabric(db_path) as reopened:
        rows = {row["key"]: row for row in reconciliation_ledger(reopened)}
        assert rows["stable-effect-key"]["status"] == "completed"
        assert rows["stable-effect-key"]["attempt_count"] == 2

    replay_effect = tmp_path / "must-not-repeat"
    replayed = _run_worker(
        "once", db_path, certificate, "stable-effect-key", replay_effect,
    )
    assert replayed["outcome"] == ALREADY_EXECUTED
    assert not replay_effect.exists()
