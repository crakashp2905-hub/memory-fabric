"""Exact Bayesian enumeration known-answer and intervention controls."""

from __future__ import annotations

import unittest
import json
from fractions import Fraction
import itertools
from dataclasses import replace

from memory_fabric.causal_replay.bayes import (BinaryNode, enumerate_posterior,
                                               independent_binary_oracle, marginal,
                                               sensitivity_sweep)
from memory_fabric.causal_replay.state import Observation, update
from memory_fabric.causal_replay.policy import ThresholdPolicy
from memory_fabric.causal_replay.types import CDMError
from memory_fabric.causal_replay.certificates import (issue, masked_export, verify,
    verify_with_minimality_proof)
from memory_fabric.causal_replay.verifier import verify_minimality_proof
from memory_fabric.causal_replay.intervention import create
from memory_fabric.causal_replay.replay import deterministic_simulator, replay
from memory_fabric.causal_replay.types import BeliefReference, ReplayStatus
from tools.verify_cdm_certificate import verify_json


class TestBayes(unittest.TestCase):
    def setUp(self):
        self.nodes = (BinaryNode("fault", (), {(): 0.2}),
                      BinaryNode("alarm", ("fault",), {(False,): 0.1, (True,): 0.9}))

    def test_known_posterior_matches_distinct_likelihood_product(self):
        posterior = enumerate_posterior(self.nodes, {"alarm": True})
        self.assertAlmostEqual(marginal(posterior, "fault"),
                               independent_binary_oracle(0.2, [0.9], [True]))
        self.assertAlmostEqual(sum(posterior.values()), 1.0)

    def test_noop_irrelevant_and_same_origin_duplicate(self):
        base = update(self.nodes, (Observation("e1", "alarm", True, "sensor", 1),))
        duplicate = update(self.nodes, (Observation("e1", "alarm", True, "sensor", 1),
                                        Observation("e2", "alarm", True, "sensor", 2)))
        self.assertEqual(base.posterior, duplicate.posterior)

    def test_noncommuting_same_origin_updates_follow_recorded_sequence(self):
        early = Observation("first", "alarm", True, "sensor", 1)
        late = Observation("second", "alarm", False, "sensor", 2)
        recorded = update(self.nodes, (early, late))
        input_permuted = update(self.nodes, (late, early))
        self.assertEqual(recorded.fingerprint, input_permuted.fingerprint)
        reordered_events = (replace(early, sequence=2), replace(late, sequence=1))
        reordered = update(self.nodes, reordered_events)
        self.assertNotEqual(recorded.posterior, reordered.posterior)
        self.assertEqual(recorded.observations[0].observation_id, "first")
        self.assertEqual(reordered.observations[0].observation_id, "second")

    def test_unrelated_latent_observation_does_not_change_fault_belief(self):
        graph = self.nodes + (BinaryNode("weather", (), {(): 0.6}),)
        base = update(graph, ())
        unrelated = update(graph, (Observation("weather-1", "weather", True, "meteo", 1),))
        self.assertEqual(base.posterior["fault"], unrelated.posterior["fault"])
        policy = ThresholdPolicy("fault")
        self.assertEqual(policy.propose(base).selected, policy.propose(unrelated).selected)

    def test_policy_swap_is_separate_from_evidence_intervention(self):
        event = Observation("alarm-event", "alarm", True, "sensor", 1)
        reference = BeliefReference("alarm-event", 1, "tenant-a", "a" * 64)
        simulator = deterministic_simulator(self.nodes, policy_id="policy-original")
        factual = replay((event,), intervention=create(None, "noop"), simulator_id="toy",
                         simulators={"toy": simulator})
        policy_swap = replay((event,), intervention=create(None, "swap_policy",
                              policy_id="policy-new"), simulator_id="toy",
                           simulators={"toy": simulator})
        evidence_suppression = replay((event,),
            intervention=create(reference, "suppress"), simulator_id="toy",
            simulators={"toy": simulator})

        self.assertEqual(factual.state.observations, policy_swap.state.observations)
        self.assertEqual(policy_swap.state.policy_id, "policy-new")
        self.assertEqual(evidence_suppression.state.policy_id, "policy-original")
        self.assertNotEqual(factual.intervention_digest, policy_swap.intervention_digest)
        self.assertNotEqual(factual.intervention_digest, evidence_suppression.intervention_digest)
        self.assertNotEqual(policy_swap.state.fingerprint, evidence_suppression.state.fingerprint)

    def test_conflicts_remain_in_trace_and_use_declared_first_source_rule(self):
        state = update(self.nodes, (Observation("e1", "alarm", True, "sensor-A", 1),
                                    Observation("e2", "alarm", False, "sensor-B", 2)))
        self.assertEqual(len(state.observations), 2)
        self.assertEqual(state.conflict_variables, ("alarm",))
        self.assertAlmostEqual(state.posterior["fault"], 0.2)

    def test_impossible_evidence_refuses(self):
        with self.assertRaises(CDMError):
            enumerate_posterior((BinaryNode("x", (), {(): 0.0}),), {"x": True})

    def test_registered_parameter_sensitivity_sweep(self):
        values = sensitivity_sweep(self.nodes, node_name="alarm", parent_assignment=(True,),
            probabilities=(0.55, 0.9), observations={"alarm": True}, query="fault")
        self.assertLess(values[0], values[1])

    def test_suppression_replay_and_certificate_tampering(self):
        events = (Observation("e1", "alarm", True, "sensor", 1),)
        ref = BeliefReference("e1", 1, "tn_default", "a" * 64)
        simulator = deterministic_simulator(self.nodes)
        factual = simulator.run(events)
        result = replay(events, intervention=create(ref, "suppress"), simulator_id="toy",
                        simulators={"toy": simulator})
        self.assertEqual(result.status, ReplayStatus.EXACT)
        self.assertFalse(result.real_actions_executed)
        cert = issue(capture_digest="b" * 64, intervention_digest="c" * 64,
                     factual_fingerprint=factual.fingerprint,
                     counterfactual_fingerprint=result.state.fingerprint,
                     updater_id=factual.updater_id, policy_id=factual.policy_id,
                     status=result.status.value, factual_proposal="investigate",
                     counterfactual_proposal="monitor", complete=result.complete)
        self.assertTrue(verify(cert))
        self.assertTrue(verify(cert.to_json()))
        self.assertTrue(verify(json.loads(cert.to_json())))
        tampered = cert.payload()
        tampered["proposal_changed"] = False
        tampered["certificate_digest"] = cert.certificate_digest
        self.assertFalse(verify(tampered))

    def test_arbitrary_callable_simulator_is_refused(self):
        events = (Observation("e1", "alarm", True, "sensor", 1),)
        ref = BeliefReference("e1", 1, "tn_default", "a" * 64)
        with self.assertRaises(Exception):
            replay(events, intervention=create(ref, "suppress"), simulator_id="hostile",
                   simulators={"hostile": lambda items: (_ for _ in ()).throw(AssertionError())})

    def test_independent_rational_oracle_for_small_generated_graphs(self):
        # Fixed local graph family, generated from a local deterministic seed.
        import random
        rng = random.Random(20261108)
        for _ in range(8):
            prior = Fraction(rng.randint(1, 4), 5)
            p_alarm = Fraction(rng.randint(1, 9), 10)
            graph = (BinaryNode("fault", (), {(): float(prior)}),
                     BinaryNode("alarm", ("fault",),
                         {(False,): float(p_alarm), (True,): float(1 - p_alarm)}))
            observed = {"alarm": bool(rng.getrandbits(1))}
            numerator = Fraction(0)
            denominator = Fraction(0)
            for fault, alarm in itertools.product((False, True), repeat=2):
                if alarm != observed["alarm"]:
                    continue
                pf = prior if fault else 1 - prior
                likelihood = p_alarm if (alarm != fault) else 1 - p_alarm
                mass = pf * likelihood
                denominator += mass
                if fault:
                    numerator += mass
            expected = float(numerator / denominator)
            actual = marginal(enumerate_posterior(graph, observed), "fault")
            self.assertAlmostEqual(actual, expected, places=14)

    def test_incomplete_replay_cannot_be_certified(self):
        with self.assertRaises(CDMError):
            issue(capture_digest="b" * 64, intervention_digest="c" * 64,
                  factual_fingerprint="d" * 64, counterfactual_fingerprint="e" * 64,
                  updater_id="x", policy_id="y", status="EXACT",
                  factual_proposal="a", counterfactual_proposal="b", complete=False)

    def test_certificate_status_world_and_minimality_claim_are_explicit(self):
        kwargs = dict(capture_digest="b" * 64, intervention_digest="c" * 64,
            factual_fingerprint="d" * 64, counterfactual_fingerprint="e" * 64,
            updater_id="x", policy_id="y", factual_proposal="a",
            counterfactual_proposal="b", complete=True)
        exact = issue(**kwargs, status="EXACT", estimand="policy_decision_flip",
                      world_semantics="simulator_world")
        self.assertTrue(verify(exact))
        self.assertEqual(exact.world_semantics, "simulator_world")
        self.assertEqual(exact.minimality_claim, "none")
        unsupported = issue(**kwargs, status="EXACT",
                            world_semantics="physical_counterfactual_unsupported")
        self.assertFalse(verify(unsupported))
        approximate = issue(**{**kwargs, "complete": False}, status="APPROXIMATE")
        self.assertFalse(verify(approximate))
        with self.assertRaises(CDMError):
            issue(**kwargs, status="EXACT", minimality_claim="cardinality_minimum")
        with self.assertRaises(CDMError):
            issue(**kwargs, status="EXACT",
                minimality_claim="verified_sufficient_subset", minimality_proof_digest="f" * 64)

    def test_certificate_binds_verified_minimality_table(self):
        kwargs = dict(capture_digest="b" * 64, intervention_digest="c" * 64,
            factual_fingerprint="d" * 64, counterfactual_fingerprint="e" * 64,
            updater_id="x", policy_id="y", factual_proposal="review",
            counterfactual_proposal="approve", complete=True, status="EXACT")
        players = ("a", "b")
        table = {(): "review", ("a",): "review", ("b",): "review",
                 ("a", "b"): "approve"}
        proof = verify_minimality_proof(players, coalition_proposals=table,
            sufficient_subset=players, target_proposal="approve",
            claim="cardinality_minimum")
        cert = issue(**kwargs, minimality_claim=proof.claim,
                     minimality_proof_digest=proof.proof_digest,
                     minimality_verification=proof)
        self.assertTrue(verify(cert))
        self.assertTrue(verify_with_minimality_proof(cert, players=players,
            coalition_proposals=table, sufficient_subset=players,
            target_proposal="approve"))
        changed = dict(table)
        changed[("a",)] = "approve"
        self.assertFalse(verify_with_minimality_proof(cert, players=players,
            coalition_proposals=changed, sufficient_subset=players,
            target_proposal="approve"))

    def test_certificate_rejects_capture_intervention_and_policy_tampering(self):
        cert = issue(capture_digest="b" * 64, intervention_digest="c" * 64,
            factual_fingerprint="d" * 64, counterfactual_fingerprint="e" * 64,
            updater_id="x", policy_id="y", status="EXACT",
            factual_proposal="monitor", counterfactual_proposal="investigate", complete=True)
        for field, value in (("capture_digest", "f" * 64),
                             ("intervention_digest", "f" * 64),
                             ("policy_id", "other-policy")):
            payload = cert.payload()
            payload[field] = value
            payload["certificate_digest"] = cert.certificate_digest
            self.assertFalse(verify(payload), field)

    def test_masked_certificate_export_omits_identifiers_hashes_and_counts(self):
        cert = issue(capture_digest="a" * 64, intervention_digest="b" * 64,
            factual_fingerprint="c" * 64, counterfactual_fingerprint="d" * 64,
            updater_id="private-updater", policy_id="private-policy", status="EXACT",
            factual_proposal="monitor", counterfactual_proposal="investigate", complete=True)
        exported = masked_export(cert)
        rendered = json.dumps(exported, sort_keys=True)
        for sensitive in ("private-updater", "private-policy", "capture_digest",
                          "intervention_digest", "factual_fingerprint", "certificate_digest"):
            self.assertNotIn(sensitive, rendered)
        self.assertFalse(exported["action_entitlement"])
        self.assertTrue(exported["masked"])

    def test_standalone_offline_verifier_accepts_valid_and_refuses_tampered_json(self):
        cert = issue(capture_digest="a" * 64, intervention_digest="b" * 64,
            factual_fingerprint="c" * 64, counterfactual_fingerprint="d" * 64,
            updater_id="up", policy_id="policy", status="EXACT",
            factual_proposal="monitor", counterfactual_proposal="investigate", complete=True)
        self.assertTrue(verify_json(cert.to_json()))
        tampered = json.loads(cert.to_json())
        tampered["policy_id"] = "changed"
        self.assertFalse(verify_json(json.dumps(tampered)))


if __name__ == "__main__":
    unittest.main()
