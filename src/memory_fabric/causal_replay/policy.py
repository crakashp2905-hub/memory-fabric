"""Read-only decision proposals derived from a belief state."""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..decision_models import DecisionContext, DecisionOption, DecisionProposal
from .state import BeliefState
from .types import NonReplayable, digest_json


@dataclass(frozen=True)
class ThresholdPolicy:
    variable: str
    investigate_above: float = 0.35
    diagnose_above: float = 0.85
    policy_id: str = "investigate-threshold-v1"

    @property
    def implementation_digest(self) -> str:
        """Digest the local policy and proposal contract sources plus parameters."""
        try:
            root = Path(__file__).resolve().parents[1]
            sources = {
                "policy.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "decision_models.py": hashlib.sha256(
                    (root / "decision_models.py").read_bytes()).hexdigest(),
            }
        except OSError as exc:
            raise NonReplayable("policy implementation source is unavailable") from exc
        return digest_json({"schema": "memory-fabric-cdm-v1",
            "implementation": "threshold-policy-source-digest-v1", "sources": sources,
            "policy_id": self.policy_id, "variable": self.variable,
            "investigate_above": self.investigate_above,
            "diagnose_above": self.diagnose_above})

    def __post_init__(self) -> None:
        if not 0 <= self.investigate_above <= self.diagnose_above <= 1:
            raise ValueError("thresholds must be ordered within [0,1]")

    def propose(self, state: BeliefState) -> DecisionProposal:
        p = state.posterior[self.variable]
        options = (DecisionOption("monitor", "Continue monitoring"),
                   DecisionOption("investigate", "Gather more evidence"),
                   DecisionOption("diagnose", "Record a provisional diagnosis"))
        context = DecisionContext("simulated diagnostic decision", options,
                                  tuple(o.observation_id for o in state.observations))
        if p >= self.diagnose_above:
            scores = {"monitor": 0.05, "investigate": 0.15, "diagnose": 0.8}
        elif p >= self.investigate_above:
            scores = {"monitor": 0.1, "investigate": 0.8, "diagnose": 0.1}
        else:
            scores = {"monitor": 0.8, "investigate": 0.15, "diagnose": 0.05}
        total = sum(scores.values())
        probs = {k: v / total for k, v in scores.items()}
        selected = max(probs, key=lambda option: probs[option])
        return DecisionProposal(selected, probs, False, probs[selected],
                                context.evidence_ids, ("deterministic threshold policy",),
                                self.policy_id).validate(context)
