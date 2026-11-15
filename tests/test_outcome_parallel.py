"""Parallel recovery measurements must use scheduled OS worker processes."""

from __future__ import annotations

import unittest

from benchmarks.outcome_parallel import run_parallel_benchmark


class TestOutcomeParallel(unittest.TestCase):
    def test_parallel_latency_uses_processes_and_matches_sequential_cases(self) -> None:
        report = run_parallel_benchmark((101, 102, 103, 104), workers=2)
        self.assertEqual(report["scheduler"], "multiprocessing.ProcessPoolExecutor_spawn")
        self.assertEqual(report["process_workers"], 2)
        self.assertEqual(report["task_case_denominator"], 4)
        self.assertTrue(report["cases_match_sequential_reference"])
        self.assertFalse(report["performance_claim_eligible"])
        self.assertEqual(report["evidence_level"], "LOCAL_SCRIPTED_PROCESS_BENCHMARK_ONLY")
        self.assertEqual(len(report["raw_rows"]), 4)
        for mode in ("sequential", "parallel"):
            self.assertGreaterEqual(report[mode]["p99_ms"], report[mode]["p95_ms"])
            self.assertGreaterEqual(report[mode]["p95_ms"], report[mode]["p50_ms"])

    def test_rejects_one_worker_and_duplicate_seed_cases(self) -> None:
        with self.assertRaisesRegex(ValueError, "workers must be"):
            run_parallel_benchmark((1, 2), workers=1)
        with self.assertRaisesRegex(ValueError, "non-empty and unique"):
            run_parallel_benchmark((1, 1), workers=2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
