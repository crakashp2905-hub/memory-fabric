from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.events import EventType
from memory_fabric.model import LifecycleState
from memory_fabric.consensus import support


class HypothesisPreservation(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = MemoryFabric(
            auto_activate=True, hold_suspicious=False, recognise_copies=True
        )
        self.addCleanup(self.fabric.close)

    def _fixture(self) -> tuple[list[str], list[str], list[str]]:
        one_root = [
            self.fabric.remember(
                f"repeat_{index}", "Pump P9 restart pressure is 6 bar."
            )
            for index in range(10)
        ]
        two_roots = [
            self.fabric.remember(
                "inspector_a", "Pump P9 restart pressure measured at 9 bar."
            ),
            self.fabric.remember(
                "inspector_b", "Field check: P9 restarts at pressure 9 bar."
            ),
        ]
        return one_root + two_roots, one_root, two_roots

    def test_conflicting_plausible_values_keep_independent_source_roots(self) -> None:
        _all_ids, one_root, two_roots = self._fixture()
        report = support(self.fabric, "Pump P9 restart pressure is 6 bar.")
        six = next(value for value in report.values if value.value == "6")
        nine = next(value for value in report.values if value.value == "9")

        self.assertEqual(six.independent_sources, 1)
        self.assertEqual(len(six.origin_clusters), 1)
        self.assertEqual(set(six.origin_clusters[0].memories), set(one_root))
        self.assertEqual(nine.independent_sources, 2)
        self.assertEqual(len(nine.origin_clusters), 2)
        self.assertEqual(
            {memory for cluster in nine.origin_clusters for memory in cluster.memories},
            set(two_roots),
        )

    def test_challenge_opens_unresolved_set_without_selecting_a_winner(self) -> None:
        memory_ids, one_root, two_roots = self._fixture()
        set_id = self.fabric.challenge(
            memory_ids, evidence="contradictory pressure readings; investigation required"
        )
        hypothesis = self.fabric.state.hypothesis_sets[set_id]

        self.assertEqual(hypothesis.memory_ids, set(memory_ids))
        self.assertFalse(hypothesis.resolved)
        self.assertEqual(len({self.fabric.source_root(mid) for mid in one_root}), 1)
        self.assertEqual(len({self.fabric.source_root(mid) for mid in two_roots}), 2)
        self.assertTrue(all(
            self.fabric.get(mid).lifecycle_state is LifecycleState.CONTESTED
            for mid in memory_ids
        ))

    def test_challenge_does_not_emit_an_experiment_or_authentication_event(self) -> None:
        memory_ids, _one_root, _two_roots = self._fixture()
        before = len(self.fabric.log)
        self.fabric.challenge(memory_ids, evidence="readings disagree")
        appended = list(self.fabric.log.read(since_seq=before))

        self.assertFalse(any(event.type is EventType.EXPERIMENT_RUN for event in appended))
        self.assertFalse(self.fabric.state.hypothesis_sets[next(iter(
            self.fabric.state.hypothesis_sets
        ))].resolved)

    def test_both_claim_texts_remain_recoverable_in_the_open_set(self) -> None:
        memory_ids, _one_root, _two_roots = self._fixture()
        set_id = self.fabric.challenge(memory_ids, evidence="open comparison")
        hypothesis = self.fabric.state.hypothesis_sets[set_id]
        texts = {self.fabric.get(mid).content for mid in hypothesis.memory_ids}

        self.assertTrue(any("6 bar" in text for text in texts))
        self.assertTrue(any("9 bar" in text for text in texts))
        self.assertFalse(hypothesis.resolved)


if __name__ == "__main__":
    unittest.main()
