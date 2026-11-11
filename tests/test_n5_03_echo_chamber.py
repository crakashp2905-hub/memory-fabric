from __future__ import annotations

import unittest

from experiments.n5_03_echo_chamber import generate


class EchoChamberGeneratorTests(unittest.TestCase):
    def test_star_chain_and_clustered_topologies_have_controlled_edges(self) -> None:
        star = generate("star", seed=7, count=8)
        chain = generate("chain", seed=7, count=8)
        clustered = generate("clustered", seed=7, count=8, cluster_size=4)

        self.assertEqual(len(star.edges), 7)
        self.assertTrue(all("agent_000" in edge for edge in star.edges))
        self.assertEqual(len(chain.edges), 7)
        self.assertEqual(chain.edges[0], ("agent_000", "agent_001"))
        self.assertEqual(chain.edges[-1], ("agent_006", "agent_007"))
        self.assertEqual(len(clustered.edges), 13)
        self.assertIn(("agent_003", "agent_004"), clustered.edges)
        self.assertNotIn(("agent_000", "agent_004"), clustered.edges)

    def test_seed_reproduces_timing_trace_and_other_seed_changes_it(self) -> None:
        first = generate("clustered", seed=41, count=12)
        replay = generate("clustered", seed=41, count=12)
        changed = generate("clustered", seed=42, count=12)

        self.assertEqual(first, replay)
        self.assertNotEqual(first.deliveries, changed.deliveries)

    def test_timing_bounds_and_all_agents_receive_one_rumor(self) -> None:
        graph = generate(
            "chain", seed=9, count=10, min_delay=2, max_delay=5, rumor_id="pressure-rumor"
        )
        times = dict(graph.adoption_times)

        self.assertEqual(set(times), set(graph.agents))
        self.assertEqual(times[graph.origin], 0)
        self.assertTrue(all(2 <= item.delay <= 5 for item in graph.deliveries))
        self.assertTrue(all(item.rumor_id == graph.rumor_id for item in graph.deliveries))
        self.assertEqual(sum(item.adopted for item in graph.deliveries), len(graph.agents) - 1)
        self.assertTrue(all(times[item.target] == item.arrives_at for item in graph.deliveries if item.adopted))

    def test_rejects_invalid_graph_and_timing_parameters(self) -> None:
        with self.assertRaises(ValueError):
            generate("chain", seed=1, count=1)
        with self.assertRaises(ValueError):
            generate("clustered", seed=1, count=8, cluster_size=1)
        with self.assertRaises(ValueError):
            generate("star", seed=1, min_delay=0)


if __name__ == "__main__":
    unittest.main()
