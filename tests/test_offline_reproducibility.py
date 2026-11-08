from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "research/OFFLINE_REPRODUCIBILITY.md"


class OfflineReproducibility(unittest.TestCase):
    def test_commands_and_external_gates_are_explicit(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for phrase in ("python tools/claims_ledger.py", "python tools/offline_qualification.py",
                       "python tools/check_product_claims.py --check", "Independent human security review",
                       "Representative-user pilot", "Physical multi-host validation",
                       "global prior-art review", "OPEN"):
            self.assertIn(phrase, text)

    def test_referenced_scripts_and_artifacts_exist(self) -> None:
        for path in ("tools/claims_ledger.py", "tools/offline_qualification.py",
                     "tools/check_product_claims.py", "tools/gen_capabilities.py",
                     "research/results/grand-50-agent-baseline-reproduction-v2.json",
                     "research/results/p4-08-local-footprint.json"):
            self.assertTrue((ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
