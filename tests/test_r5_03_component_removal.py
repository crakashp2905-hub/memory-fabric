from __future__ import annotations

import unittest

from experiments.r5_03_component_removal import run


class ComponentRemovalTests(unittest.TestCase):
    def test_marginal_effects_are_reported_for_each_component(self) -> None:
        report = run()
        self.assertTrue(report["acceptance_passed"])

        dependency = report["components"]["summary_dependencies"]
        self.assertTrue(dependency["marginal_effect"]["stale_fact_blocked_by_component"])

        routing = report["components"]["decision_routing"]
        self.assertGreater(routing["marginal_effect_vs_fixed_system1"]["unsafe_actions_avoided"], 0)
        self.assertGreater(routing["marginal_effect_vs_fixed_system2"]["unnecessary_escalations_avoided"], 0)

        compression = report["components"]["temporal_compression"]
        self.assertGreater(compression["marginal_effect"]["context_bytes_saved_mean"], 0)
        self.assertEqual(compression["marginal_effect"]["task_success_rate_delta"], 0)
        self.assertEqual(compression["arms"]["component_enabled_provenance_summary"][
            "false_stale_actions"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
