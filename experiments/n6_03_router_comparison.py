"""Compare local deterministic routing with simulated probability sources."""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric.decision_models import (  # noqa: E402
    CallableDecisionModel,
    DecisionContext,
    DecisionOption,
    EscalationPolicy,
    route_decision,
)
from memory_fabric.decision_router import RoutingFeatures, route_system  # noqa: E402

SEED = 60_301
TASKS = 2_000
HAZARD_RATE = 0.25
OPTIONS = (
    DecisionOption("system1", "Use local deterministic reasoning"),
    DecisionOption("system2", "Escalate", action="system2"),
)
POLICY = EscalationPolicy(min_confidence=0.8, max_entropy=0.5,
                          consequential_actions=frozenset({"system2"}))


def _features(hazard: bool) -> RoutingFeatures:
    return RoutingFeatures(
        risk="high" if hazard else "low",
        evidence_gaps=1 if hazard else 0,
        tool_class="execute" if hazard else "read",
        system2_budget_tokens=256,
        estimated_system2_tokens=128,
    )


def _proposal(probability_system2: float, reorder_options: bool = False) -> bool:
    probabilities = {"system1": 1.0 - probability_system2,
                     "system2": probability_system2}
    if reorder_options:
        probabilities = dict(reversed(list(probabilities.items())))
    model = CallableDecisionModel("simulated-probability-source", lambda _ctx: probabilities)
    options = tuple(reversed(OPTIONS)) if reorder_options else OPTIONS
    proposal = route_decision(model, DecisionContext("route task", options), POLICY)
    return proposal.requires_system2


def _score(hazards: list[bool], routes: list[bool]) -> dict[str, Any]:
    unsafe = sum(hazard and not route for hazard, route in zip(hazards, routes, strict=True))
    unnecessary = sum(not hazard and route for hazard, route in zip(hazards, routes, strict=True))
    correct = len(hazards) - unsafe - unnecessary
    utility = sum((1.0 if not hazard and not route else
                   0.5 if hazard and route else
                   0.2 if not hazard and route else -5.0)
                  for hazard, route in zip(hazards, routes, strict=True)) / len(hazards)
    hazard_count = sum(hazards)
    return {
        "tasks": len(hazards), "hazard_tasks": hazard_count,
        "unsafe_system1_count": unsafe,
        "unsafe_system1_rate": unsafe / hazard_count if hazard_count else 0.0,
        "unnecessary_system2_count": unnecessary,
        "correct_route_rate": correct / len(hazards),
        "mean_utility": utility,
    }


def run(tasks: int = TASKS, seed: int = SEED) -> dict[str, Any]:
    if tasks < 1:
        raise ValueError("tasks must be positive")
    started = time.perf_counter()
    rng = random.Random(seed)
    hazards = [rng.random() < HAZARD_RATE for _ in range(tasks)]
    deterministic = [route_system(_features(hazard)).route == "system2" for hazard in hazards]
    calibrated = [_proposal(0.9 if hazard else 0.1) for hazard in hazards]
    overconfident_reversed = [_proposal(0.01 if hazard else 0.99) for hazard in hazards]
    reordered = [_proposal(0.9 if hazard else 0.1, reorder_options=True)
                 for hazard in hazards]
    policies = {
        "deterministic_local_features": deterministic,
        "simulated_calibrated_probabilities": calibrated,
        "simulated_overconfident_reversed_probabilities": overconfident_reversed,
        "calibrated_probabilities_reordered_mapping": reordered,
    }
    metrics = {name: _score(hazards, routes) for name, routes in policies.items()}
    baseline = metrics["simulated_calibrated_probabilities"]
    local = metrics["deterministic_local_features"]
    adversarial = metrics["simulated_overconfident_reversed_probabilities"]
    result = {
        "schema": "memory-fabric-n6-03-router-comparison/1",
        "task_id": "N6-03", "evidence_level": "SIMULATED",
        "acceptance_passed": (
            local["unsafe_system1_count"] == 0
            and local["mean_utility"] >= baseline["mean_utility"]
            and local["unsafe_system1_count"] < adversarial["unsafe_system1_count"]
            and local["mean_utility"] > adversarial["mean_utility"]
            and policies["simulated_calibrated_probabilities"] == policies[
                "calibrated_probabilities_reordered_mapping"]
        ),
        "protocol": {"seed": seed, "tasks": tasks, "hazard_rate": HAZARD_RATE,
                     "hazard_definition": "high risk OR evidence gap OR consequential tool",
                     "budget_tokens": 256, "estimated_system2_tokens": 128,
                     "probability_cases": {"calibrated": [0.9, 0.1],
                                           "overconfident_reversed": [0.01, 0.99]},
                     "route_thresholds": {"min_confidence": 0.8, "max_entropy": 0.5}},
        "metrics": metrics,
        "paired_differences": {
            "unsafe_avoided_vs_overconfident_reversed": (
                adversarial["unsafe_system1_count"] - local["unsafe_system1_count"]),
            "utility_gain_vs_overconfident_reversed": (
                local["mean_utility"] - adversarial["mean_utility"]),
            "calibrated_mapping_order_invariant": (
                policies["simulated_calibrated_probabilities"] == policies[
                    "calibrated_probabilities_reordered_mapping"]),
        },
        "source": {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                               check=True, capture_output=True,
                                               text=True).stdout.strip(),
                   "dirty_before_result_write": bool(subprocess.run(
                       ["git", "status", "--porcelain"], cwd=ROOT, check=True,
                       capture_output=True, text=True).stdout.strip()),
                   "experiment_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "runtime_seconds": round(time.perf_counter() - started, 3),
        "limitations": [
            "Hazard labels and local features are generated from the same synthetic ground truth, giving the deterministic router an idealized feature signal.",
            "The calibrated and overconfident sources are fixed probability fixtures, not fitted real-model calibration curves.",
            "Option tuple and keyed mapping insertion order are reversed together; semantic option/probability misbinding is not treated as a valid typed output.",
            "Utility weights are declared synthetic costs and do not estimate deployment values or safety risk in a real workflow.",
        ],
    }
    result["runtime_seconds"] = round(time.perf_counter() - started, 3)
    return result


def write_result(report: dict[str, Any]) -> None:
    path = ROOT / "research" / "results" / "n6-03-router-comparison.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    result = run()
    write_result(result)
    print(json.dumps({"task_id": "N6-03", "metrics": result["metrics"],
                      "acceptance_passed": result["acceptance_passed"]}, indent=2))
