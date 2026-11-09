from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.compaction import (
    CompactionRefused,
    compact_hierarchy,
    compact_session,
    verify_hierarchical_summary,
)


class TemporalCompaction(unittest.TestCase):
    def test_revised_preference_keeps_recorded_identity_and_valid_time(self) -> None:
        fabric = MemoryFabric(
            ":memory:", auto_activate=True, hold_suspicious=False,
            recognise_copies=False,
        )
        self.addCleanup(fabric.close)
        episode = fabric.start_episode("preference-owner", "room lighting").id
        future_preference = fabric.remember(
            "preference-owner",
            "User U1 prefers warm white lighting.",
            source_episodes=[episode],
            scope="team",
            valid_from=2_000_000_000_000,
        )
        later_recorded_past_preference = fabric.remember(
            "preference-owner",
            "User U1 prefers cool white lighting.",
            source_episodes=[episode],
            scope="team",
            valid_from=1_000_000_000_000,
            valid_to=1_500_000_000_000,
        )

        revised = fabric.revise(
            future_preference,
            "User U1 prefers amber white lighting.",
            agent_id="preference-owner",
            reason="preference clarified before installation",
            expected_version=1,
        )
        self.assertEqual(revised.version, 2)
        self.assertEqual(revised.valid_from, 2_000_000_000_000)
        self.assertIsNone(revised.valid_to)

        report = compact_session(fabric, episode, "compactor")
        summary = fabric.get(report.summary_id)
        self.assertIn("amber white lighting", summary.content)
        self.assertIn("cool white lighting", summary.content)
        self.assertNotIn("warm white lighting", summary.content)

        metadata = summary.context["summary_source_metadata"]
        by_id = {item["source_id"]: item for item in metadata}
        self.assertEqual(set(by_id), {future_preference, later_recorded_past_preference})
        self.assertEqual(by_id[future_preference]["source_version"], 2)
        self.assertEqual(by_id[future_preference]["version_author"], "preference-owner")
        self.assertEqual(by_id[future_preference]["valid_from"], 2_000_000_000_000)
        self.assertIsNone(by_id[future_preference]["valid_to"])
        self.assertEqual(by_id[later_recorded_past_preference]["source_version"], 1)
        self.assertEqual(by_id[later_recorded_past_preference]["version_author"], "preference-owner")
        self.assertEqual(by_id[later_recorded_past_preference]["valid_from"], 1_000_000_000_000)
        self.assertEqual(by_id[later_recorded_past_preference]["valid_to"], 1_500_000_000_000)

        self.assertEqual(
            by_id[future_preference]["recorded_at"],
            fabric.get(future_preference).created_at,
        )
        self.assertEqual(
            by_id[later_recorded_past_preference]["recorded_at"],
            fabric.get(later_recorded_past_preference).created_at,
        )
        self.assertGreater(
            by_id[future_preference]["recorded_seq"],
            by_id[later_recorded_past_preference]["recorded_seq"],
        )
        earlier_world_time = 1_200_000_000_000
        later_world_time = 2_100_000_000_000
        self.assertFalse(fabric.get(future_preference).applies_at(earlier_world_time))
        self.assertTrue(fabric.get(later_recorded_past_preference).applies_at(earlier_world_time))
        self.assertTrue(fabric.get(later_recorded_past_preference).applies_at(1_499_999_999_999))
        self.assertFalse(fabric.get(later_recorded_past_preference).applies_at(1_500_000_000_000))
        self.assertTrue(fabric.get(future_preference).applies_at(later_world_time))
        self.assertFalse(fabric.get(later_recorded_past_preference).applies_at(later_world_time))

    def test_hierarchical_certificate_binds_valid_time_and_original_source(self) -> None:
        fabric = MemoryFabric(
            ":memory:", auto_activate=True, hold_suspicious=False,
            recognise_copies=False,
        )
        self.addCleanup(fabric.close)
        episode = fabric.start_episode("maintainer", "temporal history").id
        sources = [
            fabric.remember(
                "maintainer",
                f"Pump P{index} service interval is {index + 1} days.",
                source_episodes=[episode],
                scope="team",
                valid_from=1_000 + index,
                valid_to=2_000 + index,
            )
            for index in range(5)
        ]
        hierarchy = compact_hierarchy(
            fabric, episode, "compactor", leaf_size=2
        )
        root = fabric.get(hierarchy.root_summary_id)
        root_metadata = root.context["summary_source_metadata"]
        self.assertEqual(
            {item["source_id"] for item in root_metadata}, set(sources)
        )
        self.assertTrue(all(item["version_author"] == "maintainer" for item in root_metadata))
        self.assertTrue(verify_hierarchical_summary(fabric, hierarchy.root_summary_id)["certificate"])

        tampered = [dict(item) for item in root_metadata]
        tampered[0]["valid_from"] += 1
        context = dict(root.context)
        context["summary_source_metadata"] = tampered
        fabric.state.memories[root.id] = root.evolve(context=context)
        with self.assertRaisesRegex(CompactionRefused, "valid-time metadata"):
            verify_hierarchical_summary(fabric, hierarchy.root_summary_id)


if __name__ == "__main__":
    unittest.main()
