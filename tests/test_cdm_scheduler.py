"""Replay selector determinism, budget refusal and dependency frontier tests."""

from __future__ import annotations

import time
import unittest

from memory_fabric.causal_replay.scheduler import (Candidate, ReplayBudget, check_budget,
    branch_recall_at_k, earliest_affected_index, replay_frontier, select_centrality, select_priority,
    select_random, select_recency)
from memory_fabric.causal_replay.types import BudgetExceeded, CDMError
from memory_fabric.causal_replay.bayes import BinaryNode
from memory_fabric.causal_replay.executor import execute
from memory_fabric.causal_replay.policy import ThresholdPolicy
from memory_fabric.causal_replay.replay import deterministic_simulator
from memory_fabric.causal_replay.state import Observation


class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.candidates = (Candidate("old-central", 1, 0.2, 0.8, 0.4,
                                     ("b", "c", "d")),
                           Candidate("recent", 9, 0.3, 0.3, 0.2),
                           Candidate("risky", 2, 1.0, 0.7, 0.8))

    @staticmethod
    def _executed_loo_pivotal_ids(observations):
        simulator = deterministic_simulator((
            BinaryNode("fault", (), {(): 0.2}),
            BinaryNode("alarm", ("fault",), {(False,): 0.1, (True,): 0.9})))
        policy = ThresholdPolicy("fault")
        factual = execute(observations, simulator=simulator, policy=policy)
        pivotal = set()
        for target in observations:
            counterfactual = tuple(item for item in observations
                                   if item.observation_id != target.observation_id)
            replay = execute(counterfactual, simulator=simulator, policy=policy)
            if factual.steps[-1].proposal != replay.steps[-1].proposal:
                pivotal.add(target.observation_id)
        return pivotal

    def test_selectors_are_deterministic_and_budgeted(self):
        self.assertEqual(select_random(self.candidates, seed=4, k=2),
                         select_random(self.candidates, seed=4, k=2))
        self.assertEqual(select_recency(self.candidates, k=1)[0].candidate_id, "recent")
        self.assertEqual(select_centrality(self.candidates, k=1)[0].candidate_id, "old-central")
        self.assertEqual(select_priority(self.candidates, k=1)[0].candidate_id, "risky")
        with self.assertRaises(CDMError):
            select_priority(self.candidates, k=4)

    def test_centrality_uses_only_visible_neighbor_structure(self):
        candidates = (Candidate("hub", 1, 0.0, 0.0, 0.0, ("a", "b", "c")),
                      Candidate("isolated", 2, 1.0, 1.0, 1.0, ()))
        first = select_centrality(candidates, k=1)
        changed_nonstructural = (Candidate("hub", 1, 1.0, 1.0, 1.0, ("a", "b", "c")),
                                 Candidate("isolated", 2, 0.0, 0.0, 0.0, ()))
        self.assertEqual(first[0].candidate_id, "hub")
        self.assertEqual([item.candidate_id for item in
                          select_centrality(changed_nonstructural, k=1)],
                         [item.candidate_id for item in first])

    def test_priority_uses_declared_pre_replay_features_only(self):
        candidates = (Candidate("risk", 1, 1.0, 0.0, 0.0),
                      Candidate("context", 2, 0.0, 1.0, 1.0))
        selected = select_priority(candidates, k=1)
        self.assertEqual(selected[0].candidate_id, "context")
        changed_order = tuple(reversed(candidates))
        self.assertEqual(select_priority(changed_order, k=1), selected)

    def test_dependency_frontier_and_unknown_fallback(self):
        events = ("e0", "e1", "e2", "e3")
        graph = {"e1": ("e0",), "e2": ("e1",), "e3": ()}
        self.assertEqual(earliest_affected_index(events, "e1", dependencies=graph,
                                                   dependencies_complete=True), 1)
        self.assertEqual(replay_frontier(events, "e1", dependencies=graph,
                                         dependencies_complete=True), ("e1", "e2", "e3"))
        self.assertEqual(replay_frontier(events, "e2", dependencies=graph,
                                         dependencies_complete=False), events)

    def test_dependency_closure_includes_derived_belief_and_decision_links(self):
        events = ("source", "derived-belief", "downstream-decision", "later")
        graph = {"derived-belief": ("source",),
                 "downstream-decision": ("derived-belief",),
                 "later": ("downstream-decision",)}
        self.assertEqual(earliest_affected_index(events, "source", dependencies=graph,
                                                  dependencies_complete=True), 0)
        self.assertEqual(replay_frontier(events, "derived-belief", dependencies=graph,
                                         dependencies_complete=True),
                         ("derived-belief", "downstream-decision", "later"))

    def test_budget_checks_events_attempts_memory_and_time(self):
        budget = ReplayBudget(max_events=4, max_attempts=2, max_wall_seconds=5,
                              max_memory_bytes=100_000, max_nodes=10)
        check_budget(budget, event_count=4, node_count=4, attempt_count=2,
                     started_monotonic=time.monotonic())
        with self.assertRaises(BudgetExceeded):
            check_budget(budget, event_count=5, node_count=4, attempt_count=1,
                         started_monotonic=time.monotonic())
        with self.assertRaises(BudgetExceeded):
            check_budget(budget, event_count=1, node_count=10, attempt_count=1,
                         started_monotonic=time.monotonic())
        with self.assertRaises(BudgetExceeded):
            check_budget(budget, event_count=1, node_count=2, attempt_count=1,
                         started_monotonic=time.monotonic() - 6)

    def test_no_signal_selector_is_stable(self):
        candidates = tuple(Candidate(name, index, 0.0, 0.0, 0.0)
                          for index, name in enumerate(("c", "a", "b")))
        self.assertEqual([item.candidate_id for item in select_priority(candidates, k=3)],
                         ["a", "b", "c"])

    def test_branch_recall_uses_executed_oracle_pivotal_set(self):
        selected = select_priority(self.candidates, k=2)
        score = branch_recall_at_k(selected, {"risky", "recent"}, candidate_count=3)
        self.assertAlmostEqual(score, 0.5)
        self.assertIsNone(branch_recall_at_k((), (), candidate_count=3))

    def test_early_pivotal_event_is_visible_to_budgeted_selector_recall(self):
        observations = (Observation("early-pivotal", "alarm", True, "early", 1),
                        Observation("later-context", "alarm", False, "early", 8),
                        Observation("latest-noise", "alarm", True, "early", 12))
        candidates = (Candidate("early-pivotal", 1, 1.0, 1.0, 1.0),
                      Candidate("later-context", 8, 0.1, 0.2, 0.1),
                      Candidate("latest-noise", 12, 0.0, 0.1, 0.0))
        oracle_pivotal = self._executed_loo_pivotal_ids(observations)
        self.assertEqual(oracle_pivotal, {"early-pivotal"})
        self.assertEqual(branch_recall_at_k(select_recency(candidates, k=1),
                         oracle_pivotal, candidate_count=len(candidates)), 0.0)
        self.assertEqual(branch_recall_at_k(select_priority(candidates, k=1),
                         oracle_pivotal, candidate_count=len(candidates)), 1.0)

    def test_low_centrality_pivotal_event_can_be_missed_by_centrality(self):
        observations = (Observation("low-degree-pivotal", "alarm", True, "shared", 1),
                        Observation("hub-a", "alarm", False, "shared", 2),
                        Observation("hub-b", "alarm", True, "shared", 3))
        candidates = (Candidate("low-degree-pivotal", 1, 1.0, 1.0, 1.0),
                      Candidate("hub-a", 2, 0.0, 0.0, 0.0, ("x", "y", "z")),
                      Candidate("hub-b", 3, 0.0, 0.0, 0.0, ("u", "v")))
        oracle_pivotal = self._executed_loo_pivotal_ids(observations)
        self.assertEqual(oracle_pivotal, {"low-degree-pivotal"})
        self.assertEqual(branch_recall_at_k(select_centrality(candidates, k=1),
                         oracle_pivotal, candidate_count=len(candidates)), 0.0)
        self.assertEqual(branch_recall_at_k(select_priority(candidates, k=1),
                         oracle_pivotal, candidate_count=len(candidates)), 1.0)


if __name__ == "__main__":
    unittest.main()
