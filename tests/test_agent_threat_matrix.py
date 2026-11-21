"""The agent threat matrix (W16-01) names only tests that exist, and marks gaps as gaps."""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "AGENT_THREAT_MATRIX.md"
COLUMNS = ["#", "Injection point", "Attacker", "Trust boundary", "Goal", "Mitigation", "Test"]


def rows() -> list[list[str]]:
    table = [line for line in MATRIX.read_text(encoding="utf-8").splitlines()
             if line.startswith("| T")]
    return [[cell.strip() for cell in line.strip("|").split(" | ")] for line in table]


class ThreatMatrix(unittest.TestCase):
    def test_every_row_has_every_column(self) -> None:
        self.assertGreaterEqual(len(rows()), 10)
        for row in rows():
            self.assertEqual(len(row), len(COLUMNS), row[0])
            self.assertTrue(all(cell for cell in row), row[0])

    def test_a_row_without_a_test_says_not_covered(self) -> None:
        for row in rows():
            if "tests/" not in row[-1]:
                self.assertIn("not covered", row[-1], row[0])
                self.assertIn("not covered", row[5].lower(), row[0])

    def test_every_named_test_is_collected(self) -> None:
        named = sorted({node for row in rows() for node in re.findall(r"`(tests/[^`]+)`", row[-1])})
        self.assertTrue(named)
        files = sorted({node.split("::", 1)[0] for node in named})
        done = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                               "-p", "no:cacheprovider", *files], cwd=ROOT,
                              capture_output=True, text=True, timeout=300)
        collected = set(done.stdout.split())
        missing = [node for node in named
                   if not any(item == node or item.startswith(node + "::")
                              or item.startswith(node + "[") for item in collected)]
        self.assertEqual(missing, [], "threat matrix names tests that do not exist")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
