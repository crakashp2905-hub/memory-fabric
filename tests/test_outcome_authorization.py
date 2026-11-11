"""Recovery always defers protected effects to the current ActionGate check."""

from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import REFUSED, ActionGate, ActionPolicy, ActionRequest, ToolRule
from memory_fabric.agent_outcomes import RecoveryAction, RecoveryEpisode
from memory_fabric.service import MemoryService


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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
