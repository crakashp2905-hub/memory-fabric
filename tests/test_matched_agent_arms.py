from __future__ import annotations

import unittest

from benchmarks.matched_agent_arms import ARMS, run


class MatchedAgentArms(unittest.TestCase):
    def test_all_arms_receive_same_tasks_context_budget_and_runtime_grants(self) -> None:
        rows = [run(701, 5, arm) for arm in ARMS]
        task_ids = [[task["task_id"] for task in row["task_manifest"]] for row in rows]
        self.assertTrue(all(ids == task_ids[0] for ids in task_ids[1:]))
        contexts = [{task["task_id"]: (task["context_hash"], task["context_budget_items"])
                     for task in row["task_manifest"]} for row in rows]
        self.assertTrue(all(context == contexts[0] for context in contexts[1:]))
        for row in rows:
            self.assertEqual(row["context_budget_max"], 1)
            self.assertEqual(row["runtime_permission_grants"], 5)
            self.assertTrue(all(task["initial_exposure_equal"] for task in row["task_manifest"]))

    def test_governed_arm_blocks_stale_actions_and_oracle_is_exact(self) -> None:
        governed = run(701, 5, "memory_fabric")
        oracle = run(701, 5, "oracle")
        isolated = run(701, 5, "isolated")
        self.assertEqual(governed["counts"]["unsafe_actions"], 0)
        self.assertEqual(governed["counts"]["stale_actions"], 0)
        self.assertEqual(oracle["counts"]["accuracy"], 1.0)
        self.assertGreater(isolated["counts"]["stale_actions"], 0)


if __name__ == "__main__":
    unittest.main()
