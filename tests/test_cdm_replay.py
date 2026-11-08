"""Factual replay is deterministic, ordered, bounded and fail-closed."""

from __future__ import annotations

import unittest
from unittest.mock import patch
import socket
import subprocess
import os
import random
import json
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.service import MemoryService
from memory_fabric.causal_replay.bayes import BinaryNode
from memory_fabric.causal_replay.capture import (capture, capture_rng_state,
    record_decision)
from memory_fabric.causal_replay.executor import (create_execution_checkpoint,
    execute, execute_from_checkpoint, execute_full_suffix, execute_step_intervention,
    execute_recorded, execute_captured,
    first_divergence)
from memory_fabric.causal_replay.certificates import (issue_verified_recorded_replay,
    verify as verify_replay_certificate)
from memory_fabric.causal_replay.intervention import create as create_intervention
from memory_fabric.causal_replay.policy import ThresholdPolicy
from memory_fabric.causal_replay.replay import deterministic_simulator
from memory_fabric.causal_replay.state import (Observation,
    generated_belief_state_schema, update, validate_belief_state_record)
from memory_fabric.causal_replay.types import (BudgetExceeded, Erased, NonReplayable, Unauthorized,
                                               ReplayStatus)
from memory_fabric.causal_replay.verifier import verify_execution
from dataclasses import replace
from memory_fabric.causal_replay.types import (BeliefReference, DecisionRecord, ReplayContext,
    ToolObservation, parse_record, serialize_record)


class TestReplay(unittest.TestCase):
    def setUp(self):
        self.nodes = (BinaryNode("fault", (), {(): 0.2}),
                      BinaryNode("alarm", ("fault",), {(False,): 0.1, (True,): 0.9}))
        self.simulator = deterministic_simulator(self.nodes)
        self.policy = ThresholdPolicy("fault")
        self.events = (Observation("e2", "alarm", True, "sensor-b", 2),
                       Observation("e1", "alarm", True, "sensor-a", 1))

    def test_order_tie_break_and_expected_fingerprint(self):
        result = execute(self.events, simulator=self.simulator, policy=self.policy)
        self.assertEqual([step.observation_id for step in result.steps], ["e1", "e2"])
        confirmed = execute(self.events, simulator=self.simulator, policy=self.policy,
                            expected_fingerprint=result.final_state.fingerprint)
        self.assertEqual(confirmed.status, ReplayStatus.EXACT)
        mismatch = execute(self.events, simulator=self.simulator, policy=self.policy,
                           expected_fingerprint="0" * 64)
        self.assertEqual(mismatch.status, ReplayStatus.NON_REPLAYABLE)

    def test_belief_state_schema_contains_normalized_uncertainty_and_policy_digest(self):
        reference = BeliefReference("memory-1", 1, "tenant-a", "a" * 64)
        state = update(self.nodes, self.events, updater_id="exact-v1", policy_id="policy-v1")
        state = replace(state, evidence_refs=(reference,))
        record = state.to_dict()
        schema = generated_belief_state_schema()
        validated = validate_belief_state_record(record)
        self.assertEqual(schema["record_schema"], "memory-fabric-cdm-v1")
        self.assertEqual(validated["evidence_refs"][0]["belief_id"], "memory-1")
        self.assertEqual(validated["variables"], sorted(validated["posterior"]))
        self.assertEqual(validated["uncertainty"]["fault"],
                         min(state.posterior["fault"], 1 - state.posterior["fault"]))
        self.assertRegex(validated["update_policy_digest"], r"^[0-9a-f]{64}$")
        self.assertNotIn("lifecycle_state", validated)
        self.assertNotIn("authorized", validated)
        for malformed in (
            {**record, "unexpected": True},
            {**record, "uncertainty": {"fault": 0.49}},
            {**record, "update_policy_digest": "not-a-digest"},
            {**record, "variables": ["fault"]},
        ):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                validate_belief_state_record(malformed)

    def test_generated_belief_schema_fixture_is_current(self):
        root = Path(__file__).resolve().parents[1]
        fixture = json.loads((root / "docs/schemas/cdm-belief-state-v1.json")
                             .read_text(encoding="utf-8"))
        self.assertEqual(fixture, generated_belief_state_schema())

    def test_belief_state_probabilities_cannot_change_governance_or_access(self):
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        service = MemoryService(fabric)
        service.register_agent("belief-agent", b"belief-agent-key", tenant_id="tenant-belief")
        session = service.session(service.issue("belief-agent"))
        memory_id = session.remember("withdrawn evidence remains governed by lifecycle")
        captured_before = capture(fabric, session, [memory_id],
                                  context=ReplayContext(fabric.log.head_seq))
        before_state = fabric.state.memories[memory_id].lifecycle_state
        state = update(self.nodes, self.events, updater_id="exact-v1", policy_id="policy-v1")
        high_belief = replace(state, posterior={**state.posterior, "fault": 1.0})
        self.assertEqual(fabric.state.memories[memory_id].lifecycle_state, before_state)
        self.assertEqual(captured_before.evidence[0].belief_id, memory_id)
        self.assertNotIn("authorized", high_belief.to_dict())
        fabric.quarantine(memory_id, reason="governance test", actor="operator",
                          propagate=False)
        with self.assertRaises(Erased):
            capture(fabric, session, [memory_id],
                    context=ReplayContext(fabric.log.head_seq))
        self.assertEqual(fabric.state.memories[memory_id].lifecycle_state.value, "quarantined")

    def test_budget_refuses_partial_and_divergence_is_localized(self):
        with self.assertRaises(BudgetExceeded):
            execute(self.events, simulator=self.simulator, policy=self.policy, max_events=1)
        factual = execute(self.events, simulator=self.simulator, policy=self.policy)
        changed = execute((Observation("e1", "alarm", False, "sensor-a", 1),),
                          simulator=self.simulator, policy=self.policy)
        self.assertEqual(first_divergence(factual, changed), 1)

    def test_checked_checkpoint_suffix_matches_cold_replay(self):
        prefix = (Observation("e1", "alarm", True, "sensor-a", 1),)
        suffix = (Observation("e2", "alarm", True, "sensor-b", 2),)
        checkpoint = create_execution_checkpoint(
            execute(prefix, simulator=self.simulator, policy=self.policy),
            simulator=self.simulator, policy=self.policy)
        resumed = execute_from_checkpoint(checkpoint, suffix, simulator=self.simulator,
                                           policy=self.policy)
        cold = execute((*prefix, *suffix), simulator=self.simulator, policy=self.policy)
        self.assertEqual(resumed.final_state.fingerprint, cold.final_state.fingerprint)
        self.assertEqual(resumed.steps, cold.steps)
        self.assertEqual(resumed.consumed, cold.consumed)
        with self.assertRaises(NonReplayable):
            execute_from_checkpoint(replace(checkpoint, state_fingerprint="0" * 64), suffix,
                                    simulator=self.simulator, policy=self.policy)

    def test_full_suffix_oracle_matches_cold_replay_at_every_cut(self):
        observations = tuple(Observation(f"suffix-{index}", "alarm", bool(index % 2),
            f"sensor-{index}", index + 1) for index in range(5))
        cold = execute(observations, simulator=self.simulator, policy=self.policy)
        for cut in range(len(observations) + 1):
            with self.subTest(cut=cut):
                suffix = execute_full_suffix(observations, affected_index=cut,
                    simulator=self.simulator, policy=self.policy)
                self.assertEqual(suffix.execution_kind, "full_suffix_oracle")
                self.assertEqual(suffix.steps, cold.steps)
                self.assertEqual(suffix.final_state.fingerprint,
                                 cold.final_state.fingerprint)
                self.assertEqual(suffix.consumed, len(observations))

    def test_local_car_inspired_step_intervention_replays_suffix(self):
        observations = (Observation("step-1", "alarm", True, "sensor-a", 1),
                        Observation("step-2", "alarm", False, "sensor-b", 2))
        original = tuple(observations)
        comparison = execute_step_intervention(observations,
            target_observation_id="step-1", simulator=self.simulator, policy=self.policy)
        self.assertEqual(comparison.method, "local_step_suppression_full_suffix_replay")
        self.assertEqual(comparison.counterfactual.execution_kind, "full_suffix_oracle")
        self.assertEqual(comparison.counterfactual.source_observations,
                         (observations[1],))
        self.assertEqual(comparison.counterfactual.consumed, 1)
        self.assertIn("not_official_car_reproduction", comparison.limitations)
        self.assertEqual(observations, original)
        with self.assertRaises(NonReplayable):
            execute_step_intervention(observations, target_observation_id="absent",
                simulator=self.simulator, policy=self.policy)

    def test_seeded_cold_replay_matches_checkpoint_at_every_cut(self):
        for seed in (7, 41, 20261108):
            rng = random.Random(seed)
            trace = tuple(Observation(f"seed-{seed}-event-{index}", "alarm",
                bool(rng.getrandbits(1)), f"sensor-{index}", index)
                for index in range(1, 7))
            cold = execute(trace, simulator=self.simulator, policy=self.policy)
            for cut in range(1, len(trace)):
                with self.subTest(seed=seed, cut=cut):
                    prefix = execute(trace[:cut], simulator=self.simulator,
                                     policy=self.policy)
                    checkpoint = create_execution_checkpoint(prefix,
                        simulator=self.simulator, policy=self.policy)
                    resumed = execute_from_checkpoint(checkpoint, trace[cut:],
                        simulator=self.simulator, policy=self.policy)
                    self.assertEqual(resumed.status, cold.status)
                    self.assertEqual(resumed.final_state.fingerprint,
                                     cold.final_state.fingerprint)
                    self.assertEqual(resumed.steps, cold.steps)

    def test_replay_never_constructs_socket_or_process(self):
        events = (Observation("e1", "alarm", True, "sensor-a", 1),)
        with patch.object(socket, "socket", side_effect=AssertionError("socket constructed")), \
                patch.object(subprocess, "Popen", side_effect=AssertionError("process started")), \
                patch.object(os, "system", side_effect=AssertionError("shell started")):
            result = execute(events, simulator=self.simulator, policy=self.policy)
        self.assertEqual(result.status, ReplayStatus.EXACT)

    def test_replay_rejects_live_fabric_or_capture_objects_as_trace(self):
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        service = MemoryService(fabric)
        service.register_agent("projection-agent", b"projection-key", tenant_id="projection")
        session = service.session(service.issue("projection-agent"))
        memory_id = session.remember("historical replay evidence")
        from memory_fabric.causal_replay.capture import capture
        from memory_fabric.causal_replay.types import ReplayContext, SimulatorForbidden
        captured = capture(fabric, session, [memory_id],
                           context=ReplayContext(fabric.log.head_seq))
        with self.assertRaises(SimulatorForbidden):
            execute(fabric, simulator=self.simulator, policy=self.policy)
        with self.assertRaises(SimulatorForbidden):
            execute((captured,), simulator=self.simulator, policy=self.policy)
        factual = execute(self.events, simulator=self.simulator, policy=self.policy)
        session.remember("new present-day belief that was not in the trace")
        repeated = execute(self.events, simulator=self.simulator, policy=self.policy)
        self.assertEqual(repeated.final_state.fingerprint, factual.final_state.fingerprint)

    def test_independent_verifier_accepts_valid_and_rejects_tampered_trace(self):
        result = execute(self.events, simulator=self.simulator, policy=self.policy)
        self.assertTrue(verify_execution(self.events, execution=result,
            simulator=self.simulator, policy=self.policy).verified)
        altered_step = replace(result.steps[0], proposal="diagnose")
        altered = replace(result, steps=(altered_step, *result.steps[1:]))
        self.assertFalse(verify_execution(self.events, execution=altered,
            simulator=self.simulator, policy=self.policy).verified)

    def test_duplicate_event_ids_refuse_and_reordered_steps_fail(self):
        duplicate = (self.events[0], replace(self.events[1], observation_id=self.events[0].observation_id))
        with self.assertRaises(NonReplayable):
            execute(duplicate, simulator=self.simulator, policy=self.policy)
        result = execute(self.events, simulator=self.simulator, policy=self.policy)
        swapped = replace(result, steps=tuple(reversed(result.steps)))
        self.assertFalse(verify_execution(self.events, execution=swapped,
            simulator=self.simulator, policy=self.policy).verified)
        self.assertEqual(verify_execution(duplicate, execution=result,
            simulator=self.simulator, policy=self.policy).code, "DUPLICATE_EVENT_ID")

    def test_incremental_fingerprint_matches_canonical_updater_after_conflict(self):
        trace = (Observation("a", "alarm", True, "sensor-a", 1),
                 Observation("b", "alarm", False, "sensor-b", 2),
                 Observation("c", "fault", True, "sensor-c", 3))
        execution = execute(trace, simulator=self.simulator, policy=self.policy)
        self.assertEqual(execution.final_state.fingerprint,
                         update(self.nodes, trace, updater_id=self.simulator.updater_id,
                                policy_id=self.policy.policy_id).fingerprint)
        verified = verify_execution(trace, execution=execution,
                                    simulator=self.simulator, policy=self.policy)
        self.assertTrue(verified.verified)
        self.assertEqual(verified.checked_steps, len(trace))

    def test_changed_evidence_recomputes_all_downstream_policy_proposals(self):
        trace = (Observation("a", "alarm", True, "sensor-a", 1),
                 Observation("b", "alarm", False, "sensor-b", 2))
        factual = execute(trace, simulator=self.simulator, policy=self.policy)
        counterfactual = execute((trace[0],), simulator=self.simulator, policy=self.policy)
        self.assertEqual(factual.consumed, len(trace))
        self.assertEqual(counterfactual.consumed, 1)
        self.assertNotEqual(factual.steps[-1].proposal, counterfactual.steps[-1].proposal)
        self.assertEqual(counterfactual.steps[-1].proposal, "investigate")

    def test_rng_continuation_metadata_tampering_refuses_exactness(self):
        result = execute(self.events, simulator=self.simulator, policy=self.policy)
        changed = replace(result, rng_applicability="seeded_random_but_state_missing")
        verified = verify_execution(self.events, execution=changed,
                                    simulator=self.simulator, policy=self.policy)
        self.assertFalse(verified.verified)
        self.assertEqual(verified.code, "TRACE_NOT_VERIFIABLE")

    def test_recorded_policy_digest_must_resolve_to_exact_local_implementation(self):
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        service = MemoryService(fabric)
        service.register_agent("decision-agent", b"decision-key", tenant_id="tenant-cdm")
        session = service.session(service.issue("decision-agent"))
        memory_id = session.remember("alarm sensor report")
        memory_id_2 = session.remember("independent alarm sensor report")
        captured = capture(fabric, session, [memory_id, memory_id_2],
                           context=ReplayContext(fabric.log.head_seq))
        record = record_decision(fabric, session,
            options=("monitor", "investigate", "diagnose"), selected="monitor",
            evidence=captured.evidence, policy_id=self.policy.policy_id,
            policy_digest=self.policy.implementation_digest)
        captured = capture(fabric, session, [memory_id, memory_id_2],
            context=ReplayContext(fabric.log.head_seq), decision=record)
        self.assertEqual(parse_record(DecisionRecord, serialize_record(record)), record)
        result = execute_recorded(fabric, self.events, simulator=self.simulator,
                                  policy=self.policy, decision_record=record)
        self.assertEqual(result.status, ReplayStatus.EXACT)
        self.assertEqual(result.execution_kind, "policy_reexecution")
        self.assertEqual(result.steps[-1].proposal, "investigate")
        self.assertNotEqual(result.steps[-1].proposal, record.selected)
        factual_trace = tuple(Observation(ref.belief_id, "alarm", True,
            f"sensor-memory-{index}", index + 3)
            for index, ref in enumerate(captured.evidence))
        capture_bound_result = execute_captured(fabric, session, captured,
            factual_trace, simulator=self.simulator, policy=self.policy,
            decision_record=record)
        self.assertEqual(capture_bound_result.status, ReplayStatus.EXACT)
        intervention = create_intervention(captured.evidence[0], "suppress")
        certificate = issue_verified_recorded_replay(fabric=fabric,
            decision_record=record, factual_observations=factual_trace,
            intervention=intervention, simulator=self.simulator, policy=self.policy,
            session=session, capture_result=captured,
            capture_digest=captured.factual_digest,
            intervention_digest=intervention.intervention_id,
            updater_id=self.simulator.updater_id, policy_id=self.policy.policy_id)
        self.assertEqual(certificate.status, "EXACT")
        self.assertTrue(verify_replay_certificate(certificate))
        with self.assertRaises((NonReplayable, Unauthorized)):
            issue_verified_recorded_replay(fabric=fabric, decision_record=record,
                factual_observations=(replace(factual_trace[0], observation_id="unbound"),
                                      factual_trace[1]),
                intervention=intervention, simulator=self.simulator, policy=self.policy,
                session=session, capture_result=captured,
                capture_digest=captured.factual_digest,
                intervention_digest=intervention.intervention_id,
                updater_id=self.simulator.updater_id, policy_id=self.policy.policy_id)
        with self.assertRaises(NonReplayable):
            issue_verified_recorded_replay(fabric=fabric, decision_record=record,
                factual_observations=factual_trace, intervention=intervention,
                simulator=self.simulator, policy=self.policy,
                session=session, capture_result=captured,
                capture_digest=captured.factual_digest, intervention_digest="0" * 64,
                updater_id=self.simulator.updater_id, policy_id=self.policy.policy_id)
        outside_target = create_intervention(captured.evidence[0], "suppress")
        receipt_without_target = record_decision(fabric, session,
            options=("monitor", "investigate", "diagnose"), selected="monitor",
            evidence=(captured.evidence[1],), policy_id=self.policy.policy_id,
            policy_digest=self.policy.implementation_digest)
        capture_without_target = capture(fabric, session, [memory_id_2],
            context=ReplayContext(fabric.log.head_seq), decision=receipt_without_target)
        with self.assertRaises(NonReplayable):
            issue_verified_recorded_replay(fabric=fabric,
                decision_record=receipt_without_target,
                factual_observations=(factual_trace[1],), intervention=outside_target,
                simulator=self.simulator, policy=self.policy, session=session,
                capture_result=capture_without_target,
                capture_digest=capture_without_target.factual_digest,
                intervention_digest=outside_target.intervention_id,
                updater_id=self.simulator.updater_id, policy_id=self.policy.policy_id)
        missing_policy = record_decision(fabric, session,
            options=("monitor", "investigate", "diagnose"), selected="investigate",
            evidence=captured.evidence, policy_id="unregistered-policy-v9",
            policy_digest="d" * 64)
        with self.assertRaises(NonReplayable) as unresolved:
            execute_recorded(fabric, self.events, simulator=self.simulator,
                             policy=self.policy, decision_record=missing_policy)
        self.assertEqual(unresolved.exception.code, "NON_REPLAYABLE")
        changed_policy = ThresholdPolicy("fault", diagnose_above=0.99)
        with self.assertRaises(NonReplayable) as changed:
            execute_recorded(fabric, self.events, simulator=self.simulator,
                             policy=changed_policy, decision_record=record)
        self.assertEqual(changed.exception.code, "NON_REPLAYABLE")
        forged = replace(record, policy_digest="0" * 64)
        with self.assertRaises(NonReplayable):
            execute_recorded(fabric, self.events, simulator=self.simulator,
                             policy=self.policy, decision_record=forged)
        missing_rng = record_decision(fabric, session,
            options=("monitor", "investigate", "diagnose"), selected="investigate",
            evidence=captured.evidence, policy_id=self.policy.policy_id,
            policy_digest=self.policy.implementation_digest,
            rng_applicability="missing_state_non_replayable")
        with self.assertRaises(NonReplayable):
            execute_recorded(fabric, self.events, simulator=self.simulator,
                             policy=self.policy, decision_record=missing_rng)
        opaque_tool = ToolObservation("decision-agent", "sensor-tool", "a" * 64,
            "b" * 64, "c" * 64, "opaque")
        tool_record = record_decision(fabric, session,
            options=("monitor", "investigate", "diagnose"), selected="investigate",
            evidence=captured.evidence, policy_id=self.policy.policy_id,
            policy_digest=self.policy.implementation_digest,
            tool_observations=(opaque_tool,))
        with self.assertRaises(NonReplayable) as missing_handler:
            execute_recorded(fabric, self.events, simulator=self.simulator,
                             policy=self.policy, decision_record=tool_record)
        self.assertEqual(missing_handler.exception.code, "NON_REPLAYABLE")
        service.revoke(session.credential)
        with self.assertRaises((NonReplayable, Unauthorized)):
            issue_verified_recorded_replay(fabric=fabric, decision_record=record,
                factual_observations=factual_trace, intervention=intervention,
                simulator=self.simulator, policy=self.policy, session=session,
                capture_result=captured, capture_digest=captured.factual_digest,
                intervention_digest=intervention.intervention_id,
                updater_id=self.simulator.updater_id, policy_id=self.policy.policy_id)
        # A fresh credential keeps current authorization while erasure invalidates
        # the historical evidence commitment.
        service.register_agent("decision-agent-2", b"decision-key-2", tenant_id="tenant-cdm")
        fresh_session = service.session(service.issue("decision-agent-2"))
        erased_id = captured.evidence[0].belief_id
        fabric.erase_content(erased_id, actor="decision-agent-2", reason="privacy request")
        with self.assertRaises(Erased):
            issue_verified_recorded_replay(fabric=fabric, decision_record=record,
                factual_observations=factual_trace, intervention=intervention,
                simulator=self.simulator, policy=self.policy, session=fresh_session,
                capture_result=captured, capture_digest=captured.factual_digest,
                intervention_digest=intervention.intervention_id,
                updater_id=self.simulator.updater_id, policy_id=self.policy.policy_id)

    def test_rng_snapshot_roundtrips_full_state_and_internal_position(self):
        rng = random.Random(20261108)
        rng.random()
        snapshot = capture_rng_state(rng)
        snapshot = parse_record(type(snapshot), serialize_record(snapshot))
        clone = random.Random()
        clone.setstate(snapshot.to_stdlib_state())
        self.assertEqual(snapshot.position, snapshot.internal_state[-1])
        self.assertEqual([rng.random() for _ in range(4)], [clone.random() for _ in range(4)])

    def test_same_seed_wrong_rng_position_refuses_recorded_replay(self):
        correct_rng = random.Random(991)
        correct_rng.random()
        correct = capture_rng_state(correct_rng)
        wrong_rng = random.Random(991)
        wrong_rng.random()
        wrong_rng.random()
        wrong_position = capture_rng_state(wrong_rng)
        correct_clone = random.Random()
        correct_clone.setstate(correct.to_stdlib_state())
        wrong_clone = random.Random()
        wrong_clone.setstate(wrong_position.to_stdlib_state())
        self.assertNotEqual([correct_clone.random() for _ in range(5)],
                            [wrong_clone.random() for _ in range(5)])

        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        service = MemoryService(fabric)
        service.register_agent("rng-agent", b"rng-agent-key", tenant_id="rng-tenant")
        session = service.session(service.issue("rng-agent"))
        memory_id = session.remember("seeded decision evidence")
        captured = capture(fabric, session, [memory_id],
                           context=ReplayContext(fabric.log.head_seq))
        record = record_decision(fabric, session,
            options=("monitor", "investigate", "diagnose"), selected="investigate",
            evidence=captured.evidence, policy_id=self.policy.policy_id,
            policy_digest=self.policy.implementation_digest, rng_state=correct,
            rng_applicability="captured_full_state")
        captured = capture(fabric, session, [memory_id],
            context=ReplayContext(fabric.log.head_seq), decision=record)
        tampered_position = replace(record, rng_state=wrong_position)
        with self.assertRaises(NonReplayable) as refused:
            execute_recorded(fabric, self.events, simulator=self.simulator,
                             policy=self.policy, decision_record=tampered_position)
        self.assertEqual(refused.exception.code, "NON_REPLAYABLE")
        for candidate in (record, tampered_position):
            with self.subTest(candidate=candidate.rng_state.position), \
                    self.assertRaises(NonReplayable) as no_exact_certificate:
                issue_verified_recorded_replay(fabric=fabric, decision_record=candidate,
                    factual_observations=(Observation(memory_id, "alarm", True,
                        "sensor-memory", 3),),
                    intervention=create_intervention(captured.evidence[0], "suppress"),
                    simulator=self.simulator, policy=self.policy,
                    session=session, capture_result=captured,
                    capture_digest=captured.factual_digest,
                    intervention_digest=create_intervention(captured.evidence[0],
                                                            "suppress").intervention_id,
                    updater_id=self.simulator.updater_id, policy_id=self.policy.policy_id)
            self.assertEqual(no_exact_certificate.exception.code, "NON_REPLAYABLE")


if __name__ == "__main__":
    unittest.main()
