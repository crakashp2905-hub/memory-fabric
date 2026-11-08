"""Long-trace terminal-state measurements retain independent fidelity checks."""

from __future__ import annotations

import unittest

from benchmarks.cdm_replay_overhead import run, run_executor_sweep


class TestReplayOverhead(unittest.TestCase):
    def test_small_overhead_sweep_records_cost_and_oracle_fidelity(self):
        report = run(20261108, (100, 1_000))
        self.assertTrue(report["all_exact_state_fidelity"])
        self.assertEqual(report["mode"], "terminal_state_reconstruction_not_per_event_trace_execution")
        for row in report["rows"]:
            self.assertGreaterEqual(row["cpu_ns"], 0)
            self.assertGreater(row["wall_ns"], 0)
            self.assertGreater(row["live_allocation_blocks"], 0)
            self.assertGreater(row["peak_traced_bytes"], 0)
            self.assertLessEqual(row["posterior_abs_error"], 1e-12)

    def test_full_executor_measurement_records_per_event_trace_cost(self):
        report = run_executor_sweep(20261108, (100,), timeout_seconds=10.0)
        self.assertEqual(report["mode"], "full_per_event_executor_trace")
        row = report["rows"][0]
        self.assertEqual(row["status"], "MEASURED")
        self.assertEqual(row["step_count"], 100)
        self.assertTrue(row["exact_state_fidelity"])
        self.assertGreater(row["cpu_ns"], 0)
        self.assertGreater(row["peak_traced_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
