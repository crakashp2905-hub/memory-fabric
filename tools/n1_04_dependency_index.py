"""Reproducible 10k-decision qualification for the incremental impact index."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric import (  # noqa: E402
    DecisionEdge, DecisionLedger, DecisionOption, DecisionRecord, Event, EventLog,
    EventType, EvidenceVersion,
)


def qualify(decision_count: int, seed: int) -> dict[str, object]:
    rng = random.Random(seed)
    log = EventLog()
    ledger = DecisionLedger(log, lambda: 1_800_000_000_000)
    evidence_pool = [f"mem-{index:03d}" for index in range(257)]
    events: list[Event] = []
    source_rows: list[dict[str, object]] = []
    for index in range(decision_count):
        evidence = EvidenceVersion(rng.choice(evidence_pool), 1)
        decision = DecisionRecord(
            f"decision-{index:05d}", "tenant-1", f"agent-{index % 50}",
            "2026-11-08T10:00:00Z", f"goal-{index % 19}",
            (DecisionOption("selected", "Selected option", (evidence,)),),
            "selected", (evidence,), {"case": index},
        )
        edge = DecisionEdge(f"reliance-{index:05d}", decision.decision_id,
                            "relied_on", f"claim-{index:05d}", decision.agent_id,
                            "2026-11-08T10:00:01Z", evidence)
        events.extend((
            Event(EventType.DECISION_RECORDED, 1,
                  {"decision": decision.to_dict()}, agent_id=decision.agent_id,
                  event_id=f"decision-event-{index:05d}"),
            Event(EventType.DECISION_EDGE_RECORDED, 2,
                  {"edge": edge.to_dict()}, agent_id=decision.agent_id,
                  event_id=f"edge-event-{index:05d}"),
        ))
        source_rows.append({"decision": decision.to_dict(), "edge": edge.to_dict()})
        if index % 10 == 0:
            effect = DecisionEdge(f"authorization-{index:05d}", decision.decision_id,
                                  "authorized", f"receipt-{index:05d}", "reviewer",
                                  "2026-11-08T10:00:02Z")
            events.append(Event(EventType.DECISION_EDGE_RECORDED, 3,
                                {"edge": effect.to_dict()}, agent_id="reviewer",
                                event_id=f"effect-event-{index:05d}"))
            source_rows[-1]["effect"] = effect.to_dict()
    log.append_many(events)
    target = EvidenceVersion("mem-023", 1)
    trigger = log.append(Event(EventType.MEMORY_VERSIONED, 4,
                               {"memory": {"id": target.memory_id, "version": 2},
                                "reason": "correction"}))
    started = time.perf_counter()
    indexed = ledger.impacts_from_event(trigger.event_id)
    query_seconds = time.perf_counter() - started
    reference = ledger.reference_impacts_for(target, trigger_event_id=trigger.event_id)
    initial_stats = dict(ledger.index_stats)

    next_index = decision_count
    added_decision = DecisionRecord(
        f"decision-{next_index:05d}", "tenant-1", "agent-new",
        "2026-11-08T10:00:00Z", "incremental update",
        (DecisionOption("selected", "Selected option", (target,)),),
        "selected", (target,), {},
    )
    added_edge = DecisionEdge(f"reliance-{next_index:05d}", added_decision.decision_id,
                              "relied_on", "claim-new", "agent-new",
                              "2026-11-08T10:00:01Z", target)
    log.append_many((
        Event(EventType.DECISION_RECORDED, 5,
              {"decision": added_decision.to_dict()}, agent_id="agent-new",
              event_id=f"decision-event-{next_index:05d}"),
        Event(EventType.DECISION_EDGE_RECORDED, 6,
              {"edge": added_edge.to_dict()}, agent_id="agent-new",
              event_id=f"edge-event-{next_index:05d}"),
    ))
    updated = ledger.impacts_for(target, trigger_event_id=trigger.event_id)
    updated_reference = ledger.reference_impacts_for(target, trigger_event_id=trigger.event_id)
    final_stats = dict(ledger.index_stats)
    dataset_digest = hashlib.sha256(json.dumps(
        source_rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    log.close()
    return {
        "schema": "memory-fabric-decision-index-qualification/1",
        "seed": seed,
        "decisions": decision_count,
        "base_event_count": len(events) + 1,
        "dataset_sha256": dataset_digest,
        "target_evidence": target.to_dict(),
        "initial_impacts": len(indexed),
        "full_scan_impacts": len(reference),
        "initial_sets_equal": indexed == reference,
        "initial_events_scanned": initial_stats["events_scanned"],
        "incremental_events_added": 2,
        "incremental_events_scanned": final_stats["events_scanned"] - initial_stats["events_scanned"],
        "incremental_sets_equal": updated == updated_reference,
        "updated_impacts": len(updated),
        "indexed_through_seq": final_stats["indexed_through_seq"],
        "indexed_query_seconds": round(query_seconds, 6),
        "python": platform.python_version(),
        "platform": platform.platform(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20_261_108)
    parser.add_argument("--write", type=Path, default=None)
    args = parser.parse_args()
    if args.decisions < 1:
        parser.error("--decisions must be positive")
    result = qualify(args.decisions, args.seed)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.write:
        destination = args.write if args.write.is_absolute() else ROOT / args.write
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if (result["initial_sets_equal"] and result["incremental_sets_equal"]
                 and result["incremental_events_scanned"] == 2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
