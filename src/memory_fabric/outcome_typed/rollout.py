"""Feature flags and staged rollout for the agent-outcome stack (W24-08).

Each feature moves through ``off -> shadow -> canary -> on``. Counterfactual
dispatch (CDM) starts and stays ``advisory`` (its ``shadow`` stage): it may
report, never act. Moving any feature forward needs qualifying evidence named
for that step; moving CDM to ``on`` needs A5 promoted and the frozen A6-A5
net-utility test passed. ``rollback`` restores the last qualified flag set and
records why. Flags never touch the event log: changing them cannot change
recorded history.
"""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass, field
from typing import Mapping

STAGES = ("off", "shadow", "canary", "on")
DEFAULTS: Mapping[str, str] = {"recovery": "on", "cdm": "shadow", "model_actor": "off",
                               "outcome_api": "canary"}
REQUIRED_EVIDENCE: Mapping[tuple[str, str], frozenset[str]] = {
    ("cdm", "canary"): frozenset({"a5_promoted", "a6_net_utility_passed"}),
    ("cdm", "on"): frozenset({"a5_promoted", "a6_net_utility_passed", "canary_clean"}),
    ("model_actor", "shadow"): frozenset({"local_model_pass"}),
    ("model_actor", "canary"): frozenset({"local_model_pass", "model_attacks_pass"}),
    ("model_actor", "on"): frozenset({"local_model_pass", "model_attacks_pass", "independent_review"}),
    ("outcome_api", "on"): frozenset({"gate_pass_at_commit"}),
}


class RolloutRefused(ValueError):
    pass


@dataclass
class Rollout:
    flags: dict[str, str] = field(default_factory=lambda: dict(DEFAULTS))
    qualified: dict[str, str] = field(default_factory=lambda: dict(DEFAULTS))
    history: list[dict[str, str]] = field(default_factory=list)

    def advisory(self, feature: str) -> bool:
        return self.flags[feature] in {"off", "shadow"}

    def advance(self, feature: str, stage: str, evidence: set[str] | frozenset[str]) -> None:
        if feature not in self.flags or stage not in STAGES:
            raise RolloutRefused(f"unknown feature or stage: {feature} -> {stage}")
        if STAGES.index(stage) != STAGES.index(self.flags[feature]) + 1:
            raise RolloutRefused(f"{feature} moves one stage at a time from {self.flags[feature]}")
        missing = REQUIRED_EVIDENCE.get((feature, stage), frozenset()) - set(evidence)
        if missing:
            raise RolloutRefused(f"{feature} -> {stage} needs evidence: {sorted(missing)}")
        self.history.append({"feature": feature, "from": self.flags[feature], "to": stage})
        self.flags[feature] = stage
        self.qualified = dict(self.flags)

    def set_unqualified(self, feature: str, stage: str) -> None:
        """An operator override without evidence; rollback undoes it."""
        self.history.append({"feature": feature, "from": self.flags[feature], "to": stage,
                             "unqualified": "true"})
        self.flags[feature] = stage

    def rollback(self, reason: str) -> dict[str, str]:
        self.history.append({"rollback": reason})
        self.flags = dict(self.qualified)
        return dict(self.flags)
