import random
import unittest

from memory_fabric.causal_replay import (
    BinaryNode,
    Observation,
    ThresholdPolicy,
    dependency_frontier,
    execute_dependency_frontier,
    execute_replay,
)
from memory_fabric.causal_replay.replay import DeterministicSimulator
from memory_fabric.causal_replay.types import CDMError, NonReplayable


class DependencyFrontierTests(unittest.TestCase):
    def setUp(self):
        self.nodes = (
            BinaryNode("fault", (), {(): 0.3}),
            BinaryNode("other", (), {(): 0.45}),
            BinaryNode("third", (), {(): 0.55}),
        )
        self.simulator = DeterministicSimulator(self.nodes)
        self.policy = ThresholdPolicy("fault")
        self.dependencies = {
            "e0": (), "e1": (), "e2": ("e1",), "e3": ("e0",), "e4": ("e3",),
        }

    def _trace(self, seed):
        rng = random.Random(seed)
        return (
            Observation("e0", "other", bool(rng.getrandbits(1)), "root-0", 0),
            Observation("e1", "third", bool(rng.getrandbits(1)), "root-1", 1),
            Observation("e2", "fault", bool(rng.getrandbits(1)), "root-2", 2),
            Observation("e3", "other", bool(rng.getrandbits(1)), "root-3", 3),
            Observation("e4", "other", bool(rng.getrandbits(1)), "root-4", 4),
        )

    def test_frontier_is_transitive_ordered_and_unknown_falls_back(self):
        ids = ("e0", "e1", "e2", "e3", "e4")
        self.assertEqual(dependency_frontier(ids, "e0", dependencies=self.dependencies,
            dependencies_complete=True), ("e0", "e3", "e4"))
        self.assertEqual(dependency_frontier(ids, "e1", dependencies=self.dependencies,
            dependencies_complete=True), ("e1", "e2"))
        self.assertEqual(dependency_frontier(ids, "e0", dependencies={},
            dependencies_complete=False), ids)

    def test_selective_frontier_matches_exhaustive_replay_for_five_seeded_worlds(self):
        for seed in range(5):
            with self.subTest(seed=seed):
                factual = self._trace(seed)
                baseline = execute_replay(factual, simulator=self.simulator, policy=self.policy)
                counterfactual = tuple(item for item in factual if item.observation_id != "e0")
                selective = execute_dependency_frontier(counterfactual, baseline=baseline,
                    target_observation_id="e0", dependencies=self.dependencies,
                    dependencies_complete=True, simulator=self.simulator, policy=self.policy)
                exhaustive = execute_replay(counterfactual, simulator=self.simulator,
                                            policy=self.policy)
                self.assertEqual(selective.final_state, exhaustive.final_state)
                self.assertEqual(selective.steps, exhaustive.steps)
                self.assertEqual(selective.consumed, 2)
                self.assertEqual(selective.execution_kind, "dependency_frontier_replay")

    def test_replacement_and_unknown_graph_are_exact(self):
        factual = self._trace(17)
        baseline = execute_replay(factual, simulator=self.simulator, policy=self.policy)
        changed = list(factual)
        original = changed[0]
        changed[0] = Observation(original.observation_id, original.variable,
            not original.value, original.origin, original.sequence)
        replacement_trace = tuple(changed)
        selective = execute_dependency_frontier(replacement_trace, baseline=baseline,
            target_observation_id="e0", dependencies=self.dependencies,
            dependencies_complete=True, simulator=self.simulator, policy=self.policy)
        exhaustive = execute_replay(replacement_trace, simulator=self.simulator,
                                    policy=self.policy)
        self.assertEqual(selective.steps, exhaustive.steps)
        self.assertEqual(selective.final_state, exhaustive.final_state)
        self.assertEqual(selective.consumed, 3)

        fallback = execute_dependency_frontier(replacement_trace, baseline=baseline,
            target_observation_id="e0", dependencies={}, dependencies_complete=False,
            simulator=self.simulator, policy=self.policy)
        self.assertEqual(fallback.steps, exhaustive.steps)
        self.assertEqual(fallback.execution_kind, "dependency_frontier_incomplete_fallback")

    def test_incomplete_complete_graph_and_unrelated_mutations_refuse(self):
        ids = ("e0", "e1", "e2", "e3", "e4")
        with self.assertRaises(CDMError):
            dependency_frontier(ids, "e0", dependencies={"e0": ()},
                                dependencies_complete=True)
        factual = self._trace(21)
        baseline = execute_replay(factual, simulator=self.simulator, policy=self.policy)
        changed = list(factual)
        changed[1] = Observation("e1", "third", not changed[1].value, "root-1", 1)
        with self.assertRaises(NonReplayable):
            execute_dependency_frontier(tuple(changed), baseline=baseline,
                target_observation_id="e0", dependencies=self.dependencies,
                dependencies_complete=True, simulator=self.simulator, policy=self.policy)


if __name__ == "__main__":
    unittest.main()
