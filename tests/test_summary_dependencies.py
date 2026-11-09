from __future__ import annotations

import json
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.compaction import CompactionRefused, compact_session
from memory_fabric.conflicts import claim
from memory_fabric.model import LifecycleState
from memory_fabric.summary_dependencies import (
    DependencyMapRefused,
    reconstruct_dependency_map,
    verify_stored_dependency_map,
)


def _fact_key(text: str) -> str:
    identifiers, words, values = claim(text)
    return json.dumps(
        [sorted(identifiers), sorted(words), sorted(values)],
        ensure_ascii=False,
        separators=(",", ":"),
    )


class SummaryDependencies(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = MemoryFabric(
            ":memory:", auto_activate=True, recognise_copies=False
        )
        self.addCleanup(self.fabric.close)
        self.episode = self.fabric.start_episode("operator", "inspection-7").id
        self.pump = self.fabric.remember(
            "operator", "Pump P1 purge time is 30 seconds.",
            source_episodes=[self.episode], scope="team",
        )
        self.pump_copy = self.fabric.remember(
            "archive", "Pump P1 purge time is 30 seconds.",
            source_episodes=[self.episode], scope="team",
        )
        self.valve = self.fabric.remember(
            "operator", "Valve V7 opens below 4 bar.",
            source_episodes=[self.episode], scope="team",
        )
        self.manual = self.fabric.remember(
            "manual", "Pump P9 restart pressure is 6 bar.", scope="team",
        )
        self.forum = self.fabric.remember(
            "forum", "Pump P9 restart pressure is 9 bar.",
            context={"origin": "web:forum"}, scope="team",
        )
        self.fabric.cite("operator", self.episode, self.manual)
        self.fabric.cite("operator", self.episode, self.forum)

    def test_generated_summary_reconstructs_exact_fact_to_version_oracle(self) -> None:
        self.fabric.revise(
            self.valve,
            "Valve V7 opens below 3 bar.",
            agent_id="operator",
            reason="checked against the current gauge",
        )
        report = compact_session(self.fabric, self.episode, agent_id="compactor")
        summary = self.fabric.get(report.summary_id)
        sources = [self.fabric.get(memory_id) for memory_id in report.inputs]

        expected = {
            _fact_key("Pump P1 purge time is 30 seconds."): [
                [self.pump, 1], [self.pump_copy, 1]
            ],
            _fact_key("Valve V7 opens below 3 bar."): [[self.valve, 2]],
            _fact_key("Pump P9 restart pressure is 6 bar."): [[self.manual, 1]],
            _fact_key("Pump P9 restart pressure is 9 bar."): [[self.forum, 1]],
        }
        self.assertEqual(summary.context["summary_dependencies"], expected)
        self.assertEqual(verify_stored_dependency_map(summary, sources), expected)
        self.assertTrue(
            all(self.fabric.get(memory_id).lifecycle_state is LifecycleState.ACTIVE
                for memory_id in report.inputs)
        )
        self.assertEqual(
            set(summary.provenance.parents),
            {(memory.id, memory.version) for memory in sources},
        )

    def test_active_summary_with_an_unsupported_added_fact_is_refused(self) -> None:
        before = set(self.fabric.state.memories)

        def inject(_memories, _disputes):
            return (
                "Pump P1 purge time is 30 seconds. "
                "Unit P99 failure rate is 999 percent. "
                "Pump P9 restart pressure is 6 bar and 9 bar."
            )

        with self.assertRaises(CompactionRefused):
            compact_session(self.fabric, self.episode, "compactor", summarise=inject)
        self.assertEqual(set(self.fabric.state.memories), before)

    def test_dependency_verification_refuses_retracted_original_versions(self) -> None:
        report = compact_session(self.fabric, self.episode, agent_id="compactor")
        summary = self.fabric.get(report.summary_id)
        self.fabric.quarantine(self.pump, reason="corrected", actor="reviewer")
        sources = [self.fabric.get(memory_id) for memory_id in report.inputs]
        with self.assertRaises(DependencyMapRefused):
            verify_stored_dependency_map(summary, sources)

    def test_missing_source_fact_is_not_silently_dropped(self) -> None:
        sources = [self.fabric.get(self.pump), self.fabric.get(self.valve)]
        with self.assertRaises(DependencyMapRefused):
            reconstruct_dependency_map(
                "Session summary (inspection-7): Pump P1 purge time is 30 seconds.",
                sources,
            )


if __name__ == "__main__":
    unittest.main()
