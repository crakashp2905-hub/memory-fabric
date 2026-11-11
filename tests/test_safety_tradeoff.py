from __future__ import annotations

import unittest

from benchmarks.safety_tradeoff import run


class SafetyTradeoff(unittest.TestCase):
    def test_records_safety_costs_and_every_denominator(self) -> None:
        report = run(1001)
        self.assertEqual(report["invariant_failures"], [])
        rows = {(r["family"], r["arm"]): r for r in report["rows"]}
        self.assertEqual(len(report["rows"]), 16)
        self.assertEqual(rows[("contested_valid", "memory_fabric")]["false_refusals"], 50)
        self.assertEqual(rows[("contested_valid", "memory_fabric")]["delayed_decisions"], 50)
        self.assertEqual(rows[("corrected_withdrawn", "permissive")]["unsafe_actions"], 50)
        self.assertEqual(rows[("missing", "memory_fabric")]["unsafe_actions"], 0)
        self.assertEqual(rows[("missing", "memory_fabric")]["wasted_calls"], 100)
        self.assertEqual(rows[("contested_valid", "memory_fabric")]["attempted"], 50)

    def test_utility_uses_frozen_preregistered_weights(self) -> None:
        report = run(1009)
        row = next(r for r in report["rows"]
                   if r["family"] == "corrected_withdrawn" and r["arm"] == "permissive")
        self.assertEqual(row["utility"], -270.0)


if __name__ == "__main__":
    unittest.main()
