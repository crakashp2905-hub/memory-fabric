from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PR30WithheldCases(unittest.TestCase):
    def test_exact_candidate_replay_has_provenance_and_complete_case_fields(self) -> None:
        report = json.loads((ROOT / "research/results/pr30-withheld-cases.json").read_text(encoding="utf-8"))
        self.assertEqual(report["source_commit"], "12c612ea37980f92d206fe2b343b217603d1b3cc")
        self.assertEqual(report["base_commit"], "79a77f43c9e376968163c2164ee277052ed4117e")
        self.assertTrue(report["worktree_clean"])
        self.assertEqual(report["attempted"], 500)
        self.assertEqual(report["valid_withheld"], 84)
        self.assertEqual(report["withholding_rate"], 0.168)
        self.assertEqual(report["cases_per_seed"], {"101": 10, "102": 15, "103": 19, "104": 21, "105": 19})
        self.assertEqual(len(report["cases"]), 84)
        for case in report["cases"]:
            self.assertTrue(case["action"]["target"])
            self.assertTrue(case["evidence"]["claim"])
            self.assertTrue(case["blocker_reason"])
            self.assertTrue(case["oracle_supported"])


if __name__ == "__main__":
    unittest.main()
