"""Efficiency report shape, scaling workloads and branch recall are reproducible."""

from __future__ import annotations

import unittest

from benchmarks.cdm_efficiency import run


class TestEfficiency(unittest.TestCase):
    def test_seeded_workload_manifest_is_reproducible_and_measured(self):
        first = run([19], sizes=(10, 100))
        second = run([19], sizes=(10, 100))
        self.assertEqual(first["workload_sha256"], second["workload_sha256"])
        self.assertEqual(len(first["rows"]), 2)
        self.assertIn("p95_wall_ns", first["summary"]["10"])
        self.assertIn("peak_tracemalloc_bytes", first["rows"][0])
        self.assertIn("branch_recall_at_k", first["rows"][0])
        self.assertEqual(first["limits"]["network_calls"], 0)


if __name__ == "__main__":
    unittest.main()
