from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import (
    CREDENTIAL_INVALID,
    FAILED,
    REFUSED,
    ActionGate,
    ActionPolicy,
    ToolRule,
)
from memory_fabric.identity import IdentityError
from memory_fabric.service import MemoryService


class CredentialRotationAndActionRetry(unittest.TestCase):
    def test_key_rotation_invalidates_cached_active_session(self) -> None:
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        service = MemoryService(fabric=fabric)
        service.register_agent("agent_rotate", key=b"old-registration-key", tenant_id="tn_rotate")
        old = service.session(service.issue("agent_rotate"))
        self.assertEqual(old.principal().agent_id, "agent_rotate")

        service.register_agent("agent_rotate", key=b"new-registration-key", tenant_id="tn_rotate")
        with self.assertRaises(IdentityError):
            old.principal()
        replacement = service.session(service.issue("agent_rotate"))
        self.assertEqual(replacement.principal().agent_id, "agent_rotate")

    def test_revocation_during_retry_refuses_before_repeating_the_effect(self) -> None:
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        service = MemoryService(fabric=fabric)
        service.register_agent("agent_retry", key=b"retry-agent-key", tenant_id="tn_retry")
        session = service.session(service.issue("agent_retry"))
        memory_id = fabric.remember("reviewer", "Verified test evidence.",
                                    tenant_id="tn_retry", scope="team")
        fabric.validate(memory_id, actor="reviewer")
        certificate = fabric.certify("retry action", [memory_id], "agent_retry",
                                     tenant_id="tn_retry")
        gate = ActionGate(fabric, ActionPolicy(
            tools={"write": ToolRule("write")},
            grants={"agent_retry": frozenset({"write"})},
        ))
        effects: list[str] = []

        def fail_after_attempt(_key: str) -> None:
            effects.append("first attempt")
            raise RuntimeError("simulated outcome unknown")

        first = gate.execute("write", "caller supplied spoof", fail_after_attempt,
                             certificate, key="rotating-retry-key", tenant_id="wrong-tenant",
                             session=session)
        self.assertEqual(first.outcome, FAILED)
        self.assertEqual(fabric.log.read_types(["ActionAttempted"])[0].agent_id,
                         "agent_retry")

        service.revoke(session.credential)
        second = gate.execute("write", "agent_retry",
                              lambda _key: effects.append("must not repeat"),
                              certificate, key="rotating-retry-key", tenant_id="tn_retry",
                              session=session, retry=True)
        self.assertEqual(second.outcome, REFUSED)
        self.assertIn(CREDENTIAL_INVALID, second.decision.reason_codes)
        self.assertEqual(effects, ["first attempt"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
