"""R5 v3 confirmatory architecture comparison; stdlib-only synthetic worlds."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any, Callable

from memory_fabric.causal_replay.attribution import exhaustive_shapley, measure_computation, sampled_shapley
from memory_fabric.causal_replay.bayes import BinaryNode
from memory_fabric.causal_replay.policy import ThresholdPolicy
from memory_fabric.causal_replay.state import Observation, update

ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT_SEEDS = tuple(range(20261901, 20261906))
CONFIRMATORY_SEEDS = tuple(range(20261911, 20261931))
PROTOCOL_PATH = Path("research/prereg/cdm-r5-evaluator-executor-ablations.md")
PROTOCOL_VERSION = "CDM-R5-v3"
MARGIN_SHARE = 0.20


def _world(seed: int) -> tuple[tuple[BinaryNode, ...], tuple[Observation, ...], bool]:
    rng = random.Random(seed)
    prior = 0.1 + rng.random() * 0.3
    sensitivity = tuple(0.7 + rng.random() * 0.25 for _ in range(3))
    false_positive = (0.05, 0.12, 0.2)
    nodes = (BinaryNode("fault", (), {(): prior}),) + tuple(
        BinaryNode(f"sensor-{index}", ("fault",),
            {(False,): false_positive[index], (True,): sensitivity[index]})
        for index in range(3))
    truth = bool(rng.getrandbits(1))
    events = tuple(Observation(f"r5v3-{seed}-{index}", f"sensor-{index}",
        rng.random() < (sensitivity[index] if truth else false_positive[index]),
        f"sensor-{index}", index + 1) for index in range(3))
    return nodes, events, truth


def _utility(proposal: str, truth: bool) -> float:
    return {"diagnose": 1.0 if truth else -1.0,
            "investigate": 0.0,
            "monitor": -0.5 if truth else 0.1}[proposal]


def _proposal(nodes: tuple[BinaryNode, ...], events: tuple[Observation, ...],
              removed: Observation, policy: ThresholdPolicy) -> str:
    remaining = tuple(event for event in events if event.observation_id != removed.observation_id)
    state = update(nodes, remaining, policy_id=policy.policy_id)
    return policy.propose(state).selected or "investigate"


def _interval(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    mean = math.fsum(values) / len(values)
    if len(values) < 2:
        return mean, mean, mean
    sd = math.sqrt(math.fsum((item - mean) ** 2 for item in values) / (len(values) - 1))
    half = 1.96 * sd / math.sqrt(len(values))
    return mean, mean - half, mean + half


def run(seeds: tuple[int, ...], *, split: str) -> dict[str, Any]:
    if split not in {"development", "confirmatory"} or not seeds:
        raise ValueError("split must be development or confirmatory with registered seeds")
    expected = DEVELOPMENT_SEEDS if split == "development" else CONFIRMATORY_SEEDS
    if seeds != expected:
        raise ValueError("seed list must exactly match the frozen split")
    rows: list[dict[str, Any]] = []
    for seed in seeds:
        nodes, events, truth = _world(seed)
        policy = ThresholdPolicy("fault")
        factual_state = update(nodes, events, policy_id=policy.policy_id)
        target = policy.propose(factual_state)
        target_option = target.selected or "investigate"

        def value(coalition: frozenset[str]) -> float:
            subset = tuple(event for event in events if event.variable in coalition)
            state = update(nodes, subset, policy_id=policy.policy_id)
            return float(policy.propose(state).probabilities[target_option])

        players = tuple(event.variable for event in events)

        def select_leave_one_out() -> Observation:
            baseline = value(frozenset(players))
            return max(events, key=lambda event: abs(value(frozenset(
                other for other in players if other != event.variable)) - baseline))

        def select_exact_shapley() -> Observation:
            values = exhaustive_shapley(players, value)
            return max(events, key=lambda event: (values[event.variable], event.variable))

        def select_sampled_shapley() -> Observation:
            values = sampled_shapley(players, value, seed=seed, permutations=256)
            return max(events, key=lambda event: (values[event.variable], event.variable))

        selectors: dict[str, Callable[[], Observation]] = {
            "leave_one_out": select_leave_one_out,
            "exact_shapley": select_exact_shapley,
            "sampled_shapley": select_sampled_shapley,
            "random": lambda: events[random.Random(seed ^ 0x5A19).randrange(len(events))],
            "recency": lambda: max(events, key=lambda event: (event.sequence, event.observation_id)),
        }
        selected: dict[str, Observation] = {}
        proposals: dict[str, str] = {}
        costs: dict[str, Any] = {}
        for arm, selector in selectors.items():
            def execute(selector: Callable[[], Observation] = selector) -> tuple[Observation, str]:
                removed_event = selector()
                return removed_event, _proposal(nodes, events, removed_event, policy)
            (removed_event, proposal), cost = measure_computation(
                execute, event_transitions=len(events) * 8, simulated_calls=1)
            selected[arm] = removed_event
            proposals[arm] = proposal
            costs[arm] = cost

        # The oracle sees evaluator truth only after all scored proposals have
        # been fixed and selects among the same three legal one-removal actions.
        oracle_options = [(event, _proposal(nodes, events, event, policy)) for event in events]
        oracle_event, oracle_proposal = max(
            oracle_options, key=lambda pair: (_utility(pair[1], truth), pair[0].variable))
        oracle_utility = _utility(oracle_proposal, truth)
        for arm, removed_event in selected.items():
            proposal = proposals[arm]
            utility = _utility(proposal, truth)
            cost = costs[arm]
            rows.append({"split": split, "seed": seed, "arm": arm,
                "factual_proposal": target_option, "counterfactual_proposal": proposal,
                "removed_sensor": removed_event.variable,
                "utility_factual": _utility(target_option, truth),
                "utility_counterfactual": utility,
                "utility_difference": utility - _utility(target_option, truth),
                "utility_oracle_one_removal": oracle_utility,
                "oracle_removed_sensor": oracle_event.variable,
                "oracle_exceeded": utility > oracle_utility + 1e-12,
                "removal_budget": 1, "complete": True,
                "cpu_nanoseconds": cost.cpu_nanoseconds,
                "wall_nanoseconds": cost.wall_nanoseconds,
                "event_transitions": cost.event_transitions,
                "peak_memory_bytes": cost.peak_memory_bytes,
                "simulated_calls": cost.simulated_calls,
                "model_calls": cost.model_calls,
                "api_tokens": cost.api_tokens,
                "external_charges": cost.external_charges})
        oracle_cost = measure_computation(
            lambda: tuple(_proposal(nodes, events, event, policy) for event in events),
            event_transitions=len(events) * len(events), simulated_calls=len(events))[1]
        rows.append({"split": split, "seed": seed, "arm": "oracle_one_removal",
            "factual_proposal": target_option, "counterfactual_proposal": oracle_proposal,
            "removed_sensor": oracle_event.variable,
            "utility_factual": _utility(target_option, truth),
            "utility_counterfactual": oracle_utility,
            "utility_difference": oracle_utility - _utility(target_option, truth),
            "utility_oracle_one_removal": oracle_utility,
            "oracle_removed_sensor": oracle_event.variable, "oracle_exceeded": False,
            "removal_budget": 1, "complete": True,
            "cpu_nanoseconds": oracle_cost.cpu_nanoseconds,
            "wall_nanoseconds": oracle_cost.wall_nanoseconds,
            "event_transitions": oracle_cost.event_transitions,
            "peak_memory_bytes": oracle_cost.peak_memory_bytes,
            "simulated_calls": oracle_cost.simulated_calls,
            "model_calls": oracle_cost.model_calls, "api_tokens": oracle_cost.api_tokens,
            "external_charges": oracle_cost.external_charges})

    arm_summary: dict[str, Any] = {}
    arm_names = tuple(selectors.keys()) + ("oracle_one_removal",)
    for arm in arm_names:
        selected_rows = [row for row in rows if row["arm"] == arm]
        interval = _interval([float(row["utility_difference"]) for row in selected_rows])
        arm_summary[arm] = {"n": len(selected_rows), "mean_utility_difference": interval[0],
            "normal_approx_95_interval": [interval[1], interval[2]],
            "mean_cpu_nanoseconds": math.fsum(float(row["cpu_nanoseconds"])
                                               for row in selected_rows) / len(selected_rows),
            "mean_wall_nanoseconds": math.fsum(float(row["wall_nanoseconds"])
                                                for row in selected_rows) / len(selected_rows),
            "max_peak_memory_bytes": max(int(row["peak_memory_bytes"]) for row in selected_rows)}
    by_seed = {int(row["seed"]): row for row in rows if row["arm"] == "leave_one_out"}
    exact_by_seed = {int(row["seed"]): row for row in rows if row["arm"] == "exact_shapley"}
    oracle_by_seed = {int(row["seed"]): row for row in rows if row["arm"] == "oracle_one_removal"}
    paired_contrasts = [float(exact_by_seed[seed]["utility_counterfactual"])
        - float(by_seed[seed]["utility_counterfactual"]) for seed in seeds]
    headroom_values = [float(oracle_by_seed[seed]["utility_counterfactual"])
        - float(by_seed[seed]["utility_counterfactual"]) for seed in seeds]
    contrast = _interval(paired_contrasts)
    headroom = math.fsum(headroom_values) / len(headroom_values)
    margin = MARGIN_SHARE * max(0.0, headroom)
    oracle_exceedances = sum(bool(row["oracle_exceeded"]) for row in rows)
    supported = (headroom > 0 and contrast[1] > margin and oracle_exceedances == 0)
    if headroom <= 0:
        decision = "UNIDENTIFIABLE_NO_POSITIVE_ORACLE_HEADROOM"
    elif supported:
        decision = "SUPPORTS_REGISTERED_SUPERIORITY_HYPOTHESIS"
    else:
        decision = "DOES_NOT_SUPPORT_REGISTERED_SUPERIORITY_HYPOTHESIS"
    return {"schema": "cdm-r5-architecture-superiority-v3", "protocol": PROTOCOL_VERSION,
        "split": split, "seeds": seeds, "arms": arm_summary, "rows": rows,
        "primary": {"contrast": "exact_shapley_utility_minus_leave_one_out_utility",
            "mean_paired_difference": contrast[0],
            "normal_approx_95_interval": [contrast[1], contrast[2]],
            "oracle_headroom_mean": headroom, "superiority_margin": margin,
            "margin_share": MARGIN_SHARE, "decision": decision,
            "oracle_exceedances": oracle_exceedances},
        "safety": {"network_calls": 0, "model_calls": 0, "tool_calls": 0,
            "authority_changes": 0, "hidden_truth_visible_to_selectors": False},
        "scope": "local conceptual architecture comparison on synthetic binary-sensor worlds",
        "limitations": ["No official reproduction of Shapley, CAR or another external system.",
            "Normal-approximation intervals are imprecise at these sample sizes.",
            "No real-world transfer or efficacy claim is supported."]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("development", "confirmatory"), required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--development-manifest")
    args = parser.parse_args()
    seeds = DEVELOPMENT_SEEDS if args.split == "development" else CONFIRMATORY_SEEDS
    output = Path(args.out)
    if not output.is_absolute():
        output = ROOT / output
    output = output.resolve()
    if ROOT not in output.parents:
        parser.error("output directory must be inside the repository")
    protocol_path = ROOT / PROTOCOL_PATH
    protocol_hash = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    if args.split == "confirmatory":
        development_manifest_path = Path(args.development_manifest) if args.development_manifest else (
            ROOT / "research/results/cdm/architecture-superiority-r5v3/development/manifest.json")
        if not development_manifest_path.is_absolute():
            development_manifest_path = ROOT / development_manifest_path
        development_manifest = json.loads(development_manifest_path.read_text(encoding="utf-8"))
        if (development_manifest.get("status") != "PASS"
                or development_manifest.get("protocol_sha256") != protocol_hash):
            parser.error("registered development preflight must pass under the same frozen protocol")
    result = run(seeds, split=args.split)
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "report.json"
    csv_path = output / "cases.csv"
    markdown_path = output / "report.md"
    report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result["rows"][0]))
        writer.writeheader()
        writer.writerows(result["rows"])
    primary = result["primary"]
    lines = [f"# CDM-R5 v3 {args.split} architecture comparison", "",
        "Conceptual first-party baselines only; not official reproductions.", "",
        f"Seeds: {', '.join(str(seed) for seed in seeds)}", "",
        f"Primary contrast mean: {primary['mean_paired_difference']:.4f}; "
        f"95% interval: [{primary['normal_approx_95_interval'][0]:.4f}, "
        f"{primary['normal_approx_95_interval'][1]:.4f}]", "",
        f"Oracle headroom: {primary['oracle_headroom_mean']:.4f}; fixed margin: "
        f"{primary['superiority_margin']:.4f} (20% of positive headroom).", "",
        f"Decision: **{primary['decision']}**", "", "## Arm utility deltas", "",
        "| Arm | Mean utility difference | 95% interval | Mean CPU ns | Mean wall ns | Max peak bytes |",
        "|---|---:|---:|---:|---:|---:|"]
    for arm, summary in result["arms"].items():
        interval = summary["normal_approx_95_interval"]
        lines.append(f"| {arm} | {summary['mean_utility_difference']:.4f} | "
            f"[{interval[0]:.4f}, {interval[1]:.4f}] | {summary['mean_cpu_nanoseconds']:.0f} | "
            f"{summary['mean_wall_nanoseconds']:.0f} | {summary['max_peak_memory_bytes']} |")
    lines.extend(["", "## Scope and limitations", "",
        "All arms use the same worlds, deterministic policy and one-removal budget. "
        "The oracle is evaluator-only and selects among the same legal removals.",
        "", *[f"- {item}" for item in result["limitations"]], ""])
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    dependencies = ("benchmarks/cdm_architecture_superiority.py",
        "src/memory_fabric/causal_replay/attribution.py",
        "src/memory_fabric/causal_replay/bayes.py",
        "src/memory_fabric/causal_replay/policy.py",
        "src/memory_fabric/causal_replay/state.py")
    source_hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                     for path in dependencies}
    manifest = {key: value for key, value in result.items() if key != "rows"}
    manifest.update({"status": "PASS" if result["primary"]["oracle_exceedances"] == 0
            and all(bool(row["complete"]) for row in result["rows"]) else "FAIL",
        "protocol_path": PROTOCOL_PATH.as_posix(), "protocol_sha256": protocol_hash,
        "generator_sha256": source_hashes[dependencies[0]], "source_hashes": source_hashes,
        "configuration_sha256": hashlib.sha256(json.dumps({"split": args.split,
            "seeds": seeds, "margin_share": MARGIN_SHARE, "protocol_sha256": protocol_hash},
            sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "summary_sha256": hashlib.sha256(markdown_path.read_bytes()).hexdigest()})
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0 if manifest["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
