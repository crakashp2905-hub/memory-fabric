"""Product jobs stay operationalized as seeded, measurable hypotheses."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/product/JOBS_TO_BE_DONE.md"


class TestProductJobs(unittest.TestCase):
    def test_three_jobs_have_workflow_benefit_baseline_and_outcome(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("not validated buyer demand", text)
        lower = text.lower()
        for phrase in ("Correction continuity", "Governed tool use", "Multi-agent knowledge sharing",
                       "Seeded workflow", "Intended operator benefit", "Ordinary baseline",
                       "Measurable outcome", "stale-action rate", "unauthorized effects",
                       "false corroboration from copies"):
            self.assertIn(phrase.lower(), lower)
        for path in ("examples/poisoning_and_rollback.py", "examples/wrong_memory_demo.py",
                     "examples/action_gate.py", "examples/multi_agent_team.py"):
            self.assertTrue((ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
