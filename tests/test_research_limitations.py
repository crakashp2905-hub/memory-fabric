from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "research/RESEARCH_LIMITATIONS.md"


class ResearchLimitations(unittest.TestCase):
    def test_evidence_classes_and_external_gates_are_distinguished(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for phrase in ("Mathematical/contract checks", "Model-free implementation tests",
                       "Scripted or synthetic experiments", "Real model or external validation",
                       "remain OPEN", "Historical H2, PA and PB1"):
            self.assertIn(phrase, text)

    def test_referenced_local_artifacts_exist(self) -> None:
        for path in ("docs/VALIDATION.md", "tests/test_statistical_intervals.py",
                     "tests/test_benchmarks.py", "research/results/e4-10-deterministic-soak.json",
                     "research/results/grand-50-agent-baseline-reproduction-v2.json",
                     "research/results/p4-04-correction-strategy-comparison.json"):
            self.assertTrue((ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
