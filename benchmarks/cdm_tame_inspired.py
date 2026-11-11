"""Prequential first-party TAME-inspired comparator; not an official reproduction."""

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

TRAIN_SEEDS = tuple(range(20261201, 20261211))
HELDOUT_SEEDS = tuple(range(20261211, 20261221))


@dataclass(frozen=True)
class Experience:
    score: float = 0.5
    count: int = 0


def update_experience(state: Experience, reward: float | None, *,
                      alpha: float = 0.1, max_experiences: int = 20) -> Experience:
    if (not math.isfinite(state.score) or not 0 <= state.score <= 1
            or type(state.count) is not int or state.count < 0
            or not 0 < alpha <= 1 or type(max_experiences) is not int
            or max_experiences < 1):
        raise ValueError("invalid TAME-inspired experience state or hyperparameter")
    if reward is None:
        return state
    if not math.isfinite(reward) or not 0 <= reward <= 1:
        raise ValueError("normalized evaluator reward must be in [0,1]")
    if state.count >= max_experiences:
        return state
    return Experience(min(1.0, max(0.0, state.score + alpha * (reward - state.score))),
                      state.count + 1)


def _world(seed: int):
    rng = random.Random(seed)
    prior = 0.1 + rng.random() * 0.3
    sensitivity = tuple(0.7 + rng.random() * 0.25 for _ in range(3))
    false_positive = (0.05, 0.12, 0.2)
    nodes = (BinaryNode("fault", (), {(): prior}),) + tuple(
        BinaryNode(f"sensor-{index}", ("fault",),
                   {(False,): false_positive[index], (True,): sensitivity[index]})
        for index in range(3))
    truth = bool(rng.getrandbits(1))
    events = tuple(Observation(f"e-{seed}-{index}", f"sensor-{index}",
        rng.random() < (sensitivity[index] if truth else false_positive[index]),
        f"sensor-{index}", index + 1) for index in range(3))
    return nodes, truth, events


def _utility(proposal: str, truth: bool) -> float:
    return {"diagnose": 1.0 if truth else -1.0,
            "investigate": 0.0,
            "monitor": -0.5 if truth else 0.1}[proposal]


def run(train_seeds: tuple[int, ...] = TRAIN_SEEDS,
        heldout_seeds: tuple[int, ...] = HELDOUT_SEEDS) -> dict[str, Any]:
    if set(train_seeds) & set(heldout_seeds) or not train_seeds or not heldout_seeds:
        raise ValueError("training and held-out seed lists must be non-empty and disjoint")
    trust = {f"sensor-{index}": Experience() for index in range(3)}
    rows: list[dict[str, Any]] = []

    def episode(seed: int, split: str, *, learn: bool) -> None:
        nonlocal trust
        nodes, truth, events = _world(seed)
        policy = ThresholdPolicy("fault")
        factual = update(nodes, events, policy_id=policy.policy_id)
        factual_proposal = policy.propose(factual).selected or "investigate"
        loo_scores = []
        for item in events:
            rest = tuple(other for other in events if other.observation_id != item.observation_id)
            state = update(nodes, rest, policy_id=policy.policy_id)
            loo_scores.append(abs(factual.posterior["fault"] - state.posterior["fault"]))
        selected = {
            "tame_inspired": max(events, key=lambda item: (trust[item.variable].score,
                                                            item.variable)),
            "random": events[random.Random(seed ^ 0x4C4F).randrange(len(events))],
            "recency": max(events, key=lambda item: (item.sequence, item.observation_id)),
            "leave_one_out": events[max(range(len(events)), key=lambda index: loo_scores[index])],
        }
        proposals: dict[str, str] = {"factual": factual_proposal}
        for arm, removed in selected.items():
            changed = tuple(item for item in events if item.observation_id != removed.observation_id)
            state = update(nodes, changed, policy_id=policy.policy_id)
            proposals[arm] = policy.propose(state).selected or "investigate"
        proposals["oracle"] = "diagnose" if truth else "monitor"
        for arm, proposal in proposals.items():
            utility = _utility(proposal, truth)
            rows.append({"split": split, "seed": seed, "arm": arm, "truth": truth,
                "proposal": proposal, "utility": utility,
                "factual_proposal": factual_proposal,
                "decision_flip": proposal != factual_proposal,
                "removed_evidence": selected[arm].observation_id if arm in selected else "",
                "removal_budget": 1 if arm in selected else 0,
                "tame_annotation_score_before": trust[selected[arm].variable].score
                    if arm in selected else None,
                "tame_experience_before": trust[selected[arm].variable].count
                    if arm in selected else None,
                "outcome_revealed_after_proposal": True, "complete": True})
        # Evaluator feedback updates only diagnostic baseline state after all
        # proposals for this episode; it never changes Memory Fabric authority.
        if learn:
            chosen = selected["tame_inspired"]
            normalized_reward = (_utility(proposals["tame_inspired"], truth) + 1.0) / 2.0
            trust[chosen.variable] = update_experience(trust[chosen.variable], normalized_reward)

    for seed in train_seeds:
        episode(seed, "train", learn=True)
    train_state = {key: {"score": value.score, "count": value.count}
                   for key, value in sorted(trust.items())}
    for seed in heldout_seeds:
        episode(seed, "heldout_prequential", learn=True)
    summary = {}
    for split in ("train", "heldout_prequential"):
        for arm in sorted({row["arm"] for row in rows}):
            values = [row["utility"] for row in rows if row["split"] == split and row["arm"] == arm]
            if not values:
                continue
            mean = math.fsum(values) / len(values)
            if len(values) > 1:
                sd = math.sqrt(math.fsum((value - mean) ** 2 for value in values)
                               / (len(values) - 1))
                half = 1.96 * sd / math.sqrt(len(values))
            else:
                half = 0.0
            summary[f"{split}:{arm}"] = {"n": len(values), "mean_utility": mean,
                                         "normal_approx_95_interval": [mean-half, mean+half]}
    paired_summary = {}
    for arm in sorted({str(row["arm"]) for row in rows if row["arm"] != "oracle"}):
        for split in ("train", "heldout_prequential"):
            by_seed = {int(row["seed"]): float(row["utility"]) for row in rows
                       if row["split"] == split and row["arm"] == arm}
            factual_by_seed = {int(row["seed"]): float(row["utility"]) for row in rows
                               if row["split"] == split and row["arm"] == "factual"}
            paired = [by_seed[seed] - factual_by_seed[seed]
                      for seed in sorted(set(by_seed) & set(factual_by_seed))]
            mean = math.fsum(paired) / len(paired) if paired else 0.0
            if len(paired) > 1:
                sd = math.sqrt(math.fsum((value - mean) ** 2 for value in paired)
                               / (len(paired) - 1))
                half = 1.96 * sd / math.sqrt(len(paired))
            else:
                half = 0.0
            paired_summary[f"{split}:{arm}-minus-factual"] = {
                "n": len(paired), "mean_difference": mean,
                "normal_approx_95_interval": [mean-half, mean+half]}
    workload = json.dumps({"train": train_seeds, "heldout": heldout_seeds},
                          separators=(",", ":")).encode()
    return {"schema": "cdm-tame-inspired-v1", "train_seeds": train_seeds,
        "heldout_seeds": heldout_seeds, "train_final_annotations": train_state,
        "final_annotations": {key: {"score": value.score, "count": value.count}
                               for key, value in sorted(trust.items())},
        "rows": rows, "summary": summary, "paired_summary": paired_summary,
        "workload_sha256": hashlib.sha256(workload).hexdigest(),
        "scope": "first-party conceptual baseline; synthetic prequential heldout; not official TAME reproduction",
        "safety": {"authority_changes": 0, "network_calls": 0, "tool_calls": 0}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="research/results/cdm/tame-inspired")
    args = parser.parse_args()
    result = run()
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "cases.json"
    csv_path = output / "cases.csv"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = result["rows"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {key: value for key, value in result.items()
                if key not in {"rows", "summary"}}
    manifest.update({"source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "json_sha256": hashlib.sha256(json_path.read_bytes()).hexdigest(),
        "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(), "summary": result["summary"]})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)
                                           + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
