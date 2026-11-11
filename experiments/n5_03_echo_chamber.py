"""Deterministic synthetic echo-chamber graph and timed rumor propagation.

This is a fixture generator, not evidence about real social networks. It emits
an undirected star, chain, or clustered-team graph and schedules rumor delivery
with seeded edge delays so downstream N5 experiments can vary topology and
timing independently.
"""
from __future__ import annotations

import heapq
import hashlib
import json
import random
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Literal

Topology = Literal["star", "chain", "clustered"]
ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / "research" / "results" / "n5-03-echo-chamber.json"
MARKDOWN_PATH = ROOT / "research" / "results" / "n5-03-echo-chamber.md"
TEST_PATH = ROOT / "research" / "results" / "n5-03-echo-chamber-tests.xml"


@dataclass(frozen=True)
class Delivery:
    rumor_id: str
    source: str
    target: str
    sent_at: int
    arrives_at: int
    delay: int
    adopted: bool


@dataclass(frozen=True)
class EchoChamber:
    topology: Topology
    seed: int
    rumor_id: str
    origin: str
    agents: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]
    deliveries: tuple[Delivery, ...]
    adoption_times: tuple[tuple[str, int], ...]

    def to_json(self) -> dict[str, object]:
        return {
            "schema": "memory-fabric-n5-03-echo-chamber/1",
            "topology": self.topology,
            "seed": self.seed,
            "rumor_id": self.rumor_id,
            "origin": self.origin,
            "agents": list(self.agents),
            "edges": [list(edge) for edge in self.edges],
            "deliveries": [asdict(delivery) for delivery in self.deliveries],
            "adoption_times": dict(self.adoption_times),
        }


def _graph(topology: Topology, count: int, cluster_size: int) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    if count < 2:
        raise ValueError("count must be at least 2")
    agents = tuple(f"agent_{index:03d}" for index in range(count))
    edges: set[tuple[str, str]] = set()

    def connect(left: str, right: str) -> None:
        if left != right:
            edges.add(tuple(sorted((left, right))))

    if topology == "star":
        for agent in agents[1:]:
            connect(agents[0], agent)
    elif topology == "chain":
        for left, right in zip(agents, agents[1:]):
            connect(left, right)
    elif topology == "clustered":
        if cluster_size < 2:
            raise ValueError("cluster_size must be at least 2")
        groups = [agents[index:index + cluster_size] for index in range(0, count, cluster_size)]
        for group in groups:
            for index, left in enumerate(group):
                for right in group[index + 1:]:
                    connect(left, right)
        for left_group, right_group in zip(groups, groups[1:]):
            connect(left_group[-1], right_group[0])
    else:
        raise ValueError(f"unsupported topology: {topology}")
    return agents, tuple(sorted(edges))


def generate(
    topology: Topology,
    *,
    seed: int,
    count: int = 16,
    cluster_size: int = 4,
    min_delay: int = 1,
    max_delay: int = 3,
    rumor_id: str = "rumor_001",
) -> EchoChamber:
    """Generate one connected graph and seeded first-adoption propagation trace."""
    if min_delay < 1 or max_delay < min_delay:
        raise ValueError("delays must satisfy 1 <= min_delay <= max_delay")
    agents, edges = _graph(topology, count, cluster_size)
    neighbors: dict[str, list[str]] = {agent: [] for agent in agents}
    for left, right in edges:
        neighbors[left].append(right)
        neighbors[right].append(left)
    rng = random.Random(seed)
    origin = agents[0]
    adopted_at = {origin: 0}
    pending: list[tuple[int, str, str, int]] = []
    for target in sorted(neighbors[origin]):
        delay = rng.randint(min_delay, max_delay)
        heapq.heappush(pending, (delay, origin, target, delay))
    deliveries: list[Delivery] = []
    while pending:
        arrives_at, source, target, delay = heapq.heappop(pending)
        sent_at = arrives_at - delay
        adopted = target not in adopted_at
        deliveries.append(Delivery(rumor_id, source, target, sent_at, arrives_at, delay, adopted))
        if not adopted:
            continue
        adopted_at[target] = arrives_at
        for neighbor in sorted(neighbors[target]):
            if neighbor == source or neighbor in adopted_at:
                continue
            edge_delay = rng.randint(min_delay, max_delay)
            next_arrival = arrives_at + edge_delay
            heapq.heappush(
                pending,
                (next_arrival, target, neighbor, edge_delay),
            )
    return EchoChamber(
        topology=topology,
        seed=seed,
        rumor_id=rumor_id,
        origin=origin,
        agents=agents,
        edges=edges,
        deliveries=tuple(deliveries),
        adoption_times=tuple(sorted(adopted_at.items())),
    )


def run() -> dict[str, object]:
    """Replay five fixed seeds over all required topologies and record evidence."""
    import xml.etree.ElementTree as ET

    junit = ET.parse(TEST_PATH).getroot()
    test_cases = len(list(junit.iter("testcase")))
    failures = len(list(junit.iter("failure")))
    errors = len(list(junit.iter("error")))
    skipped = len(list(junit.iter("skipped")))
    if test_cases < 4 or failures or errors or skipped:
        raise RuntimeError("N5-03 focused tests must pass with no skips")

    runs: list[dict[str, object]] = []
    for seed in (101, 102, 103, 104, 105):
        for topology in ("star", "chain", "clustered"):
            graph = generate(topology, seed=seed, count=16, cluster_size=4)
            trace = graph.to_json()
            adoption_times = dict(graph.adoption_times)
            run_id = f"{topology}-{seed}"
            runs.append(
                {
                    "run_id": run_id,
                    "topology": topology,
                    "seed": seed,
                    "agent_count": len(graph.agents),
                    "edge_count": len(graph.edges),
                    "delivery_count": len(graph.deliveries),
                    "adopted_count": sum(item.adopted for item in graph.deliveries),
                    "rumor_reach": len(adoption_times),
                    "propagation_duration": max(adoption_times.values()),
                    "trace_sha256": hashlib.sha256(
                        json.dumps(trace, sort_keys=True, separators=(",", ":")).encode()
                    ).hexdigest(),
                }
            )
            if len(adoption_times) != len(graph.agents):
                raise RuntimeError(f"rumor failed to reach every agent in {run_id}")

    source = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    result: dict[str, object] = {
        "schema": "memory-fabric-n5-03-echo-chamber/1",
        "task_id": "N5-03",
        "acceptance_passed": True,
        "evidence_level": "CONTRACT",
        "source": {"commit": source, "dirty_before_result_write": dirty},
        "configuration": {
            "topologies": ["star", "chain", "clustered"],
            "seeds": [101, 102, 103, 104, 105],
            "agents_per_run": 16,
            "cluster_size": 4,
            "delay_bounds_in_ticks": [1, 3],
            "delay_rng": "random.Random(seed), deterministic sorted-neighbor scheduling",
            "synthetic_only": True,
        },
        "runs": runs,
        "tests": {
            "junit": TEST_PATH.relative_to(ROOT).as_posix(),
            "reported_test_cases": test_cases,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        },
        "limitations": [
            "The graph shapes and edge delays are synthetic fixtures, not measurements of real communication networks.",
            "The model assumes every informed agent forwards the rumor over each uninformed neighbor edge.",
        ],
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    MARKDOWN_PATH.write_text(
        "# N5-03 echo-chamber generator evidence\n\n"
        "Fifteen deterministic synthetic runs cover star, chain, and clustered "
        "teams at seeds 101–105. Each trace binds topology, edges, bounded "
        "seeded transmission timing, first adoption and duplicate deliveries. "
        "The focused tests assert graph shape, timing reproducibility, delay "
        "bounds and complete reach. Hashes and per-run propagation durations "
        "are in the JSON. This fixture generator does not establish real-world "
        "social-network behavior.\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    print(json.dumps(run(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

