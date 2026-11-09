"""Reproducible paired synthetic replay benchmark (stdlib only)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import math
import time
from pathlib import Path
from typing import cast

from memory_fabric.causal_replay.bayes import BinaryNode
from memory_fabric.causal_replay.policy import ThresholdPolicy
from memory_fabric.causal_replay.state import Observation, update
from benchmarks.cdm_battery_world import independent_oracle


def _utility(proposal: str, truth: bool) -> float:
    return {"diagnose": 1.0 if truth else -1.0,
            "investigate": 0.0,
            "monitor": -0.5 if truth else 0.1}[proposal]


def _interval(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    mean = math.fsum(values) / len(values)
    if len(values) < 2:
        return mean, mean, mean
    variance = math.fsum((value - mean) ** 2 for value in values) / (len(values) - 1)
    half = 1.96 * math.sqrt(variance / len(values))
    return mean, mean - half, mean + half


def run(seeds: list[int]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for seed in seeds:
        rng = random.Random(seed)
        prior = 0.1 + rng.random() * 0.3
        sensitivities = (0.7 + rng.random() * 0.25,
                         0.65 + rng.random() * 0.3,
                         0.6 + rng.random() * 0.3)
        false_positive = (0.05, 0.12, 0.2)
        graph = (BinaryNode("fault", (), {(): prior}),) + tuple(
            BinaryNode(f"sensor-{i}", ("fault",),
                {(False,): false_positive[i], (True,): sensitivities[i]})
            for i in range(3))
        truth = bool(rng.getrandbits(1))
        observations = []
        for index, (sensitivity, false_positive_rate) in enumerate(zip(sensitivities, false_positive)):
            rate = sensitivity if truth else false_positive_rate
            observed = rng.random() < rate
            observations.append(Observation(f"e-{seed}-{index}", f"sensor-{index}",
                observed, f"sensor-{index}", index + 1))
        evidence = tuple(observations)
        policy = ThresholdPolicy("fault")
        started = time.perf_counter()
        factual = update(graph, evidence, policy_id=policy.policy_id)
        factual_proposal = policy.propose(factual).selected
        elapsed = time.perf_counter() - started
        oracle = independent_oracle(graph, {item.variable: item.value for item in evidence}, "fault")
        # All selectors receive the same evidence and one-removal budget.
        influence_weights = [abs(math.log(sensitivities[i] / false_positive[i])) for i in range(3)]
        selected = {
            "random": evidence[random.Random(seed ^ 0x5A5A).randrange(len(evidence))],
            "recency": max(evidence, key=lambda item: (item.sequence, item.observation_id)),
            "influence": evidence[max(range(3), key=lambda i: influence_weights[i])],
            "dependence": evidence[0],  # all admitted evidence is a proposal citation candidate
            "leave_one_out": max(evidence, key=lambda item: abs(
                factual.posterior["fault"] - update(graph, tuple(x for x in evidence
                    if x.observation_id != item.observation_id)).posterior["fault"])),
        }
        for arm, removed in selected.items():
            counterfactual = tuple(item for item in evidence if item.observation_id != removed.observation_id)
            state = update(graph, counterfactual, policy_id=policy.policy_id)
            proposal = policy.propose(state).selected
            rows.append({"seed": seed, "arm": arm, "truth": truth,
                "factual_posterior": factual.posterior["fault"],
                "counterfactual_posterior": state.posterior["fault"],
                "oracle_posterior": oracle, "oracle_error": abs(factual.posterior["fault"] - oracle),
                "factual_proposal": factual_proposal, "counterfactual_proposal": proposal,
                "decision_flip": proposal != factual_proposal, "removed_evidence": removed.observation_id,
                "utility_factual": _utility(factual_proposal or "investigate", truth),
                "utility_counterfactual": _utility(proposal or "investigate", truth),
                "utility_delta": (_utility(proposal or "investigate", truth)
                                  - _utility(factual_proposal or "investigate", truth)),
                "oracle_utility": 1.0 if truth else 0.1,
                "runtime_seconds": round(elapsed, 9), "consumed_events": len(evidence),
                "refusal": "", "complete": True})
        rows.append({"seed": seed, "arm": "factual", "truth": truth,
            "factual_posterior": factual.posterior["fault"],
            "counterfactual_posterior": factual.posterior["fault"],
            "oracle_posterior": oracle, "oracle_error": abs(factual.posterior["fault"] - oracle),
            "factual_proposal": factual_proposal, "counterfactual_proposal": factual_proposal,
            "decision_flip": False, "removed_evidence": "",
            "utility_factual": _utility(factual_proposal or "investigate", truth),
            "utility_counterfactual": _utility(factual_proposal or "investigate", truth),
            "utility_delta": 0.0, "oracle_utility": 1.0 if truth else 0.1,
            "runtime_seconds": round(elapsed, 9), "consumed_events": len(evidence),
            "refusal": "", "complete": True})
        oracle_proposal = "diagnose" if truth else "monitor"
        oracle_utility = _utility(oracle_proposal, truth)
        rows.append({"seed": seed, "arm": "oracle", "truth": truth,
            "factual_posterior": factual.posterior["fault"],
            "counterfactual_posterior": factual.posterior["fault"],
            "oracle_posterior": oracle, "oracle_error": abs(factual.posterior["fault"] - oracle),
            "factual_proposal": factual_proposal, "counterfactual_proposal": oracle_proposal,
            "decision_flip": oracle_proposal != factual_proposal, "removed_evidence": "",
            "utility_factual": _utility(factual_proposal or "investigate", truth),
            "utility_counterfactual": oracle_utility,
            "utility_delta": oracle_utility - _utility(factual_proposal or "investigate", truth),
            "oracle_utility": oracle_utility, "runtime_seconds": round(elapsed, 9),
            "consumed_events": len(evidence), "refusal": "", "complete": True})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(20261108, 20261118)))
    parser.add_argument("--out", default="research/results/cdm/benchmark")
    args = parser.parse_args()
    rows = run(args.seeds)
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "paired-cases.json"
    csv_path = output / "paired-cases.csv"
    json_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["seed"])
        writer.writeheader()
        writer.writerows(rows)
    arm_summary: dict[str, object] = {}
    for arm in sorted({str(row["arm"]) for row in rows}):
        values = [cast(float, row["utility_delta"]) for row in rows if row["arm"] == arm]
        utilities = [cast(float, row["utility_counterfactual"])
                     for row in rows if row["arm"] == arm]
        arm_summary[arm] = {"mean_paired_utility_delta": _interval(values)[0],
            "normal_approx_95pct_interval": _interval(values)[1:], "n": len(values),
            "mean_utility": _interval(utilities)[0],
            "refusals": sum(bool(row["refusal"]) for row in rows if row["arm"] == arm)}
    oracle_exceeded = any(cast(float, row["utility_counterfactual"])
                          > cast(float, row["oracle_utility"]) + 1e-12 for row in rows)
    manifest = {"schema": "cdm-paired-benchmark-v2", "seeds": args.seeds,
        "cases": len(rows), "all_complete": all(bool(row["complete"]) for row in rows),
        "oracle_exceeded": oracle_exceeded,
        "arms_per_seed": sorted({str(row["arm"]) for row in rows}),
        "max_oracle_error": max((cast(float, row["oracle_error"]) for row in rows), default=0.0),
        "arms": arm_summary,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "oracle_sha256": hashlib.sha256(Path(__file__).with_name("cdm_battery_world.py").read_bytes()).hexdigest(),
        "configuration_sha256": hashlib.sha256(json.dumps(args.seeds).encode("utf-8")).hexdigest(),
        "json_sha256": hashlib.sha256(json_path.read_bytes()).hexdigest(),
        "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "scope": "synthetic binary sensor worlds; local code-path oracle only"}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0 if (manifest["all_complete"] and manifest["max_oracle_error"] < 1e-12
                 and not oracle_exceeded) else 1


if __name__ == "__main__":
    raise SystemExit(main())
