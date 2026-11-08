"""Competing evidence is generated over chain, star, and fork dependency shapes."""

from __future__ import annotations

import unittest

from benchmarks.cdm_dependency_shapes import run


class TestDependencyShapes(unittest.TestCase):
    def test_shapes_have_competing_evidence_and_expected_frontiers(self):
        report = run(8)
        rows = {row["shape"]: row for row in report["rows"]}
        self.assertEqual(set(rows), {"chain", "star", "fork"})
        self.assertTrue(all(row["competing_evidence"] for row in rows.values()))
        self.assertTrue(all(row["edge_count"] > 0 for row in rows.values()))
        self.assertEqual(rows["chain"]["frontier_size"], 7)
        self.assertEqual(rows["star"]["frontier_size"], 1)
        self.assertEqual(rows["fork"]["frontier_size"], 3)
        self.assertEqual(len(rows["fork"]["observations"]), 8)


if __name__ == "__main__":
    unittest.main()
