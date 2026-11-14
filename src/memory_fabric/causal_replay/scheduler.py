"""Deterministic replay candidate scheduling with conservative fallbacks."""

from __future__ import annotations

__stability__ = "experimental"

import random
import math
import time
from dataclasses import dataclass
from typing import Iterable, Mapping

from .types import BudgetExceeded, CDMError


@dataclass(frozen=True)
class ReplayBudget:
    max_events: int = 10_000
    max_attempts: int = 100
    max_wall_seconds: float = 10.0
    max_cpu_seconds: float = 10.0
    max_memory_bytes: int = 64 * 1024 * 1024
    max_nodes: int = 18
    max_tool_calls: int = 0

    def __post_init__(self) -> None:
        for name in ("max_events", "max_attempts", "max_memory_bytes", "max_nodes", "max_tool_calls"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise CDMError(f"{name} must be a non-negative integer")
        if (self.max_events < 1 or self.max_attempts < 1 or self.max_nodes < 1
                or isinstance(self.max_wall_seconds, bool)
                or not isinstance(self.max_wall_seconds, (int, float))
                or not math.isfinite(self.max_wall_seconds) or self.max_wall_seconds <= 0
                or isinstance(self.max_cpu_seconds, bool)
                or not isinstance(self.max_cpu_seconds, (int, float))
                or not math.isfinite(self.max_cpu_seconds) or self.max_cpu_seconds <= 0
                or self.max_tool_calls != 0):
            raise CDMError("invalid replay budget; real tool calls must remain zero")


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    sequence: int
    risk: float
    relevance: float
    uncertainty: float
    neighbors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id or type(self.sequence) is not int or self.sequence < 0:
            raise CDMError("candidate identity and sequence are invalid")
        if any(not 0 <= value <= 1 for value in (self.risk, self.relevance, self.uncertainty)):
            raise CDMError("candidate features must be in [0,1]")


def check_budget(budget: ReplayBudget, *, event_count: int, node_count: int,
                 attempt_count: int, started_monotonic: float,
                 started_process_cpu: float) -> None:
    if event_count > budget.max_events or attempt_count > budget.max_attempts:
        raise BudgetExceeded("replay budget exceeded")
    if node_count > budget.max_nodes:
        raise BudgetExceeded("exact enumeration node budget exceeded")
    # A conservative preflight estimate, not a measured allocation guarantee.
    estimated_bytes = (1 << node_count) * max(64, node_count * 16)
    if estimated_bytes > budget.max_memory_bytes:
        raise BudgetExceeded("estimated exact-enumeration memory exceeds budget")
    if time.monotonic() - started_monotonic > budget.max_wall_seconds:
        raise BudgetExceeded("replay wall-time budget exceeded")
    if time.process_time() - started_process_cpu > budget.max_cpu_seconds:
        raise BudgetExceeded("replay CPU-time budget exceeded")


def earliest_affected_index(event_ids: tuple[str, ...], target_id: str, *,
                            dependencies: Mapping[str, tuple[str, ...]],
                            dependencies_complete: bool) -> int:
    """Find the earliest affected event through direct or derived dependency links.

    The caller supplies the complete dependency closure, including derived
    belief/update events. Unknown graph completeness conservatively means genesis.
    """
    if target_id not in event_ids:
        raise CDMError("intervention target is absent from the trace")
    if not dependencies_complete:
        return 0
    affected = {target_id}
    changed = True
    while changed:
        changed = False
        for event_id in event_ids:
            if event_id not in affected and any(parent in affected
                                                for parent in dependencies.get(event_id, ())):
                affected.add(event_id)
                changed = True
    return min(event_ids.index(event_id) for event_id in affected if event_id in event_ids)


def replay_frontier(event_ids: tuple[str, ...], target_id: str, *,
                    dependencies: Mapping[str, tuple[str, ...]],
                    dependencies_complete: bool) -> tuple[str, ...]:
    start = earliest_affected_index(event_ids, target_id, dependencies=dependencies,
                                    dependencies_complete=dependencies_complete)
    return event_ids[start:]


def dependency_frontier(event_ids: tuple[str, ...], target_id: str, *,
                        dependencies: Mapping[str, tuple[str, ...]],
                        dependencies_complete: bool) -> tuple[str, ...]:
    """Return the target and its transitive dependents in deterministic trace order.

    A complete graph must declare every event, every parent must precede its
    child, and references must be local to the trace. Unknown completeness
    conservatively retains the full trace. This is a selector only; callers
    must still establish that the graph captures all semantic dependencies.
    """
    if type(event_ids) is not tuple or not event_ids or any(
            not isinstance(event_id, str) or not event_id for event_id in event_ids):
        raise CDMError("dependency frontier requires a non-empty ordered event tuple")
    if len(set(event_ids)) != len(event_ids):
        raise CDMError("dependency frontier event IDs must be unique")
    if not isinstance(target_id, str) or not target_id or target_id not in event_ids:
        raise CDMError("dependency frontier target is absent from the trace")
    if type(dependencies_complete) is not bool:
        raise CDMError("dependency completeness must be an explicit boolean")
    if not dependencies_complete:
        return event_ids
    if not isinstance(dependencies, Mapping) or set(dependencies) != set(event_ids):
        raise CDMError("a complete dependency graph must declare every trace event")
    positions = {event_id: index for index, event_id in enumerate(event_ids)}
    dependents: dict[str, list[str]] = {event_id: [] for event_id in event_ids}
    for child, raw_parents in dependencies.items():
        if (type(raw_parents) is not tuple
                or any(not isinstance(parent, str) or not parent for parent in raw_parents)
                or len(set(raw_parents)) != len(raw_parents)):
            raise CDMError("dependency parents must be unique immutable tuples")
        for parent in raw_parents:
            if parent not in positions or positions[parent] >= positions[child]:
                raise CDMError("dependency parent must exist before its child")
            dependents[parent].append(child)
    affected = {target_id}
    frontier = [target_id]
    while frontier:
        current = frontier.pop()
        for child in dependents[current]:
            if child not in affected:
                affected.add(child)
                frontier.append(child)
    return tuple(event_id for event_id in event_ids if event_id in affected)


def select_random(candidates: Iterable[Candidate], *, seed: int, k: int) -> tuple[Candidate, ...]:
    items = tuple(sorted(candidates, key=lambda item: item.candidate_id))
    _validate_k(k, len(items))
    return tuple(random.Random(seed).sample(items, k))


def select_recency(candidates: Iterable[Candidate], *, k: int) -> tuple[Candidate, ...]:
    items = tuple(candidates)
    _validate_k(k, len(items))
    return tuple(sorted(items, key=lambda item: (-item.sequence, item.candidate_id))[:k])


def select_centrality(candidates: Iterable[Candidate], *, k: int) -> tuple[Candidate, ...]:
    items = tuple(candidates)
    _validate_k(k, len(items))
    return tuple(sorted(items, key=lambda item: (-len(item.neighbors), item.candidate_id))[:k])


def select_priority(candidates: Iterable[Candidate], *, k: int) -> tuple[Candidate, ...]:
    """First-party System-1 heuristic over features available before replay."""
    items = tuple(candidates)
    _validate_k(k, len(items))
    def score(item: Candidate) -> float:
        return 0.5 * item.risk + 0.3 * item.relevance + 0.2 * item.uncertainty
    return tuple(sorted(items, key=lambda item: (-score(item), item.candidate_id))[:k])


def branch_recall_at_k(selected: Iterable[Candidate], oracle_pivotal_ids: Iterable[str], *,
                       candidate_count: int) -> float | None:
    """Recall of executed-oracle pivotal branches; None when oracle finds none."""
    if type(candidate_count) is not int or candidate_count < 0:
        raise CDMError("candidate_count must be non-negative")
    selected_ids = {item.candidate_id for item in selected}
    pivotal = set(oracle_pivotal_ids)
    if len(selected_ids) > candidate_count:
        raise CDMError("invalid selected candidate collection")
    return (len(selected_ids & pivotal) / len(pivotal)) if pivotal else None


def _validate_k(k: int, count: int) -> None:
    if type(k) is not int or k < 0 or k > count:
        raise CDMError("selection count exceeds candidate set")
