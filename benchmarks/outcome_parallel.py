"""Measure scheduled latency for concurrent scripted outcome-recovery episodes.

Run with ``python -m benchmarks.outcome_parallel --seeds 12 --workers 4``.
This is a local process-scheduling benchmark, not deployment performance evidence.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any

from .outcome_recovery import run_episode
from .outcome_report import report_rows


def _run_seed(seed: int) -> tuple[float, dict[str, Any]]:
    started = time.perf_counter()
    outcome = run_episode(seed)
    elapsed_ms = (time.perf_counter() - started) * 1000
    row = report_rows([outcome])[0]
    row.pop("wall_ms", None)
    return elapsed_ms, row


def _percentiles(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("latency summaries require at least one observation")

    def at(percentile: float) -> float:
        index = max(0, min(len(ordered) - 1,
                           int((percentile * len(ordered) + 99) // 100) - 1))
        return ordered[index]

    return {"p50_ms": at(50), "p95_ms": at(95), "p99_ms": at(99)}


def run_parallel_benchmark(
    seeds: tuple[int, ...] = tuple(range(12)), *, workers: int = 4,
) -> dict[str, Any]:
    """Run identical scripted episodes sequentially and in OS worker processes."""
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("benchmark seeds must be non-empty and unique")
    if (not isinstance(workers, int) or isinstance(workers, bool)
            or workers < 2 or workers > 32):
        raise ValueError("workers must be an integer from 2 through 32")

    sequential_times: list[float] = []
    sequential_rows: dict[int, dict[str, Any]] = {}
    for seed in seeds:
        elapsed, row = _run_seed(seed)
        sequential_times.append(elapsed)
        sequential_rows[seed] = row

    context = multiprocessing.get_context("spawn")
    parallel_started = time.perf_counter()
    completion_ms: list[float] = []
    parallel_rows: dict[int, dict[str, Any]] = {}
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        submitted = {pool.submit(_run_seed, seed): (seed, time.perf_counter())
                     for seed in seeds}
        for future in as_completed(submitted):
            seed, queued_at = submitted[future]
            _, row = future.result()
            completion_ms.append((time.perf_counter() - queued_at) * 1000)
            parallel_rows[seed] = row
    parallel_total_ms = (time.perf_counter() - parallel_started) * 1000

    for seed in seeds:
        sequential, parallel = sequential_rows[seed], parallel_rows[seed]
        for field in ("task_id", "arm", "agent_id", "completion", "seed",
                      "terminal_failure_codes", "attempted_unsafe_effects",
                      "executed_unsafe_effects", "outcome_oracle_digest"):
            if sequential[field] != parallel[field]:
                raise RuntimeError(f"process scheduling changed {field} for seed {seed}")

    sequential_total_ms = sum(sequential_times)
    return {
        "schema_id": "memory-fabric.parallel-outcome-benchmark.v1",
        "population": "SCRIPTED_AGENT",
        "scheduler": "multiprocessing.ProcessPoolExecutor_spawn",
        "process_workers": workers,
        "task_case_denominator": len(seeds),
        "sequential": {
            **_percentiles(sequential_times),
            "total_elapsed_ms": sequential_total_ms,
        },
        "parallel": {
            **_percentiles(completion_ms),
            "total_elapsed_ms": parallel_total_ms,
            "end_to_end_wall_ms": parallel_total_ms,
        },
        "parallel_to_sequential_p95_ratio": (
            _percentiles(completion_ms)["p95_ms"]
            / max(_percentiles(sequential_times)["p95_ms"], 1e-9)
        ),
        "cases_match_sequential_reference": True,
        "raw_rows": [parallel_rows[seed] for seed in sorted(seeds)],
        "performance_claim_eligible": False,
        "evidence_level": "LOCAL_SCRIPTED_PROCESS_BENCHMARK_ONLY",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=12)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    if args.seeds <= 0:
        parser.error("--seeds must be positive")
    result = run_parallel_benchmark(tuple(range(args.seeds)), workers=args.workers)
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
