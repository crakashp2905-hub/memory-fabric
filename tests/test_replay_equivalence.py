"""Seeded append/correction/merge histories replay to identical projections."""
from __future__ import annotations

import hashlib
import json
import random

from memory_fabric import MemoryFabric
from memory_fabric.branching import Branches


def canonical(fabric: MemoryFabric) -> str:
    rows = []
    for memory_id, memory in sorted(fabric.state.memories.items()):
        rows.append({
            "id": memory_id, "version": memory.version, "content": memory.content,
            "state": memory.lifecycle_state.value, "tenant": memory.tenant_id,
            "scope": memory.scope.value,
            "parents": sorted([list(parent) for parent in memory.provenance.parents]),
            "creator": memory.provenance.created_by,
        })
    payload = {
        "memories": rows,
        "children": {key: sorted(value) for key, value in sorted(fabric.state.children.items())},
        "withdrawal_basis": dict(sorted(fabric.state.withdrawal_basis.items())),
        "erased": sorted(fabric.state.erased),
        "log_head": fabric.log.head_seq,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def exercise(seed: int) -> None:
    rng = random.Random(seed)
    fabric = MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False)
    try:
        memories = [
            fabric.remember("agent", f"Unit U{i} pressure is {rng.randrange(2, 9)} bar.",
                            scope="team")
            for i in range(8)
        ]
        # Corrections on a seeded subset, preserving each old version in the log.
        for memory_id in rng.sample(memories, 4):
            fabric.revise(memory_id, f"{fabric.get(memory_id).content[:-1]} after calibration.",
                          "agent", "seeded correction")
        branches = Branches(fabric)
        branches.create(f"trial-{seed}", owner="agent", reviewers=("reviewer",))
        with branches.commit(f"trial-{seed}", "agent", "seeded branch") as change:
            change.revise(memories[0], "Unit U0 pressure is 10 bar.")
            change.add(f"Seed {seed} branch-only inspection is complete.")
            change.withdraw(memories[-1], "superseded procedure")
        preview = branches.preview_merge(f"trial-{seed}", "reviewer")
        receipt = branches.apply_merge(f"trial-{seed}", "reviewer", preview.digest,
                                       f"merge-{seed}")
        assert receipt["summary"]["allow"] == 3
        before = canonical(fabric)
        fabric.rebuild()
        after = canonical(fabric)
        assert after == before, f"seed {seed}: replay projection digest changed"
        assert fabric.log.chain.verify(fabric.log.read()).ok
    finally:
        fabric.close()


def test_randomized_histories_replay_equivalently() -> None:
    for seed in (701, 702, 703, 704, 705):
        exercise(seed)
