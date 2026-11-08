"""CDM historical capture respects Memory Fabric authorization and erasure."""

from __future__ import annotations

import unittest
from dataclasses import replace
from memory_fabric import events as ev

from memory_fabric import MemoryFabric

from memory_fabric.causal_replay.capture import (capture, record_decision,
    validate_replay_option, verify_decision_record)
from memory_fabric.causal_replay.intervention import create
from memory_fabric.causal_replay.types import (CDMError, Erased,
    NonReplayable, ReplayContext, parse_record, serialize_record)
from memory_fabric.service import MemoryService


class TestCapture(unittest.TestCase):
    def setUp(self):
        self.fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(self.fabric.close)
        self.service = MemoryService(self.fabric)
        self.fabric.principals.register("alice", b"test-only-key")
        self.owner = self.service.session(self.service.issue("alice"))
        self.mid = self.owner.remember("sensor calibration is biased")
        self.head = self.fabric.log.head_seq

    def test_private_memory_not_captured_by_other_agent(self):
        with self.assertRaises(Erased):
            self.service.register_agent("bob", b"test-bob", tenant_id=self.owner.tenant_id)
            bob = self.service.session(self.service.issue("bob"))
            capture(self.fabric, bob, [self.mid],
                    context=ReplayContext(self.head))

    def test_cross_tenant_capture_refuses_without_metadata(self):
        self.service.register_agent("other", b"other-key", tenant_id="tenant-other")
        other = self.service.session(self.service.issue("other"))
        with self.assertRaises(Erased) as caught:
            capture(self.fabric, other, [self.mid], context=ReplayContext(self.head))
        self.assertNotIn(self.mid, str(caught.exception))

    def test_cross_tenant_refusal_exposes_no_content_or_record_metadata(self):
        self.service.register_agent("other", b"other-key", tenant_id="tenant-other")
        other = self.service.session(self.service.issue("other"))
        with self.assertRaises(Erased) as caught:
            capture(self.fabric, other, [self.mid], context=ReplayContext(self.head))
        self.assertEqual(str(caught.exception), "requested evidence is unavailable")
        self.assertNotIn("sensor calibration", repr(caught.exception))
        self.assertNotIn(self.mid, repr(caught.exception))

    def test_revoked_session_after_recorded_history_refuses_without_metadata(self):
        self.service.revoke(self.owner.credential)
        from memory_fabric.causal_replay.types import Unauthorized
        with self.assertRaises(Unauthorized) as caught:
            capture(self.fabric, self.owner, [self.mid], context=ReplayContext(self.head))
        self.assertNotIn(self.mid, str(caught.exception))
        self.assertNotIn("sensor calibration", str(caught.exception))

    def test_unverified_asserted_identity_is_rejected(self):
        from memory_fabric.causal_replay.types import Unauthorized
        with self.assertRaises(Unauthorized):
            capture(self.fabric, object(), [self.mid],
                    context=ReplayContext(self.head))

    def test_revoked_session_cannot_capture(self):
        self.service.revoke(self.owner.credential)
        from memory_fabric.causal_replay.types import Unauthorized
        with self.assertRaises(Unauthorized):
            capture(self.fabric, self.owner, [self.mid], context=ReplayContext(self.head))

    def test_authorized_capture_contains_commitment_not_plaintext(self):
        result = capture(self.fabric, self.owner, [self.mid], context=ReplayContext(self.head))
        self.assertTrue(result.archival_only)
        self.assertNotIn("biased", repr(result))
        self.assertEqual(result.evidence[0].belief_id, self.mid)

    def test_capture_refuses_erased_content(self):
        self.fabric.erase_content(self.mid, actor="alice", reason="privacy")
        with self.assertRaises(Erased):
            capture(self.fabric, self.owner, [self.mid], context=ReplayContext(self.head))

    def test_bitemporal_capture_separates_known_time_from_valid_time(self):
        """A later corrected version changes current-valid queries, not old knowledge."""
        # The original report was known at sequence head and applied to the
        # earlier interval. A later correction becomes known at a new sequence
        # and applies to a later interval.
        original = self.fabric.state.memories[self.mid]
        original = replace(original, valid_from=100, valid_to=200)
        self.fabric._emit(ev.memory_versioned(self.fabric.now(), original,
                                              "set factual validity"))
        before_correction = self.fabric.log.head_seq
        corrected_id = self.owner.remember("sensor calibration was corrected",
            valid_from=200, valid_to=None, auto_activate=True)
        after_correction = self.fabric.log.head_seq

        known_before_valid_then = capture(
            self.fabric, self.owner, [self.mid],
            context=ReplayContext(before_correction, valid_at=150))
        with self.assertRaises(Erased):
            capture(
                self.fabric, self.owner, [corrected_id],
                context=ReplayContext(before_correction, valid_at=250))
        known_after_valid_then = capture(
            self.fabric, self.owner, [self.mid],
            context=ReplayContext(after_correction, valid_at=150))
        known_after_valid_now = capture(
            self.fabric, self.owner, [corrected_id],
            context=ReplayContext(after_correction, valid_at=250))

        self.assertEqual(known_before_valid_then.evidence[0].version, 1)
        self.assertEqual(known_after_valid_then.evidence[0].version, 1)
        self.assertEqual(known_after_valid_now.evidence[0].version, 1)
        self.assertNotEqual(known_after_valid_then.evidence[0].digest,
                            known_after_valid_now.evidence[0].digest)
        self.assertNotEqual(known_before_valid_then.evidence[0].digest,
                            known_after_valid_now.evidence[0].digest)

    def test_partial_trace_refuses_exact_replay_when_policy_is_unavailable(self):
        from memory_fabric.causal_replay.bayes import BinaryNode
        from memory_fabric.causal_replay.executor import execute_recorded
        from memory_fabric.causal_replay.policy import ThresholdPolicy
        from memory_fabric.causal_replay.replay import DeterministicSimulator
        from memory_fabric.causal_replay.state import Observation

        evidence = capture(self.fabric, self.owner, [self.mid],
                           context=ReplayContext(self.head)).evidence
        record = record_decision(self.fabric, self.owner,
            options=("monitor", "investigate"), selected="monitor", evidence=evidence,
            policy_id="policy-v1", policy_digest="a" * 64)
        simulator = DeterministicSimulator((BinaryNode("sensor", (), {(): 0.5}),))
        observations = (Observation("o1", "sensor", True, "sensor-a", 1),)
        wrong_policy = ThresholdPolicy("policy-v1", 0.4, 0.8)
        with self.assertRaises(NonReplayable):
            execute_recorded(self.fabric, observations, simulator=simulator,
                             policy=wrong_policy, decision_record=record)

    def test_missing_decision_evidence_cannot_be_recorded_as_complete(self):
        from memory_fabric.causal_replay.types import BeliefReference

        ref = BeliefReference("missing-evidence", 1, self.owner.tenant_id, "a" * 64)
        with self.assertRaises(Erased):
            record_decision(self.fabric, self.owner,
                options=("monitor", "investigate"), selected="monitor",
                evidence=(ref,), policy_id="policy-v1", policy_digest="b" * 64)

    def test_capture_is_read_only_with_respect_to_event_head(self):
        before = self.fabric.log.head_seq
        capture(self.fabric, self.owner, [self.mid], context=ReplayContext(self.head))
        self.assertEqual(self.fabric.log.head_seq, before)

    def test_capture_binds_digest_only_authorized_history_classes(self):
        self.fabric._emit(ev.retrieval_performed(self.fabric.now(), "alice", None,
            "private query text must not enter CDM", [(self.mid, 1, 0.9),
            ("unrelated-private-memory", 1, 0.1)], None))
        self.fabric._emit(ev.exposure_decided(self.fabric.now(), "alice", None,
            self.mid, 1, False, 0.25, "test-policy"))
        self.fabric._emit(ev.memory_cited(self.fabric.now(), "alice", None, self.mid))
        self.fabric._emit(ev.exposure_decided(self.fabric.now(), "alice", None,
            self.mid, 1, True, 0.75, "test-policy"))
        artifact = capture(self.fabric, self.owner, [self.mid],
                           context=ReplayContext(self.fabric.log.head_seq))
        self.assertEqual([item.kind for item in artifact.trace],
                         ["available", "exposure", "citation", "exposure"])
        self.assertEqual([item.exposed for item in artifact.trace],
                         [None, False, None, True])
        self.assertTrue(all(item.evidence_id == self.mid and item.version == 1
                            and len(item.digest) == 64 for item in artifact.trace))
        self.assertNotIn("private query text", repr(artifact))
        self.assertNotIn("unrelated-private-memory", repr(artifact))
        restored = parse_record(type(artifact), serialize_record(artifact))
        self.assertEqual(restored.trace, artifact.trace)

    def test_capture_binds_verified_decision_receipt_to_evidence_trace(self):
        evidence = capture(self.fabric, self.owner, [self.mid],
                           context=ReplayContext(self.head)).evidence
        decision = record_decision(self.fabric, self.owner,
            options=("monitor", "investigate"), selected="monitor", evidence=evidence,
            policy_id="policy-v1", policy_digest="a" * 64)
        artifact = capture(self.fabric, self.owner, [self.mid],
                           context=ReplayContext(decision.sequence), decision=decision)
        self.assertEqual([(row.kind, row.evidence_id, row.version) for row in artifact.trace],
                         [("recorded", self.mid, 1)])

    def test_original_options_and_constraints_bind_to_authorized_capture(self):
        evidence = capture(self.fabric, self.owner, [self.mid],
                           context=ReplayContext(self.head)).evidence
        record = record_decision(self.fabric, self.owner,
            options=("monitor", "investigate"), selected="investigate", evidence=evidence,
            policy_id="policy-v1", policy_digest="a" * 64,
            constraints=("no-real-action", "human-review-required"))
        self.assertTrue(verify_decision_record(self.fabric, record))
        self.assertTrue(self.fabric.log.chain.verify(self.fabric.log.read()).ok)
        receipt = next(self.fabric.log.read(since_seq=record.sequence - 1, limit=1))
        self.assertNotIn("monitor", repr(receipt.payload))
        self.assertNotIn("human-review-required", repr(receipt.payload))
        self.assertFalse(verify_decision_record(self.fabric,
            replace(record, source_event_id="forged-event")))
        self.assertFalse(verify_decision_record(self.fabric,
            replace(record, options=("monitor", "investigate", "approve"))))
        artifact = capture(self.fabric, self.owner, [self.mid],
                           context=ReplayContext(record.sequence), decision=record)
        self.assertEqual(artifact.decision, record)
        restored = parse_record(type(artifact), serialize_record(artifact))
        self.assertEqual(restored.decision.constraints, record.constraints)
        self.assertEqual(validate_replay_option(record, "monitor"), "monitor")
        with self.assertRaises(CDMError):
            validate_replay_option(record, "approve")
        policy_swap = create(None, "swap_policy", policy_id="policy-v2")
        self.assertEqual(validate_replay_option(record, "approve", intervention=policy_swap),
                         "approve")
        with self.assertRaises(CDMError):
            capture(self.fabric, self.owner, [self.mid],
                    context=ReplayContext(self.head), decision=record)


if __name__ == "__main__":
    unittest.main()
