from __future__ import annotations

import pytest

from memory_fabric.agent_outcomes import (
    READ_ONLY_RECOVERY_CATALOG,
    ReadOnlyRecoveryCatalog,
    RecoveryAction,
    RecoveryActionSpec,
)


def test_catalog_contains_only_permissible_read_only_recovery_requests() -> None:
    assert set(READ_ONLY_RECOVERY_CATALOG.actions) == set(RecoveryAction)
    assert all(not spec.externally_effectful
               for spec in READ_ONLY_RECOVERY_CATALOG.actions.values())
    assert READ_ONLY_RECOVERY_CATALOG.permits(RecoveryAction.ASK_CLARIFICATION)


def test_read_only_catalog_rejects_external_effects() -> None:
    with pytest.raises(ValueError, match="cannot cause external effects"):
        ReadOnlyRecoveryCatalog((RecoveryActionSpec(
            RecoveryAction.REPLAN, "send a command", externally_effectful=True,
        ),))


def test_catalog_rejects_untyped_or_invalid_action_names() -> None:
    with pytest.raises(ValueError, match="fixed RecoveryAction catalog"):
        RecoveryActionSpec("publish", "Publish the result.")  # type: ignore[arg-type]

    assert not READ_ONLY_RECOVERY_CATALOG.permits("replan")  # type: ignore[arg-type]


@pytest.mark.parametrize("effectful", [0, 1, "false"])
def test_catalog_requires_boolean_effect_metadata(effectful) -> None:
    with pytest.raises(ValueError, match="must be a boolean"):
        RecoveryActionSpec(RecoveryAction.REPLAN, "Replan.", effectful)  # type: ignore[arg-type]


def test_catalog_view_is_immutable() -> None:
    with pytest.raises(TypeError):
        READ_ONLY_RECOVERY_CATALOG.actions[RecoveryAction.REPLAN] = RecoveryActionSpec(
            RecoveryAction.REPLAN, "replacement",
        )
