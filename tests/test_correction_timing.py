from __future__ import annotations

import unittest

from benchmarks.correction_timing import ARMS, PHASES, run


class CorrectionTiming(unittest.TestCase):
    def test_timing_phases_have_distinct_stale_action_exposure(self) -> None:
        corrected = {phase: run(801, phase, True) for phase in PHASES}
        self.assertEqual(corrected["before_discovery"]["arms"]["cached_local"]["stale_actions"], 0)
        self.assertEqual(corrected["before_planning"]["arms"]["cached_local"]["stale_actions"], 50)
        self.assertEqual(corrected["before_action"]["arms"]["pooled_recheck"]["stale_actions"], 50)
        for phase in PHASES:
            self.assertEqual(corrected[phase]["arms"]["memory_fabric"]["stale_actions"], 0)
            self.assertEqual(set(corrected[phase]["coordination_disagreements"]), set(ARMS))
            self.assertFalse(any(corrected[phase]["coordination_disagreements"].values()))

    def test_unchanged_supported_controls_remain_completable(self) -> None:
        for phase in PHASES:
            row = run(801, phase, False)
            for arm in ARMS:
                self.assertEqual(row["arms"][arm]["correct"], 50)
                self.assertEqual(row["arms"][arm]["false_abstentions"], 0)


if __name__ == "__main__":
    unittest.main()
