"""Dependency-free timeline view model for factual/counterfactual comparison."""

from __future__ import annotations

__stability__ = "experimental"

from typing import Any, Iterable

from .state import BeliefState


def timeline(states: Iterable[BeliefState], proposals: Iterable[str | None], *,
             intervention_sequence: int | None = None) -> dict[str, Any]:
    state_list = tuple(states)
    proposal_list = tuple(proposals)
    if len(state_list) != len(proposal_list):
        raise ValueError("each timeline state needs one proposal")
    rows: list[dict[str, Any]] = []
    for index, (state, proposal) in enumerate(zip(state_list, proposal_list)):
        sequence = max((item.sequence for item in state.observations), default=0)
        rows.append({"step": index, "sequence": sequence,
            "evidence": [{"id": item.observation_id, "version": 1,
                          "origin": item.origin, "kind": item.kind}
                         for item in state.observations],
            "belief": dict(sorted(state.posterior.items())),
            "conflicts": state.conflict_variables,
            "policy": state.policy_id, "proposal": proposal,
            "fingerprint": state.fingerprint,
            "intervened": intervention_sequence is not None and sequence >= intervention_sequence})
    divergence = next((index for index, row in enumerate(rows)
                       if index > 0 and row["fingerprint"] != rows[0]["fingerprint"]), None)
    return {"schema": "cdm-decision-timeline-v1", "steps": rows,
            "first_divergence": divergence,
            "intervention_sequence": intervention_sequence,
            "real_actions_executed": False}
