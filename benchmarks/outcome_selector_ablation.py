"""Development-only matched-context selector ablation for AO-061."""

from __future__ import annotations

import itertools
import math
import random
import time
from typing import Any

from memory_fabric.causal_replay.attribution import measure_computation
from memory_fabric.causal_replay.bayes import BinaryNode
from memory_fabric.causal_replay.intervention import create
from memory_fabric.causal_replay.policy import ThresholdPolicy
from memory_fabric.causal_replay.replay import deterministic_simulator, replay
from memory_fabric.causal_replay.scheduler import Candidate, ReplayBudget, check_budget, select_priority
from memory_fabric.causal_replay.state import Observation, update
from memory_fabric.causal_replay.types import BeliefReference, digest_json

ARMS = (
    "random", "recency", "exact_dependence", "leave_one_out", "shapley",
    "budgeted_replay",
)
_REPLAY_BUDGET = ReplayBudget(max_events=3, max_attempts=1, max_nodes=4,
                              max_wall_seconds=5.0)


def _world(seed: int) -> tuple[tuple[BinaryNode, ...], tuple[Observation, ...], bool]:
    rng = random.Random(seed)
    prior = 0.1 + rng.random() * 0.3
    sensitivity = tuple(0.7 + rng.random() * 0.25 for _ in range(3))
    false_positive = (0.05, 0.12, 0.2)
    nodes = (BinaryNode("fault", (), {(): prior}),) + tuple(
        BinaryNode(f"sensor-{index}", ("fault",),
                   {(False,): false_positive[index], (True,): sensitivity[index]})
        for index in range(3)
    )
    truth = bool(rng.getrandbits(1))
    events = tuple(Observation(
        f"ao61-{seed}-{index}", f"sensor-{index}",
        rng.random() < (sensitivity[index] if truth else false_positive[index]),
        f"sensor-{index}", index + 1,
    ) for index in range(3))
    return nodes, events, truth


def _utility(proposal: str, truth: bool) -> float:
    return {"diagnose": 1.0 if truth else -1.0,
            "investigate": 0.0,
            "monitor": -0.5 if truth else 0.1}[proposal]


def _exact_shapley(players: tuple[str, ...], value: Any) -> dict[str, float]:
    result: dict[str, float] = {}
    count = len(players)
    for player in players:
        others = tuple(item for item in players if item != player)
        total = 0.0
        for size in range(count):
            weight = math.factorial(size) * math.factorial(count - size - 1) / math.factorial(count)
            for subset in itertools.combinations(others, size):
                coalition = frozenset(subset)
                total += weight * (value(coalition | {player}) - value(coalition))
        result[player] = total
    return result


def _interval(values: list[float]) -> list[float]:
    mean = math.fsum(values) / len(values)
    if len(values) < 2:
        return [mean, mean]
    variance = math.fsum((value - mean) ** 2 for value in values) / (len(values) - 1)
    half_width = 1.96 * math.sqrt(variance / len(values))
    return [mean - half_width, mean + half_width]


def run(seeds: tuple[int, ...]) -> dict[str, Any]:
    """Compare selectors on shared evidence; output remains development-only."""
    if (not isinstance(seeds, tuple) or len(seeds) < 5
            or any(type(seed) is not int or seed < 0 for seed in seeds)
            or len(set(seeds)) != len(seeds)):
        raise ValueError("development run requires at least five unique non-negative seeds")
    rows: list[dict[str, Any]] = []
    for seed in seeds:
        nodes, events, truth = _world(seed)
        node_by_name = {node.name: node for node in nodes}
        policy = ThresholdPolicy("fault")
        factual = update(nodes, events, policy_id=policy.policy_id)
        factual_proposal = policy.propose(factual).selected or "investigate"
        target_score = policy.propose(factual).probabilities[factual_proposal]
        players = tuple(event.variable for event in events)

        coalitions = tuple(frozenset(subset) for size in range(len(players) + 1)
                           for subset in itertools.combinations(players, size))

        def evaluate_all_coalitions() -> dict[frozenset[str], float]:
            return {
                coalition: float(update(
                    nodes, tuple(event for event in events if event.variable in coalition),
                    policy_id=policy.policy_id).posterior["fault"])
                for coalition in coalitions
            }

        coalition_values, shared_cost = measure_computation(
            evaluate_all_coalitions, event_transitions=len(coalitions) * len(events),
            simulated_calls=len(coalitions))

        def value(coalition: frozenset[str]) -> float:
            return coalition_values[coalition]

        # Exact model dependence is computed without evaluator truth. It is a
        # candidate eligibility set, with a deterministic tie break afterward.
        dependent, dependence_cost = measure_computation(lambda: tuple(
            event for event in events
            if abs(value(frozenset(players)) - value(frozenset(
                player for player in players if player != event.variable))) > 1e-12
        ), event_transitions=len(events) * (len(events) + 1))
        if not dependent:
            raise RuntimeError("exact dependence found no evidence connected to the proposal")

        loo_scores, loo_cost = measure_computation(lambda: {
            event.variable: abs(value(frozenset(players)) - value(frozenset(
                player for player in players if player != event.variable)))
            for event in events
        }, event_transitions=len(events) * (len(events) + 1))
        shapley_scores, shapley_cost = measure_computation(
            lambda: _exact_shapley(players, value), event_transitions=len(events) * 2**len(events))
        random_event, random_cost = measure_computation(
            lambda: random.Random(seed ^ 0xA061).choice(events), event_transitions=1)
        recent_event, recency_cost = measure_computation(
            lambda: max(events, key=lambda item: (item.sequence, item.observation_id)),
            event_transitions=len(events))
        dependence_event, exact_dep_cost = measure_computation(
            lambda: min(dependent, key=lambda item: (item.sequence, item.observation_id)),
            event_transitions=len(dependent))
        loo_event, = (max(events, key=lambda item: (loo_scores[item.variable], item.variable)),)
        shapley_event, = (max(events, key=lambda item: (shapley_scores[item.variable], item.variable)),)

        uncertainty = max(0.0, 1.0 - 2.0 * abs(target_score - 0.5))
        candidates_list = []
        for event in events:
            node = node_by_name[event.variable]
            evidence_strength = abs(math.log(
                node.probability_true[(True,)] / node.probability_true[(False,)])) / 5.0
            candidates_list.append(Candidate(
                candidate_id=event.observation_id, sequence=event.sequence,
                risk=min(1.0, evidence_strength), relevance=1.0,
                uncertainty=uncertainty,
            ))
        candidates = tuple(candidates_list)

        budget_started: float | None = None

        def budgeted_select() -> Observation:
            nonlocal budget_started
            budget_started = time.monotonic()
            check_budget(_REPLAY_BUDGET, event_count=len(events), node_count=len(nodes),
                         attempt_count=1, started_monotonic=budget_started)
            selected_id = select_priority(candidates, k=1)[0].candidate_id
            return next(event for event in events if event.observation_id == selected_id)

        budgeted_event, budgeted_cost = measure_computation(
            budgeted_select, event_transitions=len(events) + len(nodes), simulated_calls=1)
        selected = {
            "random": (random_event, random_cost),
            "recency": (recent_event, recency_cost),
            "exact_dependence": (dependence_event, exact_dep_cost),
            "leave_one_out": (loo_event, loo_cost),
            "shapley": (shapley_event, shapley_cost),
            "budgeted_replay": (budgeted_event, budgeted_cost),
        }
        simulator = deterministic_simulator(nodes, policy_id=policy.policy_id)
        for arm, (removed, selector_cost) in selected.items():
            intervention = create(BeliefReference(
                removed.observation_id, 1, "synthetic", digest_json(removed.__dict__)), "suppress")

            def execute():
                if arm == "budgeted_replay":
                    if budget_started is None:
                        raise RuntimeError("budgeted replay started without a checked budget")
                    check_budget(_REPLAY_BUDGET, event_count=len(events), node_count=len(nodes),
                                 attempt_count=1, started_monotonic=budget_started)
                    result = replay(events, intervention=intervention,
                                    simulator_id="synthetic", simulators={"synthetic": simulator},
                                    max_steps=_REPLAY_BUDGET.max_events)
                    check_budget(_REPLAY_BUDGET, event_count=len(events), node_count=len(nodes),
                                 attempt_count=1, started_monotonic=budget_started)
                    return result.state, result.consumed, result.complete
                reduced = tuple(item for item in events
                                if item.observation_id != removed.observation_id)
                return update(nodes, reduced, policy_id=policy.policy_id), len(reduced), True

            (counterfactual, transitions, complete), replay_cost = measure_computation(
                execute, event_transitions=len(events), simulated_calls=1)
            counterfactual_proposal = policy.propose(counterfactual).selected or "investigate"
            rows.append({
                "seed": seed, "arm": arm, "evidence_ids": [item.observation_id for item in events],
                "answer_context_items": len(events), "removal_budget": 1,
                "removed_evidence": removed.observation_id,
                "factual_proposal": factual_proposal,
                "counterfactual_proposal": counterfactual_proposal,
                "decision_flip": counterfactual_proposal != factual_proposal,
                "utility_factual": _utility(factual_proposal, truth),
                "utility_counterfactual": _utility(counterfactual_proposal, truth),
                "utility_difference": (_utility(counterfactual_proposal, truth)
                                       - _utility(factual_proposal, truth)),
                "truth_hidden_until_proposal": True, "complete": complete,
                "matched_posterior_evaluations": len(coalitions),
                "matched_posterior_evaluation_budget": len(coalitions),
                "replay_events": transitions,
                "cpu_nanoseconds": (shared_cost.cpu_nanoseconds + selector_cost.cpu_nanoseconds
                                    + replay_cost.cpu_nanoseconds),
                "wall_nanoseconds": (shared_cost.wall_nanoseconds + selector_cost.wall_nanoseconds
                                     + replay_cost.wall_nanoseconds),
                "peak_memory_bytes": max(selector_cost.peak_memory_bytes,
                                          replay_cost.peak_memory_bytes),
                "replay_budget": ({"max_events": _REPLAY_BUDGET.max_events,
                                   "max_attempts": _REPLAY_BUDGET.max_attempts,
                                   "max_nodes": _REPLAY_BUDGET.max_nodes,
                                   "max_wall_seconds": _REPLAY_BUDGET.max_wall_seconds,
                                   "max_tool_calls": _REPLAY_BUDGET.max_tool_calls}
                                  if arm == "budgeted_replay" else None),
                "network_calls": 0, "tool_calls": 0, "model_calls": 0,
                "authority_changes": 0,
            })

    summaries = {}
    for arm in ARMS:
        arm_rows = [row for row in rows if row["arm"] == arm]
        costs = [float(row["cpu_nanoseconds"]) for row in arm_rows]
        utilities = [float(row["utility_difference"]) for row in arm_rows]
        summaries[arm] = {
            "n": len(arm_rows), "mean_utility_difference": math.fsum(utilities) / len(utilities),
            "normal_approx_95_interval": _interval(utilities),
            "mean_cpu_nanoseconds": math.fsum(costs) / len(costs),
            "mean_wall_nanoseconds": math.fsum(row["wall_nanoseconds"] for row in arm_rows) / len(arm_rows),
            "max_peak_memory_bytes": max(row["peak_memory_bytes"] for row in arm_rows),
            "decision_flips": sum(row["decision_flip"] for row in arm_rows),
        }
    points = [{"arm": arm, "mean_cpu_nanoseconds": summaries[arm]["mean_cpu_nanoseconds"],
               "mean_utility_difference": summaries[arm]["mean_utility_difference"]}
              for arm in ARMS]
    frontier = [point for point in points if not any(
        other["mean_cpu_nanoseconds"] <= point["mean_cpu_nanoseconds"]
        and other["mean_utility_difference"] >= point["mean_utility_difference"]
        and (other["mean_cpu_nanoseconds"] < point["mean_cpu_nanoseconds"]
             or other["mean_utility_difference"] > point["mean_utility_difference"])
        for other in points if other["arm"] != point["arm"])]
    return {
        "schema_id": "memory-fabric.agent-outcome-selector-ablation.v1",
        "status": "DEVELOPMENT_ONLY_PROTOCOL_DRAFT",
        "promotion_status": "NOT_ASSESSED",
        "seeds": list(seeds), "arms": summaries, "rows": rows,
        "paired_context_verified": all(
            len({tuple(row["evidence_ids"]) for row in rows if row["seed"] == seed}) == 1
            and {row["removal_budget"] for row in rows if row["seed"] == seed} == {1}
            for seed in seeds),
        "cost_quality_points": points, "pareto_frontier": frontier,
        "comparison_contract": {
            "same_seeded_worlds": True, "same_evidence_context": True,
            "same_answer_context_items": True, "same_one_removal_budget": True,
            "hidden_truth_visible_after_proposal_only": True,
            "selector_cost": "shared eight-coalition posterior budget; local CPU and replay costs are measured",
            "equalized_compute_unit": "posterior updates over the same evidence subsets",
            "equalized_compute_count_per_arm": 2 ** 3,
            "promotion_authorized": False,
        },
        "limitations": ["synthetic worlds only", "protocol seeds and thresholds are not frozen",
                        "shared posterior-update budgets are matched; CPU and wall-clock costs still vary",
                        "no real-agent or deployment efficacy claim"],
    }
