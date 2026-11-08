"""A matched one-case comparison against a plain JSON-style key/value store.

Run from the repository root:

    python examples/memory_vs_json.py

This is a transparent demonstration fixture, not a benchmark or population
estimate. Both arms receive the exact same two source records.
"""

from __future__ import annotations

import sys
from pathlib import Path
import json
import sqlite3
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from memory_fabric import MemoryFabric, correction
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule


class Record(TypedDict):
    key: str
    value: int
    source: str
    note: str


RECORDS: tuple[Record, ...] = (
    {"key": "pump:P1:purge_seconds", "value": 30,
     "source": "field-tech", "note": "initial reading"},
    {"key": "pump:P1:purge_seconds", "value": 45,
     "source": "reviewed-manual", "note": "correction"},
)


def main() -> int:
    print("DEMO ONLY: one deterministic case; no external tool is called.")
    # Ordinary baseline: SQLite key/value records with JSON payloads. It gets
    # the exact same evidence inputs, but has no provenance-aware action gate.
    simple = sqlite3.connect(":memory:")
    simple.execute("CREATE TABLE notes (key TEXT PRIMARY KEY, value_json TEXT NOT NULL)")
    for record in RECORDS:
        simple.execute("INSERT OR REPLACE INTO notes VALUES (?, ?)",
                       (record["key"], json.dumps(record, sort_keys=True)))
    simple_current = json.loads(simple.execute(
        "SELECT value_json FROM notes WHERE key = ?", (RECORDS[-1]["key"],)
    ).fetchone()[0])
    cached_simple_action = RECORDS[0]["value"]

    with MemoryFabric(seed=0, encrypt_content=False) as fabric:
        initial, corrected = RECORDS
        gate = ActionGate(
            fabric,
            ActionPolicy(
                tools={"set_purge": ToolRule("set_purge")},
                grants={"operator": frozenset({"set_purge"})},
            ),
        )
        old_id = fabric.remember(initial["source"],
                                 f"Pump P1 purge time is {initial['value']} seconds.",
                                 scope="team", auto_activate=True)
        stale_certificate = fabric.certify(
            f"set P1 purge to {initial['value']} seconds", [old_id], "operator")
        corrected_id = fabric.remember(
            corrected["source"],
            f"Pump P1 purge time is {corrected['value']} seconds.",
            scope="team", auto_activate=True)
        correction.apply(fabric, old_id,
                         reason=f"{corrected['source']} correction: {corrected['note']}",
                         actor="reviewer", basis="contradicted")

        current = fabric.retrieve("operator", "Pump P1 purge time", k=5).exposed
        current_setting = next((m for m in current if m.id == corrected_id), None)
        stale_decision = gate.authorize("set_purge", "operator", stale_certificate)
        fresh_certificate = fabric.certify(
            f"set P1 purge to {corrected['value']} seconds", [corrected_id], "operator")
        fresh_decision = gate.authorize("set_purge", "operator", fresh_certificate)

        simple_utility = simple_current["value"] == corrected["value"]
        fabric_utility = current_setting is not None
        simple_stale_would_run = cached_simple_action == initial["value"]  # no gate in this baseline
        fabric_stale_would_run = stale_decision.allowed

        print(f"Identical source records per arm: {len(RECORDS)}; equal input: True")
        print("Ordinary baseline: SQLite key/value table with JSON record payloads.")
        print("Task utility (returns the corrected 45-second setting):")
        print(f"  JSON-style store: {'PASS' if simple_utility else 'FAIL'} "
              f"({simple_current['value']} seconds)")
        print(f"  Memory Fabric:   {'PASS' if fabric_utility else 'FAIL'} "
              f"({corrected_id if current_setting else 'not found'})")
        print("Safety (a cached action still proposes the superseded 30-second setting):")
        print(f"  JSON-style store: {'WOULD RUN' if simple_stale_would_run else 'blocked'} "
              "(no authorization gate)")
        print(f"  Memory Fabric:   {'WOULD RUN' if fabric_stale_would_run else 'BLOCKED'} "
              f"({', '.join(stale_decision.reason_codes)})")
        print(f"Fresh corrected action: {'ALLOWED' if fresh_decision.allowed else 'BLOCKED'} "
              f"({', '.join(fresh_decision.reason_codes)})")
        print("Scope: a fixed scripted example; counts do not estimate general performance.")

        simple.close()
        return 0 if (simple_utility and fabric_utility and simple_stale_would_run
                     and not fabric_stale_would_run and fresh_decision.allowed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
