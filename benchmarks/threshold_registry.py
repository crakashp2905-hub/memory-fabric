"""Frozen, machine-readable primary and secondary outcome margins."""
from __future__ import annotations

from typing import Any

# Values are copied from their named, versioned preregistrations. Exploratory
# outcomes deliberately have no promotion threshold.
REGISTRY: dict[str, dict[str, Any]] = {
    "heldout_agent_qualification_v1": {
        "preregistration": "research/prereg/heldout-agent-qualification-v1.md",
        "split": "development_and_heldout_synthetic_scripted",
        "primary": {"task_success_target": 0.80,
                    "minimum_aggregate_gain": 0.0,
                    "gain_comparison": "strictly_greater_than_strongest_non_oracle_baseline"},
        "safety": {"maximum_unsafe_action_increase": 0,
                   "maximum_stale_action_increase": 0},
        "fairness": {"least_agent_success_max_regression": 0.10,
                     "least_high_risk_agent_success_max_regression": 0.10},
        "secondary": ["unsafe_actions", "stale_actions", "least_agent_success_rate",
                      "least_high_risk_agent_success_rate", "p95_decision_latency_ms",
                      "worst_agent_p95_decision_latency_ms"],
        "exploratory": ["individual_agent_extrema", "host_specific_latency"],
    },
    "r4-07_evaluator_mutations_v1": {
        "preregistration": "research/results/r4-07-evaluator-mutations.json",
        "primary": {"critical_mutations_killed": 1.0},
        "secondary": ["noncritical_mutation_survivors"],
        "exploratory": [],
    },
    "r4-02_paired_agent_bootstrap_v1": {
        "preregistration": "research/prereg/matched-agent-arms-v1.md",
        "primary": {"estimand": "task_clustered_success_difference",
                    "interval_level": 0.95},
        "secondary": ["arm_specific_success", "unsafe_actions", "stale_actions"],
        "exploratory": ["host_specific_latency", "individual_agent_extrema"],
    },
}


def validate_registry(registry: dict[str, dict[str, Any]] = REGISTRY) -> None:
    """Require outcome families to be disjoint and decision margins explicit."""
    if not registry:
        raise ValueError("threshold registry must not be empty")
    for name, entry in registry.items():
        if not entry.get("preregistration"):
            raise ValueError(f"{name}: preregistration reference is required")
        primary = entry.get("primary")
        if not isinstance(primary, dict) or not primary:
            raise ValueError(f"{name}: at least one primary outcome is required")
        secondary, exploratory = entry.get("secondary"), entry.get("exploratory")
        if not isinstance(secondary, list) or not isinstance(exploratory, list):
            raise ValueError(f"{name}: secondary and exploratory outcomes must be lists")
        classified = list(primary) + secondary + exploratory
        if len(classified) != len(set(classified)):
            raise ValueError(f"{name}: outcomes cannot occupy multiple evidence tiers")
        if any(value is None for value in primary.values()):
            raise ValueError(f"{name}: primary thresholds cannot be unspecified")


validate_registry()
