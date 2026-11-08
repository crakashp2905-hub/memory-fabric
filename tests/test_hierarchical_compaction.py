from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.compaction import (
    CompactionRefused,
    compact_hierarchy,
    verify_hierarchical_summary,
)
from memory_fabric.model import LifecycleState


class HierarchicalCompaction(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = MemoryFabric(":memory:", auto_activate=True, recognise_copies=False)
        self.addCleanup(self.fabric.close)
        self.episode = self.fabric.start_episode("writer", "long maintenance history").id
        self.sources = [
            self.fabric.remember(
                "writer",
                f"Pump P{index} purge threshold is {index + 10} bar.",
                source_episodes=[self.episode],
                scope="team",
            )
            for index in range(10)
        ]

    def test_hierarchy_is_deterministic_and_has_exact_edge_certificates(self) -> None:
        first = compact_hierarchy(
            self.fabric, self.episode, "compactor", leaf_size=4
        )
        second = compact_hierarchy(
            self.fabric, self.episode, "compactor", leaf_size=4
        )
        first_root = self.fabric.get(first.root_summary_id)
        second_root = self.fabric.get(second.root_summary_id)

        self.assertEqual(first.leaf_source_groups, second.leaf_source_groups)
        self.assertEqual(len(first.leaf_summary_ids), 3)
        self.assertEqual(first_root.content, second_root.content)
        self.assertEqual(
            first.leaf_source_groups,
            [self.sources[:4], self.sources[4:8], self.sources[8:]],
        )
        verification = verify_hierarchical_summary(self.fabric, first.root_summary_id)
        self.assertEqual(verification["source_versions"], [(memory_id, 1) for memory_id in self.sources])
        self.assertTrue(verification["certificate"])

    def test_correction_invalidates_only_its_leaf_and_the_dependent_root(self) -> None:
        report = compact_hierarchy(
            self.fabric, self.episode, "compactor", leaf_size=4
        )
        affected_leaf = report.leaf_summary_ids[0]
        unaffected_leaves = report.leaf_summary_ids[1:]
        self.fabric.revise(
            self.sources[0],
            "Pump P0 purge threshold is 99 bar.",
            agent_id="writer",
            reason="calibrated replacement gauge",
        )

        self.assertNotEqual(
            self.fabric.get(affected_leaf).lifecycle_state,
            LifecycleState.ACTIVE,
        )
        self.assertNotEqual(
            self.fabric.get(report.root_summary_id).lifecycle_state,
            LifecycleState.ACTIVE,
        )
        self.assertTrue(all(
            self.fabric.get(leaf_id).lifecycle_state is LifecycleState.ACTIVE
            for leaf_id in unaffected_leaves
        ))
        with self.assertRaises(CompactionRefused):
            verify_hierarchical_summary(self.fabric, report.root_summary_id)

    def test_small_histories_do_not_get_a_fake_hierarchy(self) -> None:
        with self.assertRaises(CompactionRefused):
            compact_hierarchy(self.fabric, self.episode, "compactor", leaf_size=10)


if __name__ == "__main__":
    unittest.main()
