import unittest

from memory_fabric.tool_protocol import (
    CodeModePlan,
    GovernedToolRuntime,
    ToolProtocolError,
    descriptor_to_mcp_tool,
    descriptor_to_utcp_tool,
    discover_utcp,
    mcp_tool_to_descriptor,
    utcp_tool_to_descriptor,
)
from memory_fabric.adapters.mcp import EXTENDED_TOOLS, TOOLS


class RecordingGate:
    def __init__(self):
        self.calls = []

    def execute(self, tool, agent_id, callback, **kwargs):
        self.calls.append((tool, agent_id, kwargs["request"], kwargs["key"]))
        return callback(kwargs["key"])


class ToolProtocol(unittest.TestCase):
    def test_supported_utcp_fields_round_trip_without_loss(self):
        raw = {
            "name": "lookup", "description": "read records",
            "inputs": {"type": "object", "properties": {"q": {"type": "string"}}},
            "consequential": False,
            "tool_call_template": {"call_template_type": "http", "url": "https://example.test"},
        }
        self.assertEqual(descriptor_to_utcp_tool(utcp_tool_to_descriptor(raw)), raw)

    def test_supported_mcp_fields_round_trip_without_loss(self):
        raw = {
            "name": "lookup", "description": "read records",
            "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}},
            "annotations": {"readOnlyHint": True, "destructiveHint": False,
                            "idempotentHint": True, "openWorldHint": False},
        }
        self.assertEqual(descriptor_to_mcp_tool(mcp_tool_to_descriptor(raw)), raw)

    def test_repository_mcp_descriptors_round_trip(self):
        for raw in TOOLS + EXTENDED_TOOLS:
            with self.subTest(tool=raw["name"]):
                self.assertEqual(descriptor_to_mcp_tool(mcp_tool_to_descriptor(raw)), raw)

    def test_cross_protocol_conversion_reports_unrepresentable_fields(self):
        utcp = utcp_tool_to_descriptor({
            "name": "send", "inputs": {"type": "object"},
            "tool_transport": {"call_template_type": "http"},
        })
        with self.assertRaisesRegex(ToolProtocolError, "cannot represent UTCP transport"):
            descriptor_to_mcp_tool(utcp)
        mcp = mcp_tool_to_descriptor({
            "name": "read", "inputSchema": {"type": "object"},
            "annotations": {"readOnlyHint": True},
        })
        with self.assertRaisesRegex(ToolProtocolError, "cannot represent MCP tool annotations"):
            descriptor_to_utcp_tool(mcp)

    def test_unknown_security_fields_never_disappear(self):
        cases = [
            (utcp_tool_to_descriptor, {"name": "read", "inputs": {"type": "object"},
                                       "authorization": {"scopes": ["admin"]}}),
            (mcp_tool_to_descriptor, {"name": "read", "inputSchema": {"type": "object"},
                                      "permissions": ["admin"]}),
            (mcp_tool_to_descriptor, {"name": "read", "inputSchema": {"type": "object"},
                                      "annotations": {"requiresGrant": True}}),
        ]
        for converter, raw in cases:
            with self.subTest(raw=raw), self.assertRaisesRegex(ToolProtocolError, "unsupported"):
                converter(raw)

    def test_utcp_discovery_is_pinned_and_deduplicated(self):
        tools = discover_utcp({"utcp_version": "1.0.1", "manual_version": "1.0.0", "tools": [
            {"name": "send", "description": "send a message", "consequential": True,
             "inputs": {"type": "object"},
             "tool_call_template": {"call_template_type": "http", "url": "https://example.test"}}
        ]})
        self.assertEqual(tools[0].protocol, "utcp-1.0.1")
        self.assertEqual(tools[0].transport["call_template_type"], "http")
        with self.assertRaises(ToolProtocolError):
            discover_utcp({"utcp_version": "2.0.0", "manual_version": "1.0.0", "tools": []})

    def test_code_mode_accepts_literal_tool_calls(self):
        plan = CodeModePlan.parse('lookup(query="safe")\nsend(to="ops", body="ok")')
        self.assertEqual([call.tool for call in plan.calls], ["lookup", "send"])
        self.assertEqual(plan.calls[1].arguments["to"], "ops")

    def test_code_mode_rejects_imports_dynamic_arguments_and_loops(self):
        bad = ["import os", "send(body=get_secret())", "for x in xs:\n send(body=x)"]
        for source in bad:
            with self.subTest(source=source), self.assertRaises(ToolProtocolError):
                CodeModePlan.parse(source)

    def test_every_effect_is_individually_gated_with_exact_arguments(self):
        gate = RecordingGate()
        runtime = GovernedToolRuntime(gate, {"send": lambda **values: values})
        results = CodeModePlan.parse('send(to="a")\nsend(to="b")').execute(
            runtime, agent_id="agent-1")
        self.assertEqual(results, ({"to": "a"}, {"to": "b"}))
        self.assertEqual(len(gate.calls), 2)
        self.assertEqual(gate.calls[0][2].parameters, {"to": "a"})
        self.assertNotEqual(gate.calls[0][3], gate.calls[1][3])


if __name__ == "__main__":
    unittest.main()
