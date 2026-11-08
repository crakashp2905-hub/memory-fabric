"""Measure local terminal-state replay overhead over long immutable traces."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

from memory_fabric.causal_replay.bayes import BinaryNode, independent_binary_oracle
from memory_fabric.causal_replay.state import Observation, update
from memory_fabric.causal_replay.executor import execute
from memory_fabric.causal_replay.policy import ThresholdPolicy
from memory_fabric.causal_replay.replay import deterministic_simulator


def run(seed: int = 20261108,
        event_counts: tuple[int, ...] = (100, 1_000, 10_000, 100_000)
        ) -> dict[str, Any]:
    if (type(seed) is not int or not event_counts
            or any(type(count) is not int or not 100 <= count <= 100_000
                   for count in event_counts)):
        raise ValueError("seed and event counts must be valid; sizes are 100..100000")
    nodes = (BinaryNode("fault", (), {(): 0.2}),
             BinaryNode("alarm", ("fault",), {(False,): 0.1, (True,): 0.9}))
    reference = independent_binary_oracle(0.2, (0.9,), (True,))
    rows: list[dict[str, Any]] = []
    for count in event_counts:
        observations = tuple(Observation(f"replay-{seed}-{index}", "alarm", True,
            f"sensor-{index}", index) for index in range(count))
        workload_hash = hashlib.sha256(json.dumps(
            [item.__dict__ for item in observations], sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        tracemalloc.start()
        cpu_start = time.process_time_ns()
        wall_start = time.perf_counter_ns()
        state = update(nodes, observations, updater_id="exact-enumeration-v1",
                       policy_id="investigate-threshold-v1")
        wall_ns = time.perf_counter_ns() - wall_start
        cpu_ns = time.process_time_ns() - cpu_start
        snapshot = tracemalloc.take_snapshot()
        live_allocation_blocks = sum(stat.count for stat in snapshot.statistics("filename"))
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        observed = state.posterior["fault"]
        rows.append({"event_count": count, "seed": seed,
            "cpu_ns": cpu_ns, "wall_ns": wall_ns,
            "live_allocation_blocks": live_allocation_blocks,
            "peak_traced_bytes": peak_bytes,
            "posterior_fault": observed, "oracle_fault": reference,
            "posterior_abs_error": abs(observed - reference),
            "exact_state_fidelity": abs(observed - reference) <= 1e-12,
            "state_fingerprint": state.fingerprint,
            "workload_sha256": workload_hash})
    return {"schema": "cdm-replay-overhead-v1", "seed": seed,
        "mode": "terminal_state_reconstruction_not_per_event_trace_execution",
        "python": platform.python_version(), "platform": platform.platform(),
        "dependencies": "Python standard library only", "model_calls": 0,
        "network_calls": 0, "rows": rows,
        "all_exact_state_fidelity": all(row["exact_state_fidelity"] for row in rows),
        "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def _run_executor_child(seed: int, count: int) -> dict[str, Any]:
    """Measure the actual per-event executor in an isolated child process."""
    nodes = (BinaryNode("fault", (), {(): 0.2}),
             BinaryNode("alarm", ("fault",), {(False,): 0.1, (True,): 0.9}))
    observations = tuple(Observation(f"replay-{seed}-{index}", "alarm", True,
        f"sensor-{index}", index) for index in range(count))
    simulator = deterministic_simulator(nodes)
    policy = ThresholdPolicy("fault")
    tracemalloc.start()
    cpu_start = time.process_time_ns()
    wall_start = time.perf_counter_ns()
    execution = execute(observations, simulator=simulator, policy=policy,
                        max_events=count)
    wall_ns = time.perf_counter_ns() - wall_start
    cpu_ns = time.process_time_ns() - cpu_start
    snapshot = tracemalloc.take_snapshot()
    allocation_blocks = sum(stat.count for stat in snapshot.statistics("filename"))
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    oracle = independent_binary_oracle(0.2, (0.9,), (True,))
    posterior = execution.final_state.posterior["fault"]
    return {"event_count": count, "seed": seed, "status": execution.status.value,
        "complete": execution.complete, "consumed": execution.consumed,
        "step_count": len(execution.steps), "cpu_ns": cpu_ns, "wall_ns": wall_ns,
        "live_allocation_blocks": allocation_blocks, "peak_traced_bytes": peak_bytes,
        "posterior_fault": posterior, "oracle_fault": oracle,
        "posterior_abs_error": abs(posterior - oracle),
        "exact_state_fidelity": abs(posterior - oracle) <= 1e-12,
        "state_fingerprint": execution.final_state.fingerprint}


def run_executor_sweep(seed: int = 20261108,
                       event_counts: tuple[int, ...] = (100, 1_000, 10_000, 100_000),
                       timeout_seconds: float = 20.0) -> dict[str, Any]:
    """Run full per-event traces with a per-size wall bound and raw outcomes."""
    if (type(seed) is not int or not event_counts
            or any(type(count) is not int or not 1 <= count <= 100_000
                   for count in event_counts)
            or timeout_seconds <= 0):
        raise ValueError("invalid executor sweep configuration")
    rows: list[dict[str, Any]] = []
    for count in event_counts:
        started = time.perf_counter_ns()
        try:
            child = subprocess.run([sys.executable, "-m", "benchmarks.cdm_replay_overhead",
                "--executor-child", "--seed", str(seed), "--executor-count", str(count)],
                capture_output=True, text=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            rows.append({"event_count": count, "seed": seed, "status": "TIMEOUT",
                         "complete": False, "timeout_seconds": timeout_seconds,
                         "wall_ns": time.perf_counter_ns() - started})
            continue
        if child.returncode != 0:
            rows.append({"event_count": count, "seed": seed, "status": "ERROR",
                         "complete": False, "returncode": child.returncode,
                         "stdout": child.stdout[-2000:], "stderr": child.stderr[-2000:],
                         "wall_ns": time.perf_counter_ns() - started})
            continue
        row = json.loads(child.stdout)
        row["status"] = "MEASURED" if row["complete"] else row["status"]
        rows.append(row)
    return {"schema": "cdm-replay-executor-overhead-v1", "seed": seed,
        "mode": "full_per_event_executor_trace", "timeout_seconds_per_size": timeout_seconds,
        "python": platform.python_version(), "platform": platform.platform(),
        "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "dependencies": "Python standard library only", "model_calls": 0,
        "network_calls": 0, "rows": rows,
        "all_sizes_measured": all(row.get("status") == "MEASURED" for row in rows),
        "all_exact_state_fidelity": all(row.get("exact_state_fidelity", False)
                                         for row in rows)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20261108)
    parser.add_argument("--out", default="research/results/cdm/replay-overhead")
    parser.add_argument("--executor-child", action="store_true")
    parser.add_argument("--executor-count", type=int)
    parser.add_argument("--executor-timeout", type=float, default=20.0)
    args = parser.parse_args()
    if args.executor_child:
        if args.executor_count is None:
            parser.error("--executor-child requires --executor-count")
        print(json.dumps(_run_executor_child(args.seed, args.executor_count), sort_keys=True))
        return 0
    report = run(args.seed)
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "replay-overhead.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["output_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / "manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")
    executor_report = run_executor_sweep(args.seed, timeout_seconds=args.executor_timeout)
    executor_path = output / "executor-overhead.json"
    executor_path.write_text(json.dumps(executor_report, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    executor_report["output_sha256"] = hashlib.sha256(executor_path.read_bytes()).hexdigest()
    (output / "executor-manifest.json").write_text(
        json.dumps(executor_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    print(json.dumps(executor_report, sort_keys=True))
    return 0 if (report["all_exact_state_fidelity"]
                 and executor_report["all_sizes_measured"]
                 and executor_report["all_exact_state_fidelity"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
