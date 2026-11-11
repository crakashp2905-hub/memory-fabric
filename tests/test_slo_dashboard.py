from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.observability.server import Api
from tools.slo_dashboard_smoke import build_report


class SloDashboard(unittest.TestCase):
    def test_fixture_report_passes_without_claiming_live_traffic(self) -> None:
        report = build_report()
        self.assertTrue(report["passed"])
        self.assertEqual(report["scope"], "synthetic in-process fixture")

    def test_snapshot_has_denominators_units_and_bounded_latency_percentiles(self) -> None:
        with MemoryFabric(":memory:", auto_activate=True) as fabric:
            api = Api(fabric)
            api.record_http_response(200, 1.0)
            api.record_http_response(404, 2.0)
            api.record_http_response(500, 3.0)
            snapshot = api.slo_snapshot()
        self.assertEqual(snapshot["http"]["requests_total"], 3)
        self.assertEqual(snapshot["http"]["error_responses_total"], 2)
        self.assertEqual(snapshot["http"]["error_denominator"], 3)
        self.assertAlmostEqual(snapshot["http"]["error_rate"], 2 / 3)
        self.assertEqual(snapshot["http"]["latency_unit"], "milliseconds")
        self.assertEqual(snapshot["http"]["latency_denominator"], 3)
        self.assertEqual(snapshot["http"]["latency_ms"], {"p50": 2.0, "p95": 2.0, "p99": 2.0})

    def test_blocked_actions_and_correction_queue_are_explicit(self) -> None:
        with MemoryFabric(":memory:", auto_activate=True) as fabric:
            gate = ActionGate(fabric, ActionPolicy(
                tools={"ship": ToolRule("ship")}, grants={}
            ))
            gate.authorize("ship", "agent")
            snapshot = Api(fabric).slo_snapshot()
        self.assertEqual(snapshot["actions"], {"blocked_total": 1, "denominator": 1})
        self.assertEqual(snapshot["corrections"]["pending_deliveries"], 0)
        self.assertIsNone(snapshot["corrections"]["oldest_pending_lag_seconds"])
        self.assertEqual(snapshot["corrections"]["lag_denominator"], 0)


if __name__ == "__main__":
    unittest.main()
