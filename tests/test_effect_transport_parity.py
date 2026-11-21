"""Every effect path agrees with the canonical action gate (W16-09).

Three ways an agent can cause a side effect: the ActionGate directly, the
function-calling tools' ``guarded`` call, and the protocol-neutral governed
runtime that MCP, UTCP and Code Mode plans execute through. For the same action,
each must allow what the gate allows and refuse what it refuses, and a refused
effect's handler must never run.
"""

from __future__ import annotations

import os
import unittest

from memory_fabric import MemoryFabric, sdk
from memory_fabric.actions import EXECUTED, ActionGate, ActionPolicy, ToolRule
from memory_fabric.integrations.tools import FabricTools
from memory_fabric.service import MemoryService
from memory_fabric.tool_protocol import GovernedToolCall, GovernedToolRuntime

TENANT = "tn_default"
DIGEST = "a" * 64


class EffectParity(unittest.TestCase):
    def setUp(self) -> None:
        self.f = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(self.f.close)
        self.memory = self.f.remember("ana", "valve 7 is safe to open below 4 bar", scope="team",
                                      tenant_id=TENANT)
        self.gate = ActionGate(self.f, ActionPolicy(tools={"open_valve": ToolRule("open_valve")},
                                                    grants={"ops": frozenset({"open_valve"})}))
        service = MemoryService(fabric=self.f)
        for agent in ("ops", "mallory"):
            service.register_agent(agent, key=os.urandom(32), tenant_id=TENANT)
        self.sessions = {agent: service.session(service.issue(agent)) for agent in ("ops", "mallory")}
        self.ran: list[str] = []

    def paths(self, agent: str, key: str) -> dict[str, bool]:
        """Run the same action through each path; return whether each executed."""
        certificate = self.f.certify("open-7", [self.memory], agent, tenant_id=TENANT)

        def run(tag: str):
            return lambda *args, **kwargs: self.ran.append(tag) or "opened"

        canonical = self.gate.execute("open_valve", agent, run("canonical"), certificate,
                                      key=f"{key}-gate", tenant_id=TENANT)
        tools = FabricTools(sdk.agent(self.f, agent, TENANT)).guarded(
            self.gate, "open_valve", [self.memory], run("tools"), key=f"{key}-tools")
        runtime = GovernedToolRuntime(self.gate, {"open_valve": run("protocol")}).execute(
            GovernedToolCall("open_valve", {}, f"{key}-protocol", DIGEST), agent_id=agent,
            certificate=certificate, session=self.sessions[agent], tenant_id=TENANT)
        return {"canonical": canonical.outcome == EXECUTED, "tools": bool(tools.get("ran")),
                "protocol": runtime.outcome == EXECUTED}

    def test_current_evidence_is_allowed_on_every_path(self) -> None:
        self.assertEqual(self.paths("ops", "ok"), {"canonical": True, "tools": True, "protocol": True})
        self.assertEqual(sorted(self.ran), ["canonical", "protocol", "tools"])

    def test_withdrawn_evidence_is_refused_on_every_path(self) -> None:
        self.f.quarantine(self.memory, reason="valve re-rated", actor="op")
        self.assertEqual(self.paths("ops", "withdrawn"),
                         {"canonical": False, "tools": False, "protocol": False})
        self.assertEqual(self.ran, [])

    def test_an_ungranted_agent_is_refused_on_every_path(self) -> None:
        self.assertEqual(self.paths("mallory", "ungranted"),
                         {"canonical": False, "tools": False, "protocol": False})
        self.assertEqual(self.ran, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
