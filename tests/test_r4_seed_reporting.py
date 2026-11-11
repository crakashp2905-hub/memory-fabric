"""Keep the headline benchmark's per-seed report bound to its data."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestSeedReporting(unittest.TestCase):
    def test_grand_baseline_reports_every_seed_and_worst_outcomes(self):
        data = json.loads((ROOT / "research/results/grand-50-agent-baseline-reproduction-v2.json").read_text(encoding="utf-8"))
        report = (ROOT / "research/results/grand-50-agent-baseline-reproduction-v2.md").read_text(encoding="utf-8")
        rows = data["fabric_per_seed"]
        self.assertEqual({row["seed"] for row in rows}, {101, 102, 103, 104, 105})
        for row in rows:
            expected = f"| {row['seed']} | {row['task_success']:.0%} | {row['valid_evidence_withheld']:.0%} | {row['stale_action_rate']:.0%} |"
            self.assertIn(expected, report)
        worst_success = min(rows, key=lambda row: row["task_success"])
        worst_withheld = max(rows, key=lambda row: row["valid_evidence_withheld"])
        self.assertIn(f"worst observed task-success rate is {worst_success['task_success']:.0%} (seed {worst_success['seed']})", report)
        self.assertIn(f"worst valid-evidence-withholding rate is {worst_withheld['valid_evidence_withheld']:.0%} (seed {worst_withheld['seed']})", report)


if __name__ == "__main__":
    unittest.main()
