"""Frozen local factorial ablation for trust annotations and evaluator feedback."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from memory_fabric.causal_replay.bayes import BinaryNode
from memory_fabric.causal_replay.policy import ThresholdPolicy
from memory_fabric.causal_replay.state import Observation, update

TRAIN_SEEDS = tuple(range(20261801, 20261811))
HELDOUT_SEEDS = tuple(range(20261811, 20261821))
SCENARIOS = ("clean", "annotation_inversion", "feedback_inversion")


@dataclass(frozen=True)
class Experience:
    score: float = 0.5
    count: int = 0


def update_experience(state: Experience, reward: float | None, *, alpha: float = 0.1,
                      max_experiences: int = 20) -> Experience:
    if (not math.isfinite(state.score) or not 0 <= state.score <= 1
            or type(state.count) is not int or state.count < 0
            or not math.isfinite(alpha) or not 0 < alpha <= 1
            or type(max_experiences) is not int or max_experiences < 1):
        raise ValueError("invalid experience state or update hyperparameter")
    if reward is None:
        return state
    if not math.isfinite(reward) or not 0 <= reward <= 1:
        raise ValueError("normalized evaluator reward must be in [0,1]")
    if state.count >= max_experiences:
        return state
    score = min(1.0, max(0.0, state.score + alpha * (reward - state.score)))
    return Experience(score, state.count + 1)


def _world(seed: int) -> tuple[tuple[BinaryNode, ...], tuple[Observation, ...], bool]:
    rng = random.Random(seed)
    prior = 0.1 + rng.random() * 0.3
    sensitivities = tuple(0.72 + rng.random() * 0.23 for _ in range(3))
    false_positive = tuple(0.04 + rng.random() * 0.18 for _ in range(3))
    nodes = (BinaryNode("fault", (), {(): prior}),) + tuple(
        BinaryNode(f"sensor-{i}", ("fault",),
                   {(False,): false_positive[i], (True,): sensitivities[i]})
        for i in range(3))
    truth = bool(rng.getrandbits(1))
    events = tuple(Observation(
        f"r12-{seed}-{i}", f"sensor-{i}",
        rng.random() < (sensitivities[i] if truth else false_positive[i]),
        f"sensor-{i}", i + 1) for i in range(3))
    return nodes, events, truth


def _utility(proposal: str, truth: bool) -> float:
    return {"diagnose": 1.0 if truth else -1.0,
            "investigate": 0.0,
            "monitor": -0.5 if truth else 0.1}[proposal]


def _choose_removed(nodes: tuple[BinaryNode, ...], events: tuple[Observation, ...],
                    policy: ThresholdPolicy, annotations: dict[str, Experience], *,
                    use_annotations: bool, annotation_corrupted: bool) -> Observation:
    if use_annotations:
        def score(event: Observation) -> float:
            value = annotations[event.variable].score
            if annotation_corrupted:
                value = 1.0 - value
            return value
        return max(events, key=score)
    factual = update(nodes, events, policy_id=policy.policy_id)
    scores = []
    for event in events:
        remaining = tuple(other for other in events if other.observation_id != event.observation_id)
        counterfactual = update(nodes, remaining, policy_id=policy.policy_id)
        scores.append((abs(factual.posterior["fault"] - counterfactual.posterior["fault"]),
                       event.variable, event))
    return max(scores, key=lambda row: (row[0], row[1]))[2]


def _propose(nodes: tuple[BinaryNode, ...], events: tuple[Observation, ...],
             removed: Observation, policy: ThresholdPolicy) -> str:
    remaining = tuple(event for event in events if event.observation_id != removed.observation_id)
    return policy.propose(update(nodes, remaining, policy_id=policy.policy_id)).selected or "investigate"


def _interval(values: list[float]) -> tuple[float, float, float]:
    mean = math.fsum(values) / len(values) if values else 0.0
    if len(values) < 2:
        return mean, mean, mean
    sd = math.sqrt(math.fsum((value - mean) ** 2 for value in values) / (len(values) - 1))
    half = 1.96 * sd / math.sqrt(len(values))
    return mean, mean - half, mean + half


def run(train_seeds: tuple[int, ...] = TRAIN_SEEDS,
        heldout_seeds: tuple[int, ...] = HELDOUT_SEEDS) -> dict[str, Any]:
    if not train_seeds or not heldout_seeds or set(train_seeds) & set(heldout_seeds):
        raise ValueError("training and held-out seeds must be non-empty and disjoint")
    configs = ((False, False, "annotations_off_feedback_off"),
               (True, False, "annotations_on_feedback_off"),
               (False, True, "annotations_off_feedback_on"),
               (True, True, "annotations_on_feedback_on"))
    states: dict[str, dict[str, Experience]] = {
        name: {f"sensor-{i}": Experience() for i in range(3)}
        for _, _, name in configs}
    policy = ThresholdPolicy("fault")
    # Training is prequential: every arm proposes before the shared evaluator
    # reveals truth and before that arm's annotation state can be updated.
    for seed in train_seeds:
        nodes, events, truth = _world(seed)
        pending: list[tuple[str, str, Observation, bool]] = []
        for use_annotations, use_feedback, name in configs:
            removed = _choose_removed(nodes, events, policy, states[name],
                                      use_annotations=use_annotations,
                                      annotation_corrupted=False)
            proposal = _propose(nodes, events, removed, policy)
            pending.append((name, proposal, removed, use_feedback))
        for name, proposal, removed, use_feedback in pending:
            reward = (_utility(proposal, truth) + 1.0) / 2.0 if use_feedback else None
            states[name][removed.variable] = update_experience(states[name][removed.variable], reward)
    trained = {name: {sensor: {"score": state.score, "count": state.count}
                      for sensor, state in sorted(values.items())}
               for name, values in sorted(states.items())}

    rows: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        # Each held-out condition begins from the same trained state. Feedback
        # in one condition cannot leak into another condition's state.
        scenario_states = {name: dict(values) for name, values in states.items()}
        for seed in heldout_seeds:
            nodes, events, truth = _world(seed)
            pending_rows: list[tuple[str, str, Observation, bool]] = []
            for use_annotations, use_feedback, name in configs:
                removed = _choose_removed(nodes, events, policy, scenario_states[name],
                    use_annotations=use_annotations,
                    annotation_corrupted=(scenario == "annotation_inversion"))
                proposal = _propose(nodes, events, removed, policy)
                pending_rows.append((name, proposal, removed, use_feedback))

            # The one-removal oracle uses the same policy and intervention
            # budget; it chooses only after evaluating each eligible proposal.
            oracle_candidates = []
            for event in events:
                candidate = _propose(nodes, events, event, policy)
                oracle_candidates.append((_utility(candidate, truth), event.variable, candidate, event))
            oracle_utility, _, oracle_proposal, oracle_removed = max(
                oracle_candidates, key=lambda row: (row[0], row[1]))
            for name, proposal, removed, use_feedback in pending_rows:
                utility = _utility(proposal, truth)
                rows.append({"scenario": scenario, "seed": seed, "arm": name,
                    "proposal": proposal, "utility": utility,
                    "proposal_correct": proposal == ("diagnose" if truth else "monitor"),
                    "removed_sensor": removed.variable,
                    "correct_memory_withheld": removed.value == truth,
                    "removal_budget": 1,
                    "annotation_score_before": scenario_states[name][removed.variable].score,
                    "feedback_corrupted": scenario == "feedback_inversion" and use_feedback,
                    "utility_oracle": oracle_utility,
                    "oracle_proposal": oracle_proposal,
                    "oracle_removed_sensor": oracle_removed.variable,
                    "oracle_exceeded": utility > oracle_utility + 1e-12})
            # Feedback arrives after every arm has committed its proposal.
            for name, proposal, removed, use_feedback in pending_rows:
                raw_reward = (_utility(proposal, truth) + 1.0) / 2.0 if use_feedback else None
                if raw_reward is not None and scenario == "feedback_inversion":
                    raw_reward = 1.0 - raw_reward
                scenario_states[name][removed.variable] = update_experience(
                    scenario_states[name][removed.variable], raw_reward)

    metrics: dict[str, Any] = {}
    for name in (config[2] for config in configs):
        clean = [row for row in rows if row["arm"] == name and row["scenario"] == "clean"]
        for scenario in SCENARIOS:
            selected = [row for row in rows if row["arm"] == name and row["scenario"] == scenario]
            utility_interval = _interval([float(row["utility"]) for row in selected])
            accuracy_interval = _interval([float(row["proposal_correct"]) for row in selected])
            withheld = sum(bool(row["correct_memory_withheld"]) for row in selected)
            metrics[f"{name}:{scenario}"] = {
                "n": len(selected), "mean_utility": utility_interval[0],
                "utility_normal_approx_95_interval": [utility_interval[1], utility_interval[2]],
                "proposal_accuracy": accuracy_interval[0],
                "accuracy_normal_approx_95_interval": [
                    max(0.0, accuracy_interval[1]), min(1.0, accuracy_interval[2])],
                "correct_memories_withheld": withheld,
                "correct_memory_withholding_rate": withheld / len(selected) if selected else 0.0}
        clean_utility = _interval([float(row["utility"]) for row in clean])[0]
        clean_accuracy = _interval([float(row["proposal_correct"]) for row in clean])[0]
        for challenge in SCENARIOS[1:]:
            challenged = [row for row in rows if row["arm"] == name
                          and row["scenario"] == challenge]
            challenge_utility = _interval([float(row["utility"]) for row in challenged])[0]
            challenge_accuracy = _interval([float(row["proposal_correct"]) for row in challenged])[0]
            metrics[f"{name}:robustness:{challenge}"] = {
                "n": len(challenged), "clean_minus_challenge_utility":
                    clean_utility - challenge_utility,
                "clean_minus_challenge_accuracy": clean_accuracy - challenge_accuracy}

    workload = json.dumps({"train": train_seeds, "heldout": heldout_seeds,
                           "scenarios": SCENARIOS}, separators=(",", ":")).encode()
    return {"schema": "cdm-trust-feedback-ablation-v1", "train_seeds": train_seeds,
        "heldout_seeds": heldout_seeds, "scenarios": SCENARIOS, "arms": [c[2] for c in configs],
        "rows": rows, "metrics": metrics, "train_final_annotations": trained,
        "workload_sha256": hashlib.sha256(workload).hexdigest(),
        "scope": "first-party synthetic factorial ablation; evaluator feedback is diagnostic only",
        "safety": {"authority_changes": 0, "network_calls": 0, "model_calls": 0,
                   "tool_calls": 0, "truth_visible_to_proposer": False},
        "oracle_exceeded": any(bool(row["oracle_exceeded"]) for row in rows),
        "limitations": ["Finite synthetic seeds; not population evidence.",
            "Correctness means sensor value agrees with evaluator-only latent truth.",
            "The one-removal ceiling is an in-simulator mechanism check, not a deployment oracle."]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="research/results/cdm/trust-feedback-ablation-r12")
    args = parser.parse_args()
    result = run()
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "report.json"
    csv_path = output / "rows.csv"
    markdown_path = output / "report.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result["rows"][0]))
        writer.writeheader()
        writer.writerows(result["rows"])
    lines = ["# CDM-R12 trust and evaluator-feedback ablation", "",
        "Frozen synthetic factorial comparison. Utility, robustness, and correct-memory withholding are separate metrics.",
        "", "## Held-out results", "",
        "| Arm | Condition | Mean utility (95% interval) | Proposal accuracy | Correct memories withheld |",
        "|---|---|---:|---:|---:|"]
    for arm in result["arms"]:
        for scenario in result["scenarios"]:
            metric = result["metrics"][f"{arm}:{scenario}"]
            interval = metric["utility_normal_approx_95_interval"]
            lines.append(f"| {arm} | {scenario} | {metric['mean_utility']:.3f} "
                f"[{interval[0]:.3f}, {interval[1]:.3f}] | {metric['proposal_accuracy']:.3f} | "
                f"{metric['correct_memories_withheld']}/{metric['n']} "
                f"({metric['correct_memory_withholding_rate']:.1%}) |")
    lines.extend(["", "## Paired robustness deltas", "",
        "Positive clean-minus-challenge values indicate lower utility or accuracy under the challenge.",
        "", "| Arm | Challenge | Utility change | Accuracy change |", "|---|---|---:|---:|"])
    for arm in result["arms"]:
        for challenge in result["scenarios"][1:]:
            metric = result["metrics"][f"{arm}:robustness:{challenge}"]
            lines.append(f"| {arm} | {challenge} | {metric['clean_minus_challenge_utility']:.3f} | "
                         f"{metric['clean_minus_challenge_accuracy']:.3f} |")
    lines.extend(["", "## Scope and safety", "",
        f"Seeds: training {result['train_seeds'][0]}–{result['train_seeds'][-1]}, held-out "
        f"{result['heldout_seeds'][0]}–{result['heldout_seeds'][-1]}; oracle exceeded: "
        f"{result['oracle_exceeded']}; safety: `{json.dumps(result['safety'], sort_keys=True)}`.",
        "", *[f"- {limitation}" for limitation in result["limitations"]], ""])
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    manifest = {key: value for key, value in result.items() if key != "rows"}
    manifest.update({"status": "PASS" if not result["oracle_exceeded"] else "FAIL",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "protocol_sha256": hashlib.sha256(Path("research/prereg/cdm-r12-trust-feedback-ablation.md").read_bytes()).hexdigest(),
        "report_sha256": hashlib.sha256(json_path.read_bytes()).hexdigest(),
        "summary_sha256": hashlib.sha256(markdown_path.read_bytes()).hexdigest(),
        "rows_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest()})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)
                                          + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0 if manifest["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
