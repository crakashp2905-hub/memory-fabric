from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/product/decisions/2026-10-28-packaging-options.md"


class PackagingHypotheses(unittest.TestCase):
    def test_all_tiers_are_explicitly_unvalidated_and_no_price_is_invented(self) -> None:
        text = DOC.read_text(encoding="utf-8").lower()
        for tier in ("free developer", "local individual", "team", "enterprise"):
            self.assertIn(tier, text)
        for qualification in ("unvalidated tier hypotheses", "not offers", "revenue forecasts",
                              "all four rows remain hypotheses"):
            self.assertIn(qualification, text)
        self.assertNotRegex(text, r"\$\s*\d|\d+\s*(?:usd|dollars)\b")


if __name__ == "__main__":
    unittest.main()
