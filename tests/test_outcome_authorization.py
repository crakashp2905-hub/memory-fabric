"""Recovery always defers protected effects to the current ActionGate check."""

from __future__ import annotations

import secrets
import unittest
from dataclasses import replace

from memory_fabric import MemoryFabric
from memory_fabric.actions import (
    GRANT_MISMATCH, REFUSED, ActionGate, ActionPolicy, ActionRequest, ToolRule,
)
from memory_fabric.agent_outcomes import AgentObservation, RecoveryAction, RecoveryEpisode
from memory_fabric.certificates import EVIDENCE_VERSION_MOVED
from memory_fabric.identity import ROLE_AGENT
from memory_fabric.service import MemoryService
from benchmarks.outcome_agents import ExecutorActor, ObserverActor, PlannerActor


class TestOutcomeAuthorization(unittest.TestCase):
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
