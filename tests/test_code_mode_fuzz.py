from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from memory_fabric.tool_protocol import CodeModePlan, ToolProtocolError


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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
