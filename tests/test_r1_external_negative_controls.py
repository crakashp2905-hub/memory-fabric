"""External retrieval suites must expose broken and random evidence controls."""
from __future__ import annotations

import unittest

from experiments.external_bench import Dataset, evaluate
from experiments.longmemeval_bench import run_arm


class ExternalSuiteNegativeControls(unittest.TestCase):
    def test_scifact_broken_and_random_arms_fall_below_the_oracle(self) -> None:
        corpus = {f"d{i:03d}": f"irrelevant abstract {i} about unrelated materials" for i in range(100)}
        corpus["d001"] = "Aspirin reduces platelet aggregation in healthy adults."
        corpus["d002"] = "Statins lower low-density lipoprotein cholesterol."
        dataset = Dataset(
            corpus=corpus,
            queries={"q1": "Aspirin affects platelet aggregation.",
                     "q2": "Statins reduce LDL cholesterol."},
            qrels={"q1": {"d001": 1}, "q2": {"d002": 1}},
        )
        result = evaluate(dataset, ["broken_retrieval", "random_evidence", "oracle"], k=5)
        scores = {arm: row["ndcg_at_5"] for arm, row in result["arms"].items()}
        self.assertEqual(scores["oracle"], 1.0)
        self.assertEqual(scores["broken_retrieval"], 0.0)
        self.assertLess(scores["random_evidence"], scores["oracle"])

    def test_longmemeval_broken_and_random_arms_miss_the_synthetic_gold_turn(self) -> None:
        sessions = [[{"role": "user", "content": f"irrelevant note number {i}",
                      "has_answer": i == 37} for i in range(40)]]
        instance = {
            "question_id": "control-case-001",
            "question_type": "single-session-user-update",
            "question": "What is the recorded marker?",
            "question_date": "",
            "haystack_sessions": sessions,
            "haystack_session_ids": ["session-1"],
            "haystack_dates": [""],
            "answer_session_ids": ["session-1"],
        }
        oracle = run_arm("oracle", [instance], k=3).summary()
        broken = run_arm("broken_retrieval", [instance], k=3).summary()
        random_a = run_arm("random_evidence", [instance], k=3).summary()
        random_b = run_arm("random_evidence", [instance], k=3).summary()
        self.assertEqual(oracle["turn_recall"], 1.0)
        self.assertEqual(broken["turn_recall"], 0.0)
        self.assertEqual(random_a["turn_recall"], random_b["turn_recall"])
        self.assertLess(random_a["turn_recall"], oracle["turn_recall"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
