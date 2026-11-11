"""A required withdrawn premise never yields an actionable descendant."""
from __future__ import annotations

from memory_fabric import LifecycleState, MemoryFabric


def fabric() -> MemoryFabric:
    return MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False)


def assert_not_actionable(current: MemoryFabric, memory_id: str) -> None:
    assert current.get(memory_id).lifecycle_state is not LifecycleState.ACTIVE
    assert not current.use(memory_id, agent_id="agent", audit=False).usable


def test_derive_then_withdraw_parent_contests_child() -> None:
    current = fabric()
    try:
        parent = current.remember("agent", "Valve V1 opens at 3 bar.")
        child = current.derive("agent", "Procedure: open V1 at 3 bar.", [parent],
                               auto_activate=True)
        assert current.get(child).lifecycle_state is LifecycleState.ACTIVE
        current.quarantine(parent, "measurement withdrawn", basis="contradicted")
        assert_not_actionable(current, child)
    finally:
        current.close()


def test_withdraw_parent_then_derive_child_never_activates() -> None:
    current = fabric()
    try:
        parent = current.remember("agent", "Valve V1 opens at 3 bar.")
        current.quarantine(parent, "measurement withdrawn", basis="contradicted")
        child = current.derive("agent", "Procedure: open V1 at 3 bar.", [parent],
                               auto_activate=True)
        assert_not_actionable(current, child)
    finally:
        current.close()


def test_mixed_parents_do_not_let_one_active_parent_mask_one_withdrawn_parent() -> None:
    current = fabric()
    try:
        withdrawn = current.remember("agent", "Valve V1 opens at 3 bar.")
        surviving = current.remember("agent", "Pump P2 is available.")
        current.quarantine(withdrawn, "measurement withdrawn", basis="contradicted")
        child = current.derive(
            "agent", "Procedure: use P2, then open V1 at 3 bar.",
            [withdrawn, surviving], auto_activate=True,
        )
        assert_not_actionable(current, child)
    finally:
        current.close()
