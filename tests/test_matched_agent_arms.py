from __future__ import annotations

import unittest

from benchmarks.matched_agent_arms import (
    ARMS, FAILURE_CLASSES, classify_failure, randomized_agent_ids,
    randomized_tool_catalog, run,
)


class MatchedAgentArms(unittest.TestCase):
    def test_all_arms_receive_same_tasks_context_budget_and_runtime_grants(self) -> None:
        rows = [run(701, 5, arm) for arm in ARMS]
        task_ids = [[task["task_id"] for task in row["task_manifest"]] for row in rows]
        self.assertTrue(all(ids == task_ids[0] for ids in task_ids[1:]))
        contexts = [{task["task_id"]: (task["context_hash"], task["context_budget_items"])
                     for task in row["task_manifest"]} for row in rows]
        self.assertTrue(all(context == contexts[0] for context in contexts[1:]))
        permissions = [{task["task_id"]: (task["permission_grant_count"],
                                           task["permission_grants_sha256"])
                        for task in row["task_manifest"]} for row in rows]
        self.assertTrue(all(permission == permissions[0] for permission in permissions[1:]))
        for row in rows:
            self.assertEqual(row["context_budget_max"], 1)
            self.assertEqual(row["runtime_permission_grants"], 5)
            self.assertTrue(all(task["initial_exposure_equal"] for task in row["task_manifest"]))
            self.assertTrue(all(task["permission_grant_count"] == 5 for task in row["task_manifest"]))
            self.assertTrue(all(len(task["permission_grants_sha256"]) == 64 for task in row["task_manifest"]))

    def test_governed_arm_blocks_stale_actions_and_oracle_is_exact(self) -> None:
        governed = run(701, 5, "memory_fabric")
        oracle = run(701, 5, "oracle")
        isolated = run(701, 5, "isolated")
        self.assertEqual(governed["counts"]["unsafe_actions"], 0)
        self.assertEqual(governed["counts"]["stale_actions"], 0)
        self.assertEqual(oracle["counts"]["accuracy"], 1.0)
        self.assertGreater(isolated["counts"]["stale_actions"], 0)

    def test_per_agent_fairness_and_tail_latency_are_recorded(self) -> None:
        row = run(701, 5, "memory_fabric")
        fairness = row["agent_fairness"]
        self.assertEqual(len(fairness["agents"]), 5)
        self.assertTrue(all(agent["attempted"] == 8 for agent in fairness["agents"]))
        self.assertTrue(all(agent["high_risk_attempted"] == 4 for agent in fairness["agents"]))
        self.assertGreaterEqual(fairness["p95_decision_latency_ms"], 0)
        self.assertGreaterEqual(fairness["max_decision_latency_ms"], fairness["p95_decision_latency_ms"])

    def test_identity_and_tool_order_permutations_preserve_authorization_outcomes(self) -> None:
        row = run(701, 5, "memory_fabric")
        control = run(701, 5, "memory_fabric", randomize_order=False)
        repeat = run(701, 5, "memory_fabric")
        alternate = run(709, 5, "memory_fabric")
        self.assertEqual(row["counts"], repeat["counts"])
        self.assertEqual(row["counts"], control["counts"])
        self.assertEqual(row["counts"], alternate["counts"])
        self.assertEqual(row["tool_registry_order"], randomized_tool_catalog(701))
        self.assertEqual(set(row["tool_registry_order"]), {"publish", "archive", "notify"})
        self.assertIn("publish", row["tool_registry_order"])
        self.assertEqual(row["agent_identity_scheme"], "seeded_opaque_ids_v1")
        self.assertEqual(len(randomized_agent_ids(701, 5)), 5)
        self.assertNotEqual(randomized_agent_ids(701, 5), randomized_agent_ids(709, 5))
        self.assertNotEqual(row["agent_identity_order_sha256"],
                            alternate["agent_identity_order_sha256"])
        self.assertEqual(control["agent_identity_scheme"], "ordinal_control")
        self.assertEqual(control["tool_registry_order"], ["publish", "archive", "notify"])

    def test_every_decision_failure_has_a_class_and_source_trace(self) -> None:
        self.assertIn("retrieval", classify_failure("pooled_shared", "supported", False, True, "miss"))
        self.assertIn("insufficient_evidence", classify_failure("isolated", "missing", True, False, "cached"))
        for arm in ARMS:
            row = run(701, 5, arm)
            for task in row["task_manifest"]:
                counts = task["decision_counts"]
                failure_count = counts["false_abstentions"] + counts["unsafe_actions"]
                trace = task["failure_trace"]
                if failure_count:
                    self.assertIsNotNone(trace)
                    self.assertEqual(trace["task_id"], task["task_id"])
                    self.assertGreater(trace["affected_agent_count"], 0)
                    self.assertTrue(set(trace["failure_classes"]) <= set(FAILURE_CLASSES))
                else:
                    self.assertIsNone(trace)


if __name__ == "__main__":
    unittest.main()
