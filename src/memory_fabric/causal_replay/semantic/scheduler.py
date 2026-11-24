"""Which decisions to replay under a budget, and when the model is worth asking (VEGA S08).

Order of work for each candidate decision (VEGA-CDM-082, 084, 085, 086):

1. **Dependence filter.** A decision that did not depend on the changed evidence
   is skipped with a receipt; neither the model nor CDM is called.
2. **Deterministic rules.** An exactly-dependent decision with one changed input is
   settled without a model (``exact_path``).
3. **Advisor** only for what is still ambiguous. Its answer feeds an *expected value
   of information*: ``p_flip * value_of_flip - replay_cost``. Below the registered
   minimum, the case short-circuits to the deterministic policy.
4. **Uncertain answers** (abstain, unbound, a conformal set over one option, or an
   unavailable advisor) route to ``review`` or ``new_observation``, never to an
   automatic replay.

Selectors are compared with identical candidate sets and replay budgets:
:data:`SELECTORS` covers dependence-only, random, recency, cost-only and
advisor-assisted (083). :func:`score_selection` reports precision, recall at
budget, regret and wasted replays against an oracle set of decisions whose
replay really changes the outcome (089, 090). The actor's model budget and the
replay worker's budget are counted separately (088).
"""

from __future__ import annotations

__stability__ = "experimental"

import random
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence

from .advice import Answer


@dataclass(frozen=True)
class ReplayCandidate:
    decision_id: str
    depends_on_changed: bool
    changed_inputs: int
    recency: int
    replay_cost: float
    value_of_flip: float = 1.0


@dataclass
class Accounts:
    """Separate meters: model calls belong to the actor, replays to the replay worker."""
    model_calls: int = 0
    model_seconds: float = 0.0
    replays: int = 0
    replay_cost: float = 0.0
    receipts: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class Routing:
    decision_id: str
    route: str  # skip_independent | exact_path | replay | short_circuit | review | new_observation
    evoi: float | None
    reason: str


def route(candidate: ReplayCandidate, answer: Answer | None, *, min_evoi: float = 0.05
          ) -> Routing:
    if not candidate.depends_on_changed:
        return Routing(candidate.decision_id, "skip_independent", None, "no dependence on changed evidence")
    if candidate.changed_inputs == 1 and answer is None:
        return Routing(candidate.decision_id, "exact_path", None, "one exact changed input: deterministic replay")
    if answer is None or answer.status in ("UNAVAILABLE", "INVALID"):
        return Routing(candidate.decision_id, "review", None, "advisor unavailable: no automatic replay")
    if answer.status == "ABSTAIN" or answer.unbound:
        return Routing(candidate.decision_id, "new_observation", None, "advisor abstained or is off-distribution")
    if answer.prediction_set and len(answer.prediction_set) > 1:
        return Routing(candidate.decision_id, "review", None, "conformal set is ambiguous")
    p_flip = float(answer.probs.get("true", 0.0)) if answer.kind == "boolean" else 0.0
    evoi = p_flip * candidate.value_of_flip - candidate.replay_cost
    if evoi < min_evoi:
        return Routing(candidate.decision_id, "short_circuit", round(evoi, 4), "value of information below minimum")
    return Routing(candidate.decision_id, "replay", round(evoi, 4), "expected value of replay above minimum")


Selector = Callable[[Sequence[ReplayCandidate], int], list[str]]


def _dependence(cands: Sequence[ReplayCandidate], k: int) -> list[str]:
    return [c.decision_id for c in cands if c.depends_on_changed][:k]


def _random(seed: int) -> Selector:
    def pick(cands: Sequence[ReplayCandidate], k: int) -> list[str]:
        ids = [c.decision_id for c in cands]
        random.Random(seed).shuffle(ids)
        return ids[:k]
    return pick


def _recency(cands: Sequence[ReplayCandidate], k: int) -> list[str]:
    return [c.decision_id for c in sorted(cands, key=lambda c: -c.recency)][:k]


def _cost(cands: Sequence[ReplayCandidate], k: int) -> list[str]:
    return [c.decision_id for c in sorted(cands, key=lambda c: (c.replay_cost, c.decision_id))][:k]


def advisor_selector(scores: Mapping[str, float]) -> Selector:
    """Dependence filter first, then the advisor's flip probability, highest first."""
    def pick(cands: Sequence[ReplayCandidate], k: int) -> list[str]:
        dependent = [c for c in cands if c.depends_on_changed]
        return [c.decision_id for c in sorted(dependent, key=lambda c: (-scores.get(c.decision_id, 0.0),
                                                                         c.decision_id))][:k]
    return pick


SELECTORS: dict[str, Selector] = {"dependence": _dependence, "random": _random(0),
                                  "recency": _recency, "cost_only": _cost}


def score_selection(selected: Iterable[str], pivotal: Iterable[str], *, budget: int,
                    cost: Mapping[str, float]) -> dict[str, object]:
    chosen, truth = list(selected), set(pivotal)
    hits = [d for d in chosen if d in truth]
    best = min(budget, len(truth))
    return {"selected": len(chosen), "pivotal": len(truth),
            "precision": round(len(hits) / len(chosen), 4) if chosen else None,
            "recall_at_budget": round(len(hits) / best, 4) if best else None,
            "regret": best - len(hits), "wasted_replays": len(chosen) - len(hits),
            "wasted_cost": round(sum(cost.get(d, 0.0) for d in chosen if d not in truth), 4)}
