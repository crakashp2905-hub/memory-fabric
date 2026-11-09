from __future__ import annotations

import unittest

from experiments.n6_05_protocol_equivalence import run


class ProtocolEquivalenceTests(unittest.TestCase):
    def test_http_mcp_and_utcp_mock_workflows_match_semantics_and_permissions(self) -> None:
        report = run()
        self.assertTrue(report["acceptance_passed"])
        self.assertTrue(report["metrics"]["same_semantics"])
        self.assertTrue(report["metrics"]["same_tool_work"])
        self.assertTrue(report["metrics"]["same_write_permission"])
        self.assertEqual(set(report["protocols"]), {"http", "mcp", "utcp"})
        self.assertFalse(report["metrics"]["paid_services_used"])


if __name__ == "__main__":
    unittest.main()
