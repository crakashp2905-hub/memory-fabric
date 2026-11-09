from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from memory_fabric import MemoryFabric
from memory_fabric.protocol import Retraction, new_retraction_id, new_store_id
from memory_fabric.observability.health import classify
from memory_fabric.observability.server import Api


class ServiceHealth(unittest.TestCase):
    def test_healthy_requires_successful_store_and_integrity_checks(self) -> None:
        with MemoryFabric(":memory:", auto_activate=True) as fabric:
            result = Api(fabric).handle("/api/health", {})
        self.assertEqual(result["level"], "healthy")
        self.assertTrue(result["actions_allowed_by_health"])
        self.assertEqual(result["checks"]["event_integrity"], "pass")

    def test_pending_correction_is_degraded(self) -> None:
        with MemoryFabric(":memory:", auto_activate=True) as fabric:
            now = datetime.now(timezone.utc).isoformat()
            event = Retraction(new_retraction_id(), new_store_id(),
                               "01M4CV9BY8QH9AA1HN3KRASJ8V", 1, 1,
                               "contradicted", "operator", now)
            fabric.outbox.enqueue(event, ["offline-peer"], int(datetime.now().timestamp() * 1000))
            result = Api(fabric).handle("/api/health", {})
        self.assertEqual(result["level"], "degraded")
        self.assertEqual(result["reason_codes"], ["corrections_pending"])

    def test_tampered_event_chain_is_unsafe_to_execute(self) -> None:
        # Edits SQLite's trigger and rows directly: a file store, on SQLite in every run.
        with tempfile.TemporaryDirectory() as tmp, \
                MemoryFabric(Path(tmp) / "store.db", auto_activate=True) as fabric:
            fabric.remember("agent", "integrity fixture", scope="team")
            fabric.log._conn.execute("DROP TRIGGER events_no_update")
            fabric.log._conn.execute("UPDATE events SET payload = '{}' WHERE seq = 1")
            result = Api(fabric).handle("/api/health", {})
        self.assertEqual(result["level"], "unsafe-to-execute")
        self.assertFalse(result["actions_allowed_by_health"])
        self.assertEqual(result["reason_codes"], ["event_integrity_failed"])

    def test_store_read_failure_is_unavailable_not_healthy(self) -> None:
        with MemoryFabric(":memory:", auto_activate=True) as fabric:
            api = Api(fabric)
            with patch.object(fabric, "refresh", side_effect=OSError("injected read fault")):
                result = api.handle("/api/health", {})
        self.assertEqual(result["level"], "unavailable")
        self.assertFalse(result["actions_allowed_by_health"])

    def test_missing_required_check_fails_closed(self) -> None:
        result = classify(store_readable=True, integrity_ok=None, pending_corrections=0)
        self.assertEqual(result["level"], "unsafe-to-execute")
        self.assertEqual(result["reason_codes"], ["required_health_check_unavailable"])


if __name__ == "__main__":
    unittest.main()
