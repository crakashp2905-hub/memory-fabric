"""Matched local attribution architectures on identical synthetic worlds."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
from pathlib import Path
from typing import Any

from memory_fabric.causal_replay.attribution import (measure_computation,
    sampled_shapley)
from memory_fabric.causal_replay.bayes import BinaryNode
from memory_fabric.causal_replay.intervention import create
from memory_fabric.causal_replay.policy import ThresholdPolicy
from memory_fabric.causal_replay.replay import deterministic_simulator, replay
from memory_fabric.causal_replay.state import Observation, update
from memory_fabric.causal_replay.types import BeliefReference, digest_json


def _world(seed: int):
    rng = random.Random(seed)
    prior = 0.1 + rng.random() * 0.3
    sensitivity = tuple(0.7 + rng.random() * 0.25 for _ in range(3))
    false_positive = (0.05, 0.12, 0.2)
    nodes = (BinaryNode("fault", (), {(): prior}),) + tuple(
        BinaryNode(f"sensor-{i}", ("fault",),
            {(False,): false_positive[i], (True,): sensitivity[i]}) for i in range(3))
    truth = bool(rng.getrandbits(1))
    events = tuple(Observation(f"attr-{seed}-{i}", f"sensor-{i}",
        rng.random() < (sensitivity[i] if truth else false_positive[i]),
        f"sensor-{i}", i + 1) for i in range(3))
    return nodes, truth, events


def _utility(proposal: str, truth: bool) -> float:
    return {"diagnose": 1.0 if truth else -1.0,
            "investigate": 0.0,
            "monitor": -0.5 if truth else 0.1}[proposal]


def run(seeds: tuple[int, ...]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for seed in seeds:
        nodes, truth, events = _world(seed)
        policy = ThresholdPolicy("fault")
        factual = update(nodes, events, policy_id=policy.policy_id)
        proposal = policy.propose(factual)
        target_option = proposal.selected or "investigate"

        def value(coalition: frozenset[str]) -> float:
            subset = tuple(item for item in events if item.variable in coalition)
            state = update(nodes, subset, policy_id=policy.policy_id)
            return float(policy.propose(state).probabilities[target_option])

        exact_shapley, exact_cost = measure_computation(
            lambda: _exact_values(events, value), event_transitions=len(events) * 8)
        sampled, sampled_cost = measure_computation(lambda: sampled_shapley(
            tuple(item.variable for item in events), value, seed=seed, permutations=256),
            event_transitions=256 * len(events))
        exact_candidate = max(events, key=lambda item: (exact_shapley[item.variable], item.variable))
        sampled_candidate = max(events, key=lambda item: (sampled[item.variable], item.variable))
        def loo_selector():
            return max(events, key=lambda item: abs(value(frozenset(
                other.variable for other in events if other is not item)) - value(frozenset(
                    item.variable for item in events))))
        leave_one_out, loo_cost = measure_computation(loo_selector,
            event_transitions=len(events) * len(events) * 2)
        exact_subset, subset_cost = measure_computation(loo_selector,
            event_transitions=len(events) * len(events) * 2)
        random_candidate, random_cost = measure_computation(lambda:
            events[random.Random(seed ^ 0xA771).randrange(len(events))],
            event_transitions=1)
        recency_candidate, recency_cost = measure_computation(lambda:
            max(events, key=lambda item: (item.sequence, item.observation_id)),
            event_transitions=len(events))
        selected = {
            "leave_one_out": leave_one_out,
            "exact_subset_oracle": exact_subset,
            "exact_shapley": exact_candidate,
            "sampled_shapley": sampled_candidate,
            "random": random_candidate,
            "recency": recency_candidate,
            "car_full_suffix": exact_subset,
        }
        selector_costs = {"leave_one_out": loo_cost,
            "exact_subset_oracle": subset_cost, "exact_shapley": exact_cost,
            "sampled_shapley": sampled_cost, "random": random_cost,
            "recency": recency_cost, "car_full_suffix": subset_cost}
        simulator = deterministic_simulator(nodes, policy_id=policy.policy_id)
        for arm, removed in selected.items():
            intervention = create(BeliefReference(removed.observation_id, 1, "synthetic",
                digest_json(removed.__dict__)), "suppress")

            def execute():
                if arm == "car_full_suffix":
                    result = replay(events, intervention=intervention,
                        simulator_id="synthetic", simulators={"synthetic": simulator})
                    return result.state, result.consumed, result.complete
                remainder = tuple(item for item in events
                                  if item.observation_id != removed.observation_id)
                state = update(nodes, remainder, policy_id=policy.policy_id)
                return state, len(remainder), True

            (counterfactual, transitions, complete), cost = measure_computation(
                execute, event_transitions=len(events), simulated_calls=0)
            selector_cost = selector_costs[arm]
            changed = policy.propose(counterfactual).selected or "investigate"
            rows.append({"seed": seed, "arm": arm, "truth_hidden_until_proposal": True,
                "removal_budget": 1, "network_calls": 0, "tool_calls": 0,
                "authority_changes": 0,
                "factual_proposal": target_option, "counterfactual_proposal": changed,
                "decision_flip": changed != target_option,
                "removed_evidence": removed.observation_id,
                "utility_factual": _utility(target_option, truth),
                "utility_counterfactual": _utility(changed, truth),
                "utility_difference": _utility(changed, truth) - _utility(target_option, truth),
                "proposal_score_shapley": exact_shapley[removed.variable],
                "sampled_score_shapley": sampled[removed.variable],
                "complete": complete, "transitions": transitions,
                "cpu_nanoseconds": cost.cpu_nanoseconds + selector_cost.cpu_nanoseconds,
                "wall_nanoseconds": cost.wall_nanoseconds + selector_cost.wall_nanoseconds,
                "peak_memory_bytes": max(cost.peak_memory_bytes,
                                          selector_cost.peak_memory_bytes),
                "certificate_bytes": cost.certificate_bytes, "disk_bytes": cost.disk_bytes,
                "model_calls": cost.model_calls, "api_tokens": cost.api_tokens,
                "external_charges": cost.external_charges})
        rows.extend([
            {"seed": seed, "arm": "cost_exact_shapley", **exact_cost.__dict__},
            {"seed": seed, "arm": "cost_sampled_shapley", **sampled_cost.__dict__},
        ])
    arms: dict[str, Any] = {}
    for arm in sorted({row["arm"] for row in rows if not str(row["arm"]).startswith("cost_")}):
        values = [row["utility_difference"] for row in rows if row["arm"] == arm]
        mean = math.fsum(values) / len(values)
        sd = math.sqrt(math.fsum((item - mean) ** 2 for item in values) / max(1, len(values)-1))
        half = 1.96 * sd / math.sqrt(len(values)) if len(values) > 1 else 0.0
        arm_rows = [row for row in rows if row["arm"] == arm]
        mean_cpu = math.fsum(row["cpu_nanoseconds"] for row in arm_rows) / len(arm_rows)
        mean_wall = math.fsum(row["wall_nanoseconds"] for row in arm_rows) / len(arm_rows)
        peak_memory = max(row["peak_memory_bytes"] for row in arm_rows)
        arms[arm] = {"n": len(values), "mean_paired_utility_difference": mean,
                     "normal_approx_95_interval": [mean-half, mean+half],
                     "decision_flips": sum(bool(row["decision_flip"]) for row in arm_rows),
                     "mean_cpu_nanoseconds": mean_cpu,
                     "mean_wall_nanoseconds": mean_wall,
                     "max_peak_memory_bytes": peak_memory}
    points = [{"arm": arm, "cost_cpu_nanoseconds": summary["mean_cpu_nanoseconds"],
               "quality_mean_utility_difference": summary["mean_paired_utility_difference"],
               "quality_interval": summary["normal_approx_95_interval"],
               "mean_wall_nanoseconds": summary["mean_wall_nanoseconds"],
               "max_peak_memory_bytes": summary["max_peak_memory_bytes"]}
              for arm, summary in arms.items()]
    frontier = [point for point in points if not any(
        other["cost_cpu_nanoseconds"] <= point["cost_cpu_nanoseconds"]
        and other["quality_mean_utility_difference"] >= point["quality_mean_utility_difference"]
        and (other["cost_cpu_nanoseconds"] < point["cost_cpu_nanoseconds"]
             or other["quality_mean_utility_difference"] > point["quality_mean_utility_difference"])
        for other in points if other["arm"] != point["arm"])]
    frontier.sort(key=lambda point: (point["cost_cpu_nanoseconds"],
                                     -point["quality_mean_utility_difference"],
                                     point["arm"]))
    return {"schema": "cdm-attribution-benchmark-v1", "seeds": seeds,
        "arms": arms, "rows": rows,
        "comparison_contract": {"same_seeded_worlds": True,
            "same_one_removal_budget": True, "removal_budget": 1,
            "estimand": "paired counterfactual-minus-factual simulator utility",
            "hidden_truth_visible_only_after_proposal": True,
            "network_calls": 0, "tool_calls": 0, "authority_changes": 0,
            "cost_basis": "measured local selector plus arm replay CPU/wall; peak is max phase usage"},
        "cost_quality_points": points,
        "pareto_frontier": frontier,
        "scope": "matched synthetic binary sensor worlds; proposal-score attribution; outcome utility evaluator-only",
        "known_limitations": ["synthetic worlds only", "normal-approximation intervals",
            "exact subset and CAR arms share the exhaustive candidate selector",
            "not evidence of deployment efficacy"]}


def _exact_values(events: tuple[Observation, ...], value) -> dict[str, float]:
    players = tuple(item.variable for item in events)
    n = len(players)
    result = {}
    for player in players:
        total = 0.0
        others = tuple(other for other in players if other != player)
        for size in range(n):
            weight = math.factorial(size) * math.factorial(n-size-1) / math.factorial(n)
            for subset in itertools.combinations(others, size):
                coalition = frozenset(subset)
                total += weight * (value(coalition | {player}) - value(coalition))
        result[player] = total
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(20261301, 20261321)))
    parser.add_argument("--out", default="research/results/cdm/attribution-benchmark")
    args = parser.parse_args()
    result = run(tuple(args.seeds))
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(result, sort_keys=True, indent=2) + "\n"
    (output / "report.json").write_text(raw, encoding="utf-8")
    (output / "cases.csv").write_text(_csv(result["rows"]), encoding="utf-8")
    manifest = {key: value for key, value in result.items() if key != "rows"}
    prereg = Path(__file__).resolve().parents[1] / "research" / "prereg" / \
        "cdm-r8-cost-quality-pareto.md"
    manifest.update({"generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "preregistration": "research/prereg/cdm-r8-cost-quality-pareto.md",
        "preregistration_sha256": hashlib.sha256(prereg.read_bytes()).hexdigest(),
        "cost_quality_protocol": "research/prereg/cdm-r8-cost-quality-pareto.md",
        "configuration_sha256": hashlib.sha256(json.dumps({
            "seeds": args.seeds, "comparison_contract": result["comparison_contract"],
            "arms": sorted(result["arms"]),
            "cost_quality_protocol_sha256": hashlib.sha256(prereg.read_bytes()).hexdigest()},
            sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        "report_sha256": hashlib.sha256((output / "report.json").read_bytes()).hexdigest(),
        "csv_sha256": hashlib.sha256((output / "cases.csv").read_bytes()).hexdigest()})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n",
                                          encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


def _csv(rows: list[dict[str, Any]]) -> str:
    import csv
    import io
    stream = io.StringIO(newline="")
    columns = sorted({key for row in rows for key in row})
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


if __name__ == "__main__":
    raise SystemExit(main())
