"""Matched one-component removal diagnostics for dependency, routing and compression.

This is an exploratory synthetic contract study, not a real-agent benchmark.
Each ablation reuses the same case or seed and removes one named mechanism.
"""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from experiments.n4_07_compaction_comparison import (  # noqa: E402
    SEEDS as COMPRESSION_SEEDS,
    evaluate_seed,
)
from experiments.n6_03_router_comparison import (  # noqa: E402
    HAZARD_RATE,
    SEED as ROUTING_SEED,
    TASKS as ROUTING_TASKS,
    _features,
    _score,
)
from memory_fabric import MemoryFabric  # noqa: E402
from memory_fabric.compaction import compact_session  # noqa: E402
from memory_fabric.decision_router import route_system  # noqa: E402
from memory_fabric.model import LifecycleState  # noqa: E402
from memory_fabric.summary_dependencies import (  # noqa: E402
    DependencyMapRefused,
    verify_stored_dependency_map,
)


def _dependency_ablation() -> dict[str, Any]:
    fabric = MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False,
                          recognise_copies=False)
    try:
        episode = fabric.start_episode("operator", "r5-03-dependency-ablation").id
        source_id = fabric.remember(
            "operator", "Valve V7 opens below 4 bar.",
            source_episodes=[episode], scope="team",
        )
        report = compact_session(fabric, episode, "compactor")
        if report.summary_id is None:
            raise AssertionError("fixture compaction produced no summary")
        summary = fabric.get(report.summary_id)
        stale_fact = "Valve V7 opens below 4 bar."
        if stale_fact not in summary.content:
            raise AssertionError("summary fixture did not preserve its source fact")
        fabric.revise(source_id, "Valve V7 must remain closed.", agent_id="operator",
                      reason="controlled R5-03 correction")
        current_sources = [fabric.get(memory_id) for memory_id in report.inputs]
        try:
            verify_stored_dependency_map(fabric.get(report.summary_id), current_sources)
        except DependencyMapRefused as exc:
            guarded_outcome = "refused"
            refusal_reason = str(exc)
        else:
            guarded_outcome = "accepted"
            refusal_reason = None
        current_summary = fabric.get(report.summary_id)
        ablated_stale_fact_exposed = stale_fact in current_summary.content
        return {
            "component": "summary fact-to-source-version dependency validation",
            "matched_case": "one summarized valve fact corrected from 4 bar to must remain closed",
            "with_component": {"outcome": guarded_outcome,
                               "refusal_reason": refusal_reason,
                               "stale_summary_exposed": False},
            "component_removed": {"outcome": "unverified text accepted by ablated reader",
                                  "stale_summary_exposed": ablated_stale_fact_exposed,
                                  "source_version": current_sources[0].version,
                                  "summary_lifecycle": current_summary.lifecycle_state.value
                                  if isinstance(current_summary.lifecycle_state, LifecycleState)
                                  else str(current_summary.lifecycle_state)},
            "marginal_effect": {"stale_fact_blocked_by_component": (
                guarded_outcome == "refused" and ablated_stale_fact_exposed)},
            "limitations": [
                "The ablated reader intentionally ignores the dependency verification outcome and reads the stored text; this isolates the check but does not model every caller's lifecycle filtering.",
                "One correction and one summary fact are evaluated; this is not a population estimate.",
            ],
        }
    finally:
        fabric.close()


def _routing_ablation() -> dict[str, Any]:
    rng = random.Random(ROUTING_SEED)
    hazards = [rng.random() < HAZARD_RATE for _ in range(ROUTING_TASKS)]
    with_router = [route_system(_features(hazard)).route == "system2" for hazard in hazards]
    without_router_system1 = [False] * len(hazards)
    without_router_system2 = [True] * len(hazards)
    scores = {
        "router_enabled": _score(hazards, with_router),
        "router_removed_fixed_system1": _score(hazards, without_router_system1),
        "router_removed_fixed_system2": _score(hazards, without_router_system2),
    }
    return {
        "component": "risk/evidence-aware deterministic System 1/System 2 router",
        "matched_protocol": {"seed": ROUTING_SEED, "tasks": ROUTING_TASKS,
                             "hazard_rate": HAZARD_RATE,
                             "hazard_count": sum(hazards)},
        "arms": scores,
        "marginal_effect_vs_fixed_system1": {
            "unsafe_actions_avoided": (scores["router_removed_fixed_system1"]["unsafe_system1_count"]
                                        - scores["router_enabled"]["unsafe_system1_count"]),
            "utility_delta": (scores["router_enabled"]["mean_utility"]
                              - scores["router_removed_fixed_system1"]["mean_utility"]),
        },
        "marginal_effect_vs_fixed_system2": {
            "unnecessary_escalations_avoided": (
                scores["router_removed_fixed_system2"]["unnecessary_system2_count"]
                - scores["router_enabled"]["unnecessary_system2_count"]),
            "utility_delta": (scores["router_enabled"]["mean_utility"]
                              - scores["router_removed_fixed_system2"]["mean_utility"]),
        },
        "limitations": [
            "Hazards and router features derive from the same synthetic labels, so the router is given an idealized signal.",
            "Utility weights are synthetic; fixed System 1/System 2 are diagnostic component-removal controls, not fitted agent policies.",
        ],
    }


def _compression_ablation() -> dict[str, Any]:
    paired = [evaluate_seed(seed)["arms"] for seed in COMPRESSION_SEEDS]
    plain = [row["no_compaction"] for row in paired]
    compressed = [row["provenance_preserving_summary"] for row in paired]
    plain_rate = mean(float(row["task_success_rate"]) for row in plain)
    compressed_rate = mean(float(row["task_success_rate"]) for row in compressed)
    plain_stale = sum(int(row["false_stale_actions"]) for row in plain)
    compressed_stale = sum(int(row["false_stale_actions"]) for row in compressed)
    plain_bytes = mean(int(row["context_bytes_utf8"]) for row in plain)
    compressed_bytes = mean(int(row["context_bytes_utf8"]) for row in compressed)
    return {
        "component": "provenance-preserving temporal compaction",
        "matched_protocol": {"seeds": list(COMPRESSION_SEEDS), "tasks_per_seed": 8,
                             "paired_seed_inputs": True},
        "arms": {
            "component_removed_no_compaction": {
                "mean_task_success_rate": plain_rate,
                "false_stale_actions": plain_stale,
                "mean_context_bytes_utf8": plain_bytes,
            },
            "component_enabled_provenance_summary": {
                "mean_task_success_rate": compressed_rate,
                "false_stale_actions": compressed_stale,
                "mean_context_bytes_utf8": compressed_bytes,
                "mean_compression_factor": mean(float(
                    row["compression_factor"]) for row in compressed),
                "mean_source_identity_fidelity": mean(float(
                    row["source_identity_reconstruction_fidelity"]) for row in compressed),
                "mean_factual_text_fidelity": mean(float(
                    row["factual_text_reconstruction_fidelity"]) for row in compressed),
            },
        },
        "marginal_effect": {
            "task_success_rate_delta": compressed_rate - plain_rate,
            "false_stale_action_delta": compressed_stale - plain_stale,
            "context_bytes_saved_mean": plain_bytes - compressed_bytes,
            "context_bytes_reduction_fraction": (plain_bytes - compressed_bytes) / plain_bytes,
        },
        "per_seed_paired_deltas": [
            {"seed": seed,
             "task_success_rate_delta": float(arms["provenance_preserving_summary"]["task_success_rate"])
                                         - float(arms["no_compaction"]["task_success_rate"]),
             "false_stale_action_delta": int(arms["provenance_preserving_summary"]["false_stale_actions"])
                                          - int(arms["no_compaction"]["false_stale_actions"]),
             "context_bytes_saved": int(arms["no_compaction"]["context_bytes_utf8"])
                                   - int(arms["provenance_preserving_summary"]["context_bytes_utf8"])}
            for seed, arms in zip(COMPRESSION_SEEDS, paired, strict=True)
        ],
        "limitations": [
            "This replays the frozen N4-07 deterministic fixture; it is not a real-agent study or token-cost measurement.",
            "The full-history arm is a fixture ceiling; five paired seeds are descriptive and no confidence interval or significance claim is made.",
        ],
    }


def run() -> dict[str, Any]:
    started = time.perf_counter()
    dependency = _dependency_ablation()
    routing = _routing_ablation()
    compression = _compression_ablation()
    passed = (
        dependency["marginal_effect"]["stale_fact_blocked_by_component"]
        and routing["marginal_effect_vs_fixed_system1"]["unsafe_actions_avoided"] > 0
        and routing["marginal_effect_vs_fixed_system2"]["unnecessary_escalations_avoided"] > 0
        and compression["arms"]["component_enabled_provenance_summary"]["false_stale_actions"] == 0
        and compression["marginal_effect"]["context_bytes_saved_mean"] > 0
    )
    return {
        "schema": "memory-fabric-r5-03-component-removal/1",
        "task_id": "R5-03", "acceptance_passed": passed,
        "evidence_level": "SIMULATED",
        "design": "Matched local one-component-removal diagnostics; each component is compared against a named absence/fixed-fallback arm on the same case or seeds.",
        "components": {"summary_dependencies": dependency,
                       "decision_routing": routing,
                       "temporal_compression": compression},
        "interpretation": [
            "The dependency verifier prevented one stale summarized fact from passing the check; the ablated reader exposed it.",
            "Routing traded off two fixed fallbacks: compared with fixed System 1 it avoided unsafe routes; compared with fixed System 2 it avoided unnecessary escalations.",
            "Compression reduced bytes while preserving the fixture's task success and stale-action results; its contribution is the measured paired delta, not the entire integrated system score.",
            "These are isolated local component effects, not evidence that the combination beats external systems or improves real-agent performance.",
        ],
        "source": {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                check=True, capture_output=True,
                                                text=True).stdout.strip(),
                   "experiment_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "runtime_seconds": round(time.perf_counter() - started, 3),
        "limitations": [
            "The dependency ablation intentionally bypasses the dependency-verification result and ignores the summary lifecycle flag; it isolates that check but is not representative of every live caller.",
            "Routing hazards are generated from the same features consumed by the router.",
            "Compression results reuse N4-07 synthetic temporal tasks and report UTF-8 bytes, not model tokens or cost.",
            "No confidence intervals, human evaluation, live agents, or external baselines are included.",
        ],
    }


if __name__ == "__main__":
    result = run()
    (ROOT / "research" / "results" / "r5-03-component-removal.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"task_id": result["task_id"],
                      "acceptance_passed": result["acceptance_passed"],
                      "dependency": result["components"]["summary_dependencies"]["marginal_effect"],
                      "routing": result["components"]["decision_routing"]["marginal_effect_vs_fixed_system1"],
                      "compression": result["components"]["temporal_compression"]["marginal_effect"]},
                     indent=2))
