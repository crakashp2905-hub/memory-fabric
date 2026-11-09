from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.security_findings import evaluate

ROOT = Path(__file__).resolve().parents[1]


class SecurityFindingsGate(unittest.TestCase):
    def test_checked_in_register_is_locally_ready_but_requires_external_review(self) -> None:
        register = json.loads((ROOT / "research/security/internal_findings.json").read_text(encoding="utf-8"))
        result = evaluate(register, ROOT)
        # The locally reproducible F1/F16 fixes pass; O7 still requires an
        # independent external review and is deliberately outside this gate.
        self.assertTrue(result["local_ready"])
        self.assertEqual(result["blocking_findings"], [])
        self.assertEqual(result["external_review_required"], ["O7"])
        self.assertFalse(result["external_review_complete"])

    def test_open_critical_or_high_blocks_local_ready(self) -> None:
        register = {
            "schema": "memory-fabric-internal-security-findings/1",
            "findings": [{"id": "X1", "severity": "critical", "status": "open",
                          "exploit_preconditions": "attacker has access", "verified_fix": "none",
                          "verification_tests": []}],
        }
        result = evaluate(register, ROOT)
        self.assertFalse(result["local_ready"])
        self.assertEqual(result["blocking_findings"], ["X1"])

    def test_medium_and_external_findings_do_not_fake_local_high_block(self) -> None:
        register = {
            "schema": "memory-fabric-internal-security-findings/1",
            "findings": [{"id": "M1", "severity": "medium", "status": "accepted",
                          "exploit_preconditions": "specific condition", "verified_fix": "documented limit",
                          "verification_tests": []}],
        }
        self.assertTrue(evaluate(register, ROOT)["local_ready"])

    def test_fixed_finding_requires_existing_verification_test(self) -> None:
        register = {
            "schema": "memory-fabric-internal-security-findings/1",
            "findings": [{"id": "H1", "severity": "high", "status": "fixed",
                          "exploit_preconditions": "specific condition", "verified_fix": "fixed",
                          "verification_tests": ["tests/does_not_exist.py"]}],
        }
        result = evaluate(register, ROOT)
        self.assertFalse(result["local_ready"])
        self.assertIn("H1: missing verification test tests/does_not_exist.py",
                      result["blocking_findings"])

    def test_fixed_finding_requires_test_and_rationale_fields(self) -> None:
        for field in ("exploit_preconditions", "verified_fix"):
            register = {
                "schema": "memory-fabric-internal-security-findings/1",
                "findings": [{"id": "H1", "severity": "high", "status": "fixed",
                              "exploit_preconditions": "condition", "verified_fix": "fix",
                              "verification_tests": ["tests/test_security_findings.py"]}],
            }
            register["findings"][0][field] = ""
            with self.assertRaisesRegex(ValueError, field):
                evaluate(register, ROOT)


if __name__ == "__main__":
    unittest.main()
