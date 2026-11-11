"""Insufficient evidence may be shown only as a disclosed read-only advisory."""

from __future__ import annotations

import unittest

from memory_fabric import (
    MemoryFabric,
    ReadOnlyAdvisoryPolicy,
    assess_read_only_advisory,
)
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule, REFUSED


class ReadOnlyAdvisoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False)
        self.addCleanup(self.fabric.close)
        self.fabric.remember(
            "writer", "Compressor K-31 relief pressure is 14 bar.", scope="team")
        self.question = "What is the coolant flow of compressor K-31?"
        self.result = self.fabric.retrieve("reader", self.question, k=5)

    def test_insufficient_advisory_requires_policy_and_discloses_limit(self) -> None:
        denied = assess_read_only_advisory(
            self.result, self.question,
            ReadOnlyAdvisoryPolicy("maintenance-default"),
        )
        self.assertFalse(denied.presentation_allowed)

        allowed = assess_read_only_advisory(
            self.result, self.question,
            ReadOnlyAdvisoryPolicy("maintenance-console", allow_insufficient=True),
        )
        self.assertTrue(allowed.presentation_allowed)
        self.assertFalse(allowed.action_authorized)
        self.assertIn("insufficient", allowed.disclosure.lower())
        self.assertIn("does not authorize action", allowed.disclosure)
        self.assertFalse(allowed.to_json()["action_authorized"])

    def test_advisory_policy_does_not_authorize_protected_execution(self) -> None:
        advisory = assess_read_only_advisory(
            self.result, self.question,
            ReadOnlyAdvisoryPolicy("maintenance-console", allow_insufficient=True),
        )
        self.assertTrue(advisory.presentation_allowed)

        calls: list[str] = []
        gate = ActionGate(self.fabric, ActionPolicy(
            tools={"start_compressor": ToolRule("start_compressor")},
            grants={"operator": frozenset({"start_compressor"})},
        ))
        execution = gate.execute(
            "start_compressor", "operator", lambda key: calls.append(key), key="n2-08",
        )
        self.assertEqual(execution.outcome, REFUSED)
        self.assertEqual(calls, [])

    def test_ready_read_only_advisory_needs_no_degradation_disclosure(self) -> None:
        question = "What is the relief pressure of compressor K-31?"
        result = self.fabric.retrieve("reader", question, k=5)
        decision = assess_read_only_advisory(
            result, question, ReadOnlyAdvisoryPolicy("maintenance-default"),
        )
        self.assertTrue(decision.presentation_allowed)
        self.assertIsNone(decision.disclosure)
        self.assertFalse(decision.action_authorized)


if __name__ == "__main__":
    unittest.main()
