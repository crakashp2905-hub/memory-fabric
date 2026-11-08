"""A capped runaway local worker is stopped and its isolated artifacts are removed."""

from __future__ import annotations

import unittest

from benchmarks.cdm_timeout_teardown import run


class TestTimeoutTeardown(unittest.TestCase):
    def test_wall_time_interruption_terminates_child_and_removes_temp_directory(self):
        report = run(0.05)
        self.assertTrue(report["timed_out"])
        self.assertTrue(report["worker_marker_created"])
        self.assertTrue(report["worker_terminated"])
        self.assertIsNotNone(report["worker_returncode"])
        self.assertTrue(report["temporary_directory_removed"])
        self.assertEqual(report["network_calls"], 0)
        self.assertEqual(report["model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
