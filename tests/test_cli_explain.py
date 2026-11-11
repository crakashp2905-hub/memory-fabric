"""Operator refusal explanations are content-safe and actionable."""

import contextlib
import io
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.cli import build_parser, cmd_explain, main


class TestExplainCommand(unittest.TestCase):
    def test_reason_code_works_without_a_store_and_names_safe_next_step(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["explain", "evidence_withdrawn"])
        self.assertEqual(result, 0)
        self.assertIn("evidence_withdrawn", output.getvalue())
        self.assertIn("Re-certify", output.getvalue())

    def test_action_explanation_lists_policy_and_evidence_without_content(self):
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        canary = "SYNTHETIC-EXPLAIN-CANARY"
        mid = fabric.remember("agent", canary, scope="team")
        gate = ActionGate(fabric, ActionPolicy(
            tools={"deploy": ToolRule("deploy")}, grants={"agent": frozenset({"deploy"})}))
        certificate = fabric.certify("deploy", [mid], "agent")
        gate.authorize("deploy", "agent", certificate)
        fabric.quarantine(mid, reason="changed", actor="reviewer", basis="contradicted")
        gate.authorize("deploy", "agent", certificate)
        seq = max(row.seq for row in fabric.log.read() if row.type == "ActionGated")
        args = build_parser().parse_args(["explain", "--action", str(seq)])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = cmd_explain(fabric, args)
        self.assertEqual(result, 0)
        self.assertIn("Evidence", output.getvalue())
        self.assertIn("Evidence and support", output.getvalue())
        self.assertNotIn(canary, output.getvalue())
        self.assertIn("evidence_withdrawn", output.getvalue())


if __name__ == "__main__":
    unittest.main()
