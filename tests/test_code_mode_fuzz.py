from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from memory_fabric.tool_protocol import (MAX_CODE_MODE_ARGUMENT_BYTES, MAX_CODE_MODE_ARGUMENT_DEPTH,
                                         MAX_CODE_MODE_CALLS, MAX_CODE_MODE_SOURCE_BYTES,
                                         CodeModePlan, GovernedToolRuntime, ToolProtocolError)


CORPUS = Path(__file__).parent / "data/code_mode_malicious_plans.json"


class CodeModeParserFuzz(unittest.TestCase):
    def test_hostile_construct_corpus_is_rejected_during_parse(self) -> None:
        cases = json.loads(CORPUS.read_text(encoding="utf-8"))
        families = Counter()
        self.assertGreaterEqual(len(cases), 20)
        for case in cases:
            families[case["family"]] += 1
            with self.subTest(family=case["family"], source=case["source"]):
                with self.assertRaises(ToolProtocolError):
                    CodeModePlan.parse(case["source"])
        self.assertEqual(set(families), {
            "imports", "eval", "attribute_access", "comprehension", "reflection",
            "dynamic_arguments", "unpacking", "control_flow", "dunder_tool_name",
        })

    def test_reserved_evaluator_names_cannot_become_registered_tool_calls(self) -> None:
        for name in ("eval", "exec", "compile", "open", "getattr", "setattr",
                     "delattr", "globals", "locals", "vars", "dir", "type",
                     "object", "super", "input", "__import__"):
            with self.subTest(name=name), self.assertRaises(ToolProtocolError):
                CodeModePlan.parse(f"{name}(value='x')")

    def test_literal_tool_calls_remain_supported_after_negative_corpus(self) -> None:
        plan = CodeModePlan.parse("lookup(query='safe', limit=2)")
        self.assertEqual(plan.calls[0].tool, "lookup")
        self.assertEqual(plan.calls[0].arguments, {"query": "safe", "limit": 2})

    def test_call_count_source_bytes_argument_bytes_and_nesting_are_bounded(self) -> None:
        accepted = "\n".join("lookup(index=1)" for _ in range(MAX_CODE_MODE_CALLS))
        self.assertEqual(len(CodeModePlan.parse(accepted).calls), MAX_CODE_MODE_CALLS)
        with self.assertRaisesRegex(ToolProtocolError, "maximum tool calls"):
            CodeModePlan.parse(accepted + "\nlookup(index=1)")
        with self.assertRaisesRegex(ToolProtocolError, "source exceeds byte limit"):
            CodeModePlan.parse("#" + "x" * MAX_CODE_MODE_SOURCE_BYTES)
        large_argument = "lookup(value='" + "x" * (MAX_CODE_MODE_ARGUMENT_BYTES + 100) + "')"
        with self.assertRaisesRegex(ToolProtocolError, "arguments exceed byte limit"):
            CodeModePlan.parse(large_argument)
        nested = "lookup(value=" + "[" * (MAX_CODE_MODE_ARGUMENT_DEPTH + 1) + "0" + "]" * (MAX_CODE_MODE_ARGUMENT_DEPTH + 1) + ")"
        with self.assertRaisesRegex(ToolProtocolError, "nesting limit"):
            CodeModePlan.parse(nested)

    def test_runtime_rejects_unregistered_tool_before_authorization(self) -> None:
        class NeverGate:
            def execute(self, *_args, **_kwargs):
                raise AssertionError("unregistered handler must be rejected before the gate")

        runtime = GovernedToolRuntime(NeverGate(), {"lookup": lambda **_values: None})
        call = CodeModePlan.parse("not_registered(value='x')").calls[0]
        with self.assertRaisesRegex(ToolProtocolError, "no registered handler"):
            runtime.execute(call, agent_id="agent", session=object())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
