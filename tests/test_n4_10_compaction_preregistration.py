from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "research" / "prereg" / "n4-10-provenance-compression-hypothesis-v1.md"


class CompactionNoveltyPreregistration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PREREG.read_text(encoding="utf-8")

    def test_all_four_comparison_arms_are_registered(self) -> None:
        for arm in (
            "no compaction", "naive recency", "extractive summary",
            "provenance-preserving summary",
        ):
            with self.subTest(arm=arm):
                self.assertIn(arm, self.text)

    def test_heldout_history_families_are_separate_from_development(self) -> None:
        for family in (
            "corrected procedures", "source revocation", "minority/contested",
            "multi-step action dependencies",
        ):
            with self.subTest(family=family):
                self.assertIn(family, self.text)
        self.assertIn("five fixed seeds per family", self.text)

    def test_claim_gates_include_equal_safety_and_full_history_ceiling(self) -> None:
        self.assertIn("false stale actions and false authorizations", self.text)
        self.assertIn("no candidate beats the full-history ceiling", self.text)
        self.assertIn("paired 95% confidence interval", self.text)

    def test_no_result_or_novelty_claim_is_inferred_from_registration(self) -> None:
        self.assertIn("Evidence status", self.text)
        self.assertIn("NOT_RUN", self.text)
        self.assertIn("do not claim", self.text)
        self.assertIn("does not establish absolute novelty", self.text)


if __name__ == "__main__":
    unittest.main()
