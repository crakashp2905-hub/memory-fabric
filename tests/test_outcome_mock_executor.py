from __future__ import annotations

import pytest

from benchmarks.outcome_worlds import (
    MockPhysicalEffectExecutor,
    correction_after_plan_world,
)


def _run_correction_world():
    world, oracle = correction_after_plan_world(seed=43)
    world.observe(step=0, permitted_tools=("shut_down",), budget={"steps": 3})
    world.observe(step=1, permitted_tools=("shut_down",), budget={"steps": 2})
    executor = MockPhysicalEffectExecutor(world, {
        "shut_down": ("shutdown", "shut_down"),
    })
    result = executor.execute(
        "shut_down", revision_epoch=1,
        idempotency_key="shutdown-after-correction",
    )
    first_digest = world.world_digest()
    replay = executor.execute(
        "shut_down", revision_epoch=1,
        idempotency_key="shutdown-after-correction",
    )

    assert replay == result
    assert world.world_digest() == first_digest
    assert result.receipt.executed is True
    assert world.terminal_digest() == oracle.expected_terminal_digest
    return first_digest, result


def test_mock_physical_effect_replays_identically_and_is_idempotent() -> None:
    first_digest, first_result = _run_correction_world()
    replay_digest, replay_result = _run_correction_world()

    assert replay_digest == first_digest
    assert replay_result == first_result


def test_mock_executor_refuses_stale_or_undeclared_effects() -> None:
    world, _oracle = correction_after_plan_world(seed=43)
    world.observe(step=0, permitted_tools=("shut_down",), budget={"steps": 2})
    world.observe(step=1, permitted_tools=("shut_down",), budget={"steps": 1})
    executor = MockPhysicalEffectExecutor(world, {
        "shut_down": ("shutdown", "shut_down"),
    })
    before = world.world_digest()
    before_terminal = world.terminal_digest()

    stale = executor.execute(
        "shut_down", revision_epoch=0, idempotency_key="stale-shutdown",
    )
    assert stale.receipt.executed is False
    assert stale.reason_code == "STALE_REVISION_EPOCH"
    with pytest.raises(PermissionError, match="not declared"):
        executor.execute("open_valve", revision_epoch=1, idempotency_key="unknown-tool")
    assert world.world_digest() != before
    assert world.terminal_digest() == before_terminal


def test_runtime_handler_returns_only_visible_effect_receipt_fields() -> None:
    world, _oracle = correction_after_plan_world(seed=43)
    world.observe(step=1, permitted_tools=("shut_down",), budget={"steps": 1})
    executor = MockPhysicalEffectExecutor(world, {
        "shut_down": ("shutdown", "shut_down"),
    })
    output = executor.handler("shut_down")(
        {"revision_epoch": 1, "idempotency_key": "shutdown-after-correction"}, None
    )

    assert output.visible_events == ({
        "effect_id": "shutdown",
        "action": "shut_down",
        "authorized": True,
        "executed": True,
        "reason_code": "EFFECT_EXECUTED",
        "revision_epoch": 1,
    },)
    assert "truth" not in output.visible_events[0]
