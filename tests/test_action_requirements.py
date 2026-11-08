from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric, parse_requirement_graph
from memory_fabric.actions import (
    ALLOWED, REQUIREMENT_EVIDENCE_MISSING, REQUIREMENT_EXPLANATION_LIMIT,
    ActionGate, ActionPolicy, ToolRule,
)
from memory_fabric.events import EventType


def graph(root: dict[str, object]):
    return parse_requirement_graph({
        "schema": "memory-fabric-requirement-graph/1",
        "graph_id": "pump-start-v1",
        "root": root,
    })


class StaticActionRequirementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(self.fabric.close)
        self.gate = ActionGate(self.fabric, ActionPolicy(
            tools={"start_pump": ToolRule("start_pump", requirement_graph=graph({
                "op": "and", "requirements": [
                    {"op": "claim", "claim_id": "pressure_safe"},
                    {"op": "claim", "claim_id": "lockout_cleared"},
                ],
            }))},
            grants={"operator": frozenset({"start_pump"})},
        ))
        self.pressure = self.fabric.remember("sensor", "Pressure is below the restart limit.", scope="team")
        self.lockout = self.fabric.remember("operator", "Lockout tag was removed after inspection.", scope="team")
        self.pressure_cert = self.fabric.certify("pressure_safe", [self.pressure], "operator")
        self.lockout_cert = self.fabric.certify("lockout_cleared", [self.lockout], "operator")

    def test_missing_mandatory_leaf_refuses_the_action(self) -> None:
        decision = self.gate.authorize(
            "start_pump", "operator", claim_certificates={"pressure_safe": self.pressure_cert})
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, REQUIREMENT_EVIDENCE_MISSING)
        self.assertEqual(decision.missing_evidence_sets, (("claim:lockout_cleared",),))

    def test_every_mandatory_leaf_must_have_a_matching_verified_certificate(self) -> None:
        decision = self.gate.authorize("start_pump", "operator", claim_certificates={
            "pressure_safe": self.pressure_cert,
            "lockout_cleared": self.lockout_cert,
        })
        self.assertTrue(decision.allowed, decision.reason_codes)
        self.assertEqual(decision.reason_code, ALLOWED)

    def test_certificate_cannot_be_submitted_under_another_claim_key(self) -> None:
        decision = self.gate.authorize("start_pump", "operator", claim_certificates={
            "pressure_safe": self.pressure_cert,
            "lockout_cleared": self.pressure_cert,
        })
        self.assertFalse(decision.allowed)

    def test_any_of_accepts_one_verified_alternative(self) -> None:
        alternative_gate = ActionGate(self.fabric, ActionPolicy(
            tools={"start_pump": ToolRule("start_pump", requirement_graph=graph({
                "op": "or", "requirements": [
                    {"op": "claim", "claim_id": "pressure_safe"},
                    {"op": "claim", "claim_id": "lockout_cleared"},
                ],
            }))},
            grants={"operator": frozenset({"start_pump"})},
        ))
        decision = alternative_gate.authorize(
            "start_pump", "operator", claim_certificates={"pressure_safe": self.pressure_cert})
        self.assertTrue(decision.allowed, decision.reason_codes)

    def test_blocked_action_returns_minimal_or_alternatives(self) -> None:
        alternative_gate = ActionGate(self.fabric, ActionPolicy(
            tools={"start_pump": ToolRule("start_pump", requirement_graph=graph({
                "op": "or", "requirements": [
                    {"op": "claim", "claim_id": "manual_override"},
                    {"op": "claim", "claim_id": "remote_interlock"},
                ],
            }))},
            grants={"operator": frozenset({"start_pump"})},
        ))
        decision = alternative_gate.authorize("start_pump", "operator")
        self.assertEqual(decision.missing_evidence_sets, (
            ("claim:manual_override",), ("claim:remote_interlock",),
        ))
        event = self.fabric.log.read_types([EventType.ACTION_GATED])[-1]
        self.assertEqual(event.payload["missing_evidence_sets"], [
            ["claim:manual_override"], ["claim:remote_interlock"],
        ])

    def test_explanation_limit_does_not_turn_a_block_into_an_exception_or_allow(self) -> None:
        root = {"op": "and", "requirements": [
            {"op": "or", "requirements": [
                {"op": "claim", "claim_id": f"choice_{index}_a"},
                {"op": "claim", "claim_id": f"choice_{index}_b"},
            ]}
            for index in range(11)
        ]}
        limited_gate = ActionGate(self.fabric, ActionPolicy(
            tools={"start_pump": ToolRule("start_pump", requirement_graph=graph(root))},
            grants={"operator": frozenset({"start_pump"})},
        ))
        decision = limited_gate.authorize("start_pump", "operator")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_codes,
                         (REQUIREMENT_EVIDENCE_MISSING, REQUIREMENT_EXPLANATION_LIMIT))

    def test_policy_graph_is_included_in_registered_tool_digest(self) -> None:
        self.assertEqual(len(self.gate._tool_digest("start_pump")), 64)

    def test_action_execution_also_refuses_missing_mandatory_leaf(self) -> None:
        ran: list[str] = []
        result = self.gate.execute("start_pump", "operator", ran.append, key="missing-leaf",
                                   claim_certificates={"pressure_safe": self.pressure_cert})
        self.assertEqual(result.outcome, "refused")
        self.assertEqual(ran, [])

    def test_action_execution_runs_when_every_mandatory_leaf_is_verified(self) -> None:
        ran: list[str] = []
        result = self.gate.execute("start_pump", "operator", ran.append, key="complete-evidence",
                                   claim_certificates={
                                       "pressure_safe": self.pressure_cert,
                                       "lockout_cleared": self.lockout_cert,
                                   })
        self.assertEqual(result.outcome, "executed")
        self.assertEqual(ran, ["complete-evidence"])
        self.assertTrue(result.fenced)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
