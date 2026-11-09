from __future__ import annotations

import unittest

from benchmarks.agent_scale import run, task_manifest


class AgentScale(unittest.TestCase):
    def test_agent_counts_share_identical_task_ids_and_family_composition(self) -> None:
        five = run(701, 5)
        ten = run(701, 10)
        expected_ids = [task["task_id"] for task in task_manifest(701)]
        self.assertEqual([task["task_id"] for task in five["task_manifest"]], expected_ids)
        self.assertEqual([task["task_id"] for task in ten["task_manifest"]], expected_ids)
        self.assertEqual(five["counts"]["attempted"], 40)
        self.assertEqual(ten["counts"]["attempted"], 80)
        self.assertEqual(five["counts"]["unsafe_actions"], 0)
        self.assertEqual(ten["counts"]["unsafe_actions"], 0)
        self.assertLessEqual(five["counts"]["correct"], five["counts"]["attempted"])
        self.assertLessEqual(ten["counts"]["correct"], ten["counts"]["attempted"])
        self.assertGreaterEqual(five["counts"]["false_abstentions"], 0)
        self.assertGreaterEqual(ten["counts"]["false_abstentions"], 0)


if __name__ == "__main__":
    unittest.main()
