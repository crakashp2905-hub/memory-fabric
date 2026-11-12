"""Recovery always defers protected effects to the current ActionGate check."""

from __future__ import annotations

import json
import secrets
import subprocess
import sys
import tempfile
import textwrap
import unittest
from dataclasses import replace
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.events import EventType
from memory_fabric.actions import (
    GRANT_MISMATCH, REFUSED, ActionGate, ActionPolicy, ActionRequest, ToolRule,
)
from memory_fabric.agent_outcomes import (
    AgentObservation, RecoveryAction, RecoveryEpisode, diagnose_certificate,
)
from memory_fabric.agent_outcomes.eligibility import EvidenceFailureCode
from memory_fabric.certificates import (
    EVIDENCE_OUTSIDE_CURRENT_VALIDITY, EVIDENCE_VERSION_MOVED,
)
from memory_fabric.identity import ROLE_AGENT
from memory_fabric.service import MemoryService
from benchmarks.outcome_agents import ExecutorActor, ObserverActor, PlannerActor

_ROOT = Path(__file__).resolve().parents[1]
_RACE_CORRECTOR = textwrap.dedent("""
    import os, sys, time
    sys.path.insert(0, sys.argv[1])
    from memory_fabric import MemoryFabric
    fabric = MemoryFabric(sys.argv[2])
    deadline = time.monotonic() + 20
    while not os.path.exists(sys.argv[4]):
        if time.monotonic() > deadline:
            raise TimeoutError("race start signal missing")
        time.sleep(0.002)
    fabric.revise(sys.argv[3], "Updated protected setting is 9.",
                  "source", "controlled correction race")
    fabric.close()
""")
_RACE_ACTOR = textwrap.dedent("""
    import json, os, sys, time
    sys.path.insert(0, sys.argv[1])
    from memory_fabric import MemoryFabric
    from memory_fabric.actions import ActionGate, ActionPolicy, ActionRequest, ToolRule
    from memory_fabric.certificates import EvidenceCertificate
    fabric = MemoryFabric(sys.argv[2])
    gate = ActionGate(fabric, ActionPolicy(
        tools={"set_target": ToolRule("set_target")},
        grants={"executor": frozenset({"set_target"})},
    ))
    certificate = EvidenceCertificate.from_json(json.loads(sys.argv[5]))
    deadline = time.monotonic() + 20
    while not os.path.exists(sys.argv[4]):
        if time.monotonic() > deadline:
            raise TimeoutError("race start signal missing")
        time.sleep(0.002)
    def effect(key):
        with open(sys.argv[6], "w", encoding="utf-8") as output:
            output.write(key)
    result = gate.execute(
        "set_target", "executor", effect, certificate, key="controlled-race",
        request=ActionRequest("protected_setting", {"value": 4}), lease_s=1.0,
    )
    print(result.outcome)
    fabric.close()
""")


class TestOutcomeAuthorization(unittest.TestCase):
    def test_correction_and_action_race_across_processes_respects_commit_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_path, start_path, effect_path = (
                root / "race.db", root / "start", root / "effect",
            )
            fabric = MemoryFabric(str(db_path), auto_activate=True)
            memory_id = fabric.remember(
                "source", "Protected setting is 4.", scope="team",
            )
            certificate = fabric.certify(
                "Apply protected setting.", [memory_id], "executor",
            )
            certificate_json = json.dumps(certificate.to_json(), separators=(",", ":"))
            fabric.close()
            processes = [
                subprocess.Popen([
                    sys.executable, "-c", _RACE_CORRECTOR, str(_ROOT), str(db_path),
                    memory_id, str(start_path),
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True),
                subprocess.Popen([
                    sys.executable, "-c", _RACE_ACTOR, str(_ROOT), str(db_path),
                    memory_id, str(start_path), certificate_json, str(effect_path),
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True),
            ]
            start_path.touch()
            try:
                outputs = [process.communicate(timeout=30) for process in processes]
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)
            for process, (stdout, stderr) in zip(processes, outputs):
                self.assertEqual(process.returncode, 0, stderr[-2000:])

            fabric = MemoryFabric(str(db_path))
            events = list(fabric.log.read())
            correction = next(
                event for event in events
                if event.payload.get("reason") == "controlled correction race"
            )
            action = next((
                event for event in events
                if event.payload.get("key") == "controlled-race"
                and event.type == EventType.ACTION_EXECUTED
            ), None)
            self.assertIsNotNone(action, (outputs, [(e.type, e.payload) for e in events]))
            if action.payload.get("outcome") == "executed":
                self.assertLess(action.seq, correction.seq)
                self.assertTrue(effect_path.exists())
            else:
                self.assertEqual(action.payload.get("outcome"), REFUSED)
                self.assertGreater(action.seq, correction.seq)
                self.assertFalse(effect_path.exists())
            fabric.close()

    def test_historical_truth_is_readable_but_not_current_action_authority(self) -> None:
        now = [500]
        fabric = MemoryFabric(":memory:", auto_activate=True, clock=lambda: now[0])
        self.addCleanup(fabric.close)
        memory_id = fabric.remember(
            "source", "Pump beta target was 6 at 10:00.",
            valid_from=0, valid_to=1000, scope="team",
        )
        history = fabric.retrieve(
            "executor", "Pump beta target at 10:00", as_of=500,
            k=3, min_relevance=0.0,
        )
        self.assertIn(memory_id, {memory.id for memory in history.exposed})
        certificate = fabric.certify(
            "Set the current pump beta target.", [memory_id], "executor",
        )
        request = ActionRequest("protected_setting", {"value": 6})
        gate = ActionGate(fabric, ActionPolicy(
            tools={"set_protected_setting": ToolRule(
                "set_protected_setting", requires_grant=True)},
            grants={"executor": frozenset({"set_protected_setting"})},
        ))
        grant = gate.issue_grant(
            "set_protected_setting", "executor", issuer="host",
            certificate=certificate, request=request,
        )
        now[0] = 1000
        effects: list[str] = []
        result = gate.execute(
            "set_protected_setting", "executor", lambda key: effects.append(key),
            certificate, key="historical-not-current", request=request, grant=grant,
        )
        self.assertEqual(result.outcome, REFUSED)
        self.assertIn(EVIDENCE_OUTSIDE_CURRENT_VALIDITY, result.decision.reason_codes)
        self.assertIsNotNone(result.decision.verification)
        diagnosis = diagnose_certificate(result.decision.verification)
        self.assertEqual(diagnosis.failure_codes, (EvidenceFailureCode.STALE,))
        self.assertEqual(effects, [])

    def setUp(self) -> None:
        self.fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(self.fabric.close)

    def _prepared_action(self, label: str):
        memory_id = self.fabric.remember(
            "source", f"Protected setting for {label} is 4.",
            tenant_id="tenant-a", scope="team",
        )
        certificate = self.fabric.certify(
            f"Apply protected setting for {label}.", [memory_id], "executor",
            tenant_id="tenant-a",
        )
        request = ActionRequest("protected_setting", {"value": 4})
        gate = ActionGate(self.fabric, ActionPolicy(
            tools={"set_protected_setting": ToolRule(
                "set_protected_setting", requires_grant=True)},
            grants={"executor": frozenset({"set_protected_setting"})},
        ))
        grant = gate.issue_grant(
            "set_protected_setting", "executor", issuer="host",
            certificate=certificate, request=request, tenant_id="tenant-a",
        )
        return memory_id, certificate, request, gate, grant

    def _run_after_recovery(self, label: str, prepared, **kwargs):
        memory_id, certificate, request, gate, grant = prepared
        episode = RecoveryEpisode(f"authorization-{label}")
        self.assertTrue(episode.record("evidence_blocked", {"reason": "stale"}))
        self.assertTrue(episode.request_recovery(
            RecoveryAction.REFRESH, before_token=f"{label}-before"))
        self.assertTrue(episode.resolve_recovery(
            RecoveryAction.REFRESH, after_token=f"{label}-after"))
        effects: list[str] = []
        result = episode.execute(
            gate, "set_protected_setting", "executor", certificate,
            lambda key: effects.append(key), key=f"authorization-{label}",
            request=request, tenant_id=kwargs.get("tenant_id", "tenant-a"),
            grant=grant, session=kwargs.get("session"),
        )
        self.assertEqual(result.outcome, REFUSED)
        self.assertFalse(result.ran)
        self.assertEqual(effects, [])
        self.assertEqual(episode.status.value, "BLOCKED")
        self.assertIsNotNone(result.decision)
        return memory_id, result

    def test_cross_tenant_erased_and_revised_evidence_stay_blocked_after_recovery(self) -> None:
        cross_tenant = self._prepared_action("cross-tenant")
        _, cross_tenant_result = self._run_after_recovery(
            "cross-tenant", cross_tenant, tenant_id="tenant-b")
        self.assertIn("wrong_tenant", cross_tenant_result.decision.reason_codes)

        erased = self._prepared_action("erased")
        erased_id = erased[0]
        self.fabric.erase_content(erased_id, reason="subject request", actor="operator")
        _, erased_result = self._run_after_recovery("erased", erased)
        self.assertEqual(erased_result.outcome, REFUSED)
        self.assertIn("evidence_erased", erased_result.decision.reason_codes)

        stale = self._prepared_action("revised")
        stale_id = stale[0]
        self.fabric.revise(
            stale_id, "Updated protected setting is 5.", "source", "superseded source",
        )
        _, stale_result = self._run_after_recovery("revised", stale)
        self.assertEqual(stale_result.outcome, REFUSED)
        self.assertIn("evidence_version_moved", stale_result.decision.reason_codes)

    def test_revoked_session_cannot_execute_after_read_only_recovery(self) -> None:
        service = MemoryService(MemoryFabric(":memory:", auto_activate=True))
        self.addCleanup(service.close)
        service.register_agent("executor", key=b"outcome-auth-key", tenant_id="tenant-c")
        session = service.session(service.issue("executor"))
        memory_id = session.remember("Protected setting is 4.", scope="team")
        certificate = session.certify("Apply protected setting.", [memory_id])
        request = ActionRequest("protected_setting", {"value": 4})
        fabric = service._fabric
        gate = ActionGate(fabric, ActionPolicy(
            tools={"set_protected_setting": ToolRule(
                "set_protected_setting", requires_grant=True)},
            grants={"executor": frozenset({"set_protected_setting"})},
        ))
        grant = gate.issue_grant(
            "set_protected_setting", "executor", issuer="host",
            certificate=certificate, request=request, tenant_id="tenant-c",
        )
        episode = RecoveryEpisode("authorization-revoked")
        self.assertTrue(episode.record("evidence_blocked", {"reason": "credential"}))
        self.assertTrue(episode.request_recovery(
            RecoveryAction.REPLAN, before_token="credential-current"))
        self.assertTrue(episode.resolve_recovery(
            RecoveryAction.REPLAN, after_token="credential-refreshed"))
        service.revoke(session.credential)
        effects: list[str] = []
        result = episode.execute(
            gate, "set_protected_setting", "executor", certificate,
            lambda key: effects.append(key), key="authorization-revoked",
            request=request, tenant_id="tenant-c", grant=grant, session=session,
        )
        self.assertEqual(result.outcome, REFUSED)
        self.assertFalse(result.ran)
        self.assertEqual(effects, [])
        self.assertIsNotNone(result.decision)
        self.assertIn("credential_invalid", result.decision.reason_codes)


class TestTypedPlanAuthorization(unittest.TestCase):
    def _prepared_plan(self):
        service = MemoryService(MemoryFabric(":memory:", auto_activate=True))
        self.addCleanup(service.close)
        for agent in ("observer", "planner", "executor"):
            service.register_agent(agent, key=secrets.token_bytes(32),
                                   tenant_id="tenant-plan-binding", roles=(ROLE_AGENT,))
        observation = AgentObservation(
            task_id="typed-plan-binding", instruction="Set the current observed target.",
            visible_events=(),
            permitted_tools=("remember_evidence", "retrieve_evidence", "propose_action",
                             "certify_evidence", "set_target"),
            budget={"steps": 10},
        )
        observer = ObserverActor(service.session(service.issue("observer")), observation)
        planner = PlannerActor(service.session(service.issue("planner")), observation)
        executor = ExecutorActor(service.session(service.issue("executor")), observation)
        observer.remember("Pump beta target setting is 6.")
        observer.remember("Independent instrument confirms pump beta target 6.")
        evidence, _ = planner.retrieve("pump beta target 6", k=3)
        plan = planner.propose(
            "set_target", {"value": 6}, evidence,
            claim="Pump beta should use its current target of 6.",
        )
        gate = ActionGate(service._fabric, ActionPolicy(
            tools={"set_target": ToolRule(
                "set_target", requires_grant=True, min_independent_sources=2)},
            grants={"executor": frozenset({"set_target"})},
        ))
        certificate = executor.certify(plan)
        request = ActionRequest(plan.tool, plan.parameters)
        grant = gate.issue_grant(
            plan.tool, executor.actor_id, issuer="host", certificate=certificate,
            request=request, tenant_id=executor.tenant_id,
        )
        return service, executor, gate, plan, certificate, grant

    def test_revision_after_plan_certificate_and_grant_is_refused_by_gate(self) -> None:
        service, executor, gate, plan, certificate, grant = self._prepared_plan()
        memory_id = plan.evidence_versions[0][0]
        service._fabric.revise(
            memory_id, "Pump beta target setting is 9.", "observer", "new instrument result",
        )
        effects: list[int] = []

        execution = executor.execute(
            plan, certificate, gate, grant,
            lambda _key: effects.append(plan.parameters["value"]),
            key="typed-plan-stale-evidence",
        )

        self.assertEqual(execution.outcome, REFUSED)
        self.assertIn(EVIDENCE_VERSION_MOVED, execution.decision.reason_codes)
        self.assertEqual(effects, [])

    def test_changed_action_cannot_reuse_the_original_exact_action_grant(self) -> None:
        _, executor, gate, plan, certificate, grant = self._prepared_plan()
        changed = replace(plan, parameters={"value": 99})
        effects: list[int] = []

        execution = executor.execute(
            changed, certificate, gate, grant,
            lambda _key: effects.append(99), key="typed-plan-changed-request",
        )

        self.assertEqual(execution.outcome, REFUSED)
        self.assertIn(GRANT_MISMATCH, execution.decision.reason_codes)
        self.assertEqual(effects, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
