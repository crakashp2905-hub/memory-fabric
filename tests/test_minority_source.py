from __future__ import annotations

import unittest

from benchmarks.minority_source import run


class MinoritySource(unittest.TestCase):
    def test_copy_majority_counts_one_root_and_reports_minority_separately(self) -> None:
        row = run(901)
        self.assertEqual(row["agent_count"], 50)
        self.assertEqual(row["source_counts"]["majority_observations"], 49)
        self.assertEqual(row["source_counts"]["majority_independent_roots"], 1)
        self.assertEqual(row["source_counts"]["total_independent_roots"], 2)
        mf = row["arms"]["memory_fabric"]
        self.assertEqual(mf["minority_agent"]["false_refusal_rate"], 1.0)
        self.assertEqual(mf["population_mean"]["false_refusal_rate"], 1.0)
        self.assertEqual(row["blocker_reason"]["memory_fabric"], "evidence_not_usable")
        self.assertEqual(row["arms"]["minority_source"]["minority_agent"]["success_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
