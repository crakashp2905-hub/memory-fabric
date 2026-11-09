from __future__ import annotations

import unittest
import math

from tools.measure_local_footprint import THRESHOLDS


class LocalFootprintContract(unittest.TestCase):
    def test_thresholds_are_explicit_and_positive(self) -> None:
        self.assertEqual(set(THRESHOLDS), {
            "installed_package_bytes_max", "wheel_bytes_max",
            "cli_version_median_ms_max", "cli_version_p95_ms_max",
            "sqlite_bytes_per_record_max", "idle_cpu_percent_max",
        })
        self.assertTrue(all(value > 0 for value in THRESHOLDS.values()))

    def test_tail_startup_threshold_is_not_looser_than_median_by_less_than_expected(self) -> None:
        self.assertGreaterEqual(THRESHOLDS["cli_version_p95_ms_max"],
                                THRESHOLDS["cli_version_median_ms_max"])

    def test_nearest_rank_p95_includes_max_for_fifteen_samples(self) -> None:
        self.assertEqual(math.ceil(0.95 * 15) - 1, 14)


if __name__ == "__main__":
    unittest.main()
