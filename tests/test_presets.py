"""Preset modes: personal, team, regulated."""

from __future__ import annotations

import contextlib
import io
import inspect
import json
import tempfile
import unittest
from dataclasses import fields
from pathlib import Path

from memory_fabric.cli import main
from memory_fabric.presets import MODES, mcp_flags, open_store, store_settings, tool_rule


class TestPresets(unittest.TestCase):
    def test_default_preset_and_opt_in_feature_flags_match_the_snapshot(self):
        from memory_fabric.adapters.mcp import McpServer

        snapshot = {"modes": {}, "tool_rules": {}, "mcp_flags": {}}
        for mode in MODES:
            settings = store_settings(mode)
            snapshot["modes"][mode] = {
                key: type(value).__name__ if key == "claim_checker" else value
                for key, value in settings.items()
            }
            rule = tool_rule(mode, "snapshot-tool")
            snapshot["tool_rules"][mode] = {
                item.name: list(value) if isinstance(value, tuple) else value
                for item in fields(rule)
                if (value := getattr(rule, item.name)) is not None
            }
            snapshot["mcp_flags"][mode] = mcp_flags(mode)
        signature = inspect.signature(McpServer)
        snapshot["mcp_default_flags"] = {
            "trusted_local": signature.parameters["trusted_local"].default,
            "extended": signature.parameters["extended"].default,
        }
        expected = json.loads((Path(__file__).parent / "data/default_features.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual(snapshot, expected)

    def test_personal_writes_are_active_team_writes_wait(self):
        for mode, expected in (("personal", "active"), ("team", "candidate")):
            f = open_store(":memory:", mode)
            mid = f.remember("ag", "The staging cluster runs in eu-west-2.", scope="team")
            self.assertEqual(f.lifecycle_of(mid).value, expected, mode)
            f.close()

    def test_rules_tighten_with_the_mode(self):
        self.assertEqual(tool_rule("personal", "t").min_independent_sources, 1)
        r = tool_rule("regulated", "t")
        self.assertEqual((r.min_independent_sources, r.require_fresh, r.refuse_provisional),
                         (2, True, True))
        self.assertEqual(tool_rule("regulated", "t", min_independent_sources=3)
                         .min_independent_sources, 3)
        self.assertEqual(mcp_flags("personal"), ["--trusted-local"])
        with self.assertRaises(ValueError):
            tool_rule("chaos", "t")
        self.assertEqual(MODES, ("personal", "team", "regulated"))

    def test_init_records_the_mode_and_the_cli_uses_it(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp) / "m"
            main(["init", str(root), "--mode", "personal"])
            self.assertEqual((root / "mode").read_text().strip(), "personal")


if __name__ == "__main__":
    unittest.main()
