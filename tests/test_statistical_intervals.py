"""Reference-value checks for completion and false-block intervals."""
from __future__ import annotations

import unittest

from benchmarks.stats import wilson, zero_events_upper


class BinomialIntervalReferences(unittest.TestCase):
    def test_wilson_zero_half_and_all_successes(self) -> None:
        self.assertEqual(wilson(0, 20), (0.0, 0.16112516018512965))
        low, high = wilson(10, 20)
        self.assertAlmostEqual(low, 0.2992980068701797, places=12)
        self.assertAlmostEqual(high, 0.7007019931298203, places=12)
        self.assertEqual(wilson(20, 20), (0.8388748398148705, 1.0))

    def test_zero_denominator_is_explicitly_uninformative(self) -> None:
        self.assertEqual(wilson(0, 0), (0.0, 1.0))

    def test_zero_event_exact_upper_bound_reference_cases(self) -> None:
        self.assertAlmostEqual(zero_events_upper(20), 0.13910834066826516, places=12)
        self.assertAlmostEqual(zero_events_upper(100), 0.029513049607039932, places=12)
        self.assertEqual(zero_events_upper(0), 1.0)


if __name__ == "__main__":
    unittest.main()
