"""Small standard-library reporting primitives for outcome experiments."""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from typing import Any, Iterable

from memory_fabric.agent_outcomes import EpisodeOutcome


def zero_event_upper_bound(events: int, trials: int, confidence: float = 0.95) -> float:
    """One-sided exact binomial upper bound; for zero events use 1-(1-CI)^(1/n)."""
    if trials <= 0 or events < 0 or events > trials or not 0 < confidence < 1:
        raise ValueError("require trials > 0, 0 <= events <= trials, and 0 < confidence < 1")
    if events == 0:
        return 1.0 - (1.0 - confidence) ** (1.0 / trials)
    # Invert P_p(X <= events) = 1-confidence by bounded bisection.
    target = 1.0 - confidence

    def lower_tail(probability: float) -> float:
        terms = [math.comb(trials, k) * probability**k * (1 - probability)**(trials-k)
                 for k in range(events + 1)]
        return min(1.0, sum(terms))

    low, high = 0.0, 1.0
    for _ in range(80):
        mid = (low + high) / 2
        if lower_tail(mid) > target:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def report_rows(outcomes: Iterable[EpisodeOutcome]) -> list[dict[str, Any]]:
    """Return stable per-case rows; evaluator digest is opaque and no hidden labels are emitted."""
    rows = [asdict(item) for item in outcomes]
    rows.sort(key=lambda row: (row["seed"], row["task_id"], row["arm"]))
    return rows


def canonical_report(outcomes: Iterable[EpisodeOutcome]) -> str:
    return json.dumps({"schema_id": "memory-fabric.outcome-report.v3",
                       "population": "SCRIPTED_AGENT", "rows": report_rows(outcomes)},
                      sort_keys=True, separators=(",", ":"), allow_nan=False)
