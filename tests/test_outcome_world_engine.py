"""Deterministic in-house world replay and actor/evaluator separation."""

from __future__ import annotations

import unittest

from benchmarks.outcome_worlds import (
    DeterministicWorldSpec,
    IncidentPlan,
    ScheduledWorldEvent,
    build_battery_diagnosis_world,
    build_federated_evidence_world,
    build_incident_triage_world,
    build_maintenance_world,
    create_coding_repair_session,
    diagnose_battery,
    replay_world,
    run_maintenance_actions,
    run_federated_evidence_scenario,
    run_correction_after_plan_scenario,
    run_incident_triage_actions,
)
from memory_fabric.agent_outcomes import AgentObservation


def _spec(seed: int = 41) -> DeterministicWorldSpec:
    return DeterministicWorldSpec(
        task_id="battery-case-41",
        seed=seed,
        initial_truth={"actual_temperature": 91, "sensor_fault": False},
        initial_legal_effects=("inspect_sensor", "reduce_load"),
        events=(
            ScheduledWorldEvent(
                event_id="event-correction",
                tick=4,
                kind="correction",
                observation={"source": "calibration", "status": "verified"},
                truth_updates={"sensor_fault": True, "actual_temperature": 91},
                legal_effects=("inspect_sensor", "replace_sensor", "reduce_load"),
            ),
            ScheduledWorldEvent(
                event_id="event-reading",
                tick=1,
                kind="observation",
                observation={"source": "sensor-a", "reading": 91},
            ),
        ),
    )


class TestDeterministicOutcomeWorldEngine(unittest.TestCase):
    def test_same_seed_replays_to_identical_state_and_outcome_digest(self) -> None:
        first = replay_world(_spec())
        second = replay_world(_spec())
        self.assertEqual(first.canonical_state_bytes(), second.canonical_state_bytes())
        self.assertEqual(first.outcome_digest, second.outcome_digest)
        self.assertEqual(first.revision_epoch, 1)
        self.assertEqual([event["event_id"] for event in first.observations],
                         ["event-reading", "event-correction"])
        self.assertEqual(first.observations[0]["revision_epoch"], 0)
        self.assertEqual(first.observations[1]["revision_epoch"], 1)
        self.assertNotEqual(first.outcome_digest, replay_world(_spec(seed=42)).outcome_digest)

    def test_scheduled_replay_hides_future_observations_truth_and_legal_effects(self) -> None:
        before_correction = replay_world(_spec(), through_tick=2)
        self.assertEqual(before_correction.revision_epoch, 0)
        self.assertEqual(len(before_correction.observations), 1)
        public = before_correction.public_view()
        self.assertEqual(public["tick"], 2)
        self.assertEqual(public["revision_epoch"], 0)
        self.assertNotIn("hidden_truth", public)
        self.assertNotIn("actual_temperature", repr(public))
        self.assertNotIn("legal_effects", public)
        self.assertEqual(public["observations"][0]["data"]["reading"], 91)
        actor_observation = AgentObservation(
            "battery-case-41", "Diagnose the battery.", tuple(public["observations"]),
            ("inspect_sensor", "reduce_load"), {"steps": 3},
        )
        self.assertNotIn("actual_temperature", actor_observation.canonical_json())

        after_correction = replay_world(_spec(), through_tick=4)
        self.assertEqual(after_correction.revision_epoch, 1)
        self.assertEqual(after_correction.hidden_truth["sensor_fault"], True)
        self.assertIn("replace_sensor", after_correction.legal_effects)

    def test_world_inputs_and_snapshots_detach_and_freeze_nested_json(self) -> None:
        initial_truth = {"nested": {"value": 1}}
        observation = {"reading": {"samples": [1, 2]}}
        truth_update = {"nested": {"value": 2}}
        event = ScheduledWorldEvent("event-1", 1, "reading", observation,
                                    truth_updates=truth_update)
        spec = DeterministicWorldSpec("immutable-world", 3, initial_truth,
                                      events=(event,))
        initial_truth["nested"]["value"] = 99
        observation["reading"]["samples"].append(3)
        truth_update["nested"]["value"] = 99
        snapshot = replay_world(spec)
        self.assertEqual(snapshot.hidden_truth["nested"]["value"], 2)
        self.assertEqual(snapshot.observations[0]["data"]["reading"]["samples"], (1, 2))
        with self.assertRaises(TypeError):
            snapshot.hidden_truth["nested"]["value"] = 4
        with self.assertRaises(TypeError):
            snapshot.observations[0]["data"]["reading"]["samples"] = ()

    def test_invalid_event_json_and_duplicate_ids_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite numbers"):
            ScheduledWorldEvent("event-bad", 0, "reading", {"value": float("nan")})
        with self.assertRaisesRegex(ValueError, "unique"):
            DeterministicWorldSpec("duplicate-world", 1, {}, events=(
                ScheduledWorldEvent("event-same", 0, "reading", {}),
                ScheduledWorldEvent("event-same", 1, "correction", {}),
            ))

    def test_correction_after_plan_blocks_stale_effect_and_completes_replan(self) -> None:
        result = run_correction_after_plan_scenario(42)
        self.assertGreater(result.correction_revision_epoch,
                           result.planned_revision_epoch)
        self.assertEqual(result.stale_outcome, "refused")
        self.assertEqual(result.stale_side_effect_count, 0)
        self.assertEqual(result.stale_reason_codes, ("evidence_withdrawn",))
        self.assertEqual(result.replanned_revision_epoch,
                         result.correction_revision_epoch)
        self.assertEqual(result.final_value, result.replanned_value)
        self.assertEqual(result.terminal_status, "COMPLETE")
        self.assertEqual(result.terminal_reason, "complete")

    def test_correction_scenario_digest_is_repeatable(self) -> None:
        first = run_correction_after_plan_scenario(8)
        second = run_correction_after_plan_scenario(8)
        self.assertEqual(first, second)
        self.assertEqual(len(first.world_outcome_digest), 64)

    def test_battery_diagnosis_keeps_sensor_fault_and_overheating_nonexclusive(self) -> None:
        spec = build_battery_diagnosis_world(23)
        snapshot = replay_world(spec)
        diagnosis = diagnose_battery(snapshot.public_view())
        self.assertEqual(diagnosis.conditions, ("overheating", "sensor_fault"))
        self.assertIsNone(diagnosis.root_cause)
        self.assertEqual(
            set(diagnosis.supporting_source_roots), {"overheating", "sensor_fault"})
        condition_roots = {
            root for roots in diagnosis.supporting_source_roots.values() for root in roots
        }
        self.assertEqual(len(condition_roots), 2)
        observation_kinds = {event["kind"] for event in snapshot.observations}
        self.assertEqual(observation_kinds, {
            "sensor_reading", "independent_probe_reading", "calibration_record",
        })
        self.assertTrue(snapshot.hidden_truth["pack_sensor_fault"])
        public = snapshot.public_view()
        self.assertNotIn("pack_sensor_fault", repr(public))
        self.assertNotIn("pack_sensor_offset_c", repr(public))

    def test_maintenance_requires_all_dependent_prerequisites_and_allows_safe_alternatives(self) -> None:
        snapshot = replay_world(build_maintenance_world(7))
        single_answer = run_maintenance_actions(snapshot, ("release_to_service",))
        self.assertFalse(single_answer.completed)
        self.assertEqual(single_answer.executed_actions, ())
        self.assertEqual(single_answer.failure_reason, "mandatory_prerequisites_missing")
        self.assertEqual(single_answer.missing_prerequisites, (
            "cooling_restored", "isolation", "temperature_verified",
        ))

        primary_path = run_maintenance_actions(snapshot, (
            "lockout_primary", "replace_filter", "calibrate_probe", "release_to_service",
        ))
        alternate_path = run_maintenance_actions(snapshot, (
            "lockout_backup", "clear_intake", "crosscheck_probe", "release_to_service",
        ))
        for outcome in (primary_path, alternate_path):
            with self.subTest(path=outcome.executed_actions):
                self.assertTrue(outcome.completed)
                self.assertEqual(outcome.missing_prerequisites, ())
                self.assertEqual(len(outcome.satisfied_prerequisites), 3)

        wrong_order = run_maintenance_actions(snapshot, ("clear_intake", "lockout_primary"))
        self.assertFalse(wrong_order.completed)
        self.assertEqual(wrong_order.executed_actions, ())
        self.assertEqual(wrong_order.failure_reason, "prerequisite_dependency_missing")

    def test_new_incident_alert_requires_rollback_and_revision_bound_replan(self) -> None:
        spec = build_incident_triage_world(9)
        planned_world = replay_world(spec, through_tick=0)
        current_world = replay_world(spec, through_tick=2)
        old_plan = IncidentPlan(
            planned_world.revision_epoch, ("cache",), ("restart_cache",),
        )
        current_plan = IncidentPlan(
            current_world.revision_epoch, ("cache", "queue"),
            ("contain_current_dependencies",),
        )

        outcome = run_incident_triage_actions(
            current_world, prior_plan=old_plan, replan=current_plan,
            prior_remediation_applied=True,
            actions=("rollback_restart_cache", "contain_current_dependencies",
                     "verify_current_dependencies", "close_incident"),
        )
        self.assertTrue(outcome.stale_plan_detected)
        self.assertTrue(outcome.rollback_executed)
        self.assertEqual(outcome.current_revision_epoch, current_plan.revision_epoch)
        self.assertEqual(outcome.contained_dependencies, ("cache", "queue"))
        self.assertTrue(outcome.completed)

        without_rollback = run_incident_triage_actions(
            current_world, prior_plan=old_plan, replan=current_plan,
            prior_remediation_applied=True,
            actions=("contain_current_dependencies", "verify_current_dependencies",
                     "close_incident"),
        )
        self.assertFalse(without_rollback.completed)
        self.assertEqual(without_rollback.failure_reason, "rollback_required")

        stale_replan = IncidentPlan(
            old_plan.revision_epoch, old_plan.dependency_ids,
            ("contain_current_dependencies",),
        )
        rejected_replan = run_incident_triage_actions(
            current_world, prior_plan=old_plan, replan=stale_replan,
            prior_remediation_applied=True,
            actions=("rollback_restart_cache", "contain_current_dependencies",
                     "verify_current_dependencies", "close_incident"),
        )
        self.assertFalse(rejected_replan.completed)
        self.assertEqual(rejected_replan.failure_reason, "replan_required")

    def test_coding_repair_hides_oracle_cases_and_bounds_tool_calls(self) -> None:
        session = create_coding_repair_session(12)
        self.assertEqual(session.visible_files, (
            "src/dependency_compat.py", "tests/public_contract.py",
        ))
        with self.assertRaises(PermissionError):
            session.read_file("tests/hidden_oracle.py")
        source = session.read_file("src/dependency_compat.py")
        broken = (
            "    return (installed[0] == required[0]\n"
            "            and installed[1] >= required[1]\n"
            "            and installed[2] >= required[2])"
        )
        naive = "    return installed[0] >= required[0]"
        correct = "    return installed[0] == required[0] and installed >= required"
        self.assertIn(broken, source)
        session.apply_patch("src/dependency_compat.py", broken, naive)
        self.assertEqual(session.run_public_tests()["status"], "PASS")
        self.assertEqual(session.submit(), {"status": "FAIL"})

        session.apply_patch("src/dependency_compat.py", naive, correct)
        self.assertEqual(session.run_public_tests()["status"], "PASS")
        self.assertEqual(session.submit(), {"status": "PASS"})
        self.assertEqual(session.tool_calls_used, 8)

    def test_coding_patch_interpreter_never_executes_submitted_calls(self) -> None:
        session = create_coding_repair_session(13)
        session.read_file("src/dependency_compat.py")
        broken = (
            "    return (installed[0] == required[0]\n"
            "            and installed[1] >= required[1]\n"
            "            and installed[2] >= required[2])"
        )
        unsafe = "    return __import__('os').system('echo must-not-run')"
        session.apply_patch("src/dependency_compat.py", broken, unsafe)
        self.assertEqual(session.run_public_tests()["status"], "FAIL")
        self.assertEqual(session.submit(), {"status": "FAIL"})

    def test_federation_copies_do_not_count_as_independent_and_late_effect_is_logged(self) -> None:
        result = run_federated_evidence_scenario(31)
        self.assertEqual(result.early_assessment.status, "SINGLE_SOURCE")
        self.assertEqual(result.early_assessment.record_count, 3)
        self.assertEqual(result.early_assessment.copy_count, 2)
        self.assertEqual(result.early_assessment.independent_source_count, 1)
        root_a = "root-source-A-31"
        self.assertEqual(result.early_assessment.claims_by_root[root_a], 7)

        self.assertEqual(result.contradictory_assessment.status, "CONTRADICTORY")
        self.assertEqual(result.contradictory_assessment.independent_source_count, 2)
        self.assertEqual(result.final_assessment.status, "CORROBORATED")
        self.assertEqual(set(result.final_assessment.claims_by_root.values()), {5})
        self.assertEqual(len(result.stale_effect_logs), 1)
        log = result.stale_effect_logs[0]
        self.assertEqual(log.reason, "delayed_federation_notice")
        self.assertEqual(log.original_revision_epoch, 0)
        self.assertGreater(log.current_revision_epoch, log.original_revision_epoch)
        self.assertEqual(set(log.invalidating_event_ids), {
            "credible-source-b", "delayed-notice-a",
        })
        snapshot = replay_world(build_federated_evidence_world(31), through_tick=2)
        self.assertEqual(len(snapshot.observations), 3)
        self.assertNotIn("delayed-notice-a", repr(snapshot.public_view()))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
