"""CDM source roots survive a real federation import and local derivation."""

from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.causal_replay.attribution import assess_fabric_source_roots
from memory_fabric.causal_replay.attribution import assess_federated_versions
from memory_fabric.federation import offer
from memory_fabric.governance.firewall import (Firewall,
    rule_capabilities_must_be_granted, rule_must_be_active,
    rule_restricted_stays_private)
from memory_fabric.service import MemoryService


def _store() -> MemoryFabric:
    return MemoryFabric(":memory:", auto_activate=True, firewall=Firewall(rules=(
        rule_restricted_stays_private, rule_must_be_active,
        rule_capabilities_must_be_granted)))


class TestFederatedProvenance(unittest.TestCase):
    def test_import_and_local_derivation_share_the_original_portable_root(self):
        source, target = _store(), _store()
        self.addCleanup(source.close)
        self.addCleanup(target.close)
        source_id = source.remember("origin-agent",
                                    "The verified relay pressure reading remains stable during calibration",
                                    scope="team")
        imported = offer(source, source_id, target, recipient_agent="reader", activate=True)
        self.assertTrue(imported.accepted)
        imported_id = imported.imported_memory_id
        self.assertIsNotNone(imported_id)

        service = MemoryService(target)
        service.register_agent("reader", b"reader-test-key",
            tenant_id=target.state.memories[imported_id].tenant_id)
        session = service.session(service.issue("reader"))
        derived_id = session.derive("relay pressure remains stable during calibration",
                                    parents=[imported_id])
        target.validate(derived_id, actor="reader")
        self.assertTrue(target.use(imported_id, agent_id="reader",
            tenant_id=target.state.memories[imported_id].tenant_id, audit=False).usable)
        self.assertTrue(target.use(derived_id, agent_id="reader",
            tenant_id=target.state.memories[derived_id].tenant_id, audit=False).usable)
        assessment = assess_fabric_source_roots(target, session, (imported_id, derived_id))
        self.assertEqual(assessment.status, "ROOTS_RESOLVED")
        self.assertEqual(assessment.independent_root_count, 1)
        expected = ((f"{source.store_id}/{source_id}",
                     tuple(sorted((imported_id, derived_id)))),)
        self.assertEqual(assessment.groups, expected)

    def test_local_context_cannot_forge_a_remote_source_root(self):
        target = _store()
        self.addCleanup(target.close)
        service = MemoryService(target)
        service.register_agent("reader", b"reader-test-key", tenant_id="default")
        session = service.session(service.issue("reader"))
        imported_id = session.remember("federated evidence placeholder", context={
            "federation": {"root": {"store": "", "memory_id": ""}}})
        assessment = assess_fabric_source_roots(target, session, (imported_id,))
        self.assertEqual(assessment.status, "ROOTS_RESOLVED")
        self.assertEqual(assessment.independent_root_count, 1)
        self.assertEqual(assessment.groups,
                         ((f"{target.store_id}/{imported_id}", (imported_id,)),))

    def test_mixed_origin_versions_are_explicit_but_local_snapshots_remain_bound(self):
        source, target = _store(), _store()
        self.addCleanup(source.close)
        self.addCleanup(target.close)
        source_id = source.remember("origin-agent",
            "The upstream relay pressure remains stable during calibration",
            scope="team")
        first = offer(source, source_id, target, recipient_agent="reader", activate=True)
        source.revise(source_id,
            "The upstream relay pressure remains stable after recalibration",
            agent_id="origin-agent", reason="source version update")
        second = offer(source, source_id, target, recipient_agent="reader", activate=True)
        self.assertTrue(first.accepted and second.accepted)
        service = MemoryService(target)
        service.register_agent("reader", b"reader-version-key",
            tenant_id=target.state.memories[first.imported_memory_id].tenant_id)
        session = service.session(service.issue("reader"))

        assessment = assess_federated_versions(target, session,
            (first.imported_memory_id, second.imported_memory_id))
        self.assertEqual(assessment.status, "MIXED_ORIGIN_VERSIONS")
        self.assertTrue(assessment.local_snapshot_replayable)
        self.assertEqual(sorted(binding.origin_version for binding in assessment.bindings),
                         [1, 2])
        self.assertEqual({binding.local_version for binding in assessment.bindings}, {1})

    def test_partitioned_stale_imports_do_not_become_independent_corroboration(self):
        source, recipient = _store(), _store()
        self.addCleanup(source.close)
        self.addCleanup(recipient.close)
        source_id = source.remember("origin-agent",
            "The north relay pressure remains stable during calibration", scope="team")
        derived_id = source.derive("origin-agent",
            "The north relay pressure remains stable throughout calibration",
            parents=[source_id], scope="team")
        source.validate(derived_id, actor="reviewer")
        imported_original = offer(source, source_id, recipient, "reader", activate=True)
        imported_derivative = offer(source, derived_id, recipient, "reader", activate=True)
        self.assertTrue(imported_original.accepted and imported_derivative.accepted)

        # Model a partition by delivering no retraction after the source changes state.
        source.quarantine(source_id, reason="calibration source withdrawn", actor="reviewer")
        recipient_service = MemoryService(recipient)
        tenant_id = recipient.state.memories[imported_original.imported_memory_id].tenant_id
        recipient_service.register_agent("reader", b"reader-partition-key", tenant_id=tenant_id)
        session = recipient_service.session(recipient_service.issue("reader"))
        self.assertEqual(recipient.get(imported_original.imported_memory_id).lifecycle_state.value,
                         "active")
        self.assertEqual(recipient.get(imported_derivative.imported_memory_id).lifecycle_state.value,
                         "active")

        assessment = assess_fabric_source_roots(recipient, session,
            (imported_original.imported_memory_id, imported_derivative.imported_memory_id))
        self.assertEqual(assessment.status, "ROOTS_RESOLVED")
        self.assertEqual(assessment.independent_root_count, 1)


if __name__ == "__main__":
    unittest.main()
