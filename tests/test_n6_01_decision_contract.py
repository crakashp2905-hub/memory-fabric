from __future__ import annotations

import math
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import CERTIFICATE_REQUIRED, ActionGate, ActionPolicy, ToolRule
from memory_fabric.decision_models import (
    DecisionContext,
    DecisionModelError,
    DecisionOption,
    DecisionProposal,
    DeterministicDecisionModel,
    EscalationPolicy,
    route_decision,
)
from experiments.n6_01_typed_decision_tasks import evaluate


class TypedDecisionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = DecisionContext("choose", (
            DecisionOption("a", "Option A", action="deploy"),
            DecisionOption("b", "Option B"),
        ))

    def test_new_task_dataset_satisfies_typed_selection_and_escalation_contracts(self) -> None:
        report = evaluate()
        self.assertEqual(report["passed"], 6)
        self.assertEqual(report["failed"], [])
        self.assertTrue(report["acceptance_passed"])

    def test_malformed_probability_vectors_fail_with_decision_model_error(self) -> None:
        malformed = (
            {"a": 0.9, "b": 0.9},
            {"a": -0.1, "b": 1.1},
            {"a": 1.1, "b": -0.1},
            {"a": math.nan, "b": 0.0},
            {"a": math.inf, "b": 0.0},
            {"a": 0.5},
            {"a": 0.5, "b": 0.5, "c": 0.0},
            {"a": True, "b": 0},
            {"a": "0.5", "b": 0.5},
            {"a": 10**400, "b": 0},
        )
        for probabilities in malformed:
            with self.subTest(probabilities=repr(probabilities)[:80]):
                proposal = DecisionProposal("a", probabilities, False, 0.5)  # type: ignore[arg-type]
                with self.assertRaises(DecisionModelError):
                    proposal.validate(self.context)

    def test_invalid_confidence_and_inconsistent_abstention_fail(self) -> None:
        for confidence in (-0.1, 1.1, math.nan, math.inf, True, "high"):
            with self.subTest(confidence=confidence):
                proposal = DecisionProposal("a", {"a": 0.6, "b": 0.4}, False,
                                            confidence)  # type: ignore[arg-type]
                with self.assertRaises(DecisionModelError):
                    proposal.validate(self.context)
        inconsistent = DecisionProposal("a", {"a": 0.6, "b": 0.4}, True, 0.6)
        with self.assertRaises(DecisionModelError):
            inconsistent.validate(self.context)

    def test_proposal_selection_alone_does_not_authorize_tool(self) -> None:
        proposal = route_decision(
            DeterministicDecisionModel({"a": 99, "b": 1}), self.context,
            EscalationPolicy(min_confidence=0.5, max_entropy=1.0),
        )
        self.assertEqual(proposal.selected, "a")
        self.assertFalse(proposal.requires_system2)
        fabric = MemoryFabric(auto_activate=True)
        try:
            gate = ActionGate(fabric, ActionPolicy(
                tools={"deploy": ToolRule("deploy", min_authority="untrusted")},
                grants={"agent": frozenset({"deploy"})},
            ))
            decision = gate.authorize("deploy", "agent")
            self.assertFalse(decision.allowed)
            self.assertIn(CERTIFICATE_REQUIRED, decision.reason_codes)
        finally:
            fabric.close()


if __name__ == "__main__":
    unittest.main()
