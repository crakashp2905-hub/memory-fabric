"""Local selector/frontier scaling measurements with stdlib-only manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import statistics
import time
import tracemalloc
from pathlib import Path
from typing import Any

from memory_fabric.causal_replay.scheduler import (Candidate, branch_recall_at_k,
    earliest_affected_index, select_priority)


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[min(len(ordered) - 1, max(0, int((len(ordered) - 1) * q)))]


def run(seeds: list[int], sizes: tuple[int, ...] = (10, 100, 1_000)) -> dict[str, object]:
    rows: list[dict[str, Any]] = []
    workload_rows: list[dict[str, Any]] = []
    for seed in seeds:
        for size in sizes:
            rng = random.Random(seed ^ size)
            candidates = tuple(Candidate(f"e-{index:05d}", index, rng.random(),
                rng.random(), rng.random(), tuple(f"e-{j:05d}" for j in
                rng.sample(range(size), min(3, size)))) for index in range(size))
            pivotal = {item.candidate_id for item in candidates
                       if item.risk > 0.95 and item.relevance > 0.9}
            workload_rows.append({"seed": seed, "candidate_count": size,
                "candidates": [{"id": item.candidate_id, "sequence": item.sequence,
                    "risk": item.risk, "relevance": item.relevance,
                    "uncertainty": item.uncertainty, "neighbors": item.neighbors}
                    for item in candidates], "oracle_pivotal_ids": sorted(pivotal)})
            tracemalloc.start()
            started_cpu = time.process_time_ns()
            started = time.perf_counter_ns()
            selected: tuple[Candidate, ...] = ()
            repetitions = 10_000 if size <= 100 else 100
            for _ in range(repetitions):
                selected = select_priority(candidates, k=min(10, size))
            selected_cpu = time.process_time_ns() - started_cpu
            elapsed = (time.perf_counter_ns() - started) // repetitions
            selected_cpu //= repetitions
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            event_ids = tuple(item.candidate_id for item in candidates)
            graph = {item.candidate_id: item.neighbors for item in candidates}
            frontier_started = time.perf_counter_ns()
            earliest = earliest_affected_index(event_ids, event_ids[0],
                dependencies=graph, dependencies_complete=True)
            frontier_elapsed = time.perf_counter_ns() - frontier_started
            rows.append({"seed": seed, "candidate_count": size, "k": min(10, size),
                "selected_ids": [item.candidate_id for item in selected],
                "oracle_pivotal_ids": sorted(pivotal),
                "branch_recall_at_k": branch_recall_at_k(selected, pivotal,
                                                           candidate_count=size),
                "selector_cpu_ns": selected_cpu, "selector_wall_ns": elapsed,
                "frontier_wall_ns": frontier_elapsed, "peak_tracemalloc_bytes": peak,
                "frontier_start_index": earliest, "replay_transitions": size - earliest})
    body = json.dumps(workload_rows, sort_keys=True, separators=(",", ":")).encode()
    return {"schema": "cdm-efficiency-v1", "seeds": seeds,
        "workload_sha256": hashlib.sha256(body).hexdigest(), "rows": rows,
        "summary": {str(size): {"p50_cpu_ns": statistics.median(
            [row["selector_cpu_ns"] for row in rows if row["candidate_count"] == size]),
            "p95_wall_ns": _percentile([row["selector_wall_ns"] for row in rows
                                         if row["candidate_count"] == size], .95),
            "p99_wall_ns": _percentile([row["selector_wall_ns"] for row in rows
                                         if row["candidate_count"] == size], .99),
            "max_peak_bytes": max(row["peak_tracemalloc_bytes"] for row in rows
                                   if row["candidate_count"] == size)} for size in sizes},
        "python": platform.python_version(), "platform": platform.platform(),
        "cpu": platform.processor() or "unreported", "limits": {"k": 10,
        "tool_calls": 0, "network_calls": 0}, "remote_telemetry": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[20261108, 20261109])
    parser.add_argument("--out", default="research/results/cdm/efficiency")
    args = parser.parse_args()
    report = run(args.seeds)
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "efficiency.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {key: value for key, value in report.items() if key != "rows"}
    manifest["source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest["output_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)
                                           + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
