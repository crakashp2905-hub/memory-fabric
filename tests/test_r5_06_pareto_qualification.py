from __future__ import annotations

import unittest

from tools.r5_06_pareto_qualification import dominates


class R506ParetoQualification(unittest.TestCase):
    def test_pareto_dominance_requires_no_worse_on_every_objective(self) -> None:
        better = {"success_rate": 0.9, "unsafe_rate": 0.0,
                  "mean_latency_ms": 10.0, "mean_memory_storage_bytes": 1000.0}
        worse = {"success_rate": 0.8, "unsafe_rate": 0.1,
                 "mean_latency_ms": 12.0, "mean_memory_storage_bytes": 1100.0}
        tradeoff = {"success_rate": 1.0, "unsafe_rate": 0.0,
                    "mean_latency_ms": 20.0, "mean_memory_storage_bytes": 900.0}
        self.assertTrue(dominates(better, worse))
        self.assertFalse(dominates(tradeoff, worse))
        self.assertFalse(dominates(better, better))


if __name__ == "__main__":
    unittest.main()
