from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "research/CONTRIBUTION_MAP.md"


class ContributionMap(unittest.TestCase):
    def test_each_direction_has_a_falsifier_and_existing_baseline_credit(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for phrase in ("Correction-aware decision continuity", "Proof-carrying evidence sufficiency",
                       "Provenance-preserving consolidation", "falsified by", "falsifier",
                       "predates the study", "answerability", "action certificates",
                       "Context Map", "global literature"):
            self.assertIn(phrase.lower(), text.lower())

    def test_prior_mechanism_references_exist(self) -> None:
        for path in ("src/memory_fabric/lineage.py", "src/memory_fabric/certificates.py",
                     "tests/test_transitive_retraction.py", "src/memory_fabric/answerability.py",
                     "src/memory_fabric/actions.py", "tests/test_certificates.py",
                     "src/memory_fabric/context_map.py", "tests/test_context_map.py"):
            self.assertTrue((ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
