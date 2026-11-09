"""Compare plain versioning, blanket invalidation, and exact decision impacts.

This deterministic synthetic benchmark measures correction routing only. It
does not run a model re-evaluation or an external action; the oracle says that
decisions relying on the corrected exact evidence version require review while
all other decisions remain valid.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric import (  # noqa: E402
    DecisionEdge,
    DecisionLedger,
    DecisionOption,
    DecisionRecord,
    Event,
    EventLog,
    EventType,
    EvidenceVersion,
)


def benchmark_seed(decision_count: int, seed: int) -> dict[str, Any]:
    if decision_count < 1:
        raise ValueError("decision_count must be positive")
    rng = random.Random(seed)
    target = EvidenceVersion("corrected-memory", 1)
    events: list[Event] = []
    source_rows: list[dict[str, Any]] = []
    decision_ids: list[str] = []
    affected_ids: set[str] = set()
    target_seen = 0

    for index in range(decision_count):
        decision_id = f"decision-{index:06d}"
        agent_id = f"agent-{index % 50:02d}"
        affected = rng.random() < 0.10
        evidence = target if affected else EvidenceVersion(
            f"unrelated-memory-{rng.randrange(1024):04d}", 1
        )
        if affected:
            target_seen += 1
            affected_ids.add(decision_id)
        decision = DecisionRecord(
            decision_id,
            "tenant-benchmark",
            agent_id,
            "2026-11-09T10:00:00Z",
            f"complete maintenance case {index}",
            (DecisionOption("proceed", "Proceed using cited premise", (evidence,)),),
            "proceed",
            (evidence,),
            {"case": index, "seed": seed},
        )
        edge = DecisionEdge(
            f"reliance-{index:06d}", decision_id, "relied_on",
            f"claim-{index:06d}", agent_id, "2026-11-09T10:00:01Z", evidence,
        )
        events.extend((
            Event(EventType.DECISION_RECORDED, 1,
                  {"decision": decision.to_dict()}, agent_id=agent_id,
                  event_id=f"decision-event-{index:06d}"),
            Event(EventType.DECISION_EDGE_RECORDED, 2,
                  {"edge": edge.to_dict()}, agent_id=agent_id,
                  event_id=f"edge-event-{index:06d}"),
        ))
        source_rows.append({"decision": decision.to_dict(), "edge": edge.to_dict()})
        decision_ids.append(decision_id)

    digest = hashlib.sha256(json.dumps(
        source_rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()
    log = EventLog()
    try:
        log.append_many(events)
        ledger = DecisionLedger(log, lambda: 1_798_000_000_000)

        build_started = time.perf_counter_ns()
        before = ledger.index_stats  # build the warm dependency index
        index_build_ns = time.perf_counter_ns() - build_started

        trigger = log.append(Event(
            EventType.MEMORY_VERSIONED, 3,
            {"memory": {"id": target.memory_id, "version": 2},
             "reason": "controlled correction"},
            event_id=f"correction-{seed}",
        ))

        index_started = time.perf_counter_ns()
        indexed_impacts = ledger.impacts_from_event(trigger.event_id)
        index_update_ns = time.perf_counter_ns() - index_started
        indexed_ids = {impact.decision_id for impact in indexed_impacts}

        # Baseline A: version the memory but keep no decision dependency. The
        # memory pointer update is constant work; old decision actions remain
        # usable, so every affected decision is stale.
        versions = {target.memory_id: target.version}
        plain_samples: list[int] = []
        for _ in range(200):
            started = time.perf_counter_ns()
            versions[target.memory_id] = target.version + 1
            plain_samples.append(time.perf_counter_ns() - started)

        # Baseline B: invalidate every decision after any correction.
        blanket_samples: list[int] = []
        blanket_invalidated: list[str] = []
        for _ in range(5):
            started = time.perf_counter_ns()
            blanket_invalidated = list(decision_ids)
            blanket_samples.append(time.perf_counter_ns() - started)

        plain = {
            "re_evaluations": 0,
            "unnecessary_re_evaluations": 0,
            "stale_decisions": len(affected_ids),
            "correctly_routed_decisions": decision_count - len(affected_ids),
            "update_cost_ns_median": int(statistics.median(plain_samples)),
        }
        blanket = {
            "re_evaluations": len(blanket_invalidated),
            "unnecessary_re_evaluations": len(blanket_invalidated) - len(affected_ids),
            "stale_decisions": 0,
            "correctly_routed_decisions": decision_count - (
                len(blanket_invalidated) - len(affected_ids)),
            "update_cost_ns_median": int(statistics.median(blanket_samples)),
        }
        indexed = {
            "re_evaluations": len(indexed_ids),
            "unnecessary_re_evaluations": len(indexed_ids - affected_ids),
            "stale_decisions": len(affected_ids - indexed_ids),
            "correctly_routed_decisions": decision_count - len(
                affected_ids.symmetric_difference(indexed_ids)),
            "update_cost_ns_median": index_update_ns,
        }
        for result in (plain, blanket, indexed):
            result["decision_correctness_rate"] = round(
                result["correctly_routed_decisions"] / decision_count, 6)

        return {
            "seed": seed,
            "decisions": decision_count,
            "affected_decisions_oracle": len(affected_ids),
            "dataset_sha256": digest,
            "base_events": len(events),
            "index_build_events_scanned": before["events_scanned"],
            "index_build_ns": index_build_ns,
            "correction_events_scanned": ledger.index_stats["events_scanned"] - before["events_scanned"],
            "indexed_impacts_match_oracle": indexed_ids == affected_ids,
            "arms": {
                "plain_versioning": plain,
                "blanket_invalidation": blanket,
                "exact_dependency_index": indexed,
            },
        }
    finally:
        log.close()


def aggregate(rows: list[dict[str, Any]], decisions: int) -> dict[str, Any]:
    arms: dict[str, Any] = {}
    for name in ("plain_versioning", "blanket_invalidation", "exact_dependency_index"):
        fields = ("re_evaluations", "unnecessary_re_evaluations", "stale_decisions",
                  "correctly_routed_decisions")
        arms[name] = {
            key: int(statistics.median([row["arms"][name][key] for row in rows]))
            for key in fields
        }
        arms[name]["decision_correctness_rate_median"] = round(statistics.median(
            [row["arms"][name]["decision_correctness_rate"] for row in rows]), 6)
        arms[name]["update_cost_ns_median"] = int(statistics.median(
            [row["arms"][name]["update_cost_ns_median"] for row in rows]))
    return {
        "decisions_per_seed": decisions,
        "seeds": len(rows),
        "arms": arms,
        "oracle_definition": (
            "Only decisions relying on corrected-memory v1 require re-evaluation; "
            "all other decisions should remain usable."),
    }


def run(decisions: int, seeds: list[int]) -> dict[str, Any]:
    rows = [benchmark_seed(decisions, seed) for seed in seeds]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip())
    script_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {
        "schema": "memory-fabric-decision-continuity-benchmark/1",
        "benchmark": "N1-09 decision continuity",
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "source": {"commit": commit, "dirty_before_result_write": dirty,
                   "benchmark_script_sha256": script_sha256},
        "configuration": {"decisions_per_seed": decisions, "seeds": seeds,
                           "correction_fraction_target": 0.10,
                           "model_assisted_re_evaluation": False},
        "aggregate": aggregate(rows, decisions),
        "runs": rows,
        "limitations": [
            "Synthetic deterministic decisions and oracle; not a real-agent task-success benchmark.",
            "Re-evaluation is counted as routing work; model inference latency, quality and cost are excluded.",
            "Timed baseline operations have different computational shapes; timings are descriptive and host-specific.",
            "Dependency-index warm-up is reported separately from hot correction update cost.",
            "No external actions are executed.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=int, default=2_000)
    parser.add_argument("--seeds", type=int, nargs="+", default=[20261109, 20261110, 20261111,
                                                                    20261112, 20261113])
    parser.add_argument("--write", type=Path, default=None)
    args = parser.parse_args()
    if args.decisions < 1 or not args.seeds or len(args.seeds) != len(set(args.seeds)):
        parser.error("decisions and unique seeds must be positive")
    result = run(args.decisions, args.seeds)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.write:
        destination = args.write if args.write.is_absolute() else ROOT / args.write
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    valid = all(row["indexed_impacts_match_oracle"] for row in result["runs"])
    valid = valid and result["aggregate"]["arms"]["exact_dependency_index"][
        "unnecessary_re_evaluations"] == 0
    valid = valid and result["aggregate"]["arms"]["exact_dependency_index"]["stale_decisions"] == 0
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
