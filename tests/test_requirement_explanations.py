from __future__ import annotations

from itertools import combinations
import unittest

from memory_fabric import (
    AllOfRequirement,
    AnyOfRequirement,
    ClaimRequirement,
    IndependentSourcesRequirement,
    RequirementGraph,
    RuleReference,
    TemporalRequirement,
    minimal_missing_evidence_sets,
    parse_requirement_graph,
    requirement_atom_keys,
    RequirementGraphError,
)


def make_graph(root: dict[str, object], rules: dict[str, object] | None = None) -> RequirementGraph:
    return parse_requirement_graph({
        "schema": "memory-fabric-requirement-graph/1",
        "graph_id": "minimal-missing-v1",
        "root": root,
        "rules": rules or {},
    })


def oracle_atom_keys(node, graph, temporal=(), active=frozenset()):
    """Independent test oracle: enumerate the atomic obligations by AST walk."""
    if isinstance(node, ClaimRequirement):
        key = f"claim:{node.claim_id}"
    elif isinstance(node, IndependentSourcesRequirement):
        key = f"independent_sources:{node.claim_id}:{node.min_sources}"
    elif isinstance(node, TemporalRequirement):
        return oracle_atom_keys(node.requirement, graph,
                                (*temporal, (node.anchor, node.max_age_ms)), active)
    elif isinstance(node, RuleReference):
        if node.rule_id in active:
            raise AssertionError("parser allowed a recursive named rule")
        return oracle_atom_keys(graph.rules[node.rule_id], graph, temporal,
                                active | {node.rule_id})
    elif isinstance(node, (AllOfRequirement, AnyOfRequirement)):
        return set().union(*(oracle_atom_keys(child, graph, temporal, active)
                             for child in node.requirements))
    else:
        raise AssertionError(f"unexpected AST node {node!r}")
    for anchor, age in temporal:
        key += f"@temporal:{anchor}:{age}"
    return {key}


def oracle_satisfied(node, graph, satisfied, temporal=(), active=frozenset()):
    """Brute-force Boolean semantics, intentionally separate from production code."""
    if isinstance(node, ClaimRequirement):
        key = f"claim:{node.claim_id}"
    elif isinstance(node, IndependentSourcesRequirement):
        key = f"independent_sources:{node.claim_id}:{node.min_sources}"
    elif isinstance(node, TemporalRequirement):
        return oracle_satisfied(node.requirement, graph, satisfied,
                                (*temporal, (node.anchor, node.max_age_ms)), active)
    elif isinstance(node, RuleReference):
        if node.rule_id in active:
            raise AssertionError("parser allowed a recursive named rule")
        return oracle_satisfied(graph.rules[node.rule_id], graph, satisfied, temporal,
                                active | {node.rule_id})
    elif isinstance(node, AllOfRequirement):
        return all(oracle_satisfied(child, graph, satisfied, temporal, active)
                   for child in node.requirements)
    elif isinstance(node, AnyOfRequirement):
        return any(oracle_satisfied(child, graph, satisfied, temporal, active)
                   for child in node.requirements)
    else:
        raise AssertionError(f"unexpected AST node {node!r}")
    for anchor, age in temporal:
        key += f"@temporal:{anchor}:{age}"
    return key in satisfied


def exhaustive_missing_sets(graph: RequirementGraph, satisfied: frozenset[str]):
    atoms = sorted(oracle_atom_keys(graph.root, graph))
    remaining = [atom for atom in atoms if atom not in satisfied]
    solutions = []
    for size in range(len(remaining) + 1):
        for candidate in combinations(remaining, size):
            if oracle_satisfied(graph.root, graph, satisfied | frozenset(candidate)):
                solutions.append(frozenset(candidate))
    minimal = [candidate for candidate in solutions
               if not any(other < candidate for other in solutions)]
    return tuple(tuple(sorted(item)) for item in sorted(
        minimal, key=lambda item: (len(item), tuple(sorted(item)))))


class MinimalMissingEvidenceTests(unittest.TestCase):
    def test_small_graph_outputs_match_exhaustive_oracle_for_every_satisfaction_state(self) -> None:
        graphs = [
            make_graph({"op": "and", "requirements": [
                {"op": "claim", "claim_id": "a"},
                {"op": "or", "requirements": [
                    {"op": "claim", "claim_id": "b"},
                    {"op": "claim", "claim_id": "c"},
                ]},
            ]}),
            make_graph({"op": "or", "requirements": [
                {"op": "and", "requirements": [
                    {"op": "claim", "claim_id": "a"},
                    {"op": "claim", "claim_id": "b"},
                ]},
                {"op": "claim", "claim_id": "c"},
            ]}),
            make_graph({"op": "and", "requirements": [
                {"op": "independent_sources", "claim_id": "sensor", "min_sources": 2},
                {"op": "claim", "claim_id": "review"},
            ]}),
            make_graph({"op": "and", "requirements": [
                {"op": "rule", "rule_id": "safety"},
                {"op": "claim", "claim_id": "permit"},
            ]}, {"safety": {"op": "or", "requirements": [
                {"op": "claim", "claim_id": "sensor_a"},
                {"op": "claim", "claim_id": "sensor_b"},
            ]}}),
            make_graph({"op": "temporal", "max_age_ms": 50, "anchor": "action_time",
                       "requirement": {"op": "and", "requirements": [
                           {"op": "claim", "claim_id": "pressure"},
                           {"op": "claim", "claim_id": "temperature"},
                       ]}}),
        ]
        for graph in graphs:
            atoms = sorted(oracle_atom_keys(graph.root, graph))
            for size in range(len(atoms) + 1):
                for selected in combinations(atoms, size):
                    satisfied = frozenset(selected)
                    with self.subTest(graph=graph.graph_id, satisfied=selected):
                        self.assertEqual(
                            minimal_missing_evidence_sets(graph, satisfied),
                            exhaustive_missing_sets(graph, satisfied),
                        )

    def test_missing_mandatory_claim_and_alternative_sets_are_explained(self) -> None:
        graph = make_graph({"op": "and", "requirements": [
            {"op": "claim", "claim_id": "pressure"},
            {"op": "or", "requirements": [
                {"op": "claim", "claim_id": "manual_check"},
                {"op": "claim", "claim_id": "sensor_check"},
            ]},
        ]})
        self.assertEqual(minimal_missing_evidence_sets(graph, {"claim:pressure"}), (
            ("claim:manual_check",), ("claim:sensor_check",),
        ))

    def test_satisfied_policy_returns_one_empty_missing_set(self) -> None:
        graph = make_graph({"op": "claim", "claim_id": "permit"})
        self.assertEqual(minimal_missing_evidence_sets(graph, {"claim:permit"}), ((),))

    def test_atom_keys_include_independence_and_temporal_constraints(self) -> None:
        graph = make_graph({"op": "temporal", "max_age_ms": 50, "anchor": "action_time",
                           "requirement": {"op": "independent_sources",
                                            "claim_id": "reading", "min_sources": 2}})
        self.assertEqual(requirement_atom_keys(graph), (
            "independent_sources:reading:2@temporal:action_time:50",
        ))

    def test_unknown_satisfied_atom_fails_instead_of_hiding_a_misspelling(self) -> None:
        graph = make_graph({"op": "claim", "claim_id": "permit"})
        with self.assertRaisesRegex(ValueError, "unknown satisfied requirement"):
            minimal_missing_evidence_sets(graph, {"claim:permti"})

    def test_result_bound_fails_explicitly_instead_of_truncating_alternatives(self) -> None:
        graph = make_graph({"op": "or", "requirements": [
            {"op": "claim", "claim_id": "manual"},
            {"op": "claim", "claim_id": "sensor"},
        ]})
        with self.assertRaisesRegex(RequirementGraphError, "max_sets"):
            minimal_missing_evidence_sets(graph, (), max_sets=1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
