from __future__ import annotations

import json
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.compaction import compact_hierarchy, compact_session, verify_hierarchical_summary
from memory_fabric.model import LifecycleState
from memory_fabric.summary_dependencies import verify_stored_dependency_map
from memory_fabric.validation import review_queue


class ContestedCompactionFacts(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = MemoryFabric(
            ":memory:",
            auto_activate=True,
            recognise_copies=False,
            # Model sources already admitted for review. This disables only
            # write-time suspicion holding; compaction still marks the full
            # cross-author disagreement unresolved and does not choose a side.
            hold_suspicious=False,
        )
        self.addCleanup(self.fabric.close)
        self.episode = self.fabric.start_episode("operator", "minority pressure report").id
        self.majority_ids = [
            self.fabric.remember(
                "majority-log",
                "Pump P9 restart pressure is 6 bar.",
                source_episodes=[self.episode],
                scope="team",
            )
            for _ in range(10)
        ]
        self.minority_id = self.fabric.remember(
            "minority-inspector",
            "Pump P9 restart pressure is 9 bar.",
            source_episodes=[self.episode],
            scope="team",
        )
        self.source_ids = [*self.majority_ids, self.minority_id]

    def _assert_both_alternatives_are_supported(self, summary_id: str) -> None:
        summary = self.fabric.get(summary_id)
        self.assertEqual(summary.lifecycle_state, LifecycleState.ACTIVE)
        self.assertIn("Disputed, unresolved", summary.content)
        self.assertIn("Pump P9 restart pressure is 6 bar.", summary.content)
        self.assertIn("Pump P9 restart pressure is 9 bar.", summary.content)

        sources = [self.fabric.get(memory_id) for memory_id in self.source_ids]
        dependencies = verify_stored_dependency_map(summary, sources)
        mapped_ids = {
            str(reference[0])
            for references in dependencies.values()
            for reference in references
        }
        self.assertEqual(mapped_ids, set(self.source_ids))
        value_alternatives = {
            tuple(json.loads(fact_key)[2]) for fact_key in dependencies
        }
        self.assertIn(("6",), value_alternatives)
        self.assertIn(("9",), value_alternatives)

    def test_compaction_retains_a_single_minority_against_ten_repetitions(self) -> None:
        report = compact_session(self.fabric, self.episode, "compactor")
        summary = self.fabric.get(report.summary_id)

        self.assertEqual(len(report.disputes), 1)
        self.assertEqual(set(report.disputes[0]), set(self.source_ids))
        self._assert_both_alternatives_are_supported(summary.id)

    def test_hierarchy_keeps_minority_when_it_is_alone_in_a_separate_leaf(self) -> None:
        report = compact_hierarchy(
            self.fabric, self.episode, "compactor", leaf_size=10
        )
        minority_leaf = self.fabric.get(report.leaf_summary_ids[1])
        self.assertEqual(report.leaf_source_groups[1], [self.minority_id])
        self.assertIn("9 bar", minority_leaf.content)
        self.assertNotIn("6 bar", minority_leaf.content)

        self._assert_both_alternatives_are_supported(report.root_summary_id)
        verified = verify_hierarchical_summary(self.fabric, report.root_summary_id)
        self.assertEqual(
            {memory_id for memory_id, _version in verified["source_versions"]},
            set(self.source_ids),
        )

    def test_default_hold_keeps_candidate_reviewable_without_promoting_it(self) -> None:
        fabric = MemoryFabric(
            ":memory:", auto_activate=True, recognise_copies=False
        )
        self.addCleanup(fabric.close)
        episode = fabric.start_episode("operator", "held minority report").id
        for _ in range(10):
            fabric.remember(
                "majority-log",
                "Pump P9 restart pressure is 6 bar.",
                source_episodes=[episode],
                scope="team",
            )
        minority_id = fabric.remember(
            "minority-inspector",
            "Pump P9 restart pressure is 9 bar.",
            source_episodes=[episode],
            scope="team",
        )
        self.assertEqual(fabric.get(minority_id).lifecycle_state, LifecycleState.CANDIDATE)

        report = compact_session(fabric, episode, "compactor")
        summary = fabric.get(report.summary_id)
        self.assertEqual(report.left_out[minority_id], "candidate")
        self.assertIn("6 bar", summary.content)
        self.assertNotIn("9 bar", summary.content)
        self.assertIn(minority_id, {item.memory_id for item in review_queue(fabric)})
        self.assertNotEqual(fabric.get(minority_id).lifecycle_state, LifecycleState.ACTIVE)


if __name__ == "__main__":
    unittest.main()
