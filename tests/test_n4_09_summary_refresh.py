from __future__ import annotations

import unittest
from typing import Any, ClassVar

from experiments.n4_09_summary_refresh import evaluate_seed


class SummaryRefreshProfile(unittest.TestCase):
    result: ClassVar[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.result = evaluate_seed(13)

    def test_affected_refresh_recomputes_one_summary_per_correction(self) -> None:
        rows = self.result["affected_refresh"]["correction_recomputations"]
        self.assertEqual([row["writes"] for row in rows], [1, 1, 1])
        self.assertTrue(all(row["unaffected_summaries_unchanged"] for row in rows))

    def test_full_rebuild_recomputes_every_session(self) -> None:
        rows = self.result["complete_rebuild"]["correction_recomputations"]
        self.assertEqual([row["writes"] for row in rows], [6, 6, 6])
        self.assertEqual(
            self.result["complete_rebuild"]["total_source_inputs_reprocessed_after_corrections"],
            144,
        )

    def test_affected_refresh_uses_bounded_source_work(self) -> None:
        incremental = self.result["affected_refresh"]
        self.assertEqual(
            incremental["total_source_inputs_reprocessed_after_corrections"], 24
        )
        self.assertEqual(incremental["total_summary_writes"], 9)
        self.assertTrue(incremental["all_final_summaries_active"])

    def test_repeated_same_seed_refresh_has_identical_final_summaries(self) -> None:
        self.assertTrue(self.result["same_seed_refresh_deterministic"])
        self.assertTrue(self.result["complete_rebuild"]["all_final_summaries_active"])


if __name__ == "__main__":
    unittest.main()
