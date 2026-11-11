"""Deterministic simulated continuations are version-bound and local."""

from __future__ import annotations

import unittest

from memory_fabric.causal_replay.environment import (DeterministicEnvironment,
    WorldTransition, battery_sensor_environment, continue_counterfactual)
from memory_fabric.causal_replay.certificates import ExplanationStatus
from memory_fabric.causal_replay.types import CDMError


class TestDeterministicEnvironment(unittest.TestCase):
    def setUp(self):
        self.environment = DeterministicEnvironment("battery-world", "v1",
            "sim-agent", "sim-sensor", (
                WorldTransition("normal", "cool", "stable", "overheat", False),
                WorldTransition("normal", "inspect", "diagnosed", "overheat", True)))

    def test_changed_action_regenerates_versioned_tool_and_observation(self):
        cooled = self.environment.step("normal", "cool", sequence=12)
        inspected = self.environment.step("normal", "inspect", sequence=12)
        repeated = self.environment.step("normal", "cool", sequence=12)
        self.assertEqual(cooled, repeated)
        self.assertEqual(cooled.simulator_version, "v1")
        self.assertNotEqual(cooled.tool_observation.output_digest,
                            inspected.tool_observation.output_digest)
        self.assertEqual(cooled.observation.kind, "simulated_endogenous")
        self.assertNotEqual(cooled.observation.observation_id,
                            inspected.observation.observation_id)
        updated = DeterministicEnvironment("battery-world", "v2", "sim-agent",
            "sim-sensor", self.environment.transitions)
        self.assertNotEqual(self.environment.schema_digest, updated.schema_digest)

    def test_unknown_action_does_not_fall_through_to_real_execution(self):
        with self.assertRaises(CDMError):
            self.environment.step("normal", "shell", sequence=1)

    def test_synthetic_battery_sensor_and_diagnostics_are_first_party_data(self):
        world = battery_sensor_environment()
        normal = world.step("nominal", "inspect", sequence=10)
        failure = world.step("cooling-failure", "inspect", sequence=10)
        diagnostic = world.step(failure.next_state, "diagnose", sequence=11)
        self.assertFalse(normal.observation.value)
        self.assertTrue(failure.observation.value)
        self.assertTrue(diagnostic.observation.value)
        self.assertEqual(world.simulator_id, "synthetic-battery-world")
        self.assertNotIn("physical", world.simulator_id)

    def test_dependent_altered_action_is_undefined_without_simulator(self):
        refused = continue_counterfactual("cool", "inspect",
            dependent_later_observation=True, state="normal", sequence=13)
        self.assertEqual(refused.status, ExplanationStatus.UNDEFINED_CONTINUATION)
        self.assertIsNone(refused.simulated)
        simulated = continue_counterfactual("cool", "inspect",
            dependent_later_observation=True, state="normal", sequence=13,
            simulator=self.environment)
        self.assertEqual(simulated.status, ExplanationStatus.EXACT)
        self.assertEqual(simulated.simulated.observation.value, True)
        self.assertEqual(simulated.simulated.simulator_version, "v1")
        independent = continue_counterfactual("cool", "inspect",
            dependent_later_observation=False, state="normal", sequence=13)
        self.assertEqual(independent.status, ExplanationStatus.EXACT)


if __name__ == "__main__":
    unittest.main()
