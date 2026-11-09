from __future__ import annotations

import unittest

from experiments.n6_09_orchestration_cost_benchmark import run


class OrchestrationCostBenchmarkTests(unittest.TestCase):
    def test_equivalent_protocols_measure_calls_bytes_latency_and_safe_completion(self) -> None:
        report = run(samples=5)
        self.assertTrue(report["acceptance_passed"])
        self.assertTrue(report["comparison"]["same_semantics"])
        self.assertTrue(report["comparison"]["safe_completion_all_samples"])
        self.assertFalse(report["comparison"]["model_token_savings_claimed"])
        for protocol in ("direct_sdk", "mcp", "utcp"):
            metrics = report["protocols"][protocol]
            self.assertEqual(metrics["safe_completion_rate"], 1.0)
            self.assertEqual(metrics["tool_calls_per_workflow"], [5])
            self.assertGreater(metrics["application_request_bytes_median"], 0)
            self.assertGreater(metrics["application_response_bytes_median"], 0)
            self.assertGreaterEqual(metrics["workflow_wall_ms_p95"],
                                    metrics["workflow_wall_ms_p50"])
        self.assertEqual(report["protocols"]["direct_sdk"]["wire_body_bytes_median"], 0)
        self.assertGreater(report["protocols"]["mcp"]["wire_body_bytes_median"], 0)
        self.assertGreater(report["protocols"]["utcp"]["wire_body_bytes_median"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
