from __future__ import annotations

import unittest

from memory_fabric.decision_router import ABSTAIN, SYSTEM1, SYSTEM2, RoutingFeatures, route_system


class LocalSystemRouterTests(unittest.TestCase):
    def test_repeated_runs_are_deterministic(self) -> None:
        features = RoutingFeatures("low", 0, "read", 200, 100)
        results = [route_system(features) for _ in range(20)]
        self.assertTrue(all(row == results[0] for row in results))
        self.assertEqual(results[0].route, SYSTEM1)

    def test_risk_gaps_and_tool_class_each_trigger_system2(self) -> None:
        cases = (
            RoutingFeatures("high", 0, "read", 200, 100),
            RoutingFeatures("low", 1, "analysis", 200, 100),
            RoutingFeatures("low", 0, "write", 200, 100),
        )
        for features in cases:
            with self.subTest(features=features):
                decision = route_system(features)
                self.assertEqual(decision.route, SYSTEM2)

    def test_insufficient_budget_abstains_instead_of_downgrading(self) -> None:
        decision = route_system(RoutingFeatures("critical", 2, "destructive", 99, 100))
        self.assertEqual(decision.route, ABSTAIN)
        self.assertIn("system2_budget_insufficient", decision.reasons)

    def test_unknown_tool_class_fails_closed_to_system2(self) -> None:
        decision = route_system(RoutingFeatures("low", 0, "new_tool_kind", 100, 100))
        self.assertEqual(decision.route, SYSTEM2)
        self.assertIn("unrecognized_tool_class", decision.reasons)

    def test_invalid_feature_values_are_rejected(self) -> None:
        invalid = (
            ("extreme", 0, "read", 100, 20),
            ("low", True, "read", 100, 20),
            ("low", -1, "read", 100, 20),
            ("low", 0, "read", -1, 20),
            ("low", 0, "read", 100, True),
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValueError):
                RoutingFeatures(*values)


if __name__ == "__main__":
    unittest.main()
