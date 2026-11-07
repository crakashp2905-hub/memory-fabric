from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.federation import PreparedOffer, accept_offer, offer, prepare_offer
from memory_fabric.governance.firewall import (
    Firewall,
    rule_capabilities_must_be_granted,
    rule_must_be_active,
    rule_restricted_stays_private,
)
from memory_fabric.model import LifecycleState
from memory_fabric.tombstones import export_bundle, import_bundle


class PortableTombstoneExchange(unittest.TestCase):
    def setUp(self) -> None:
        firewall = Firewall(
            rules=(
                rule_restricted_stays_private,
                rule_must_be_active,
                rule_capabilities_must_be_granted,
            )
        )
        self.origin = MemoryFabric(":memory:", auto_activate=True, firewall=firewall)
        self.first = MemoryFabric(":memory:", auto_activate=True, firewall=firewall)
        self.second = MemoryFabric(":memory:", auto_activate=True, firewall=firewall)
        self.addCleanup(self.origin.close)
        self.addCleanup(self.first.close)
        self.addCleanup(self.second.close)
        self.mid = self.origin.remember("origin", "The retired limit is 10 bar.")
        self.snapshot = prepare_offer(self.origin, self.mid, self.first.store_id)
        self.second_snapshot = prepare_offer(self.origin, self.mid, self.second.store_id)
        self.assertIsInstance(self.snapshot, PreparedOffer)
        self.assertIsInstance(self.second_snapshot, PreparedOffer)
        imported = offer(self.origin, self.mid, self.first, "reader", activate=True)
        self.assertTrue(imported.accepted)
        self.imported_id = imported.imported_memory_id
        self.origin.request_retraction(
            self.mid,
            reason="withdrawn",
            recipients=[self.first.store_id, self.second.store_id],
            actor="origin",
        )
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bundle = Path(self.tmp.name) / "tombstones.json"
        export_bundle(self.origin, self.bundle)

    def test_snapshot_then_tombstone_withdraws_and_cannot_resurrect(self) -> None:
        report = import_bundle(
            self.first, self.bundle, trusted_origins=[self.origin.store_id]
        )
        self.assertEqual(report.enforced, 1)
        self.assertEqual(
            self.first.get(self.imported_id).lifecycle_state,
            LifecycleState.QUARANTINED,
        )
        replay = accept_offer(self.first, self.snapshot, "reader", activate=True)
        self.assertFalse(replay.accepted)
        self.assertIn("durable tombstone", replay.reasons[0])

    def test_tombstone_then_snapshot_is_fenced(self) -> None:
        report = import_bundle(
            self.second, self.bundle, trusted_origins=[self.origin.store_id]
        )
        self.assertEqual(report.recorded, 1)
        result = accept_offer(self.second, self.second_snapshot, "reader", activate=True)
        self.assertFalse(result.accepted)
        self.assertEqual(list(self.second.state.memories), [])

    def test_import_is_explicit_and_idempotent(self) -> None:
        with self.assertRaises(PermissionError):
            import_bundle(self.second, self.bundle, trusted_origins=[])
        first = import_bundle(
            self.second, self.bundle, trusted_origins=[self.origin.store_id]
        )
        second = import_bundle(
            self.second, self.bundle, trusted_origins=[self.origin.store_id]
        )
        self.assertEqual(first.recorded, 1)
        self.assertEqual(second.duplicates, 1)

    def test_bundle_contains_no_memory_content(self) -> None:
        text = self.bundle.read_text(encoding="utf-8")
        self.assertNotIn("retired limit", text)
        self.assertNotIn("10 bar", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
