from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.compaction import (
    CompactionRefused,
    compact_session,
    verify_compaction_certificate,
)


class CompactionCertificate(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = MemoryFabric(
            ":memory:", auto_activate=True, hold_suspicious=False,
            recognise_copies=False,
        )
        self.addCleanup(self.fabric.close)
        self.episode = self.fabric.start_episode("operator", "lossy summary").id

    def test_nonconsequential_chatter_can_be_dropped_with_exact_edge_certificate(self) -> None:
        fact_id = self.fabric.remember(
            "operator", "Pump P1 purge interval is 30 seconds.",
            source_episodes=[self.episode], scope="team",
        )
        chatter_id = self.fabric.remember(
            "operator", "The shift handover was pleasant.",
            source_episodes=[self.episode], scope="team",
        )

        report = compact_session(
            self.fabric, self.episode, "compactor",
            summarise=lambda memories, disputes: "Pump P1 purge interval is 30 seconds.",
        )
        self.assertIsNotNone(report.summary_id)
        summary = self.fabric.get(report.summary_id)
        self.assertNotIn("pleasant", summary.content)
        verified = verify_compaction_certificate(self.fabric, summary.id)
        self.assertEqual(
            set(verified["source_versions"]),
            {(fact_id, 1), (chatter_id, 1)},
        )
        self.assertTrue(verified["certificate"])

    def test_strict_compaction_refuses_dropped_consequential_fact_before_write(self) -> None:
        self.fabric.remember(
            "operator", "Pump P1 purge interval is 30 seconds.",
            source_episodes=[self.episode], scope="team",
        )
        self.fabric.remember(
            "operator", "Valve V7 opens below 4 bar.",
            source_episodes=[self.episode], scope="team",
        )
        before = set(self.fabric.state.memories)

        with self.assertRaises(CompactionRefused):
            compact_session(
                self.fabric, self.episode, "compactor",
                summarise=lambda memories, disputes: "Pump P1 purge interval is 30 seconds.",
            )

        self.assertEqual(set(self.fabric.state.memories), before)

    def test_tampered_dependency_edges_fail_closed(self) -> None:
        self.fabric.remember(
            "operator", "Pump P1 purge interval is 30 seconds.",
            source_episodes=[self.episode], scope="team",
        )
        report = compact_session(self.fabric, self.episode, "compactor")
        self.assertIsNotNone(report.summary_id)
        summary = self.fabric.get(report.summary_id)
        context = dict(summary.context)
        context["summary_dependencies"] = {}
        self.fabric.state.memories[summary.id] = summary.evolve(context=context)

        with self.assertRaisesRegex(CompactionRefused, "proof edges"):
            verify_compaction_certificate(self.fabric, summary.id)

    def test_tampered_certificate_digest_fails_closed(self) -> None:
        self.fabric.remember(
            "operator", "Pump P1 purge interval is 30 seconds.",
            source_episodes=[self.episode], scope="team",
        )
        report = compact_session(self.fabric, self.episode, "compactor")
        self.assertIsNotNone(report.summary_id)
        summary = self.fabric.get(report.summary_id)
        context = dict(summary.context)
        context["summary_edge_certificate"] = "0" * 64
        self.fabric.state.memories[summary.id] = summary.evolve(context=context)

        with self.assertRaisesRegex(CompactionRefused, "certificate digest mismatch"):
            verify_compaction_certificate(self.fabric, summary.id)


if __name__ == "__main__":
    unittest.main()
