"""Order-independent seeded treatment and observation assignment records."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class InterventionRecord:
    unit_id: str
    seed: int
    probability_treated: float
    treated: bool
    assignment_propensity: float
    probability_observed: float
    observed: bool


class RandomizedInterventionHarness:
    """Derive deterministic, domain-separated draws for each named unit."""

    def __init__(self, seed: int) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("seed must be a non-negative integer")
        self.seed = seed

    def _uniform(self, stream: str, unit_id: str) -> float:
        payload = json.dumps(
            ["memory-fabric-intervention-harness/1", self.seed, stream, unit_id],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
        return integer / 2**64

    @staticmethod
    def _probability(value: float, name: str, *, allow_boundary: bool) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be numeric")
        probability = float(value)
        if not math.isfinite(probability):
            raise ValueError(f"{name} must be finite")
        lower_ok = probability >= 0.0 if allow_boundary else probability > 0.0
        upper_ok = probability <= 1.0 if allow_boundary else probability < 1.0
        if not lower_ok or not upper_ok:
            bounds = "between 0 and 1 inclusive" if allow_boundary else "strictly between 0 and 1"
            raise ValueError(f"{name} must be {bounds}")
        return probability

    def assign_and_observe(
        self,
        unit_id: str,
        *,
        probability_treated: float,
        probability_observed_treated: float,
        probability_observed_control: float,
    ) -> InterventionRecord:
        if not isinstance(unit_id, str) or not unit_id:
            raise ValueError("unit_id must be a non-empty string")
        treatment_probability = self._probability(
            probability_treated, "probability_treated", allow_boundary=False
        )
        observed_treatment_probability = self._probability(
            probability_observed_treated,
            "probability_observed_treated",
            allow_boundary=True,
        )
        observed_control_probability = self._probability(
            probability_observed_control,
            "probability_observed_control",
            allow_boundary=True,
        )
        treated = self._uniform("treatment", unit_id) < treatment_probability
        observation_probability = (
            observed_treatment_probability if treated else observed_control_probability
        )
        observed = self._uniform("observation", unit_id) < observation_probability
        return InterventionRecord(
            unit_id=unit_id,
            seed=self.seed,
            probability_treated=treatment_probability,
            treated=treated,
            assignment_propensity=(
                treatment_probability if treated else 1.0 - treatment_probability
            ),
            probability_observed=observation_probability,
            observed=observed,
        )

    @staticmethod
    def serialize(record: InterventionRecord) -> dict[str, object]:
        return asdict(record)
