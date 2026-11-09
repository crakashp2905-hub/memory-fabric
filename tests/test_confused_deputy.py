from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule, TOOL_NOT_GRANTED
from memory_fabric.events import EventType
from memory_fabric.service import MemoryService
from memory_fabric.tool_protocol import CodeModePlan, GovernedToolRuntime, ToolProtocolError


class ConfusedDeputyTests(unittest.TestCase):
    def test_privileged_descriptor_cannot_change_authenticated_effective_identity(self) -> None:
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        service = MemoryService(fabric=fabric)
        service.register_agent("agent_low", key=b"low-agent-key", tenant_id="tenant_low")
        low_session = service.session(service.issue("agent_low"))
        effects: list[str] = []
        policy = ActionPolicy(
            tools={"privileged_write": ToolRule("privileged_write")},
            grants={"agent_privileged": frozenset({"privileged_write"})},
        )
        gate = ActionGate(fabric, policy)
        runtime = GovernedToolRuntime(
            gate, {"privileged_write": lambda **_values: effects.append("executed")})

        # The low-trust principal has copied the privileged tool descriptor and
        # supplies the privileged display name as agent_id. The session is the
        # authenticated identity and must control authorization and the audit.
        call = CodeModePlan.parse('privileged_write(target="server-1")').calls[0]
        with self.assertRaisesRegex(ToolProtocolError, "requires an authenticated session"):
            runtime.execute(call, agent_id="agent_privileged")
        result = runtime.execute(
            call, agent_id="agent_privileged", session=low_session,
        )

        self.assertEqual(result.outcome, "refused")
        self.assertEqual(result.decision.agent_id, "agent_low")
        self.assertIn(TOOL_NOT_GRANTED, result.decision.reason_codes)
        self.assertEqual(effects, [])
        attempt = fabric.log.read_types([EventType.ACTION_ATTEMPTED])[0]
        outcome = fabric.log.read_types([EventType.ACTION_EXECUTED])[0]
        self.assertEqual(attempt.agent_id, "agent_low")
        self.assertEqual(outcome.agent_id, "agent_low")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
