"""docs/API.md and docs/CLI.md match the code, and every CLI option says what it does."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import unittest
from pathlib import Path

from memory_fabric.cli import build_parser

ROOT = Path(__file__).resolve().parents[1]


class ReferenceDocs(unittest.TestCase):
    def test_generated_references_are_current(self) -> None:
        done = subprocess.run([sys.executable, "tools/gen_reference.py", "--check"], cwd=ROOT,
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_public_inventory_has_unique_tiered_signatures_and_migration_policy(self) -> None:
        inventory = json.loads((ROOT / "docs/API_INVENTORY.json").read_text(encoding="utf-8"))
        self.assertEqual(inventory["schema"], "memory-fabric-public-api/1")
        self.assertIn("CHANGELOG migration note", inventory["compatibility_policy"])
        symbols = inventory["symbols"]
        names = [entry["symbol"] for entry in symbols]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(symbols)
        for entry in symbols:
            with self.subTest(symbol=entry["symbol"]):
                self.assertIn(entry["tier"], {"stable", "beta", "experimental"})
                self.assertTrue(entry["signature"])

    def test_every_cli_option_has_help(self) -> None:
        parser = build_parser()
        sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        missing = [(name, a.option_strings or a.dest) for name, command in sub.choices.items()
                   for a in command._actions if a.dest != "help" and not a.help]
        self.assertEqual(missing, [], "add a help= or an entry in cli.HELP")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
