"""Deterministic in-house world replay and actor/evaluator separation."""

from __future__ import annotations

import unittest

from benchmarks.outcome_worlds import (
    DeterministicWorldSpec,
    ScheduledWorldEvent,
    build_battery_diagnosis_world,
    diagnose_battery,
    replay_world,
    run_correction_after_plan_scenario,
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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
