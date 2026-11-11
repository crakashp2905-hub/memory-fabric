"""Interventions are disposable overlays and factual state remains unchanged."""

from __future__ import annotations

import unittest
from dataclasses import replace

from memory_fabric import MemoryFabric
from memory_fabric.causal_replay.bayes import BinaryNode
from memory_fabric.causal_replay.intervention import (ReplacementFixture,
    SensitivityFixture, compose, create)
from memory_fabric.causal_replay.capture import capture
from memory_fabric.causal_replay.replay import (deterministic_simulator, replay,
                                                replay_captured)
from memory_fabric.causal_replay.state import Observation
from memory_fabric.causal_replay.types import (BeliefReference, InvalidIntervention,
    Erased, ReplayContext, ReplayStatus)
from memory_fabric.service import MemoryService


class TestInterventions(unittest.TestCase):
    def test_overlay_lifecycle_drops_disposable_state_on_success_and_refusal(self):
        nodes = (BinaryNode("fault", (), {(): 0.2}),)
        simulator = deterministic_simulator(nodes)
        source = (Observation("e1", "fault", True, "sensor", 1),)
        source_snapshot = tuple(source)
        ref = BeliefReference("e1", 1, "tenant-a", "a" * 64)
        successful = replay(source, intervention=create(ref, "suppress"),
            simulator_id="local", simulators={"local": simulator})
        self.assertEqual(successful.state.observations, ())
        self.assertEqual(source, source_snapshot)
        with self.assertRaises(ValueError):
            replay(source, intervention=create(
                BeliefReference("missing", 1, "tenant-a", "b" * 64), "suppress"),
                simulator_id="local", simulators={"local": simulator})
        self.assertEqual(source, source_snapshot)

    def test_noop_irrelevant_replace_and_suppress_ground_truth_controls(self):
        nodes = (BinaryNode("fault", (), {(): 0.2}),
                 BinaryNode("alarm", ("fault",), {(False,): 0.1, (True,): 0.9}),
                 BinaryNode("weather", (), {(): 0.5}))
        simulator = deterministic_simulator(nodes)
        evidence = (Observation("e1", "alarm", True, "sensor-a", 1),)
        reference = BeliefReference("e1", 1, "tenant-a", "a" * 64)
        baseline = simulator.run(evidence)
        noop = replay(evidence, intervention=create(None, "noop"), simulator_id="local",
                      simulators={"local": simulator})
        self.assertEqual(noop.state.fingerprint, baseline.fingerprint)
        irrelevant = simulator.run((*evidence,
            Observation("weather-1", "weather", True, "weather-sensor", 2)))
        self.assertEqual(irrelevant.posterior["fault"], baseline.posterior["fault"])
        suppressed = replay(evidence, intervention=create(reference, "suppress"),
            simulator_id="local", simulators={"local": simulator})
        self.assertEqual(suppressed.state.observations, ())
        replacement = create(reference, "replace", replacement=ReplacementFixture(
            "replace-control-v1", Observation("e1", "alarm", False, "fixture", 1)))
        replaced = replay(evidence, intervention=replacement, simulator_id="local",
                          simulators={"local": simulator})
        self.assertFalse(replaced.state.observations[0].value)
        self.assertTrue(evidence[0].value)

    def test_model_sensitivity_is_labelled_and_does_not_delete_evidence(self):
        nodes = (BinaryNode("fault", (), {(): 0.2}),
                 BinaryNode("alarm", ("fault",), {(False,): 0.1, (True,): 0.9}))
        observations = (Observation("e1", "alarm", True, "sensor", 1),)
        simulator = deterministic_simulator(nodes)
        fixture = SensitivityFixture("reliability-fixture-v1", "alarm", (True,), 0.5)
        result = replay(observations,
            intervention=create(None, "sensitivity", sensitivity=fixture),
            simulator_id="local", simulators={"local": simulator})
        factual = simulator.run(observations)
        self.assertEqual(result.intervention_kind, "model_assumption_change")
        self.assertEqual(result.state.observations, factual.observations)
        self.assertNotEqual(result.state.posterior["fault"], factual.posterior["fault"])
        with self.assertRaises(InvalidIntervention):
            replay(observations,
                intervention=replace(create(None, "sensitivity", sensitivity=fixture),
                                     intervention_id="0" * 64),
                simulator_id="local", simulators={"local": simulator})
        removed = replay(observations,
            intervention=create(BeliefReference("e1", 1, "tenant-a", "a" * 64),
                                "suppress"),
            simulator_id="local", simulators={"local": simulator})
        self.assertEqual(removed.intervention_kind, "evidence_change")
        self.assertEqual(removed.state.observations, ())

    def test_withhold_is_time_bounded_and_requires_current_authorized_capture(self):
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        service = MemoryService(fabric)
        service.register_agent("withhold-agent", b"withhold-key", tenant_id="tenant-wh")
        session = service.session(service.issue("withhold-agent"))
        memory_id = session.remember("captured source for temporary withholding")
        captured = capture(fabric, session, [memory_id],
                           context=ReplayContext(fabric.log.head_seq))
        ref = captured.evidence[0]
        observation = Observation(memory_id, "fault", True, "captured-source", 5)
        nodes = (BinaryNode("fault", (), {(): 0.2}),)
        simulator = deterministic_simulator(nodes)
        within = create(ref, "withhold", window_start=4, window_end=6)
        withheld = replay_captured(fabric, session, captured, (observation,),
            intervention=within, simulator_id="local", simulators={"local": simulator})
        self.assertEqual(withheld.state.observations, ())
        outside = create(ref, "withhold", window_start=6, window_end=8)
        visible = replay_captured(fabric, session, captured, (observation,),
            intervention=outside, simulator_id="local", simulators={"local": simulator})
        self.assertEqual(visible.state.observations, (observation,))
        with self.assertRaises(InvalidIntervention):
            create(ref, "withhold", window_start=8, window_end=7)
        fabric.quarantine(memory_id, reason="revoke source", actor="operator",
                          propagate=False)
        with self.assertRaises(Erased):
            replay_captured(fabric, session, captured, (observation,),
                intervention=within, simulator_id="local", simulators={"local": simulator})

    def test_batch_rejects_overlaps_before_replay_and_applies_independent_ops(self):
        nodes = (BinaryNode("fault", (), {(): 0.2}),)
        observations = (Observation("e1", "fault", True, "s1", 1),
                        Observation("e2", "fault", False, "s2", 2))
        first = BeliefReference("e1", 1, "tenant-a", "a" * 64)
        second = BeliefReference("e2", 1, "tenant-a", "b" * 64)
        suppress = create(first, "suppress")
        replace_same = create(first, "replace", replacement=ReplacementFixture(
            "fixture-v1", Observation("e1", "fault", False, "fixture", 1)))
        with self.assertRaises(InvalidIntervention):
            compose((suppress, replace_same))

        batch = compose((suppress, create(second, "delay", delay_until=5)))
        result = replay(observations, intervention=batch, simulator_id="local",
                        simulators={"local": deterministic_simulator(nodes)})
        self.assertEqual([(item.observation_id, item.sequence)
                          for item in result.state.observations], [("e2", 5)])
        self.assertEqual([(item.observation_id, item.sequence)
                          for item in observations], [("e1", 1), ("e2", 2)])

    def test_frozen_replacement_fixture_is_schema_checked_and_source_safe(self):
        nodes = (BinaryNode("fault", (), {(): 0.2}),)
        original = (Observation("e1", "fault", True, "sensor", 1),)
        ref = BeliefReference("e1", 1, "tenant-a", "a" * 64)
        fixture = ReplacementFixture("fixture-v1",
            Observation("e1", "fault", False, "frozen-fixture", 1))
        intervention = create(ref, "replace", replacement=fixture)
        result = replay(original, intervention=intervention, simulator_id="local",
                        simulators={"local": deterministic_simulator(nodes)})
        self.assertNotEqual(result.state.posterior["fault"],
                            deterministic_simulator(nodes).run(original).posterior["fault"])
        self.assertEqual(original[0].value, True)
        self.assertEqual(result.state.observations[0].origin, "frozen-fixture")
        with self.assertRaises(InvalidIntervention):
            create(ref, "replace", replacement=Observation("e1", "fault", False,
                                                            "unlabelled", 1))
        with self.assertRaises(InvalidIntervention):
            create(ref, "replace", replacement=ReplacementFixture("fixture-v1",
                Observation("other-id", "fault", False, "frozen-fixture", 1)))

    def test_noop_suppress_delay_and_policy_swap_are_distinct(self):
        nodes = (BinaryNode("fault", (), {(): 0.2}),
                 BinaryNode("alarm", ("fault",), {(False,): 0.1, (True,): 0.9}))
        observations = (Observation("e1", "alarm", True, "sensor", 1),)
        ref = BeliefReference("e1", 1, "tenant-a", "a" * 64)
        simulator = deterministic_simulator(nodes)
        registry = {"local": simulator}
        noop = replay(observations, intervention=create(None, "noop"),
                      simulator_id="local", simulators=registry)
        self.assertEqual(noop.status, ReplayStatus.EXACT)
        self.assertEqual(noop.state.fingerprint, simulator.run(observations).fingerprint)
        delay = replay(observations, intervention=create(ref, "delay", delay_until=4),
                       simulator_id="local", simulators=registry)
        self.assertEqual(delay.state.observations[0].sequence, 4)
        self.assertEqual(observations[0].sequence, 1)
        with self.assertRaises(ValueError):
            replay(observations, intervention=create(ref, "delay", delay_until=1),
                   simulator_id="local", simulators=registry)
        with self.assertRaises(ValueError):
            replay(observations, intervention=create(ref, "delay", delay_until=0),
                   simulator_id="local", simulators=registry)
        changed_policy = replay(observations,
            intervention=create(None, "swap_policy", policy_id="review-v2"),
            simulator_id="local", simulators=registry)
        self.assertEqual(changed_policy.state.policy_id, "review-v2")
        self.assertNotEqual(changed_policy.state.fingerprint, noop.state.fingerprint)

    def test_replay_does_not_change_fabric_or_auth_state(self):
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        service = MemoryService(fabric)
        service.register_agent("agent-a", b"test", tenant_id="tenant-a")
        session = service.session(service.issue("agent-a"))
        memory_id = session.remember("ordinary evidence")
        before = (fabric.log.head_seq, fabric.state.memories[memory_id].version,
                  dict(fabric.state.withdrawal_basis))
        nodes = (BinaryNode("fault", (), {(): 0.3}),)
        observation = Observation("e1", "fault", True, "sensor", 1)
        ref = BeliefReference("e1", 1, "tenant-a", "b" * 64)
        replay((observation,), intervention=create(ref, "suppress"),
               simulator_id="local", simulators={"local": deterministic_simulator(nodes)})
        after = (fabric.log.head_seq, fabric.state.memories[memory_id].version,
                 dict(fabric.state.withdrawal_basis))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
