from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = (
    "research/results/r3-01-agent-scale.json",
    "research/results/r3-02-matched-agent-arms.json",
    "research/results/r3-03-failure-taxonomy.json",
    "research/results/r3-04-correction-timing.json",
    "research/results/r3-05-minority-source.json",
    "research/results/r3-06-safety-tradeoff.json",
)


class SimulationLabels(unittest.TestCase):
    def test_every_local_r3_report_separates_synthetic_from_model_evidence(self) -> None:
        for relative in REPORTS:
            with self.subTest(report=relative):
                report = json.loads((ROOT / relative).read_text(encoding="utf-8"))
                self.assertEqual(report["population"], "synthetic_scripted")
                limitations = " ".join(report.get("limitations", [])).lower()
                self.assertTrue(any(token in limitations for token in
                                    ("model", "real-agent", "real-world consensus")))


if __name__ == "__main__":
    unittest.main()
