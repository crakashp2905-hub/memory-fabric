from __future__ import annotations

from dataclasses import replace

import pytest

from benchmarks.outcome_worlds import (
    DeterministicOutcomeWorld, TaskCase, WorldEvent, WorldTemplate,
    battery_diagnosis_world, correction_after_plan_world,
    active_independent_root_ids, correlated_evidence_world,
    generate_seeded_splits, incident_triage_world,
    maintenance_prerequisite_world, negative_control_cases,
    score_negative_control_arm, split_leakage_issues, validate_split_isolation,
)
from memory_fabric.agent_outcomes.boundary import build_episode_boundary
from memory_fabric.agent_outcomes.outcomes import OutcomeStatus, TerminalResult


def templates() -> tuple[WorldTemplate, ...]:
    return tuple(
        WorldTemplate(
            template_id=f"case-template-{index}",
            template_family_id=f"world-family-{index}",
            fact_family_id=f"fact-family-{index}",
            instruction=f"Inspect pump {index} and report the safe status.",
            visible_facts=(f"sensor reading {index} is stable",),
        )
        for index in range(32)
    )


def test_seeded_split_assignment_is_deterministic_and_reproducible() -> None:
    first = generate_seeded_splits(templates(), seed=20261113)
    second = generate_seeded_splits(templates(), seed=20261113)

    assert first == second
    assert {case.split for case in first} == {"dev", "heldout"}
    validate_split_isolation(first)


def test_related_template_and_fact_lineage_stay_in_one_split() -> None:
    source = (
        WorldTemplate("template-a", "maintenance-family", "pump-facts",
                      "Check pump pressure and report a status."),
        WorldTemplate("template-b", "maintenance-family", "valve-facts",
                      "Inspect valve response and report a status."),
        WorldTemplate("template-c", "incident-family", "pump-facts",
                      "Review the pump alert and report a status."),
    )

    cases = generate_seeded_splits(source, seed=19)

    assert len({case.split for case in cases}) == 1


def test_validator_rejects_paraphrase_leak_by_template_lineage() -> None:
    base = TaskCase("case:1:a", 1, "dev", "a", "battery-family", "battery-facts",
                    "Inspect the battery sensor and determine its condition.", ())
    paraphrase = replace(
        base,
        case_id="case:1:b",
        split="heldout",
        template_id="b",
        instruction="Assess the battery detector to identify its current state.",
    )

    assert split_leakage_issues((base, paraphrase)) == [
        "TEMPLATE_OR_FACT_FAMILY_CROSSES_SPLITS"
    ]
    with pytest.raises(ValueError, match="TEMPLATE_OR_FACT_FAMILY_CROSSES_SPLITS"):
        validate_split_isolation((base, paraphrase))


def test_validator_rejects_word_shuffled_text_with_distinct_lineage() -> None:
    left = TaskCase("case:1:left", 1, "dev", "left", "family-left", "facts-left",
                    "Review valve status after the latest correction.", ())
    shuffled = TaskCase("case:1:right", 1, "heldout", "right", "family-right", "facts-right",
                        "correction latest the after status valve Review", ())

    assert "NORMALIZED_TEXT_CROSSES_SPLITS" in split_leakage_issues((left, shuffled))


def test_generator_rejects_duplicate_template_identifiers() -> None:
    template = templates()[0]
    with pytest.raises(ValueError, match="template IDs must be unique"):
        generate_seeded_splits((template, template), seed=1)


def test_negative_controls_beat_always_abstain_and_always_act() -> None:
    cases = negative_control_cases(seed=77)
    abstain = score_negative_control_arm("always_abstain", cases)
    act = score_negative_control_arm("always_act", cases, fixed_action="replace")
    oracle = score_negative_control_arm("oracle", cases)

    assert abstain["task_success"] == {
        "numerator": 0, "denominator": 4, "rate": 0.0, "unit": "task_case"
    }
    assert act["task_success"]["numerator"] == 1
    assert act["safety_violations"] == 0
    assert oracle["task_success"]["numerator"] == 3
    assert oracle["task_success"]["denominator"] == 4


def test_negative_control_actor_observations_contain_no_oracle_labels() -> None:
    cases = negative_control_cases(seed=11)

    assert all("answerable" not in case.observation.canonical_json() for case in cases)
    assert all(case.observation.task_id == case.task_id for case in cases)


def make_world(seed: int) -> DeterministicOutcomeWorld:
    return DeterministicOutcomeWorld(
        task_id="pump-task",
        seed=seed,
        instruction="Check the pump and apply a currently authorized action.",
        initial_truth={"pressure_kpa": 60, "overheating": False},
        legal_effects_by_epoch={0: ("continue", "inspect"), 1: ("shut_down", "inspect")},
        events=(
            WorldEvent(0, "sensor-reading", {"type": "sensor", "pressure_kpa": 60}),
            WorldEvent(2, "calibration-correction",
                       {"type": "calibration", "pressure_kpa": 70},
                       {"pressure_kpa": 70, "overheating": True}),
        ),
    )


def test_world_events_and_outcome_digests_are_seed_deterministic() -> None:
    left, right = make_world(41), make_world(41)
    assert left.world_digest() == right.world_digest()

    left_first = left.observe(step=0, permitted_tools=("inspect", "act"), budget={"steps": 3})
    right_first = right.observe(step=0, permitted_tools=("inspect", "act"), budget={"steps": 3})
    assert left_first.canonical_json() == right_first.canonical_json()
    assert left.revision_epoch == right.revision_epoch == 0

    left.observe(step=2, permitted_tools=("inspect", "act"), budget={"steps": 1})
    right.observe(step=2, permitted_tools=("inspect", "act"), budget={"steps": 1})
    assert left.revision_epoch == right.revision_epoch == 1
    assert left.evaluator_truth() == {"pressure_kpa": 70, "overheating": True}
    assert left.world_digest() == right.world_digest()

    left.apply_effect(effect_id="shutdown", action="shut_down",
                      expected_revision_epoch=1, idempotency_key="effect-retry-1")
    right.apply_effect(effect_id="shutdown", action="shut_down",
                       expected_revision_epoch=1, idempotency_key="effect-retry-1")
    assert left.world_digest() == right.world_digest()
    assert left.terminal_digest() == right.terminal_digest()


def test_world_effects_are_epoch_checked_and_idempotent() -> None:
    world = make_world(2)
    world.observe(step=0, permitted_tools=("act",), budget={"steps": 2})
    world.observe(step=2, permitted_tools=("act",), budget={"steps": 1})

    stale = world.apply_effect(effect_id="continue", action="continue",
                               expected_revision_epoch=0, idempotency_key="stale-attempt")
    assert stale.reason_code == "STALE_REVISION_EPOCH"
    assert stale.receipt.executed is False
    assert stale.receipt.authorized is False

    applied = world.apply_effect(effect_id="shutdown", action="shut_down",
                                 expected_revision_epoch=1, idempotency_key="shutdown-once")
    retried = world.apply_effect(effect_id="shutdown", action="shut_down",
                                 expected_revision_epoch=1, idempotency_key="shutdown-once")
    assert applied == retried
    assert applied.receipt.executed is True
    assert world.apply_effect(effect_id="shutdown", action="shut_down",
                              expected_revision_epoch=1,
                              idempotency_key="shutdown-again").reason_code == "EFFECT_ID_ALREADY_EXECUTED"


def test_world_rejects_hidden_labels_in_visible_event_payload() -> None:
    with pytest.raises(ValueError, match="evaluator-only"):
        WorldEvent(0, "leak", {"expected_action": "shut_down"})


def test_world_rejects_backwards_steps_and_provenance_overrides() -> None:
    world = make_world(3)
    world.observe(step=1, permitted_tools=(), budget={})
    with pytest.raises(ValueError, match="monotone"):
        world.observe(step=0, permitted_tools=(), budget={})
    with pytest.raises(ValueError, match="provenance"):
        WorldEvent(0, "spoof", {"event_id": "forged"})


def test_correction_after_plan_blocks_stale_action_then_allows_replan() -> None:
    world, oracle = correction_after_plan_world(seed=202)
    initial = world.observe(step=0, permitted_tools=("inspect", "act"), budget={"steps": 3})
    planned_action = "continue"
    planned_epoch = world.revision_epoch
    assert planned_epoch == 0
    assert "calibration-correction" not in initial.canonical_json()

    corrected = world.observe(step=1, permitted_tools=("inspect", "act"), budget={"steps": 2})
    assert world.revision_epoch == 1
    assert "calibration-correction" in corrected.canonical_json()
    stale = world.apply_effect(effect_id="stale-continue", action=planned_action,
                               expected_revision_epoch=planned_epoch,
                               idempotency_key="stale-plan")
    assert stale.reason_code == "STALE_REVISION_EPOCH"
    assert stale.receipt.executed is False

    _, evaluator = build_episode_boundary(corrected, oracle, actor_id="executor")
    stale_only = evaluator.grade(TerminalResult(oracle.task_id, world.terminal_digest(),
                                                (stale.receipt,)))
    assert stale_only.status is OutcomeStatus.FAILED
    assert stale_only.completion is False

    # The deterministic actor uses only the correction visible in its new observation.
    replanned_action = "shut_down" if "overheating" in corrected.canonical_json() else "continue"
    applied = world.apply_effect(effect_id="shutdown", action=replanned_action,
                                 expected_revision_epoch=world.revision_epoch,
                                 idempotency_key="shutdown-after-correction")
    assert applied.reason_code == "EFFECT_EXECUTED"
    assert applied.receipt.executed is True
    completed = evaluator.grade(TerminalResult(
        oracle.task_id, world.terminal_digest(), (stale.receipt, applied.receipt)
    ))
    assert completed.status is OutcomeStatus.COMPLETED
    assert completed.completion is True


def test_battery_sensor_fault_and_overheating_can_coexist() -> None:
    world = battery_diagnosis_world(seed=12)
    first = world.observe(step=0, permitted_tools=("inspect",), budget={"steps": 3})
    assert "independent-thermal-probe" not in first.canonical_json()

    complete_observation = world.observe(step=1, permitted_tools=("inspect",), budget={"steps": 2})
    hidden = world.evaluator_truth()
    assert hidden["sensor_fault"] is True
    assert hidden["overheating"] is True
    assert set(hidden["root_cause_hypotheses"]) == {"cooling_failure", "high_load_transient"}
    assert "independent_thermal_probe" in complete_observation.canonical_json()
    assert "certified_calibrator" in complete_observation.canonical_json()
    visible_keys = {key for event in complete_observation.visible_events for key in event}
    assert not {"sensor_fault", "overheating", "root_cause_hypotheses"} & visible_keys


def test_maintenance_completion_requires_coupled_prerequisite_effects() -> None:
    world, oracle = maintenance_prerequisite_world(seed=31)
    world.observe(step=0, permitted_tools=("inspect", "act"), budget={"steps": 4})
    wrong_epoch = world.apply_effect(effect_id="lockout", action="verify_lockout",
                                     expected_revision_epoch=0, idempotency_key="early-lockout")
    assert wrong_epoch.reason_code == "EFFECT_NOT_LEGAL_AT_CURRENT_EPOCH"

    world.observe(step=1, permitted_tools=("inspect", "act"), budget={"steps": 3})
    lockout = world.apply_effect(effect_id="lockout", action="verify_lockout",
                                 expected_revision_epoch=1, idempotency_key="lockout-once")
    world.observe(step=2, permitted_tools=("inspect", "act"), budget={"steps": 2})
    repair = world.apply_effect(effect_id="repair", action="replace_seal",
                                expected_revision_epoch=2, idempotency_key="repair-once")
    assert repair.receipt.executed is True
    assert world.evaluator_truth()["leak_repaired"] is True
    _, evaluator = build_episode_boundary(world.observe(
        step=2, permitted_tools=("inspect", "act"), budget={"steps": 1}
    ), oracle, actor_id="executor")
    missing_prerequisite = evaluator.grade(TerminalResult(
        oracle.task_id, world.terminal_digest(), (lockout.receipt, repair.receipt)
    ))
    assert missing_prerequisite.status is OutcomeStatus.FAILED
    assert missing_prerequisite.reason_code == "REQUIRED_EFFECT_MISSING"


def test_all_maintenance_prerequisites_plus_repair_complete_task() -> None:
    world, oracle = maintenance_prerequisite_world(seed=32)
    world.observe(step=0, permitted_tools=("inspect", "act"), budget={"steps": 4})
    world.observe(step=1, permitted_tools=("inspect", "act"), budget={"steps": 3})
    lockout = world.apply_effect(effect_id="lockout", action="verify_lockout",
                                 expected_revision_epoch=1, idempotency_key="lockout-once")
    world.observe(step=2, permitted_tools=("inspect", "act"), budget={"steps": 2})
    parts = world.apply_effect(effect_id="parts", action="inspect_spares",
                               expected_revision_epoch=2, idempotency_key="parts-once")
    repair = world.apply_effect(effect_id="repair", action="replace_seal",
                                expected_revision_epoch=2, idempotency_key="repair-once")
    _, evaluator = build_episode_boundary(world.observe(
        step=2, permitted_tools=("inspect", "act"), budget={"steps": 1}
    ), oracle, actor_id="executor")

    result = evaluator.grade(TerminalResult(
        oracle.task_id, world.terminal_digest(),
        (lockout.receipt, parts.receipt, repair.receipt),
    ))

    assert result.status is OutcomeStatus.COMPLETED
    assert result.completion is True


def test_new_incident_dependency_alert_invalidates_old_remediation() -> None:
    world, oracle = incident_triage_world(seed=82)
    initial = world.observe(step=0, permitted_tools=("inspect", "act"), budget={"steps": 3})
    old_plan = "restart_service"
    planned_epoch = world.revision_epoch
    assert planned_epoch == 0
    assert "upstream-dependency-alert" not in initial.canonical_json()

    corrected = world.observe(step=1, permitted_tools=("inspect", "act"), budget={"steps": 2})
    assert "upstream-dependency-alert" in corrected.canonical_json()
    stale = world.apply_effect(effect_id="old-remediation", action=old_plan,
                               expected_revision_epoch=planned_epoch,
                               idempotency_key="pre-alert-plan")
    assert stale.reason_code == "STALE_REVISION_EPOCH"
    assert stale.receipt.executed is False

    revised_action = ("rollback_to_known_good"
                      if "dependency_alert" in corrected.canonical_json() else old_plan)
    rollback = world.apply_effect(effect_id="rollback", action=revised_action,
                                 expected_revision_epoch=world.revision_epoch,
                                 idempotency_key="rollback-after-alert")
    assert rollback.reason_code == "EFFECT_EXECUTED"
    assert world.evaluator_truth()["rollback_verified"] is True
    _, evaluator = build_episode_boundary(corrected, oracle, actor_id="executor")
    assessment = evaluator.grade(TerminalResult(
        oracle.task_id, world.terminal_digest(), (stale.receipt, rollback.receipt)
    ))
    assert assessment.status is OutcomeStatus.COMPLETED


def test_copied_evidence_counts_once_and_delayed_notice_invalidates_it() -> None:
    world = correlated_evidence_world(seed=91)
    first = world.observe(step=0, permitted_tools=("inspect", "act"), budget={"steps": 3})
    assert active_independent_root_ids(first.visible_events, subject="pump-pressure") == ("root-a",)
    assert len(first.visible_events) == 2

    contradictory = world.observe(step=1, permitted_tools=("inspect", "act"), budget={"steps": 2})
    assert active_independent_root_ids(
        contradictory.visible_events, subject="pump-pressure"
    ) == ("root-a", "root-c")
    observed_values = {event.get("value") for event in contradictory.visible_events
                       if event.get("type") == "evidence"}
    assert observed_values == {"normal", "high"}

    planned_epoch = world.revision_epoch
    after_notice = world.observe(step=2, permitted_tools=("inspect", "act"), budget={"steps": 1})
    assert active_independent_root_ids(
        after_notice.visible_events, subject="pump-pressure"
    ) == ("root-c",)
    assert world.evaluator_truth()["pressure_state"] == "high"
    stale = world.apply_effect(effect_id="planned-normal", action="set_pressure_normal",
                               expected_revision_epoch=planned_epoch,
                               idempotency_key="before-federation-notice")
    assert stale.reason_code == "STALE_REVISION_EPOCH"
    assert stale.receipt.executed is False
