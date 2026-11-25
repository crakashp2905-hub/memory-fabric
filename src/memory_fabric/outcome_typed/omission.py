"""Omission safety: a host hazard policy that inaction must satisfy (VEGA next W05).

``ActionGate`` decides whether an *executed* effect is authorized. It has nothing to
say about a decision to do nothing, and the development run showed that is where the
harm was: two ``no_action`` decisions on really hot packs. This module adds the missing
boundary without touching ``ActionGate``, permissions or grants.

A :class:`HazardPolicy` names the property, the threshold predicate, the sensors whose
readings are required and the actions that count as inaction. :func:`assess` reads only
verified findings (:mod:`..causal_replay.semantic.verified_observations`), never a model
answer, and returns:

``VERIFIED_HAZARD``  a required sensor verifiably meets the hazard predicate;
``VERIFIED_CLEAR``   every required sensor has a current, verified negative reading;
``CONTESTED``        verified readings disagree across sensors;
``UNRESOLVED``       anything else (missing, unreadable, disputed, straddling).

:func:`guard` lets an inaction close a task only on ``VERIFIED_CLEAR``. Otherwise the
proposal is replaced by ``REQUEST_MEASUREMENT`` or ``REVIEW_REQUIRED`` with a bounded
retry count (W05-02, 03, 05). Kinds of non-action are kept apart: ``no_action`` (a
decision that nothing is needed), ``abstain`` (an explicit escalation),
``missing_response`` (no decision at all, e.g. a timeout) (W05-08). A model answer
cannot lower a verified hazard because :func:`assess` never reads one (W05-04).
"""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass, field
from typing import Any, Sequence

ACTION_KINDS = ("intervention", "no_action", "abstain", "missing_response")
ASSESSMENTS = ("VERIFIED_HAZARD", "VERIFIED_CLEAR", "CONTESTED", "UNRESOLVED")


@dataclass(frozen=True)
class HazardPolicy:
    name: str
    required_sensors: tuple[str, ...]
    inaction: frozenset[str] = frozenset({"no_action", "do_nothing"})
    escalation: frozenset[str] = frozenset({"abstain", "escalate"})
    response: frozenset[str] = frozenset()
    """Interventions that discharge a verified hazard. Under ``VERIFIED_HAZARD`` any other
    intervention is a missed required response and is escalated (W05-06). Empty means the
    host registered none, and interventions are not checked."""
    max_measurement_requests: int = 2
    severity: str = "high"


@dataclass(frozen=True)
class Assessment:
    status: str
    sensors: dict[str, str] = field(default_factory=dict)
    next_step: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class GuardResult:
    proposed: str
    kind: str
    allowed: bool
    replacement: str | None
    reason: str
    assessment: str


def classify(action: str | None, policy: HazardPolicy) -> str:
    if action is None or action == "missing_response":
        return "missing_response"
    if action in policy.inaction:
        return "no_action"
    if action in policy.escalation:
        return "abstain"
    return "intervention"


def assess(verification: Any, policy: HazardPolicy) -> Assessment:
    findings = verification.findings
    states = {}
    for sensor in policy.required_sensors:
        f = findings.get(sensor)
        states[sensor] = f"{f.status}:{f.value}" if f else "UNKNOWN:UNKNOWN"
    verified = {s: v.split(":")[1] for s, v in states.items() if v.startswith("VERIFIED")}
    if "TRUE" in verified.values() and "FALSE" in verified.values():
        return Assessment("CONTESTED", states, "REVIEW_REQUIRED", "verified sensors disagree")
    if "TRUE" in verified.values():
        return Assessment("VERIFIED_HAZARD", states, None, "a required sensor verifiably meets the hazard")
    if len(verified) == len(policy.required_sensors) and set(verified.values()) == {"FALSE"}:
        return Assessment("VERIFIED_CLEAR", states, None, "every required sensor has a verified negative")
    disputed = any(v.startswith("DISPUTED") for v in states.values())
    return Assessment("UNRESOLVED", states, "REVIEW_REQUIRED" if disputed else "REQUEST_MEASUREMENT",
                      "required readings are missing, unreadable or disputed")


def guard(action: str | None, assessment: Assessment, policy: HazardPolicy, *,
          measurement_requests: int = 0) -> GuardResult:
    """Inaction closes a task only on a verified clear; everything else is unchanged."""
    kind = classify(action, policy)
    if kind == "abstain":
        return GuardResult(str(action), kind, True, None, "explicit escalation", assessment.status)
    if kind == "intervention":
        if assessment.status == "VERIFIED_HAZARD" and policy.response and action not in policy.response:
            return GuardResult(str(action), kind, False, "REVIEW_REQUIRED",
                               f"{action} does not discharge the verified hazard", assessment.status)
        return GuardResult(str(action), kind, True, None, "intervention", assessment.status)
    if assessment.status == "VERIFIED_CLEAR" and kind == "no_action":
        return GuardResult(str(action), kind, True, None, "verified clear", assessment.status)
    if assessment.status in ("UNRESOLVED",) and measurement_requests < policy.max_measurement_requests \
            and assessment.next_step == "REQUEST_MEASUREMENT":
        replacement = "REQUEST_MEASUREMENT"
    else:
        replacement = "REVIEW_REQUIRED"
    return GuardResult(str(action), kind, False, replacement,
                       f"{kind} is not safe under {assessment.status}", assessment.status)


def terminal_action(guarded: GuardResult) -> str:
    """The action the episode ends with: a blocked inaction becomes an explicit escalation."""
    return guarded.proposed if guarded.allowed else "abstain"


def coverage_bound(unsafe: int, cases: int, confidence: float = 0.95) -> dict[str, Any]:
    """Exact one-sided upper bound on the unsafe rate; zero events is never zero risk (W05-10)."""
    if cases <= 0:
        return {"cases": 0, "bound": None, "statement": "no cases: nothing is known"}
    if unsafe == 0:
        bound = 1 - (1 - confidence) ** (1 / cases)
    else:  # Clopper-Pearson upper limit by bisection on the binomial tail
        lo, hi = unsafe / cases, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            tail = sum(_binom(cases, k) * mid ** k * (1 - mid) ** (cases - k) for k in range(unsafe + 1))
            lo, hi = (mid, hi) if tail > 1 - confidence else (lo, mid)
        bound = hi
    return {"cases": cases, "unsafe": unsafe, "confidence": confidence, "upper_bound": round(bound, 4),
            "statement": f"{unsafe} unsafe in {cases}: the rate is below {round(bound, 4)} at "
                         f"{int(confidence * 100)}% confidence, not zero"}


def _binom(n: int, k: int) -> float:
    from math import comb
    return float(comb(n, k))


def required_for(registry_sensors: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(registry_sensors))


def explain(result: GuardResult, assessment: Assessment) -> dict[str, Any]:
    """What an operator sees: reason, sensors in scope, next permitted step, terminal action.

    Built from statuses and sensor ids only, so it carries no evidence text (VEGA next W16-03).
    """
    terminal = terminal_action(result)
    next_step = None if result.allowed else (result.replacement or assessment.next_step)
    return {"decision": "ALLOWED" if result.allowed else "BLOCKED", "proposed": result.proposed,
            "action_kind": result.kind, "terminal_action": terminal,
            "assessment": assessment.status, "sensors": dict(assessment.sensors),
            "reason": result.reason if not result.allowed else assessment.reason,
            "next_permitted_step": next_step,
            "uncertainty": "readings disagree" if assessment.status == "CONTESTED" else
            ("required readings missing or unreadable" if assessment.status == "UNRESOLVED" else None)}
