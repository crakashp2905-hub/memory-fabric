"""Principals, permission matrix and causality labels (W19-01, W19-08)."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "AGENT_PRINCIPALS.md"
PRINCIPALS = ["actor", "evaluator", "operator", "integration", "auditor"]


def matrix() -> dict[str, dict[str, str]]:
    rows = {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        if line.startswith("| ") and "`" in line.split("|")[1]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows[cells[0].replace("`", "").replace(" (protected)", "")] = dict(zip(PRINCIPALS, cells[1:]))
    return rows


class PermissionMatrix(unittest.TestCase):
    def test_every_exposed_endpoint_is_in_the_matrix(self) -> None:
        from memory_fabric.adapters.mcp import EXTENDED_TOOLS, TOOLS
        from memory_fabric.outcome_typed.episode import default_tools

        rows = matrix()
        names = lambda tools: [t["name"] if isinstance(t, dict) else t.name for t in tools]  # noqa: E731
        for name in names(TOOLS) + names(EXTENDED_TOOLS):
            self.assertIn(f"mcp {name}", rows)
        for op in ("recall", "fetch", "verify", "remember"):
            self.assertIn(f"agent-api {op}", rows)
        for name in default_tools()._specs:  # noqa: SLF001
            self.assertIn(f"episode {name}", rows)

    def test_no_actor_endpoint_reaches_evaluator_operator_or_grant_power(self) -> None:
        rows = matrix()
        for endpoint in ("evaluator grade_episode", "evaluator open_payload", "operator review_decide",
                         "operator quarantine", "operator erase_content", "action issue_grant"):
            self.assertEqual(rows[endpoint]["actor"], "no", endpoint)
        for endpoint, row in rows.items():
            if endpoint.startswith(("agent-api", "mcp")):
                self.assertEqual(row["evaluator"], "no", endpoint)
        self.assertEqual({row["auditor"] for row in rows.values()} - {"no"}, {"yes"})

    def test_every_principal_has_its_own_secret(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for principal in PRINCIPALS:
            self.assertIn(f"| **{principal}** |", text)


class CausalityLabels(unittest.TestCase):
    def test_reports_say_physical_causality_is_not_established(self) -> None:
        from benchmarks.outcome_arms import run
        from benchmarks.outcome_scorecard import scorecard

        report = run(seeds=1)
        self.assertEqual(report["cdm"]["physical_causality"], "NOT_ESTABLISHED")
        self.assertEqual(report["cdm"]["root_cause_level"], "simulator")
        card = scorecard(report, source_sha="e" * 40, evidence_type="scripted")
        self.assertEqual((card["physical_causality"], card["root_cause_level"]),
                         ("NOT_ESTABLISHED", "simulator"))
        model = scorecard(report, source_sha="e" * 40, evidence_type="local_model")
        self.assertEqual(model["root_cause_level"], "agent_policy")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
