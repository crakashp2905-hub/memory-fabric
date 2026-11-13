#!/usr/bin/env python3
"""Measure scripted outcome-runtime latency under OS process scheduling.

This is a local CPU-contention probe, not an estimate of production or model
latency. Submit-to-result time includes process queueing and serialization.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import math
import os
from pathlib import Path
import sys
import time
from typing import Any

# Let the repository benchmark run directly from a source checkout as well as
# from an installed environment.
_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from benchmarks.agent_scale import task_manifest  # noqa: E402
from benchmarks.matched_agent_arms import ARMS as LEGACY_ARMS  # noqa: E402
from benchmarks.matched_agent_arms import run as run_legacy_arm  # noqa: E402
from memory_fabric.agent_outcomes.observations import AgentObservation, AgentStep  # noqa: E402
from memory_fabric.agent_outcomes.runtime import AgentRuntime, ToolOutput  # noqa: E402

OUTCOME_ARMS = (
    {"id": "A0", "name": "no_memory", "legacy_arm": "no_memory", "status": "RUN"},
    {"id": "A1", "name": "local_only", "legacy_arm": "isolated", "status": "RUN"},
    {"id": "A2", "name": "pooled_shared", "legacy_arm": "pooled_shared", "status": "RUN"},
    {"id": "A3", "name": "pooled_shared_plus_recovery",
     "legacy_arm": "pooled_shared_plus_recovery", "status": "RUN"},
    {"id": "A4", "name": "memory_fabric", "legacy_arm": "memory_fabric", "status": "RUN"},
    {"id": "A5", "name": "memory_fabric_recovery", "legacy_arm": None, "status": "NOT_RUN"},
    {"id": "A6", "name": "memory_fabric_recovery_cdm", "legacy_arm": None,
     "status": "NOT_RUN"},
    {"id": "A7", "name": "oracle", "legacy_arm": "oracle", "status": "RUN"},
)
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


def build_outcome_matrix(*, seed: int, agent_count: int = 5) -> dict[str, Any]:
    """Adapt the existing matched harness to A0..A7 without changing its totals."""
    expected_tasks = task_manifest(seed)
    expected_ids = [task["task_id"] for task in expected_tasks]
    arms: list[dict[str, Any]] = []
    for arm_spec in OUTCOME_ARMS:
        base = {key: value for key, value in arm_spec.items()}
        if arm_spec["status"] == "NOT_RUN":
            arms.append({
                **base,
                "reason": "Governed recovery or CDM intervention is not integrated yet.",
                "task_ids": expected_ids,
                "case_outcomes": [],
            })
            continue
        legacy_arm = arm_spec["legacy_arm"]
        if legacy_arm not in LEGACY_ARMS and legacy_arm not in {
            "no_memory", "pooled_shared_plus_recovery",
        }:
            raise RuntimeError(f"unrecognized legacy matched arm: {legacy_arm}")
        legacy = run_legacy_arm(seed, agent_count, legacy_arm)
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
    return {
        "schema_id": "memory-fabric.outcome-matched-arms.v1",
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
            "A3 executed bounded alternate-source searches; the current corrected cases have "
            "no independent replacement source, so no recovery completion can be claimed."
        ),
        "arms": arms,
        "limitations": [
            "A5 and A6 remain NOT_RUN until governed recovery and CDM are integrated.",
            "A3 is operational but has zero authorized replacement sources in the current task fixture.",
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
    parser.add_argument("--mode", choices=("contention", "matched"), default="contention",
                        help="run the process contention probe or matched A0-A7 matrix")
    parser.add_argument("--seed", type=int, default=701)
    parser.add_argument("--agent-count", type=int, default=5)
    parser.add_argument("--workers", default="1,2,4",
                        help="comma-separated process counts (default: 1,2,4)")
    parser.add_argument("--tasks", type=int, default=64)
    parser.add_argument("--work-units", type=int, default=100_000)
    args = parser.parse_args()
    try:
        if args.mode == "matched":
            report = build_outcome_matrix(seed=args.seed, agent_count=args.agent_count)
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
