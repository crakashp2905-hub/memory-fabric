"""Decision guide stays grounded in existing evidence and stated limits."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/product/WHEN_TO_USE_MEMORY_FABRIC.md"


class TestProductFitGuidance(unittest.TestCase):
    def test_ordinary_vector_fit_and_tradeoffs_are_explicit(self):
        text = DOC.read_text(encoding="utf-8")
        for phrase in ("Prefer ordinary vector retrieval", "Consider Memory Fabric",
                       "not a universal result", "4.3–4.8 operations per second",
                       "24.2-second mean p99", "No buyer demand or revenue conclusion"):
            self.assertIn(phrase, text)
        for target in ("../../research/results/l1-long-running.md",
                       "../../research/results/x4-governed-vs-pooled.md",
                       "../../research/results/master-checklist-http-capacity-v1.md"):
            self.assertTrue((DOC.parent / target).resolve().is_file(), target)


if __name__ == "__main__":
    unittest.main()
