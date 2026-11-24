"""Dependence-first counterfactual dispatch and its utility ledger (W09-01, W09-09, W07-05).

Counterfactual replay is expensive, so it is the last rung, not the first. For
each recorded decision, :func:`dispatch` decides with an explicit reason:

``non_replayable``                 the trace is incomplete; nothing is filled in
``skip_independent``               no evidence the decision used has changed
``skip_no_material_alternative``   the decision had no other admissible choice
``resolved_by_alternate_source``   a current exact source already answers it
``skip_budget``                    the replay budget is spent
``replayed``                       the replay callback ran once

The callback runs only for ``replayed`` rows, so independent decisions cost
nothing: no replay and no model call. Everything this module returns is
advisory. A :class:`DispatchReport` carries no grant, no certificate and no
proposal commitment; acting on a flipped decision goes through the ordinary
re-plan, verification and action gate like any other proposal.

:func:`utility_ledger` keeps four quantities apart: how many decisions would
flip, the observed completion difference, the observed safety difference, and
the replay cost. A flip alone earns nothing; net utility comes only from
observed differences, minus cost.
"""

from __future__ import annotations

__stability__ = "experimental"

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

NON_REPLAYABLE = "non_replayable"
SKIP_INDEPENDENT = "skip_independent"
SKIP_NO_ALTERNATIVE = "skip_no_material_alternative"
RESOLVED_BY_ALTERNATE_SOURCE = "resolved_by_alternate_source"
SKIP_BUDGET = "skip_budget"
REPLAYED = "replayed"
REASONS = (NON_REPLAYABLE, SKIP_INDEPENDENT, SKIP_NO_ALTERNATIVE, RESOLVED_BY_ALTERNATE_SOURCE,
           SKIP_BUDGET, REPLAYED)


@dataclass(frozen=True)
class DecisionRecord:
    """One past decision: what it chose, from which evidence, among which options."""

    decision_id: str
    chosen: str
    evidence: frozenset[tuple[str, int]]
    alternatives: tuple[str, ...]
    trace_complete: bool = True

    def depends_on(self, changed: Iterable[str]) -> bool:
        changed = set(changed)
        return any(memory_id in changed for memory_id, _ in self.evidence)


@dataclass(frozen=True)
class DispatchRow:
    decision_id: str
    reason: str
    original: str
    replayed: str | None = None
    seconds: float = 0.0

    @property
    def flipped(self) -> bool:
        return self.replayed is not None and self.replayed != self.original


@dataclass(frozen=True)
class DispatchReport:
    rows: tuple[DispatchRow, ...]
    replays: int
    replay_seconds: float
    advisory: bool = True
    authorizes_effects: bool = False
    counts: Mapping[str, int] = field(default_factory=dict)

    @property
    def flips(self) -> int:
        return sum(1 for row in self.rows if row.flipped)

    def to_dict(self) -> dict[str, Any]:
        return {"advisory": self.advisory, "authorizes_effects": self.authorizes_effects,
                "replays": self.replays, "replay_seconds": round(self.replay_seconds, 6),
                "flips": self.flips, "counts": dict(self.counts),
                "rows": [{"decision_id": r.decision_id, "reason": r.reason,
                          "original": r.original, "replayed": r.replayed,
                          "flipped": r.flipped} for r in self.rows]}


def dispatch(decisions: Sequence[DecisionRecord], changed: Iterable[str],
             replay: Callable[[DecisionRecord], str], *, budget: int = 1,
             alternate_source: Callable[[DecisionRecord], str | None] | None = None,
             clock: Callable[[], float] = time.perf_counter) -> DispatchReport:
    """Replay only decisions that depend on changed evidence and could have gone otherwise."""
    if budget < 0:
        raise ValueError("replay budget must be non-negative")
    changed = frozenset(changed)
    rows: list[DispatchRow] = []
    replays, seconds = 0, 0.0
    for decision in decisions:
        if not decision.trace_complete:
            rows.append(DispatchRow(decision.decision_id, NON_REPLAYABLE, decision.chosen))
            continue
        if not decision.depends_on(changed):
            rows.append(DispatchRow(decision.decision_id, SKIP_INDEPENDENT, decision.chosen))
            continue
        if len(set(decision.alternatives) | {decision.chosen}) < 2:
            rows.append(DispatchRow(decision.decision_id, SKIP_NO_ALTERNATIVE, decision.chosen))
            continue
        if alternate_source is not None:
            answer = alternate_source(decision)
            if answer is not None:
                # The cheap rung: a current exact source settles it without replay.
                rows.append(DispatchRow(decision.decision_id, RESOLVED_BY_ALTERNATE_SOURCE,
                                        decision.chosen, replayed=answer))
                continue
        if replays >= budget:
            rows.append(DispatchRow(decision.decision_id, SKIP_BUDGET, decision.chosen))
            continue
        started = clock()
        answer = replay(decision)
        took = clock() - started
        replays, seconds = replays + 1, seconds + took
        rows.append(DispatchRow(decision.decision_id, REPLAYED, decision.chosen,
                                replayed=answer, seconds=took))
    counts = {reason: sum(1 for row in rows if row.reason == reason) for reason in REASONS}
    return DispatchReport(tuple(rows), replays, seconds, counts=counts)


def always_on(decisions: Sequence[DecisionRecord], replay: Callable[[DecisionRecord], str],
              clock: Callable[[], float] = time.perf_counter) -> DispatchReport:
    """The comparator: replay every replayable decision, dependent or not."""
    rows: list[DispatchRow] = []
    replays, seconds = 0, 0.0
    for decision in decisions:
        if not decision.trace_complete:
            rows.append(DispatchRow(decision.decision_id, NON_REPLAYABLE, decision.chosen))
            continue
        started = clock()
        answer = replay(decision)
        took = clock() - started
        replays, seconds = replays + 1, seconds + took
        rows.append(DispatchRow(decision.decision_id, REPLAYED, decision.chosen,
                                replayed=answer, seconds=took))
    counts = {reason: sum(1 for row in rows if row.reason == reason) for reason in REASONS}
    return DispatchReport(tuple(rows), replays, seconds, counts=counts)


def utility_ledger(*, policy_flips: int, completion_difference: float,
                   safety_difference: float, replays: int, cost_per_replay: float = 0.01,
                   unsafe_weight: float = 1.0) -> dict[str, Any]:
    """Separate flips, observed outcome differences and cost; flips never add utility.

    ``completion_difference`` and ``safety_difference`` are observed paired
    differences against the arm without replay (safety: increase in unsafe
    rate, so positive is worse).
    """
    net = completion_difference - unsafe_weight * safety_difference - cost_per_replay * replays
    return {"policy_flips": policy_flips, "completion_difference": completion_difference,
            "safety_difference": safety_difference, "replays": replays,
            "cost_per_replay": cost_per_replay, "replay_cost": round(cost_per_replay * replays, 6),
            "net_utility": round(net, 6),
            "promotable": net > 0 and completion_difference > 0 and safety_difference <= 0,
            "note": "policy flips are reported, never credited"}
