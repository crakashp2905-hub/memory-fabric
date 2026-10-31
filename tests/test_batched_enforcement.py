"""A recall refreshes once, while still enforcing and tokenising every row."""

from __future__ import annotations

import unittest
from unittest import mock

from memory_fabric import MemoryFabric
from memory_fabric.sdk import agent


class BatchedEnforcement(unittest.TestCase):
    def test_batch_enforcement_has_one_refresh(self) -> None:
        fabric = MemoryFabric(auto_activate=True)
        self.addCleanup(fabric.close)
        for i in range(5):
            fabric.remember("writer", f"Pump P-{i} pressure is {i + 1} bar.", scope="team")
        ids = list(fabric.state.memories)
        with mock.patch.object(fabric, "refresh", wraps=fabric.refresh) as refresh:
            reads = fabric._use_many(ids, "reader", audit=False)
        self.assertEqual(len(reads), 5)
        self.assertEqual(refresh.call_count, 1)
        self.assertTrue(all(read.token is not None for read in reads))

        # The SDK path uses the batch and still returns one capability per row.
        rows = agent(fabric, "reader").recall("pump pressure", k=5)
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row.token is not None for row in rows))

    def test_withdrawn_row_is_still_refused_in_a_batch(self) -> None:
        fabric = MemoryFabric(auto_activate=True)
        self.addCleanup(fabric.close)
        live = fabric.remember("writer", "Pump P-1 pressure is 10 bar.", scope="team")
        gone = fabric.remember("writer", "Pump P-2 pressure is 20 bar.", scope="team")
        fabric.quarantine(gone, reason="wrong", actor="op", basis="contradicted")
        reads = fabric._use_many([live, gone], "reader", audit=False)
        self.assertTrue(reads[0].usable)
        self.assertFalse(reads[1].usable)


if __name__ == "__main__":
    unittest.main()
