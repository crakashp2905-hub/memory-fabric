from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from experiments import longmemeval_bench

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research" / "results" / "longmemeval.md"


class RetrievalBaselineContract(unittest.TestCase):
    def test_all_four_arms_share_the_run_arm_k_parameter(self) -> None:
        signature = inspect.signature(longmemeval_bench.run_arm)
        self.assertIn("k", signature.parameters)
        source = inspect.getsource(longmemeval_bench.run_arm)
        self.assertIn("query=instance[\"question\"], k=k", source)
        self.assertIn("query=instance[\"question\"], k=k,", source)
        for arm in ("lexical", "vector", "hybrid", "chain"):
            self.assertIn(arm, longmemeval_bench.ARMS)

    def test_committed_report_has_overall_and_six_family_rows_for_each_arm(self) -> None:
        text = REPORT.read_text(encoding="utf-8")
        self.assertIn("500 instances", text)
        self.assertIn("k=10", text)
        self.assertIn("knowledge-update (78)", text)
        self.assertIn("single-preference (30)", text)
        for arm in ("`lexical`", "`vector`", "`hybrid`", "`chain`"):
            # Once in the overall table and once in the per-question-type table.
            self.assertGreaterEqual(text.count(f"| {arm} |"), 2, arm)

    def test_report_does_not_claim_end_to_end_accuracy(self) -> None:
        text = REPORT.read_text(encoding="utf-8")
        self.assertIn("Retrieval stage only", text)
        self.assertIn("those numbers and these are not comparable", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
