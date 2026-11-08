"""Checkpoint integrity and current authorization controls."""

from __future__ import annotations

import unittest
import random
from dataclasses import replace

from memory_fabric.causal_replay.checkpoints import (CacheKey, CheckpointCache, create,
    restore_rng, verify, verify_exact_ready)
from memory_fabric.causal_replay.capture import capture_rng_state
from memory_fabric.causal_replay.state import Observation
from memory_fabric.causal_replay.types import BeliefReference, CDMError, digest_json
from memory_fabric import MemoryFabric
from memory_fabric.service import MemoryService


class TestCheckpoints(unittest.TestCase):
    def setUp(self):
        self.fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(self.fabric.close)
        self.service = MemoryService(self.fabric)
        self.service.register_agent("agent-a", b"test-key", tenant_id="tenant-a")
        self.session = self.service.session(self.service.issue("agent-a"))
        self.memory_id = self.session.remember("checkpoint evidence")
        current = self.fabric.state.memories[self.memory_id]
        self.ref = BeliefReference(self.memory_id, current.version, "tenant-a", "a" * 64)
        self.checkpoint = create(source_head=self.fabric.log.head_seq, tenant_id="tenant-a", principal_id="agent-a",
            evidence=(self.ref,), updater_id="up-v1", updater_digest="b" * 64,
            policy_id="pol-v1", policy_digest="c" * 64)

    def test_roundtrip_integrity_and_no_plaintext(self):
        self.assertTrue(verify(self.checkpoint, fabric=self.fabric, session=self.session))
        self.assertNotIn("plaintext", repr(self.checkpoint))

    def test_stale_revoked_or_erased_checkpoint_refuses(self):
        self.assertTrue(verify(self.checkpoint, fabric=self.fabric, session=self.session))
        self.service.revoke(self.session.credential)
        self.assertFalse(verify(self.checkpoint, fabric=self.fabric, session=self.session))

    def test_stale_checkpoint_refuses_after_source_version_changes(self):
        from memory_fabric import events as ev
        current = self.fabric.state.memories[self.memory_id]
        updated = replace(current, version=current.version + 1,
                          content="checkpoint evidence corrected")
        self.fabric._emit(ev.memory_versioned(self.fabric.now(), updated,
                                              "checkpoint staleness test"))
        self.assertFalse(verify(self.checkpoint, fabric=self.fabric, session=self.session))

    def test_erasure_invalidates_checkpoint(self):
        self.service.revoke_agent("agent-a")
        self.service.register_agent("operator", b"operator-key", tenant_id="tenant-a",
                                    roles=("agent", "operator"))
        operator = self.service.session(self.service.issue("operator"))
        operator.erase_content(self.memory_id, "privacy")
        self.assertFalse(verify(self.checkpoint, fabric=self.fabric, session=self.session))

    def test_mutation_refuses(self):
        from dataclasses import replace
        changed = replace(self.checkpoint, policy_id="changed")
        self.assertFalse(verify(changed, fabric=self.fabric, session=self.session))

    def test_cache_binds_versions_and_policy_and_revalidates_auth(self):
        key = CacheKey("tenant-a", "agent-a", ((self.memory_id, self.ref.version),),
                       "b" * 64, "c" * 64, None, "d" * 64)
        cache = CheckpointCache()
        cache.put(key, self.checkpoint)
        self.assertEqual(cache.get(key, fabric=self.fabric, session=self.session),
                         self.checkpoint)
        wrong_policy = CacheKey("tenant-a", "agent-a", ((self.memory_id, self.ref.version),),
                                "b" * 64, "e" * 64, None, "d" * 64)
        self.assertIsNone(cache.get(wrong_policy, fabric=self.fabric, session=self.session))
        self.service.revoke(self.session.credential)
        self.assertIsNone(cache.get(key, fabric=self.fabric, session=self.session))

    def test_cache_invalidation_drops_memory_and_principal(self):
        key = CacheKey("tenant-a", "agent-a", ((self.memory_id, self.ref.version),),
                       "b" * 64, "c" * 64, None, "d" * 64)
        cache = CheckpointCache()
        cache.put(key, self.checkpoint)
        cache.invalidate_memory(self.memory_id)
        self.assertIsNone(cache.get(key, fabric=self.fabric, session=self.session))
        cache.put(key, self.checkpoint)
        cache.invalidate_principal("tenant-a", "agent-a")
        self.assertIsNone(cache.get(key, fabric=self.fabric, session=self.session))

    def test_blanket_invalidation_discards_unrelated_valid_checkpoint(self):
        other_id = self.session.remember("independent checkpoint evidence")
        other = self.fabric.state.memories[other_id]
        other_ref = BeliefReference(other_id, other.version, "tenant-a", "e" * 64)
        other_checkpoint = create(source_head=self.fabric.log.head_seq,
            tenant_id="tenant-a", principal_id="agent-a", evidence=(other_ref,),
            updater_id="up-v1", updater_digest="b" * 64, policy_id="pol-v1",
            policy_digest="c" * 64)
        affected_key = CacheKey("tenant-a", "agent-a", ((self.memory_id, self.ref.version),),
            "b" * 64, "c" * 64, None, "d" * 64)
        independent_key = CacheKey("tenant-a", "agent-a", ((other_id, other_ref.version),),
            "b" * 64, "c" * 64, None, "f" * 64)

        targeted = CheckpointCache()
        targeted.put(affected_key, self.checkpoint)
        targeted.put(independent_key, other_checkpoint)
        targeted.invalidate_memory(self.memory_id)
        self.assertIsNone(targeted.get(affected_key, fabric=self.fabric, session=self.session))
        self.assertEqual(targeted.get(independent_key, fabric=self.fabric,
                                      session=self.session), other_checkpoint)

        blanket = CheckpointCache()
        blanket.put(affected_key, self.checkpoint)
        blanket.put(independent_key, other_checkpoint)
        blanket.clear()
        self.assertIsNone(blanket.get(affected_key, fabric=self.fabric, session=self.session))
        self.assertIsNone(blanket.get(independent_key, fabric=self.fabric, session=self.session))

    def test_cache_tenant_collision_and_poisoning_are_misses(self):
        key = CacheKey("tenant-a", "agent-a", ((self.memory_id, self.ref.version),),
                       "b" * 64, "c" * 64, None, "d" * 64)
        cache = CheckpointCache()
        cache.put(key, self.checkpoint)
        other_tenant = CacheKey("tenant-b", "agent-a", ((self.memory_id, self.ref.version),),
                                "b" * 64, "c" * 64, None, "d" * 64)
        self.assertIsNone(cache.get(other_tenant, fabric=self.fabric, session=self.session))
        cache.put(key, create(source_head=self.checkpoint.source_head, tenant_id="tenant-a",
            principal_id="agent-a", evidence=(self.ref,), updater_id="up-v1",
            updater_digest="b" * 64, policy_id="pol-v1", policy_digest="c" * 64))
        self.assertEqual(cache.get(key, fabric=self.fabric, session=self.session),
                         self.checkpoint)

    def test_rng_checkpoint_restores_exact_algorithm_position(self):
        for seed, advance in ((742, 0), (13, 1), (2026, 4)):
            with self.subTest(seed=seed, advance=advance):
                rng = random.Random(seed)
                for _ in range(advance):
                    rng.random()
                if seed == 2026:
                    rng.gauss(0, 1)  # exercise the cached Gaussian continuation value
                snapshot = capture_rng_state(rng)
                checkpoint = create(source_head=self.fabric.log.head_seq, tenant_id="tenant-a",
                    principal_id="agent-a", evidence=(self.ref,), updater_id="up-v1",
                    updater_digest="b" * 64, policy_id="pol-v1", policy_digest="c" * 64,
                    rng_algorithm=snapshot.algorithm,
                    rng_state_digest=digest_json(snapshot.__dict__), rng_snapshot=snapshot,
                    rng_applicability="captured_full_state")
                restored = restore_rng(checkpoint)
                if seed == 2026:
                    self.assertEqual([rng.gauss(0, 1) for _ in range(8)],
                                     [restored.gauss(0, 1) for _ in range(8)])
                else:
                    self.assertEqual([rng.random() for _ in range(8)],
                                     [restored.random() for _ in range(8)])
                self.assertTrue(verify(checkpoint, fabric=self.fabric, session=self.session))
        with self.assertRaises(CDMError):
            restore_rng(replace(checkpoint, rng_snapshot=None))

    def test_rng_checkpoint_rejects_digest_or_algorithm_mismatch(self):
        snapshot = capture_rng_state(random.Random(123))
        with self.assertRaises(CDMError):
            create(source_head=self.fabric.log.head_seq, tenant_id="tenant-a",
                principal_id="agent-a", evidence=(self.ref,), updater_id="up-v1",
                updater_digest="b" * 64, policy_id="pol-v1", policy_digest="c" * 64,
                rng_algorithm=snapshot.algorithm, rng_state_digest="0" * 64,
                rng_snapshot=snapshot)

    def test_exact_checkpoint_requires_current_complete_replay_inputs(self):
        event = (Observation("trace-1", "sensor", True, "sensor-a", 1),)
        deterministic = create(source_head=self.fabric.log.head_seq, tenant_id="tenant-a",
            principal_id="agent-a", evidence=(self.ref,), updater_id="up-v1",
            updater_digest="b" * 64, policy_id="pol-v1", policy_digest="c" * 64,
            observation_digest=digest_json([event[0].__dict__]),
            rng_applicability="not_applicable_deterministic")
        self.assertTrue(verify_exact_ready(deterministic, fabric=self.fabric,
            session=self.session, updater_digest="b" * 64, policy_digest="c" * 64,
            observations=event))
        self.assertFalse(verify_exact_ready(self.checkpoint, fabric=self.fabric,
            session=self.session, updater_digest="b" * 64, policy_digest="c" * 64,
            observations=event))
        self.assertFalse(verify_exact_ready(deterministic, fabric=self.fabric,
            session=self.session, updater_digest="0" * 64, policy_digest="c" * 64,
            observations=event))
        self.assertFalse(verify_exact_ready(deterministic, fabric=self.fabric,
            session=self.session, updater_digest="b" * 64, policy_digest="c" * 64,
            observations=()))
        altered = (replace(event[0], value=False),)
        self.assertFalse(verify_exact_ready(deterministic, fabric=self.fabric,
            session=self.session, updater_digest="b" * 64, policy_digest="c" * 64,
            observations=altered))


if __name__ == "__main__":
    unittest.main()
