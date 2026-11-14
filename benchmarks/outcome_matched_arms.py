#!/usr/bin/env python3
"""Measure scripted outcome-runtime latency under OS process scheduling.

This is a local CPU-contention probe, not an estimate of production or model
latency. Submit-to-result time includes process queueing and serialization.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Mapping

# Let the repository benchmark run directly from a source checkout as well as
# from an installed environment.
_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from benchmarks.agent_scale import outcome_task_manifest  # noqa: E402
from benchmarks.matched_agent_arms import ARMS as LEGACY_ARMS  # noqa: E402
from benchmarks.matched_agent_arms import run as run_legacy_arm  # noqa: E402
from benchmarks.manifest import capture_environment, head  # noqa: E402
from benchmarks.outcome_agents import InvalidModelStep, OllamaOutcomePlanner  # noqa: E402
from memory_fabric.agent_outcomes.observations import AgentObservation, AgentStep  # noqa: E402
from memory_fabric.agent_outcomes.runtime import AgentRuntime, ToolOutput  # noqa: E402
from memory_fabric import MemoryFabric  # noqa: E402

RETRIEVAL_BASELINE_ARMS = ("recency", "lexical", "full_context", "governed_memory")
RETRIEVAL_CONTEXT_BUDGET_TOKENS = 12


def build_retrieval_baseline_comparison(*, seed: int) -> dict[str, Any]:
    """Compare common-pool retrieval policies under one equal token cap.

    Outcomes are target-evidence inclusion only. The comparison is descriptive
    and deliberately does not feed the agent task-completion estimate.
    """
    tasks = outcome_task_manifest(seed)
    task_rows: list[dict[str, Any]] = []
    selected_by_arm: dict[str, list[int]] = {arm: [] for arm in RETRIEVAL_BASELINE_ARMS}
    with MemoryFabric(":memory:", recognise_copies=False, encrypt_content=False,
                      hold_suspicious=False) as fabric:
        for task in tasks:
            case_key = task["task_id"].replace("-", "").upper()
            query = f"Record {case_key} status code"
            target = f"Record {case_key} status code is 1."
            corpus = [
                ("target", target),
                ("note-a", f"Record {case_key} was reviewed by operations."),
                ("note-b", f"Status code for unrelated ticket {case_key} is pending."),
                ("note-c", f"Archive record {case_key} status was checked last week."),
            ]
            ids: dict[str, str] = {}
            for name, content in corpus:
                memory_id = fabric.remember(name, content, scope="team", auto_activate=True)
                fabric.elevate(memory_id, approver="reviewer", reason="benchmark fixture checked")
                ids[name] = memory_id

            # Every strategy receives the same active, governed, task-local pool.
            eligible_ids = tuple(ids.values())
            lexical_hits = fabric.retrieve(
                "retrieval-baseline", query, k=len(eligible_ids), min_relevance=0.0,
                within=eligible_ids, method="lexical", group_by_source_root=False,
                expand_lineage=0,
            ).exposed
            governed_hits = fabric.retrieve(
                "retrieval-baseline", query, k=len(eligible_ids), min_relevance=0.0,
                within=eligible_ids, group_by_source_root=False, expand_lineage=0,
            ).exposed
            visible = {memory.id: memory for memory in fabric.state.memories.values()
                       if memory.id in eligible_ids}
            ranked: dict[str, list[str]] = {
                "recency": sorted(eligible_ids,
                                  key=lambda mid: (-visible[mid].created_at, mid)),
                "lexical": [memory.id for memory in lexical_hits],
                # Full-context traverses the complete eligible pool in a
                # label-blind canonical content order, subject to the same cap.
                "full_context": sorted(eligible_ids,
                                       key=lambda mid: (hashlib.sha256(
                                           visible[mid].content.encode("utf-8")).hexdigest(), mid)),
                "governed_memory": [memory.id for memory in governed_hits],
            }

            def pack(order: list[str]) -> tuple[list[str], int]:
                chosen: list[str] = []
                tokens = 0
                for memory_id in order:
                    cost = len(visible[memory_id].content.split())
                    if tokens + cost <= RETRIEVAL_CONTEXT_BUDGET_TOKENS:
                        chosen.append(memory_id)
                        tokens += cost
                return chosen, tokens

            arms: dict[str, Any] = {}
            for arm in RETRIEVAL_BASELINE_ARMS:
                chosen, token_count = pack(ranked[arm])
                found = ids["target"] in chosen
                selected_by_arm[arm].append(int(found))
                arms[arm] = {
                    "selected_ids": chosen,
                    "target_evidence_included": found,
                    "tokens_exposed": token_count,
                    "token_budget": RETRIEVAL_CONTEXT_BUDGET_TOKENS,
                }
            task_rows.append({
                "task_id": task["task_id"],
                "eligible_candidate_count": len(eligible_ids),
                "eligible_pool_sha256": hashlib.sha256(
                    "\n".join(sorted(eligible_ids)).encode("utf-8")).hexdigest(),
                "arms": arms,
            })

    recall = {arm: sum(values) / len(tasks)
              for arm, values in selected_by_arm.items()}
    paired_gaps = {arm: recall[arm] - recall["governed_memory"]
                   for arm in RETRIEVAL_BASELINE_ARMS if arm != "governed_memory"}
    return {
        "status": "DESCRIPTIVE_NOT_CONFIRMATORY",
        "unit": "matched task fixture",
        "arms": list(RETRIEVAL_BASELINE_ARMS),
        "candidate_pool": "identical task-local eligible active and reviewed memories",
        "resource_budget": {"context_tokens_max": RETRIEVAL_CONTEXT_BUDGET_TOKENS,
                             "selection_passes_per_arm": 1},
        "parity": {
            "same_task_ids": True,
            "same_candidate_pool_per_task": True,
            "same_context_token_budget": True,
            "full_context_is_budgeted": True,
        },
        "target_evidence_recall": recall,
        "paired_difference_vs_governed_memory": paired_gaps,
        "inference": "NONE; do not infer improvement from these scripted fixtures",
        "task_rows": task_rows,
    }

OUTCOME_ARMS = (
    {"id": "A0", "name": "no_memory", "legacy_arm": "no_memory", "status": "RUN"},
    {"id": "A1", "name": "local_only", "legacy_arm": "isolated", "status": "RUN"},
    {"id": "A2", "name": "pooled_shared", "legacy_arm": "pooled_shared", "status": "RUN"},
    {"id": "A3", "name": "pooled_shared_plus_recovery",
     "legacy_arm": "pooled_shared_plus_recovery", "status": "RUN"},
    {"id": "A4", "name": "memory_fabric", "legacy_arm": "memory_fabric", "status": "RUN"},
    {"id": "A5", "name": "memory_fabric_recovery",
     "legacy_arm": "memory_fabric_recovery", "status": "RUN"},
    {"id": "A6", "name": "memory_fabric_recovery_cdm", "legacy_arm": None,
     "status": "NOT_RUN"},
    {"id": "A7", "name": "oracle", "legacy_arm": "oracle", "status": "RUN"},
)


def run_paired_model_proposals(
    planner: OllamaOutcomePlanner,
    observations: Mapping[str, AgentObservation],
) -> dict[str, Any]:
    """Run the same pinned prompt and decoding budget once per matched arm.

    Across arms, only ``visible_events`` may differ. Requests execute
    sequentially through one planner/client so a local checkpoint is shared.
    This records model proposals only; it does not grade or execute effects.
    """
    if not isinstance(planner, OllamaOutcomePlanner):
        raise TypeError("planner must be an OllamaOutcomePlanner")
    if planner.model_digest is None or planner.quantization is None:
        raise ValueError("paired local-model runs require a pinned digest and quantization")
    if not isinstance(observations, Mapping) or len(observations) < 2:
        raise ValueError("at least two arm observations are required")
    if any(not isinstance(arm, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", arm)
           for arm in observations):
        raise ValueError("arm IDs must be stable short identifiers")
    if any(not isinstance(item, AgentObservation) for item in observations.values()):
        raise TypeError("every arm must supply an AgentObservation")

    first = next(iter(observations.values()))
    common = (first.task_id, first.instruction, first.permitted_tools,
              first.budget, first.schema_id)
    if any((item.task_id, item.instruction, item.permitted_tools,
            item.budget, item.schema_id) != common
           for item in observations.values()):
        raise ValueError(
            "paired arms must share task, instruction, tools, and budgets; only evidence may vary"
        )

    def digest(value: Any) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    schema_hashes = {arm: digest(planner.response_schema(item))
                     for arm, item in observations.items()}
    if len(set(schema_hashes.values())) != 1:
        raise ValueError("paired arms must receive the same constrained output schema")
    system_prompt_hash = hashlib.sha256(planner.SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    usage = getattr(planner.client, "usage", None)
    arm_results: list[dict[str, Any]] = []
    for arm, observation in observations.items():
        usage_before = usage() if callable(usage) else None
        counters_before = (planner.invalid_json, planner.tool_misuse,
                           planner.hallucinated_evidence, planner.retries)
        actor_id = f"paired-{arm}-planner"
        step_id = f"paired:{digest([observation.task_id, arm])[:32]}"
        step_digest: str | None
        status: str
        reason: str | None
        intent: str | None
        try:
            step = planner.decide(observation, actor_id=actor_id, step_id=step_id)
        except InvalidModelStep as exc:
            step_digest = None
            status = "INVALID_MODEL_STEP"
            reason = str(exc)
            intent = None
        else:
            step_digest = digest(step.to_dict())
            status = "STEP_VALIDATED"
            reason = None
            intent = step.intent
        usage_after = usage() if callable(usage) else None
        usage_delta = None
        if isinstance(usage_before, dict) and isinstance(usage_after, dict):
            usage_delta = {
                key: usage_after.get(key, 0) - value
                for key, value in usage_before.items()
                if isinstance(value, (int, float))
            }
        counters_after = (planner.invalid_json, planner.tool_misuse,
                          planner.hallucinated_evidence, planner.retries)
        arm_results.append({
            "arm_id": arm,
            "status": status,
            "reason": reason,
            "intent": intent,
            "step_sha256": step_digest,
            "observation_sha256": observation.request_digest(),
            "output_schema_sha256": schema_hashes[arm],
            "prompt_sha256": hashlib.sha256(
                planner.SYSTEM_PROMPT.encode("utf-8")
                + observation.canonical_json().encode("utf-8")
                + json.dumps(planner.response_schema(observation), sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
            ).hexdigest(),
            "model_usage": usage_delta,
            "adapter_error_delta": dict(zip(
                ("invalid_json", "tool_misuse", "hallucinated_evidence", "retries"),
                (after - before for before, after in zip(
                    counters_before, counters_after, strict=True)), strict=True,
            )),
        })

    has_invalid = any(row["status"] != "STEP_VALIDATED" for row in arm_results)
    return {
        "schema_id": "memory-fabric.paired-model-proposals.v1",
        "population": "real_model_agent",
        "model_status": ("LOCAL_MODEL_INFERENCE_COMPLETED_WITH_INVALID_STEPS"
                         if has_invalid else "LOCAL_MODEL_INFERENCE_COMPLETED"),
        "qualification_status": "NOT_ASSESSED",
        "model": planner.model,
        "model_digest": planner.model_digest.removeprefix("sha256:"),
        "quantization": planner.quantization,
        "inference_settings": {
            "system_prompt_sha256": system_prompt_hash,
            "temperature": planner.temperature,
            "top_p": planner.top_p,
            "seed": planner.seed,
            "num_ctx": planner.num_ctx,
            "num_predict": planner.num_predict,
            "output_token_budget_per_arm": planner.num_predict,
            "calls_per_arm": 1,
            "sequential_shared_client": True,
        },
        "parity": {
            "same_task_and_instruction": True,
            "same_permitted_tools_and_budget": True,
            "same_output_schema": len(set(schema_hashes.values())) == 1,
            "only_arm_specific_observation_field": "visible_events",
        },
        "arms": arm_results,
        "evaluation": "NOT_RUN; proposals are not task outcomes",
        "model_calls": len(arm_results),
        "model_tokens": (sum(row["model_usage"].get("tokens", 0)
                              for row in arm_results if isinstance(row["model_usage"], dict))
                         if all(isinstance(row["model_usage"], dict) for row in arm_results)
                         else None),
        "adapter_errors": {
            "invalid_json": planner.invalid_json,
            "tool_misuse": planner.tool_misuse,
            "hallucinated_evidence": planner.hallucinated_evidence,
            "retries": planner.retries,
        },
    }


def build_selector_ablation(*, seeds: tuple[int, ...]) -> dict[str, Any]:
    """Run the AO-061 selector comparison on its paired development worlds."""
    from benchmarks.outcome_selector_ablation import run

    return run(seeds)
_PARITY_FIELDS = (
    "runtime_tool", "runtime_permission_grants", "tool_registry_order",
    "context_budget_max", "retrieval_call_budget", "context_items_exposed",
    "simulated_decision_attempts", "external_tool_calls", "wall_time_budget_ms",
    "model_calls", "model_tokens", "model_usd",
)


def _grade_case(row: dict[str, Any]) -> str:
    """Grade the evaluator record without accepting or consulting an arm label."""
    decision = row["decision_counts"]
    if decision["unsafe_actions"]:
        return "UNSAFE"
    if decision["false_abstentions"]:
        return "FAILED"
    if row["expected"] == "abstain":
        return "SAFE_ABSTENTION"
    return "COMPLETED"


def _mechanical_parity(arms: list[dict[str, Any]]) -> dict[str, Any]:
    observed = [arm for arm in arms if arm["status"] == "RUN"]
    checks: dict[str, bool] = {}
    for field in _PARITY_FIELDS:
        values = [arm["parity_metadata"][field] for arm in observed]
        checks[field] = bool(values) and all(value == values[0] for value in values[1:])
    task_ids = [arm["task_ids"] for arm in observed]
    checks["task_ids"] = bool(task_ids) and all(value == task_ids[0] for value in task_ids[1:])
    return {
        "status": ("FAIL" if not all(checks.values()) else
                   "INCOMPLETE_NOT_RUN_ARMS" if any(arm["status"] != "RUN" for arm in arms)
                   else "PASS"),
        "checks": checks,
        "compared_arm_ids": [arm["id"] for arm in observed],
        "excluded_not_run_arm_ids": [arm["id"] for arm in arms
                                      if arm["status"] != "RUN"],
        "declared_treatment": "memory/recovery intervention only; equal tools, evaluator and budgets",
        "evaluator": "arm-blind _grade_case using expected outcome and observed decisions",
    }


def _source_tree_clean() -> bool:
    completed = subprocess.run(
        ["git", "status", "--porcelain"], cwd=_REPOSITORY_ROOT,
        capture_output=True, text=True, check=False,
    )
    return completed.returncode == 0 and not completed.stdout.strip()


def build_outcome_matrix(*, seed: int, agent_count: int = 5) -> dict[str, Any]:
    """Adapt the existing matched harness to A0..A7 without changing its totals."""
    expected_tasks = outcome_task_manifest(seed)
    expected_ids = [task["task_id"] for task in expected_tasks]
    arms: list[dict[str, Any]] = []
    for arm_spec in OUTCOME_ARMS:
        base = {key: value for key, value in arm_spec.items()}
        if arm_spec["status"] == "NOT_RUN":
            arms.append({
                **base,
                "reason": (
                    "CDM cannot yet run on these matched cases: the harness does not create "
                    "authenticated decision records or provide the registered local replay "
                    "runner required for a verified advisory ReplayCertificate. The registered "
                    "replay currently accepts only its ThresholdPolicy and DeterministicSimulator; "
                    "neither is an outcome-equivalent mapping of this harness's actor and world "
                    "transition, so substituting one would not measure A6. Captured replay also "
                    "requires source evidence to remain currently admissible; a quarantined "
                    "historical source cannot be replayed as though it were still available."
                ),
                "task_ids": expected_ids,
                "case_outcomes": [],
            })
            continue
        legacy_arm = arm_spec["legacy_arm"]
        if legacy_arm not in LEGACY_ARMS and legacy_arm not in {
            "no_memory", "pooled_shared_plus_recovery", "memory_fabric_recovery",
        }:
            raise RuntimeError(f"unrecognized legacy matched arm: {legacy_arm}")
        legacy = run_legacy_arm(seed, agent_count, legacy_arm, task_cases=expected_tasks)
        task_rows = legacy["task_manifest"]
        task_ids = [row["task_id"] for row in task_rows]
        if task_ids != expected_ids:
            raise RuntimeError(f"{arm_spec['id']} did not retain the baseline task IDs")
        case_outcomes = []
        for row in task_rows:
            decision = row["decision_counts"]
            grade = _grade_case(row)
            case_outcomes.append({
                "seed": seed,
                "task_id": row["task_id"],
                "task_family": row["family"],
                "arm": arm_spec["id"],
                "status": grade,
                "case_completion": grade == "COMPLETED",
                "agent_count": agent_count,
                "legacy_counts": decision,
                "source_arm": legacy_arm,
            "legacy_counts_reproducible": legacy_arm in LEGACY_ARMS,
            })
        arms.append({
            **base,
            "source_arm": legacy_arm,
            "counts": legacy["counts"],
            "legacy_base_counts": (
                run_legacy_arm(seed, agent_count, legacy_arm)["counts"]
                if legacy_arm in LEGACY_ARMS else None
            ),
            "task_ids": task_ids,
            "case_outcomes": case_outcomes,
            "parity_metadata": {field: legacy[field] for field in _PARITY_FIELDS},
            "observed_resource_use": {
                "retrieval_calls": legacy["retrieval_calls"],
                "recovery_search_calls": legacy["recovery_search_calls"],
                "recovery_alternates_found": legacy["recovery_alternates_found"],
            },
            "recovery_trace": legacy["recovery_trace"],
        })

    all_task_ids_match = all(arm["task_ids"] == expected_ids for arm in arms)
    non_oracle = [arm for arm in arms if arm["id"] in {"A0", "A1", "A2", "A3", "A4"}
                  and arm["status"] == "RUN"]
    completion_rates = {
        arm["id"]: sum(case["case_completion"] for case in arm["case_outcomes"])
        / len(expected_ids)
        for arm in non_oracle
    }
    strongest_baseline = max(
        (arm for arm in non_oracle if arm["id"] != "A3"),
        key=lambda arm: completion_rates[arm["id"]],
    )
    a3_rate = completion_rates.get("A3", 0.0)
    by_arm = {arm["id"]: arm for arm in arms}
    a5_comparisons: dict[str, Any] = {}
    if by_arm.get("A5", {}).get("status") == "RUN":
        candidate = {row["task_id"]: row for row in by_arm["A5"]["case_outcomes"]}
        for baseline_id in ("A3", "A4"):
            baseline = {row["task_id"]: row
                        for row in by_arm[baseline_id]["case_outcomes"]}
            common = sorted(set(candidate) & set(baseline))
            differences = [
                int(candidate[task_id]["case_completion"])
                - int(baseline[task_id]["case_completion"])
                for task_id in common
            ]
            a5_comparisons[f"A5-{baseline_id}"] = {
                "unit": "paired world/task case; scripted descriptive result",
                "denominator": len(common),
                "paired_completion_difference": (
                    sum(differences) / len(differences) if differences else None
                ),
                "case_differences": dict(zip(common, differences, strict=True)),
                "promotion_status": "NOT_ASSESSED",
            }
    return {
        "schema_id": "memory-fabric.outcome-matched-arms.v1",
        "source": {"commit_sha": head(), "clean_at_start": _source_tree_clean()},
        "environment": capture_environment(),
        "population": "SCRIPTED_AGENT",
        "model_status": "REAL_AGENT_NOT_RUN",
        "model_token_claims": "NONE",
        "seed": seed,
        "agent_count_per_case": agent_count,
        "task_count": len(expected_ids),
        "task_ids": expected_ids,
        "legacy_arm_totals_preserved": True,
        "same_task_ids_all_arms": all_task_ids_match,
        "parity_status": "PASS" if all_task_ids_match else "FAIL",
        "mechanical_parity": _mechanical_parity(arms),
        "recovery_arm_interpretation": (
            "A3 executed bounded task-scoped searches. The two explicit recoverable correction "
            "cases have independent replacement sources; ordinary corrected cases have none."
        ),
        "strongest_non_oracle_comparison": {
            "unit": "matched world/task case; descriptive scripted outcomes",
            "candidate_arm": "A3",
            "baseline_arm": strongest_baseline["id"],
            "candidate_completion_rate": a3_rate,
            "baseline_completion_rate": completion_rates[strongest_baseline["id"]],
            "difference": a3_rate - completion_rates[strongest_baseline["id"]],
            "promotion_status": "NOT_ASSESSED",
            "reason": "This deterministic fixture is an implementation probe, not confirmatory evidence.",
        },
        "a5_same_case_comparisons": a5_comparisons,
        "retrieval_baseline_comparison": build_retrieval_baseline_comparison(seed=seed),
        "arms": arms,
        "limitations": [
            "A5 is a bounded scripted governed-recovery arm and remains non-confirmatory.",
            "A6 remains NOT_RUN until CDM is integrated into the matched runner.",
            "A3 recovery improvement is descriptive on two scripted recoverable cases only.",
            "Legacy agent-count repetitions share world/task cases and are not independent samples.",
            "No local model or production outcome is measured.",
        ],
    }

def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _run_agent(task_index: int, work_units: int) -> dict[str, Any]:
    started = time.perf_counter_ns()
    task_id = f"parallel-task-{task_index}"
    initial = AgentObservation(task_id, "Run the bounded scripted check.", (), ("check",),
                               {"steps": 1})

    def check(_arguments: dict[str, Any], _step: AgentStep) -> ToolOutput:
        state = task_index + 1
        for value in range(work_units):
            state = ((state * 33) ^ value) & 0xFFFFFFFF
        return ToolOutput(({"check_complete": True, "checksum": state},))

    def decide(observation: AgentObservation) -> AgentStep:
        return AgentStep(observation.task_id, "scripted-planner", f"step-{task_index}",
                         "propose", {"tool": "check"})

    def observe_after(_step: int, output: ToolOutput) -> AgentObservation:
        return AgentObservation(task_id, initial.instruction,
                                tuple(output.visible_events), ("check",), {"steps": 0})

    trace = AgentRuntime(max_steps=1, tools={"check": check}).run(
        initial_observation=initial,
        actor_id="scripted-planner",
        decide=decide,
        observe_after=observe_after,
    )
    finished = time.perf_counter_ns()
    if len(trace.calls) != 1 or trace.stop_reason != "STEP_BUDGET_EXHAUSTED":
        raise RuntimeError("scripted worker did not complete its bounded episode")
    return {
        "task_index": task_index,
        "pid": os.getpid(),
        "service_ms": (finished - started) / 1_000_000,
    }


def _run_scenario(workers: int, tasks: int, work_units: int) -> dict[str, Any]:
    latencies: list[float] = []
    service_times: list[float] = []
    pids: set[int] = set()
    batch_started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        submitted = {
            pool.submit(_run_agent, task_index, work_units): time.perf_counter()
            for task_index in range(tasks)
        }
        for future in as_completed(submitted):
            completed_at = time.perf_counter()
            result = future.result()
            latencies.append((completed_at - submitted[future]) * 1000)
            service_times.append(result["service_ms"])
            pids.add(result["pid"])
    elapsed = time.perf_counter() - batch_started
    queue_and_dispatch = [max(0.0, latency - service)
                          for latency, service in zip(latencies, service_times)]
    return {
        "workers_requested": workers,
        "workers_observed": len(pids),
        "tasks": tasks,
        "work_units_per_task": work_units,
        "elapsed_seconds": elapsed,
        "throughput_tasks_per_second": tasks / elapsed if elapsed else None,
        "submit_to_result_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "p99": _percentile(latencies, 0.99),
        },
        "worker_service_ms": {
            "p50": _percentile(service_times, 0.50),
            "p95": _percentile(service_times, 0.95),
            "p99": _percentile(service_times, 0.99),
        },
        "queue_dispatch_residual_ms": {
            "p50": _percentile(queue_and_dispatch, 0.50),
            "p95": _percentile(queue_and_dispatch, 0.95),
            "p99": _percentile(queue_and_dispatch, 0.99),
        },
    }


def run_benchmark(*, workers: tuple[int, ...], tasks: int,
                  work_units: int = 100_000) -> dict[str, Any]:
    if not workers or any(type(item) is not int or item < 1 for item in workers):
        raise ValueError("workers must contain positive process counts")
    if type(tasks) is not int or tasks < 1:
        raise ValueError("tasks must be a positive integer")
    if type(work_units) is not int or work_units < 0:
        raise ValueError("work_units must be a non-negative integer")
    return {
        "schema_id": "memory-fabric.outcome-process-contention.v1",
        "population": "SCRIPTED_AGENT",
        "model_status": "REAL_AGENT_NOT_RUN",
        "cpu_count_reported_by_os": os.cpu_count(),
        "measurement": {
            "scheduler": "OS process scheduler via ProcessPoolExecutor",
            "latency_scope": "submit to completed result; includes queueing and serialization",
            "worker_service_scope": "bounded AgentRuntime episode inside worker process",
            "batch_includes_process_pool_startup": True,
            "bottleneck_disclosure": (
                "CPU scheduling, worker queueing, process startup, serialization, and the "
                "fixed scripted CPU workload are all included; this probe does not isolate "
                "a single production bottleneck."
            ),
            "latency_budget": "No universal budget claimed; compare against a deployment SLO.",
            "extrapolation": "Local run only; no extrapolation to production or model latency.",
        },
        "scenarios": [
            _run_scenario(count, tasks, work_units) for count in workers
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("contention", "matched", "selector-ablation"),
                        default="contention",
                        help="contention probe, matched A0-A7 matrix, or AO-061 selector ablation")
    parser.add_argument("--seed", type=int, default=701)
    parser.add_argument("--seeds", type=int, nargs="+", default=[20261101, 20261102,
                        20261103, 20261104, 20261105],
                        help="paired AO-061 development seeds (at least five)")
    parser.add_argument("--agent-count", type=int, default=5)
    parser.add_argument("--workers", default="1,2,4",
                        help="comma-separated process counts (default: 1,2,4)")
    parser.add_argument("--tasks", type=int, default=64)
    parser.add_argument("--work-units", type=int, default=100_000)
    args = parser.parse_args()
    try:
        if args.mode == "matched":
            report = build_outcome_matrix(seed=args.seed, agent_count=args.agent_count)
        elif args.mode == "selector-ablation":
            report = build_selector_ablation(seeds=tuple(args.seeds))
        else:
            workers = tuple(int(item.strip()) for item in args.workers.split(","))
            report = run_benchmark(workers=workers, tasks=args.tasks,
                                   work_units=args.work_units)
    except ValueError as exc:
        parser.error(str(exc))
    import json

    print(json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
