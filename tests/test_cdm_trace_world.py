"""Generated multi-agent traces preserve roots and decision-time visibility."""

from __future__ import annotations

import unittest

from benchmarks.cdm_trace_world import (delayed_retraction_world,
    independent_source_root, negative_control_world, shared_source_world,
    temporal_conflict_world)


class TestTraceWorld(unittest.TestCase):
    def test_shared_copies_keep_one_independent_root_at_scale(self):
        for count in (2, 3, 10, 50):
            world = shared_source_world(agent_count=count, seed=81)
            roots = {independent_source_root(world, source_id)
                     for source_id in world["source_roots"]}
            self.assertEqual(len(roots), 1)
            self.assertEqual(world["remote_calls"], 0)

    def test_future_conflict_is_not_visible_to_earlier_decision(self):
        world = temporal_conflict_world(seed=2)
        by_id = {event.event_id: event for event in world["events"]}
        self.assertEqual(by_id["decision-1"].visible_sources, ("sensor-a",))
        self.assertNotIn("sensor-b", by_id["decision-1"].visible_sources)
        self.assertIn("sensor-b", by_id["decision-2"].visible_sources)

    def test_delayed_retraction_waits_for_peer_sync(self):
        world = delayed_retraction_world(agent_count=3, seed=5)
        rows = {event.event_id: event for event in world["events"]}
        self.assertLess(rows["retraction"].sequence, rows["peer-sync"].sequence)
        earlier = [event for event in world["events"]
                   if event.agent_id == "agent-00" and event.kind == "decision"]
        self.assertTrue(earlier)
        self.assertIn("source-5-root", earlier[0].visible_sources)

    def test_negative_control_families_are_explicit(self):
        world = negative_control_world(seed=4)
        kinds = {event.kind for event in world["events"]}
        self.assertTrue({"irrelevant", "duplicate", "copy", "delayed", "policy_swap"} <= kinds)
        self.assertEqual(independent_source_root(world, "a-copy-2"), "root-a")
        self.assertNotEqual(independent_source_root(world, "weather"), "root-a")


if __name__ == "__main__":
    unittest.main()
