from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.events import EventType
from memory_fabric.projections import Projection


class WriteFaultInjection(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "store.db"
        self.fabric = MemoryFabric(self.path, auto_activate=True)
        self.addCleanup(self.fabric.close)

    def fail_event(self, event_type: str) -> None:
        self.fabric.log._conn.execute(
            "CREATE TRIGGER injected_failure BEFORE INSERT ON events "
            f"WHEN NEW.type = '{event_type}' "
            "BEGIN SELECT RAISE(ABORT, 'injected stage failure'); END",
        )

    def clear_failure(self) -> None:
        self.fabric.log._conn.execute("DROP TRIGGER IF EXISTS injected_failure")

    def assert_projection_matches_replay(self) -> None:
        rebuilt = Projection.rebuild(self.fabric.log, unsealer=self.fabric._unseal_content)
        self.assertEqual(set(rebuilt.state.memories), set(self.fabric.state.memories))
        self.assertEqual(
            {mid: m.content for mid, m in rebuilt.state.memories.items()},
            {mid: m.content for mid, m in self.fabric.state.memories.items()},
        )

    def test_append_and_correction_failures_leave_no_partial_version(self) -> None:
        self.fail_event(EventType.MEMORY_CREATED)
        with self.assertRaises(sqlite3.IntegrityError):
            self.fabric.remember("agent_a", "new append")
        self.clear_failure()
        self.assertEqual(self.fabric.state.memories, {})
        self.assert_projection_matches_replay()

        memory_id = self.fabric.remember("agent_a", "original wording")
        self.fail_event(EventType.MEMORY_VERSIONED)
        with self.assertRaises(sqlite3.IntegrityError):
            self.fabric.revise(memory_id, "corrected wording", "agent_a", "correction")
        self.clear_failure()
        self.assertEqual(self.fabric.get(memory_id).version, 1)
        self.assertEqual(self.fabric.get(memory_id).content, "original wording")
        self.assert_projection_matches_replay()

    def test_erasure_failure_keeps_key_and_projection_consistent(self) -> None:
        memory_id = self.fabric.remember("agent_a", "erase probe secret")
        self.fail_event(EventType.CONTENT_ERASED)
        with self.assertRaises(sqlite3.IntegrityError):
            self.fabric.erase_content(memory_id, reason="fault injection", actor="dpo")
        self.clear_failure()
        self.assertEqual(self.fabric.get(memory_id).content, "erase probe secret")
        self.assertFalse(self.fabric.vault.status(memory_id).erased)
        self.assert_projection_matches_replay()

    def test_action_receipt_failure_leaves_unknown_attempt_not_duplicate_receipt(self) -> None:
        memory_id = self.fabric.remember("agent_a", "verified maintenance record")
        self.fabric.validate(memory_id, actor="reviewer")
        certificate = self.fabric.certify("maintenance", [memory_id], "agent_a")
        policy = ActionPolicy(
            tools={"inspect": ToolRule("inspect")},
            grants={"agent_a": frozenset({"inspect"})},
        )
        gate = ActionGate(self.fabric, policy)
        effects: list[str] = []
        self.fail_event(EventType.ACTION_EXECUTED)
        with self.assertRaises(sqlite3.IntegrityError):
            gate.execute("inspect", "agent_a", lambda key: effects.append(key) or "ok",
                         certificate, key="receipt-failure")
        self.clear_failure()
        self.assertEqual(effects, ["receipt-failure"])
        attempts = list(self.fabric.log.read_types([EventType.ACTION_ATTEMPTED]))
        receipts = [e for e in self.fabric.log.read_types([EventType.ACTION_EXECUTED])
                    if e.payload.get("key") == "receipt-failure"]
        self.assertEqual(len(attempts), 1)
        self.assertEqual(receipts, [])
        self.assert_projection_matches_replay()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
