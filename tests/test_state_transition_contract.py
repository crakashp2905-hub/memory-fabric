from __future__ import annotations

import json
from pathlib import Path

import pytest

from memory_fabric import LifecycleState, MemoryFabric, PolicyViolation
from memory_fabric.branching import Branches, StalePreview
from memory_fabric.governance.erasure import ERASED_MARKER

ROOT = Path(__file__).resolve().parents[1]


def test_contract_has_six_complete_operations() -> None:
    contract = json.loads((ROOT / "docs" / "STATE_TRANSITIONS.json").read_text())
    rows = {row["operation"]: row for row in contract["operations"]}
    assert set(rows) == {"append", "correct", "withdraw", "erase", "branch", "merge"}
    assert all(row["preconditions"] and row["postconditions"] and row["invariants"]
               for row in rows.values())


def test_append_correct_withdraw_and_erase_hold_the_contract() -> None:
    fabric = MemoryFabric(":memory:", auto_activate=False, hold_suspicious=False)
    try:
        memory_id = fabric.remember("agent", "Pump P1 is rated at 4 bar.")
        assert fabric.get(memory_id).lifecycle_state is LifecycleState.CANDIDATE
        assert fabric.get(memory_id).version == 1
        fabric.validate(memory_id, actor="reviewer")
        fabric.revise(memory_id, "Pump P1 is rated at 5 bar.", "agent", "re-measured")
        assert fabric.get(memory_id).version == 2
        fabric.quarantine(memory_id, "incorrect", basis="contradicted")
        assert fabric.get(memory_id).lifecycle_state is LifecycleState.QUARANTINED
        assert not fabric.use(memory_id, agent_id="agent", audit=False).usable
        assert fabric.erase_content(memory_id, "privacy request")
        with pytest.raises(PolicyViolation):
            fabric.revise(memory_id, "plaintext resurrection", "agent", "invalid")
        fabric.rebuild()
        assert fabric.get(memory_id).content == ERASED_MARKER
    finally:
        fabric.close()


def test_branch_isolation_and_merge_use_governed_transitions() -> None:
    fabric = MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False)
    try:
        target = fabric.remember("ann", "Valve V2 opens at 3 bar.", scope="team")
        branches = Branches(fabric)
        branches.create("trial", owner="ann", reviewers=("lead",))
        with branches.commit("trial", "ann", "correction") as change:
            change.revise(target, "Valve V2 opens at 4 bar.")
        assert fabric.get(target).content.endswith("3 bar.")
        preview = branches.preview_merge("trial", "lead")
        with branches.commit("trial", "ann", "move head") as change:
            change.add("Pump P3 is rated at 7 bar.")
        with pytest.raises(StalePreview):
            branches.apply_merge("trial", "lead", preview.digest, "stale-key")
        assert fabric.get(target).content.endswith("3 bar.")
        fresh = branches.preview_merge("trial", "lead")
        receipt = branches.apply_merge("trial", "lead", fresh.digest, "merge-key")
        assert receipt["summary"]["allow"] == 2
        assert fabric.get(target).content.endswith("4 bar.")
    finally:
        fabric.close()
