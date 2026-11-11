"""Checkpoint placement measurements disclose storage and current verification cost."""

from __future__ import annotations

import unittest

from benchmarks.cdm_checkpoint_granularity import run


class TestCheckpointGranularity(unittest.TestCase):
    def test_schedules_measure_checkpoint_count_bytes_and_integrity_work(self):
        report = run(20261109, 10)
        self.assertFalse(report["restore_speedup_claimed"])
        self.assertEqual(report["event_count"], 10)
        rows = {row["schedule"]: row for row in report["rows"]}
        self.assertEqual(rows["every_1"]["checkpoint_count"], 10)
        self.assertEqual(rows["terminal_only"]["checkpoint_count"], 1)
        self.assertGreater(rows["every_1"]["total_payload_bytes"],
                           rows["terminal_only"]["total_payload_bytes"])
        for row in report["rows"]:
            self.assertEqual(row["current_restore_prefix_replay_events"],
                             sum(point["prefix_events"] for point in row["checkpoints"]))
            self.assertTrue(all(point["checkpoint_sha256"] for point in row["checkpoints"]))


if __name__ == "__main__":
    unittest.main()
