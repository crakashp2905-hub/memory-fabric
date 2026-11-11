from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.compaction import (
    CompactionBudgetExceeded,
    compact_session,
    summary_for,
)
from memory_fabric.summary_dependencies import verify_stored_dependency_map


class CompactionTokenBudget(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = MemoryFabric(
            ":memory:", auto_activate=True, hold_suspicious=False,
            recognise_copies=False,
        )
        self.addCleanup(self.fabric.close)
        self.episode = self.fabric.start_episode("operator", "budgeted handoff").id
        self.sources = [
            self.fabric.remember(
                "operator", text, source_episodes=[self.episode], scope="team"
            )
            for text in (
                "Pump P1 purge interval is 30 seconds.",
                "Valve V7 opens below 4 bar.",
                "Pump P9 restart pressure is 6 bar.",
            )
        ]
        self.counter = lambda text: len(text.split())
        self.tokenizer = "test-whitespace-tokenizer/1"

    def test_fitting_budget_records_limit_count_and_all_dependencies(self) -> None:
        report = compact_session(
            self.fabric,
            self.episode,
            "compactor",
            token_counter=self.counter,
            tokenizer_provenance=self.tokenizer,
            max_summary_tokens=100,
        )
        summary = self.fabric.get(report.summary_id)

        self.assertEqual(report.token_budget_status, "WITHIN_BUDGET")
        self.assertEqual(report.max_summary_tokens, 100)
        self.assertLessEqual(report.summary_token_estimate, 100)
        budget = summary.context["summary_token_budget"]
        self.assertEqual(budget["limit"], 100)
        self.assertEqual(budget["observed"], report.summary_token_estimate)
        self.assertEqual(budget["tokenizer_provenance"], self.tokenizer)
        self.assertEqual(
            {tuple(ref) for refs in verify_stored_dependency_map(
                summary, [self.fabric.get(memory_id) for memory_id in self.sources]
            ).values() for ref in refs},
            {(memory_id, 1) for memory_id in self.sources},
        )

    def test_over_budget_returns_structured_failure_without_writing(self) -> None:
        before = set(self.fabric.state.memories)

        with self.assertRaises(CompactionBudgetExceeded) as raised:
            compact_session(
                self.fabric,
                self.episode,
                "compactor",
                token_counter=self.counter,
                tokenizer_provenance=self.tokenizer,
                max_summary_tokens=1,
            )

        failure = raised.exception.to_dict()
        self.assertEqual(failure["code"], "required_evidence_exceeds_token_budget")
        self.assertEqual(failure["max_summary_tokens"], 1)
        self.assertGreater(failure["required_summary_tokens"], 1)
        self.assertGreater(failure["source_bytes_utf8"], 0)
        self.assertGreater(failure["summary_bytes_utf8"], 0)
        self.assertEqual(failure["tokenizer_provenance"], self.tokenizer)
        self.assertEqual(failure["required_source_count"], len(self.sources))
        self.assertEqual(set(failure["required_source_ids"]), set(self.sources))
        self.assertFalse(failure["summary_written"])
        self.assertEqual(set(self.fabric.state.memories), before)
        self.assertIsNone(summary_for(self.fabric, self.episode))

    def test_conflicting_alternatives_are_both_compulsory(self) -> None:
        first = self.fabric.remember(
            "manual", "Pump P3 restart pressure is 5 bar.",
            source_episodes=[self.episode], scope="team",
        )
        second = self.fabric.remember(
            "inspector", "Pump P3 restart pressure is 8 bar.",
            source_episodes=[self.episode], scope="team",
        )

        with self.assertRaises(CompactionBudgetExceeded) as raised:
            compact_session(
                self.fabric,
                self.episode,
                "compactor",
                token_counter=self.counter,
                tokenizer_provenance=self.tokenizer,
                max_summary_tokens=5,
            )

        self.assertEqual(
            set(raised.exception.to_dict()["required_source_ids"]),
            set([*self.sources, first, second]),
        )
        self.assertIsNone(summary_for(self.fabric, self.episode))

    def test_budget_requires_an_explicit_tokenizer_before_writing(self) -> None:
        before = set(self.fabric.state.memories)
        with self.assertRaisesRegex(ValueError, "requires a token counter"):
            compact_session(
                self.fabric, self.episode, "compactor", max_summary_tokens=50
            )
        self.assertEqual(set(self.fabric.state.memories), before)


if __name__ == "__main__":
    unittest.main()
