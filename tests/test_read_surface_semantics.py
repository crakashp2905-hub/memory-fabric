"""All public read surfaces expose the same semantic reason codes."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.adapters.mcp import McpServer
from memory_fabric.agent_api import AgentApi
from memory_fabric.cli import cmd_search
from memory_fabric.sdk import agent
from memory_fabric.service import MemoryService


class ReadSurfaceSemantics(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = MemoryFabric(auto_activate=True, hold_suspicious=False)
        self.addCleanup(self.fabric.close)
        self.fabric.remember("a", "Pump P-14 pressure is 12 bar.", scope="team")
        self.fabric.remember("b", "Pump P-14 pressure is 9 bar.", scope="team")
        self.client = agent(self.fabric, "reader")

    def codes(self, query: str) -> tuple[str, str, str, str]:
        sdk = self.client.recall(query, k=10, include_contested=True)

        server = McpServer(self.client, self.fabric)
        mcp = server._recall({"query": query, "k": 10, "include_contested": True})

        http = AgentApi(MemoryService(fabric=self.fabric))._recall(
            self.client, {"query": query, "k": 10, "include_contested": True}
        )

        output = io.StringIO()
        args = argparse.Namespace(query=query, limit=10, retrievable=False, json=True)
        with contextlib.redirect_stdout(output):
            cmd_search(self.fabric, args)
        cli = json.loads(output.getvalue())
        return (
            sdk.answerability.reason_code,
            mcp["answerability"]["reason_code"],
            http["answerability"]["reason_code"],
            cli["answerability"]["reason_code"],
        )

    def test_unknown_is_consistent(self) -> None:
        self.assertEqual(self.codes("What is the coolant flow of pump P-14?"),
                         ("UNKNOWN",) * 4)

    def test_conflicting_is_consistent(self) -> None:
        self.assertEqual(self.codes("What is the pressure of pump P-14?"),
                         ("CONFLICTING",) * 4)

    def test_undetermined_is_consistent(self) -> None:
        self.assertEqual(self.codes("What is the usual pressure?"),
                         ("UNDETERMINED",) * 4)


if __name__ == "__main__":
    unittest.main()
