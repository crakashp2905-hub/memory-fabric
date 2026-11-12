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
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from memory_fabric.agent_outcomes.observations import AgentObservation, AgentStep  # noqa: E402
from memory_fabric.agent_outcomes.runtime import AgentRuntime, ToolOutput  # noqa: E402


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
    parser.add_argument("--workers", default="1,2,4",
                        help="comma-separated process counts (default: 1,2,4)")
    parser.add_argument("--tasks", type=int, default=64)
    parser.add_argument("--work-units", type=int, default=100_000)
    args = parser.parse_args()
    try:
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
