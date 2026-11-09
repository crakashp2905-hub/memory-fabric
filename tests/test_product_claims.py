"""Public claims must be supported by the maturity inventory and evidence."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import check_product_claims

ROOT = Path(__file__).resolve().parents[1]


class ProductClaims(unittest.TestCase):
    def test_current_public_claims_pass_the_maturity_gate(self) -> None:
        self.assertEqual(check_product_claims.validate_claims(), [])

    def test_generated_capability_matrix_is_current(self) -> None:
        done = subprocess.run([sys.executable, str(ROOT / "tools/check_product_claims.py"),
                               "--check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_simulated_or_externally_unverified_sales_claim_fails(self) -> None:
        bad = {
            "schema": "memory-fabric-public-claims/1",
            "claims": [{
                "id": "claim.unsupported", "text": "Certified and proven universally.",
                "capabilities": ["compliance.certification", "research.general_effectiveness"],
                "evidence": ["docs/product/CAPABILITY_REGISTRY.md"],
                "qualification": "none",
            }],
        }
        (ROOT / ".task-tmp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".task-tmp") as directory:
            path = Path(directory) / "claims.json"
            path.write_text(json.dumps(bad), encoding="utf-8")
            with patch.object(check_product_claims, "CLAIMS", path):
                issues = check_product_claims.validate_claims()
        self.assertTrue(any("externally_unverified" in issue for issue in issues), issues)
        self.assertTrue(any("simulated" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
