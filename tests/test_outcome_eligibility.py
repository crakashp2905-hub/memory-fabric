"""Alternate recovery evidence must have a current grant and a new source root."""

from __future__ import annotations

import secrets
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.agent_outcomes import find_alternate_sources
from memory_fabric.certificates import EvidenceRef
from memory_fabric.identity import IdentityError, ROLE_AGENT
from memory_fabric.service import MemoryService


TENANT = "tenant-outcome-alternates"


class TestAlternateSources(unittest.TestCase):
    def setUp(self) -> None:
        self.service = MemoryService(MemoryFabric(":memory:", auto_activate=True))
        self.addCleanup(self.service.close)
        self.fabric = self.service._fabric
        for name in ("writer", "executor"):
            self.service.register_agent(name, key=secrets.token_bytes(32),
                                        tenant_id=TENANT, roles=(ROLE_AGENT,))
        self.writer = self.service.session(self.service.issue("writer"))
        self.executor = self.service.session(self.service.issue("executor"))

    def _grant_read(self, collection: str, *memory_ids: str) -> None:
        for memory_id in memory_ids:
            self.fabric.collection_add(collection, memory_id, actor="admin")
        self.fabric.collection_grant(
            collection, "executor", ["read"], actor="admin", tenant_id=TENANT,
        )

    def test_independent_current_source_recovers_a_valid_certificate(self) -> None:
        original = self.writer.remember(
            "Pump A report confirms operating pressure is four bar.", scope="private")
        duplicate = self.writer.derive(
            "Pump A pressure was confirmed at four bar by the report.",
            parents=[original], scope="private",
        )
        independent = self.writer.remember(
            "Independent gauge reading: Pump A pressure equals four bar.", scope="private")
        self._grant_read("pump-evidence", original, duplicate, independent)

        alternatives = find_alternate_sources(
            self.executor, "Pump A pressure four bar",
            [EvidenceRef(original, 1)], limit=2,
        )

        self.assertEqual(alternatives, (EvidenceRef(independent, 1),))
        self.assertEqual(self.fabric.source_root(original), self.fabric.source_root(duplicate))
        certificate = self.executor.certify(
            "Pump A is within its simulated pressure range.",
            [ref.memory_id for ref in alternatives],
        )
        self.assertTrue(self.executor.verify_certificate(certificate).ok)

    def test_revoked_collection_grant_excludes_the_candidate(self) -> None:
        revoked = self.writer.remember(
            "Unique revoked pump sensor reading is 91 kilopascals.", scope="private")
        self._grant_read("temporary-evidence", revoked)
        self.fabric.collection_revoke(
            "temporary-evidence", "executor", actor="admin", permissions=["read"],
            tenant_id=TENANT,
        )

        alternatives = find_alternate_sources(
            self.executor, "Unique revoked pump sensor reading 91 kilopascals",
        )

        self.assertEqual(alternatives, ())

    def test_revoked_session_cannot_search_for_alternate_sources(self) -> None:
        self.service.revoke(self.executor.credential)

        with self.assertRaises(IdentityError):
            find_alternate_sources(self.executor, "pump pressure")

    def test_search_limits_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            find_alternate_sources(self.executor, "   ")
        with self.assertRaises(ValueError):
            find_alternate_sources(self.executor, "pump pressure", limit=True)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
