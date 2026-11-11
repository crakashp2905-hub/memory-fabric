from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "research/REPRODUCIBILITY_APPENDIX.md"


class ReproducibilityAppendix(unittest.TestCase):
    def test_tables_have_local_commands_seed_and_scope_limits(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for phrase in ("Python: 3.13.5", "seed: `0`", "without API keys or external datasets",
                       "not live-model", "dirty source snapshot", "tests.test_examples_run"):
            self.assertIn(phrase.lower(), text.lower())

    def test_each_replay_script_and_result_file_exists(self) -> None:
        for path in ("examples/correction_strategy_comparison.py",
                     "examples/correction_spares_unrelated_action.py",
                     "examples/multi_agent_provenance_dispute.py",
                     "research/results/p4-04-correction-strategy-comparison.json",
                     "research/results/p4-05-selective-correction-demo.json",
                     "research/results/p4-06-provenance-dispute-demo.json",
                     "tests/test_examples_run.py"):
            self.assertTrue((ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
