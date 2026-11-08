from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "research/FAILURE_TAXONOMY.md"


class FailureTaxonomy(unittest.TestCase):
    def test_named_historical_outcomes_and_next_boundaries_are_kept(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for phrase in ("H2 — KILLED", "PA — KILLED", "PA′1 — KILLED", "PA′2 — SUPPORTED",
                       "PB1 — KILLED", "PB3 — INCONCLUSIVE", "invalid oracle",
                       "Next test boundary"):
            self.assertIn(phrase, text)

    def test_all_source_records_exist(self) -> None:
        for path in ("research/results/h2-credit-driven-retention.md",
                     "research/prereg/h2-credit-driven-retention.md",
                     "research/results/phase-a-real-agent-benchmark.md",
                     "research/prereg/phase-a-real-agent-benchmark.md",
                     "research/results/phase-a-prime-attribution.md",
                     "research/prereg/phase-a-prime-attribution.md",
                     "research/results/phase-b-federated-agents.md",
                     "research/prereg/phase-b-federated-agents.md"):
            self.assertTrue((ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
