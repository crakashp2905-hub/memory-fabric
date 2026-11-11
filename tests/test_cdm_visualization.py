"""Timeline view-model and local viewer safety checks."""

from __future__ import annotations

import unittest

from memory_fabric.causal_replay.bayes import BinaryNode
from memory_fabric.causal_replay.state import Observation, update
from memory_fabric.causal_replay.visualization import timeline
from memory_fabric.causal_replay.viewer import render


class TestVisualization(unittest.TestCase):
    def test_timeline_marks_belief_policy_and_divergence(self):
        nodes = (BinaryNode("fault", (), {(): 0.2}),)
        first = update(nodes, (), policy_id="p1")
        second = update(nodes, (Observation("e1", "fault", True, "sensor", 2),), policy_id="p2")
        model = timeline((first, second), ("monitor", "investigate"), intervention_sequence=2)
        self.assertEqual(model["first_divergence"], 1)
        self.assertEqual(model["steps"][1]["policy"], "p2")
        self.assertTrue(model["steps"][1]["intervened"])

    def test_viewer_embeds_data_without_remote_assets_or_html_injection(self):
        document = {"steps": [{"step": 0, "sequence": 1, "policy": "</script><x>",
            "proposal": "monitor", "fingerprint": "a", "belief": {}, "evidence": []}]}
        page = render(document)
        self.assertNotIn("</script><x>", page)
        self.assertNotIn("https://", page)
        self.assertIn("application/json", page)
        self.assertIn("How to use Memory Fabric", page)
        self.assertIn("Traceable evidence", page)
        self.assertIn("Proposal only · no action executed", page)


if __name__ == "__main__":
    unittest.main()
