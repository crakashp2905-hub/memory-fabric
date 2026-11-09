from __future__ import annotations

import unittest

from memory_fabric import LifecycleState, MemoryFabric
from memory_fabric.governance.retention import RetentionPolicy, DAY_MS


class RetentionBoundaryTests(unittest.TestCase):
    def test_deprecated_zero_and_large_grace_boundaries(self) -> None:
        now = [1_700_000_000_000]
        policy = RetentionPolicy(deprecated_grace_days=0)
        fabric = MemoryFabric(auto_activate=True, clock=lambda: now[0], retention=policy)
        self.addCleanup(fabric.close)
        expired = fabric.remember("agent_a", "zero grace record")
        deprecated = fabric.get(expired)
        from dataclasses import replace
        deprecated = replace(deprecated, lifecycle_state=LifecycleState.DEPRECATED)
        stats = fabric.stats(expired)
        zero_decision = policy.decide(deprecated, stats, deprecated.created_at)
        self.assertEqual(zero_decision.action, "delete")
        self.assertEqual(policy.decide(deprecated, stats, deprecated.created_at - 1).action, "keep")

        # Large configured grace must not overflow or be treated as expired.
        large_policy = RetentionPolicy(deprecated_grace_days=10**12)
        large_decision = large_policy.decide(deprecated, stats, deprecated.created_at)
        self.assertEqual(large_decision.action, "keep")
        boundary_decision = large_policy.decide(deprecated, stats,
                                                deprecated.created_at + 10**12 * DAY_MS)
        self.assertEqual(boundary_decision.action, "delete")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
