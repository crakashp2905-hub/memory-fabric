from __future__ import annotations

import json
import unittest

from memory_fabric import (
    AllOfRequirement,
    AnyOfRequirement,
    IndependentSourcesRequirement,
    RequirementGraph,
    RequirementGraphError,
    RuleReference,
    TemporalRequirement,
    parse_requirement_graph,
)


def valid_graph() -> dict[str, object]:
    return {
        "schema": "memory-fabric-requirement-graph/1",
        "graph_id": "pump-restart-v1",
        "rules": {
            "pressure-check": {
                "op": "and",
                "requirements": [
                    {"op": "claim", "claim_id": "pressure-within-limit"},
                    {"op": "independent_sources", "claim_id": "pressure-reading",
                     "min_sources": 2},
                ],
            },
            "power-check": {
                "op": "or",
                "requirements": [
                    {"op": "claim", "claim_id": "power-isolated"},
                    {"op": "claim", "claim_id": "lockout-tagout-verified"},
                ],
            },
        },
        "root": {
            "op": "and",
            "requirements": [
                {"op": "rule", "rule_id": "pressure-check"},
                {"op": "temporal", "max_age_ms": 60_000, "anchor": "action_time",
                 "requirement": {"op": "rule", "rule_id": "power-check"}},
            ],
        },
    }


class RequirementGraphTests(unittest.TestCase):
    def test_parses_typed_operators_and_round_trips_canonical_json(self) -> None:
        graph = parse_requirement_graph(valid_graph())
        self.assertIsInstance(graph.root, AllOfRequirement)
        self.assertIsInstance(graph.root.requirements[0], RuleReference)
        temporal = graph.root.requirements[1]
        self.assertIsInstance(temporal, TemporalRequirement)
        self.assertEqual(temporal.anchor, "action_time")
        pressure = graph.rules["pressure-check"]
        self.assertIsInstance(pressure, AllOfRequirement)
        self.assertIsInstance(pressure.requirements[1], IndependentSourcesRequirement)
        self.assertIsInstance(graph.rules["power-check"], AnyOfRequirement)
        restored = parse_requirement_graph(graph.to_json())
        self.assertEqual(restored, graph)
        self.assertEqual(json.loads(graph.to_json()), graph.to_dict())
        with self.assertRaises(TypeError):
            graph.rules["untrusted"] = graph.root  # type: ignore[index]
        with self.assertRaises(TypeError):
            RequirementGraph("unchecked", graph.root, {})

    def test_reports_unknown_operator_fields_and_missing_fields_with_paths(self) -> None:
        payload = valid_graph()
        payload["root"] = {"op": "xor", "requirements": []}
        with self.assertRaises(RequirementGraphError) as unknown:
            parse_requirement_graph(payload)
        self.assertEqual(unknown.exception.code, "unknown_op")
        self.assertIn("$.root.op", str(unknown.exception))

        payload["root"] = {"op": "claim", "claim_id": "x", "surprise": True}
        with self.assertRaises(RequirementGraphError) as extra:
            parse_requirement_graph(payload)
        self.assertEqual(extra.exception.code, "unknown_field")
        self.assertIn("surprise", str(extra.exception))

        payload["root"] = {"op": "claim"}
        with self.assertRaises(RequirementGraphError) as missing:
            parse_requirement_graph(payload)
        self.assertEqual(missing.exception.code, "missing_field")
        self.assertIn("claim_id", str(missing.exception))

    def test_rejects_undefined_and_cyclic_rule_references(self) -> None:
        payload = valid_graph()
        payload["root"] = {"op": "rule", "rule_id": "missing"}
        with self.assertRaises(RequirementGraphError) as undefined:
            parse_requirement_graph(payload)
        self.assertEqual(undefined.exception.code, "undefined_rule")

        payload["rules"] = {
            "a": {"op": "rule", "rule_id": "b"},
            "b": {"op": "temporal", "max_age_ms": 1000, "anchor": "decision_time",
                  "requirement": {"op": "rule", "rule_id": "a"}},
        }
        payload["root"] = {"op": "rule", "rule_id": "a"}
        with self.assertRaises(RequirementGraphError) as cycle:
            parse_requirement_graph(payload)
        self.assertEqual(cycle.exception.code, "cycle")
        self.assertIn("a -> b -> a", str(cycle.exception))

    def test_rejects_python_container_cycles_and_excessive_size_or_depth(self) -> None:
        cyclic: dict[str, object] = {"op": "and", "requirements": []}
        cyclic["requirements"] = [cyclic, {"op": "claim", "claim_id": "x"}]
        payload = {"schema": "memory-fabric-requirement-graph/1", "graph_id": "cycle",
                   "root": cyclic}
        with self.assertRaises(RequirementGraphError) as cycle:
            parse_requirement_graph(payload)
        self.assertEqual(cycle.exception.code, "cycle")

        with self.assertRaises(RequirementGraphError) as size:
            parse_requirement_graph(valid_graph(), max_nodes=2)
        self.assertEqual(size.exception.code, "limit")

        deep: dict[str, object] = {"op": "claim", "claim_id": "leaf"}
        for _ in range(33):
            deep = {"op": "temporal", "max_age_ms": 1000,
                    "anchor": "action_time", "requirement": deep}
        payload["root"] = deep
        with self.assertRaises(RequirementGraphError) as depth:
            parse_requirement_graph(payload)
        self.assertEqual(depth.exception.code, "limit")

    def test_validates_temporal_independence_and_json_boundaries(self) -> None:
        payload = valid_graph()
        rules = payload["rules"]
        assert isinstance(rules, dict)
        rules["pressure-check"]["requirements"][1]["min_sources"] = True
        with self.assertRaises(RequirementGraphError) as minimum:
            parse_requirement_graph(payload)
        self.assertEqual(minimum.exception.code, "type")

        payload = valid_graph()
        payload["root"]["requirements"][1]["anchor"] = []
        with self.assertRaises(RequirementGraphError) as anchor:
            parse_requirement_graph(payload)
        self.assertEqual(anchor.exception.code, "value")

        with self.assertRaises(RequirementGraphError) as duplicate:
            parse_requirement_graph('{"schema":"memory-fabric-requirement-graph/1",'
                                    '"graph_id":"g","root":{"op":"claim",'
                                    '"claim_id":"x","claim_id":"y"}}')
        self.assertEqual(duplicate.exception.code, "json")


if __name__ == "__main__":
    unittest.main()
