from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

from experiments import p12b_api_load


class TestP12bApiLoad(unittest.TestCase):
    def test_agent_reaches_fetch_and_verify_after_recall(self) -> None:
        calls: list[str] = []

        def fake_post(port: int, op: str, body: dict, bearer: str):
            calls.append(op)
            if op == "recall":
                return 200, {"memories": [{"memory_id": "m1"}]}
            return 200, {}

        out: list[tuple[str, float, int]] = []
        barrier = threading.Barrier(1)
        with patch.object(p12b_api_load, "post", side_effect=fake_post):
            p12b_api_load.agent_loop(1, "token", 0, barrier, out)

        self.assertIn("recall", calls)
        self.assertIn("fetch", calls)
        self.assertIn("verify", calls)
        self.assertTrue(any(op == "fetch+verify" for op, _, _ in out))

    def test_capacity_curve_aggregates_repeated_trials(self) -> None:
        rows = [
            {"agents": 5, "ok": 100, "ops": 100, "ops_per_s": 20.0,
             "latency_ms": {"all": {"p99": 100.0}}},
            {"agents": 5, "ok": 99, "ops": 100, "ops_per_s": 30.0,
             "latency_ms": {"all": {"p99": 200.0}}},
        ]
        curve = p12b_api_load.summarise_trials(rows)
        self.assertEqual(curve[0]["trials"], 2)
        self.assertEqual(curve[0]["successful_operations"], 199)
        self.assertEqual(curve[0]["throughput_ops_s"]["mean"], 25.0)
        self.assertEqual(curve[0]["p99_ms"]["mean"], 150.0)

    def test_positive_metric_confidence_bounds_do_not_go_negative(self) -> None:
        rows = [
            {"agents": 5, "ok": 1, "ops": 1, "ops_per_s": 1.0,
             "latency_ms": {"all": {"p99": 2.0}}},
            {"agents": 5, "ok": 100, "ops": 100, "ops_per_s": 100.0,
             "latency_ms": {"all": {"p99": 300.0}}},
        ]
        curve = p12b_api_load.summarise_trials(rows)[0]
        self.assertEqual(curve["throughput_ops_s"]["ci95_low"], 0.0)
        self.assertEqual(curve["p99_ms"]["ci95_low"], 0.0)


if __name__ == "__main__":
    unittest.main()
