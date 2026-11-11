from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from tools.claims_ledger import validate_claim

ROOT = Path(__file__).resolve().parents[1]


class ClaimCheckerContract(unittest.TestCase):
    def setUp(self) -> None:
        registry = json.loads((ROOT / "research/claims.json").read_text(encoding="utf-8"))
        self.claim = next(row for row in registry["claims"]
                          if row["id"] == "teamworld-current-baseline")
        self.evidence = ROOT / self.claim["evidence"]
        self.payload = json.loads(self.evidence.read_text(encoding="utf-8"))
        self.digest = hashlib.sha256(self.evidence.read_bytes()).hexdigest()

    def test_wrong_denominator_cannot_remain_supported(self) -> None:
        claim = copy.deepcopy(self.claim)
        claim["quantitative_assertions"][1]["equals"] = 499
        self.assertTrue(any("assertion" in issue for issue in
                            validate_claim(claim, self.payload, self.digest)))

    def test_changed_evidence_bytes_or_run_commit_fail(self) -> None:
        self.assertTrue(any("SHA-256 changed" in issue for issue in
                            validate_claim(self.claim, self.payload, "0" * 64)))
        changed = dict(self.payload)
        changed[self.claim["commit_field"]] = "different-run"
        self.assertTrue(any("outdated" in issue for issue in
                            validate_claim(self.claim, changed, self.digest)))


if __name__ == "__main__":
    unittest.main()
