"""Typed, bounded grammar for action evidence requirements.

This module parses policy structure only. It does not evaluate claims, infer
truth, or authorize actions.
"""
from __future__ import annotations

__stability__ = "stable"

from dataclasses import dataclass
import json
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias

GRAPH_SCHEMA = "memory-fabric-requirement-graph/1"
MAX_GRAPH_NODES = 256
MAX_GRAPH_DEPTH = 32
MAX_RULES = 64
MAX_CHILDREN = 32
MAX_ID_LENGTH = 128


class RequirementGraphError(ValueError):
    """A requirement graph is malformed, cyclic, or exceeds parser limits."""

    def __init__(self, message: str, *, path: str = "$", code: str = "invalid") -> None:
        self.path = path
        self.code = code
        super().__init__(f"{path}: {message}")


@dataclass(frozen=True, slots=True)
class ClaimRequirement:
    claim_id: str


@dataclass(frozen=True, slots=True)
class AllOfRequirement:
    requirements: tuple[RequirementNode, ...]


@dataclass(frozen=True, slots=True)
class AnyOfRequirement:
    requirements: tuple[RequirementNode, ...]


@dataclass(frozen=True, slots=True)
class IndependentSourcesRequirement:
    claim_id: str
    min_sources: int


@dataclass(frozen=True, slots=True)
class TemporalRequirement:
    requirement: RequirementNode
    max_age_ms: int
    anchor: str


@dataclass(frozen=True, slots=True)
class RuleReference:
    rule_id: str


RequirementNode: TypeAlias = (
    ClaimRequirement | AllOfRequirement | AnyOfRequirement
    | IndependentSourcesRequirement | TemporalRequirement | RuleReference
)


@dataclass(frozen=True, slots=True, init=False)
class RequirementGraph:
    """Immutable validated graph returned by `parse_requirement_graph`.

    Construct policy from a document with the parser; this class has no public
    unchecked constructor.
    """

    graph_id: str
    root: RequirementNode
    rules: Mapping[str, RequirementNode]
    schema: str = GRAPH_SCHEMA

    @classmethod
    def _from_parsed(cls, graph_id: str, root: RequirementNode,
                     rules: Mapping[str, RequirementNode]) -> RequirementGraph:
        """Create a graph only after the structural parser validates it."""
        graph = object.__new__(cls)
        object.__setattr__(graph, "graph_id", graph_id)
        object.__setattr__(graph, "root", root)
        object.__setattr__(graph, "rules", MappingProxyType(dict(sorted(rules.items()))))
        object.__setattr__(graph, "schema", GRAPH_SCHEMA)
        return graph

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "graph_id": self.graph_id,
            "rules": {key: _node_to_dict(value) for key, value in self.rules.items()},
            "root": _node_to_dict(self.root),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)


def _node_to_dict(node: RequirementNode) -> dict[str, Any]:
    if isinstance(node, ClaimRequirement):
        return {"op": "claim", "claim_id": node.claim_id}
    if isinstance(node, AllOfRequirement):
        return {"op": "and", "requirements": [_node_to_dict(child)
                                                for child in node.requirements]}
    if isinstance(node, AnyOfRequirement):
        return {"op": "or", "requirements": [_node_to_dict(child)
                                               for child in node.requirements]}
    if isinstance(node, IndependentSourcesRequirement):
        return {"op": "independent_sources", "claim_id": node.claim_id,
                "min_sources": node.min_sources}
    if isinstance(node, TemporalRequirement):
        return {"op": "temporal", "requirement": _node_to_dict(node.requirement),
                "max_age_ms": node.max_age_ms, "anchor": node.anchor}
    if isinstance(node, RuleReference):
        return {"op": "rule", "rule_id": node.rule_id}
    raise TypeError(f"unsupported requirement node: {type(node).__name__}")


class _Parser:
    def __init__(self, max_nodes: int) -> None:
        if isinstance(max_nodes, bool) or not isinstance(max_nodes, int) or not 1 <= max_nodes <= MAX_GRAPH_NODES:
            raise ValueError(f"max_nodes must be an integer from 1 to {MAX_GRAPH_NODES}")
        self.max_nodes = max_nodes
        self.nodes = 0
        self.active_containers: set[int] = set()

    @staticmethod
    def mapping(value: Any, path: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise RequirementGraphError("expected an object", path=path, code="type")
        if any(not isinstance(key, str) for key in value):
            raise RequirementGraphError("object keys must be strings", path=path, code="type")
        return value

    @staticmethod
    def fields(value: Mapping[str, Any], *, required: set[str], optional: set[str],
               path: str) -> None:
        missing = required - value.keys()
        extra = value.keys() - required - optional
        if missing:
            raise RequirementGraphError(f"missing field(s): {', '.join(sorted(missing))}",
                                        path=path, code="missing_field")
        if extra:
            raise RequirementGraphError(f"unknown field(s): {', '.join(sorted(extra))}",
                                        path=path, code="unknown_field")

    @staticmethod
    def identifier(value: Any, path: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise RequirementGraphError("must be a non-empty string", path=path, code="type")
        if len(value) > MAX_ID_LENGTH:
            raise RequirementGraphError(f"must be at most {MAX_ID_LENGTH} characters",
                                        path=path, code="limit")
        return value

    @staticmethod
    def integer(value: Any, path: str, *, minimum: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise RequirementGraphError("must be an integer", path=path, code="type")
        if value < minimum:
            raise RequirementGraphError(f"must be at least {minimum}", path=path, code="range")
        return value

    def node(self, value: Any, path: str = "$.root", depth: int = 1) -> RequirementNode:
        if depth > MAX_GRAPH_DEPTH:
            raise RequirementGraphError(f"maximum nested depth is {MAX_GRAPH_DEPTH}",
                                        path=path, code="limit")
        if self.nodes >= self.max_nodes:
            raise RequirementGraphError(f"maximum node count is {self.max_nodes}",
                                        path=path, code="limit")
        self.nodes += 1
        row = self.mapping(value, path)
        identity = id(row)
        if identity in self.active_containers:
            raise RequirementGraphError("cyclic object reference", path=path, code="cycle")
        self.active_containers.add(identity)
        try:
            op = row.get("op")
            if not isinstance(op, str):
                raise RequirementGraphError("op must be a string", path=f"{path}.op", code="type")
            if op == "claim":
                self.fields(row, required={"op", "claim_id"}, optional=set(), path=path)
                return ClaimRequirement(self.identifier(row["claim_id"], f"{path}.claim_id"))
            if op in {"and", "or"}:
                self.fields(row, required={"op", "requirements"}, optional=set(), path=path)
                children = row["requirements"]
                if not isinstance(children, (list, tuple)):
                    raise RequirementGraphError("requirements must be an array",
                                                path=f"{path}.requirements", code="type")
                if not 2 <= len(children) <= MAX_CHILDREN:
                    raise RequirementGraphError(
                        f"requires 2 to {MAX_CHILDREN} children", path=f"{path}.requirements",
                        code="limit")
                parsed = tuple(self.node(child, f"{path}.requirements[{index}]", depth + 1)
                               for index, child in enumerate(children))
                return AllOfRequirement(parsed) if op == "and" else AnyOfRequirement(parsed)
            if op == "independent_sources":
                self.fields(row, required={"op", "claim_id", "min_sources"},
                            optional=set(), path=path)
                return IndependentSourcesRequirement(
                    self.identifier(row["claim_id"], f"{path}.claim_id"),
                    self.integer(row["min_sources"], f"{path}.min_sources", minimum=2),
                )
            if op == "temporal":
                self.fields(row, required={"op", "requirement", "max_age_ms", "anchor"},
                            optional=set(), path=path)
                anchor = row["anchor"]
                if not isinstance(anchor, str) or anchor not in {"decision_time", "action_time"}:
                    raise RequirementGraphError(
                        "must be 'decision_time' or 'action_time'", path=f"{path}.anchor",
                        code="value")
                child = self.node(row["requirement"], f"{path}.requirement", depth + 1)
                return TemporalRequirement(
                    child, self.integer(row["max_age_ms"], f"{path}.max_age_ms", minimum=1),
                    anchor,
                )
            if op == "rule":
                self.fields(row, required={"op", "rule_id"}, optional=set(), path=path)
                return RuleReference(self.identifier(row["rule_id"], f"{path}.rule_id"))
            raise RequirementGraphError(
                f"unknown op {op!r}; expected claim, and, or, independent_sources, temporal, or rule",
                path=f"{path}.op", code="unknown_op")
        finally:
            self.active_containers.remove(identity)


def parse_requirement_graph(payload: Mapping[str, Any] | str | bytes, *,
                            max_nodes: int = MAX_GRAPH_NODES) -> RequirementGraph:
    """Parse and validate a bounded acyclic requirement graph.

    JSON strings and bytes are accepted alongside decoded objects. Errors carry
    a JSON path and stable reason code to support actionable policy diagnostics.
    """
    if isinstance(payload, (str, bytes)):
        try:
            payload = json.loads(payload, object_pairs_hook=_unique_object)
        except (json.JSONDecodeError, UnicodeDecodeError, _DuplicateKeyError) as exc:
            raise RequirementGraphError(f"invalid JSON: {exc}", code="json") from exc
    parser = _Parser(max_nodes)
    row = parser.mapping(payload, "$")
    parser.fields(row, required={"schema", "graph_id", "root"}, optional={"rules"}, path="$")
    if row["schema"] != GRAPH_SCHEMA:
        raise RequirementGraphError(f"schema must be {GRAPH_SCHEMA!r}",
                                    path="$.schema", code="schema")
    graph_id = parser.identifier(row["graph_id"], "$.graph_id")
    raw_rules = row.get("rules", {})
    rules_map = parser.mapping(raw_rules, "$.rules")
    if len(rules_map) > MAX_RULES:
        raise RequirementGraphError(f"maximum rule count is {MAX_RULES}",
                                    path="$.rules", code="limit")
    rules: dict[str, RequirementNode] = {}
    for rule_id in sorted(rules_map):
        parser.identifier(rule_id, f"$.rules[{rule_id!r}]")
        rules[rule_id] = parser.node(rules_map[rule_id], f"$.rules[{rule_id!r}]")
    root = parser.node(row["root"])

    rule_refs: dict[str, set[str]] = {}
    all_refs: set[str] = set()

    def references(node: RequirementNode) -> set[str]:
        if isinstance(node, RuleReference):
            return {node.rule_id}
        if isinstance(node, (AllOfRequirement, AnyOfRequirement)):
            return set().union(*(references(child) for child in node.requirements))
        if isinstance(node, TemporalRequirement):
            return references(node.requirement)
        return set()

    for node in (*rules.values(), root):
        all_refs.update(references(node))
    missing_refs = all_refs - rules.keys()
    if missing_refs:
        missing = sorted(missing_refs)[0]
        raise RequirementGraphError(f"references undefined rule {missing!r}",
                                    path="$.rules", code="undefined_rule")
    for rule_id, node in rules.items():
        rule_refs[rule_id] = references(node)

    visiting: list[str] = []
    visited: set[str] = set()

    def visit(rule_id: str) -> None:
        if rule_id in visiting:
            cycle = " -> ".join((*visiting, rule_id))
            raise RequirementGraphError(f"cyclic rule reference: {cycle}",
                                        path=f"$.rules[{rule_id!r}]", code="cycle")
        if rule_id in visited:
            return
        visiting.append(rule_id)
        for child in sorted(rule_refs[rule_id]):
            visit(child)
        visiting.pop()
        visited.add(rule_id)

    for rule_id in sorted(rules):
        visit(rule_id)
    return RequirementGraph._from_parsed(graph_id, root, rules)


class _DuplicateKeyError(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate object key {key!r}")
        result[key] = value
    return result
