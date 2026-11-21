"""Evidence-version-aware partial replanning (W07-07).

A plan is a list of steps, each resting on exact evidence versions and on the
steps before it. When evidence changes, only the steps that used it, and the
steps that depend on those, are planned again; everything else is kept as it
was. :func:`full_replan` is the comparator that redoes every step.
"""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    action: str
    evidence: frozenset[tuple[str, int]]
    after: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReplanResult:
    plan: tuple[PlanStep, ...]
    redone: tuple[str, ...]
    kept: tuple[str, ...]


def affected_steps(plan: Sequence[PlanStep], changed: Iterable[str]) -> set[str]:
    """Steps whose evidence changed, closed over the steps that depend on them."""
    changed = set(changed)
    ids = [step.step_id for step in plan]
    if len(ids) != len(set(ids)):
        raise ValueError("step ids must be unique")
    known = set(ids)
    for step in plan:
        if any(dep not in known for dep in step.after):
            raise ValueError(f"step {step.step_id} depends on an unknown step")
    hit = {step.step_id for step in plan
           if any(memory_id in changed for memory_id, _ in step.evidence)}
    grew = True
    while grew:
        grew = False
        for step in plan:
            if step.step_id not in hit and any(dep in hit for dep in step.after):
                hit.add(step.step_id)
                grew = True
    return hit


def partial_replan(plan: Sequence[PlanStep], changed: Iterable[str],
                   redo: Callable[[PlanStep], PlanStep]) -> ReplanResult:
    affected = affected_steps(plan, changed)
    new_plan, redone, kept = [], [], []
    for step in plan:
        if step.step_id in affected:
            fresh = redo(step)
            if fresh.step_id != step.step_id:
                raise ValueError("a re-planned step keeps its id")
            new_plan.append(fresh)
            redone.append(step.step_id)
        else:
            new_plan.append(step)
            kept.append(step.step_id)
    return ReplanResult(tuple(new_plan), tuple(redone), tuple(kept))


def full_replan(plan: Sequence[PlanStep], redo: Callable[[PlanStep], PlanStep]) -> ReplanResult:
    fresh = tuple(redo(step) for step in plan)
    return ReplanResult(fresh, tuple(step.step_id for step in plan), ())
