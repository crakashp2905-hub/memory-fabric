"""Frozen correction-aware review utility scoring contract (CDM-199)."""

from __future__ import annotations

from typing import Iterable

MISSED_DEPENDENT_COST = 10.0
FALSE_REVIEW_COST = 1.0
PER_REVIEW_COST = 0.1
MINIMUM_MEAN_PAIRED_GAIN = 0.1
MINIMUM_CONFIRMATORY_PAIRS = 20
CONFIDENCE_LEVEL = 0.95


def score_review_utility(universe: Iterable[str], depended: Iterable[str],
                         reviewed: Iterable[str]) -> float:
    """Score one scenario per eligible decision; labels are recorded-policy dependence."""
    universe_items = tuple(universe)
    all_ids, truth, selected = set(universe_items), set(depended), set(reviewed)
    if (not all_ids or len(all_ids) != len(universe_items)
            or not truth <= all_ids or not selected <= all_ids):
        raise ValueError("utility inputs must be non-empty unique IDs within the scenario")
    true_positive = len(truth & selected)
    false_negative = len(truth - selected)
    false_positive = len(selected - truth)
    value = (MISSED_DEPENDENT_COST * true_positive
        - MISSED_DEPENDENT_COST * false_negative
        - FALSE_REVIEW_COST * false_positive
        - PER_REVIEW_COST * len(selected)) / len(all_ids)
    return value


def confirmatory_go(*, paired_deltas: tuple[float, ...], lower_confidence_bound: float,
                    missed_dependent_decisions: int,
                    safety_violations: int) -> bool:
    """Apply the frozen threshold; the caller supplies paired bootstrap bound."""
    if (type(paired_deltas) is not tuple or not paired_deltas
            or any(type(value) not in (int, float) for value in paired_deltas)
            or type(lower_confidence_bound) not in (int, float)
            or type(missed_dependent_decisions) is not int or missed_dependent_decisions < 0
            or type(safety_violations) is not int or safety_violations < 0):
        raise ValueError("invalid confirmatory utility inputs")
    mean_delta = sum(paired_deltas) / len(paired_deltas)
    return (len(paired_deltas) >= MINIMUM_CONFIRMATORY_PAIRS
            and mean_delta >= MINIMUM_MEAN_PAIRED_GAIN
            and lower_confidence_bound > 0
            and missed_dependent_decisions == 0 and safety_violations == 0)
