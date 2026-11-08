"""Exact enumeration for small, finite Bayesian networks (stdlib only)."""

from __future__ import annotations

__stability__ = "experimental"

import itertools
import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from .types import CDMError


@dataclass(frozen=True)
class BinaryNode:
    """P(node=True | parents assignment), where keys are parent bit tuples."""
    name: str
    parents: tuple[str, ...]
    probability_true: Mapping[tuple[bool, ...], float]

    def __post_init__(self) -> None:
        if (not isinstance(self.name, str) or not self.name
                or type(self.parents) is not tuple
                or type(self.probability_true) is not dict):
            raise CDMError("binary node requires plain data fields")
        if any(type(parent) is not str or not parent for parent in self.parents):
            raise CDMError("parent names must be non-empty strings")
        expected = set(itertools.product((False, True), repeat=len(self.parents)))
        if set(self.probability_true) != expected:
            raise CDMError(f"{self.name}: CPT must cover every parent assignment")
        if any(not math.isfinite(p) or not 0 <= p <= 1 for p in self.probability_true.values()):
            raise CDMError(f"{self.name}: CPT probabilities must be finite and in [0,1]")


def enumerate_posterior(nodes: Sequence[BinaryNode], observations: Mapping[str, bool]
                        ) -> dict[tuple[tuple[str, bool], ...], float]:
    names = [n.name for n in nodes]
    if len(set(names)) != len(names):
        raise CDMError("node names must be unique")
    node_by_name = {n.name: n for n in nodes}
    if any(parent not in node_by_name for n in nodes for parent in n.parents):
        raise CDMError("all parents must be declared nodes")
    if set(observations) - set(names) or any(type(v) is not bool for v in observations.values()):
        raise CDMError("observations must map declared nodes to booleans")
    assignments: list[tuple[tuple[tuple[str, bool], ...], float]] = []
    for bits in itertools.product((False, True), repeat=len(nodes)):
        state = dict(zip(names, bits))
        if any(state[k] != v for k, v in observations.items()):
            continue
        probability = 1.0
        for node in nodes:
            p = node.probability_true[tuple(state[pn] for pn in node.parents)]
            probability *= p if state[node.name] else 1 - p
        assignments.append((tuple(sorted(state.items())), probability))
    total = math.fsum(p for _, p in assignments)
    if total <= 0 or not math.isfinite(total):
        raise CDMError("observations have zero or invalid probability")
    return {state: p / total for state, p in assignments}


def marginal(posterior: Mapping[tuple[tuple[str, bool], ...], float], variable: str) -> float:
    value = math.fsum(p for state, p in posterior.items() if dict(state).get(variable) is True)
    if not math.isfinite(value) or value < -1e-12 or value > 1 + 1e-12:
        raise CDMError("marginal escaped probability bounds")
    return min(1.0, max(0.0, value))


def independent_binary_oracle(prior: float, likelihood_true: Sequence[float],
                              observations: Sequence[bool]) -> float:
    """Distinct direct likelihood product used as a small independent test oracle."""
    if len(likelihood_true) != len(observations) or not 0 < prior < 1:
        raise CDMError("oracle inputs do not align")
    t, f = prior, 1 - prior
    for likelihood, observed in zip(likelihood_true, observations):
        if not 0 <= likelihood <= 1:
            raise CDMError("likelihood must be in [0,1]")
        t *= likelihood if observed else 1 - likelihood
        f *= (1 - likelihood) if observed else likelihood
    if t + f == 0:
        raise CDMError("impossible evidence")
    return t / (t + f)


def sensitivity_sweep(nodes: Sequence[BinaryNode], *, node_name: str,
                      parent_assignment: tuple[bool, ...], probabilities: Sequence[float],
                      observations: Mapping[str, bool], query: str) -> tuple[float, ...]:
    """Recompute a query marginal across declared CPT values; no hidden tuning."""
    by_name = {node.name: node for node in nodes}
    if node_name not in by_name or query not in by_name:
        raise CDMError("sensitivity sweep names must refer to declared nodes")
    original = by_name[node_name]
    if len(parent_assignment) != len(original.parents):
        raise CDMError("sensitivity parent assignment does not match the CPT")
    results = []
    for probability in probabilities:
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise CDMError("sensitivity probability must be finite and in [0,1]")
        cpt = dict(original.probability_true)
        cpt[parent_assignment] = float(probability)
        changed = tuple(BinaryNode(node.name, node.parents,
            cpt if node.name == node_name else dict(node.probability_true)) for node in nodes)
        results.append(marginal(enumerate_posterior(changed, observations), query))
    return tuple(results)
