"""Validated immutable evidence interventions for disposable replay."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import asdict, dataclass
import math
from typing import Any

from .state import Observation
from .types import BeliefReference, InvalidIntervention, digest_json


@dataclass(frozen=True)
class ReplacementFixture:
    """Schema-validated immutable replacement with explicit local provenance."""
    fixture_id: str
    observation: Observation
    provenance: str = "frozen_local_fixture"

    def __post_init__(self) -> None:
        if (not isinstance(self.fixture_id, str) or not self.fixture_id.strip()
                or type(self.observation) is not Observation
                or self.provenance != "frozen_local_fixture"):
            raise InvalidIntervention("replacement fixture is invalid or unlabelled")

    def to_dict(self) -> dict[str, Any]:
        return {"fixture_id": self.fixture_id, "observation": asdict(self.observation),
                "provenance": self.provenance}


@dataclass(frozen=True)
class Intervention:
    target: BeliefReference | None
    operation: str
    replacement: Any = None
    delay_until: int | None = None
    policy_id: str | None = None
    window_start: int | None = None
    window_end: int | None = None
    sensitivity: SensitivityFixture | None = None
    intervention_id: str = ""


@dataclass(frozen=True)
class InterventionBatch:
    """Prevalidated independent overlay operations for one hypothetical run."""
    interventions: tuple[Intervention, ...]
    intervention_id: str


@dataclass(frozen=True)
class SensitivityFixture:
    """Frozen CPT edit, explicitly distinct from changing observed evidence."""
    fixture_id: str
    node_name: str
    parent_assignment: tuple[bool, ...]
    probability_true: float
    provenance: str = "frozen_local_fixture"

    def __post_init__(self) -> None:
        if (not isinstance(self.fixture_id, str) or not self.fixture_id
                or not isinstance(self.node_name, str) or not self.node_name
                or type(self.parent_assignment) is not tuple
                or any(type(value) is not bool for value in self.parent_assignment)
                or type(self.probability_true) not in (int, float)
                or not math.isfinite(self.probability_true)
                or not 0 <= self.probability_true <= 1
                or self.provenance != "frozen_local_fixture"):
            raise InvalidIntervention("sensitivity fixture is malformed or unlabelled")

    def to_dict(self) -> dict[str, Any]:
        return {"fixture_id": self.fixture_id, "node_name": self.node_name,
            "parent_assignment": self.parent_assignment,
            "probability_true": self.probability_true, "provenance": self.provenance}


def create(target: BeliefReference | None, operation: str, *, replacement: Any = None,
           delay_until: int | None = None, policy_id: str | None = None,
           window_start: int | None = None,
           window_end: int | None = None,
           sensitivity: SensitivityFixture | None = None) -> Intervention:
    if operation not in {"noop", "suppress", "replace", "delay", "withhold",
                         "swap_policy", "sensitivity"}:
        raise InvalidIntervention("unsupported intervention")
    if operation == "noop" and any(x is not None for x in (target, replacement, delay_until, policy_id)):
        raise InvalidIntervention("noop has no target or parameters")
    if operation in {"suppress", "replace", "delay", "withhold"} and target is None:
        raise InvalidIntervention("evidence intervention requires a target")
    if operation == "replace":
        if (target is None or type(replacement) is not ReplacementFixture
                or replacement.observation.observation_id != target.belief_id):
            raise InvalidIntervention("replacement must be a labelled fixture for the target")
    elif replacement is not None:
        raise InvalidIntervention("replacement payload is only valid for replace")
    if operation == "delay" and (type(delay_until) is not int or delay_until < 0):
        raise InvalidIntervention("delay_until must be a non-negative sequence")
    if operation == "withhold":
        if (type(window_start) is not int or type(window_end) is not int
                or window_start < 0 or window_end < window_start):
            raise InvalidIntervention("withhold requires a valid inclusive sequence interval")
    elif window_start is not None or window_end is not None:
        raise InvalidIntervention("time window is only valid for withhold")
    if operation == "swap_policy" and (not policy_id or target is not None):
        raise InvalidIntervention("policy intervention requires only a policy id")
    if operation == "sensitivity":
        if target is not None or type(sensitivity) is not SensitivityFixture:
            raise InvalidIntervention("sensitivity requires only a frozen model fixture")
    elif sensitivity is not None:
        raise InvalidIntervention("sensitivity fixture is only valid for sensitivity")
    if operation != "swap_policy" and policy_id is not None:
        raise InvalidIntervention("policy id is only valid for swap_policy")
    return Intervention(target, operation, replacement, delay_until, policy_id,
                        window_start, window_end, sensitivity,
                        digest_json({"op": operation,
                                     "target": target.belief_id if target else None,
                                     "replacement": replacement.to_dict() if replacement else None,
                                     "delay": delay_until,
                                     "policy": policy_id,
                                     "window_start": window_start,
                                     "window_end": window_end,
                                     "sensitivity": sensitivity.to_dict()
                                         if sensitivity else None}))


def compose(interventions: tuple[Intervention, ...]) -> InterventionBatch:
    """Reject ambiguous overlaps before any simulator or replay work begins."""
    if (type(interventions) is not tuple or not interventions
            or any(type(item) is not Intervention for item in interventions)):
        raise InvalidIntervention("a batch requires a non-empty tuple of typed interventions")
    if any(item.operation == "noop" for item in interventions) and len(interventions) > 1:
        raise InvalidIntervention("noop cannot be composed with another intervention")
    seen_targets: set[str] = set()
    policy_swaps = 0
    for item in interventions:
        if item.operation == "sensitivity":
            if len(interventions) > 1:
                raise InvalidIntervention("model sensitivity must run alone, not in a mixed batch")
        replacement = (item.replacement.to_dict()
                       if type(item.replacement) is ReplacementFixture else item.replacement)
        expected_id = digest_json({"op": item.operation,
            "target": item.target.belief_id if item.target else None,
            "replacement": replacement, "delay": item.delay_until,
            "policy": item.policy_id, "window_start": item.window_start,
            "window_end": item.window_end,
            "sensitivity": item.sensitivity.to_dict() if item.sensitivity else None})
        if item.intervention_id != expected_id:
            raise InvalidIntervention("batch contains an intervention with an invalid digest")
        if item.operation == "swap_policy":
            policy_swaps += 1
            continue
        if item.target is None:
            continue
        target_id = item.target.belief_id
        if target_id in seen_targets:
            raise InvalidIntervention("overlapping interventions target the same evidence")
        seen_targets.add(target_id)
    if policy_swaps > 1:
        raise InvalidIntervention("multiple policy swaps have ambiguous ordering")
    digest = digest_json({"interventions": [item.intervention_id for item in interventions]})
    return InterventionBatch(interventions, digest)


def apply(evidence: tuple[BeliefReference, ...], intervention: Intervention
          ) -> tuple[BeliefReference, ...]:
    """Return references visible to the hypothetical run; never mutates source data."""
    if intervention.operation == "noop":
        return evidence
    if intervention.operation == "suppress":
        if not any(r == intervention.target for r in evidence):
            raise InvalidIntervention("target is not in captured evidence")
        return tuple(r for r in evidence if r != intervention.target)
    if intervention.operation == "delay":
        if not any(r == intervention.target for r in evidence):
            raise InvalidIntervention("target is not in captured evidence")
        return evidence
    if intervention.operation == "withhold":
        raise InvalidIntervention("withhold requires observation sequence and authorized capture")
    if intervention.operation == "sensitivity":
        raise InvalidIntervention("sensitivity changes the model, not evidence references")
    if intervention.operation == "replace":
        target = intervention.target
        if target is None or not any(r == target for r in evidence):
            raise InvalidIntervention("target is not in captured evidence")
        # Replacement lives in the overlay, represented by a content digest;
        # it does not create a Memory or event in the real fabric.
        replacement_ref = BeliefReference(
            "cf:" + intervention.intervention_id[:32], 1,
            target.tenant_id,
                         digest_json({"intervention": intervention.intervention_id,
                         "replacement": intervention.replacement.to_dict()}))
        return tuple(replacement_ref if r == target else r for r in evidence)
    return evidence
