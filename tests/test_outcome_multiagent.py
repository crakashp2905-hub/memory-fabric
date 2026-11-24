"""Delegation, coordination overhead and cluster-level scale reporting (W10-06, W10-07, W10-10)."""

from __future__ import annotations

import unittest

from memory_fabric.outcome_typed.delegation import DelegationRefused, delegate
from memory_fabric.outcome_typed.episode import default_tools


class Delegation(unittest.TestCase):
    def test_a_role_delegates_only_what_it_may_call(self) -> None:
        receipt = delegate(default_tools(), "task-1", "planner", "observer", ["recall"], 5)
        self.assertEqual(receipt.tools, ("recall",))
        self.assertTrue(receipt.verify())
        with self.assertRaises(DelegationRefused):
            delegate(default_tools(), "task-1", "observer", "planner", ["recall"], 5)

    def test_protected_effects_cannot_be_delegated(self) -> None:
        for tool, role in (("set_target", "planner"), ("execute_proposal", "executor")):
            with self.subTest(tool=tool), self.assertRaises(DelegationRefused):
                delegate(default_tools(), "task-1", role, "observer", [tool], 5)

    def test_a_receipt_carries_no_credential_grant_or_certificate_and_cannot_be_edited(self) -> None:
        receipt = delegate(default_tools(), "task-1", "planner", "observer", ["recall"], 5)
        body = receipt.to_dict()
        for field in ("credential", "grant", "certificate", "token", "secret"):
            self.assertNotIn(field, body)
        from dataclasses import replace

        self.assertFalse(replace(receipt, tools=("recall", "set_target")).verify())


class CoordinationOverhead(unittest.TestCase):
    def test_overhead_is_reported_apart_from_outcomes_under_one_policy(self) -> None:
        from benchmarks.outcome_arms import POLICY_ID, run

        report = run(seeds=1)
        coordination = report["coordination"]
        self.assertEqual(coordination["policy"], POLICY_ID)
        self.assertEqual(set(coordination["by_arm"]), {f"A{i}" for i in range(7)})
        self.assertEqual(report["parity"]["problems"], [])
        a5, a6 = coordination["by_arm"]["A5"], coordination["by_arm"]["A6"]
        self.assertEqual(a5, a6)  # advisory replay adds no coordination inside the episode
        self.assertGreater(coordination["by_arm"]["A3"]["recoveries_mean"], 0)


class ScaleClusters(unittest.TestCase):
    def test_more_agents_add_attempts_not_independent_units(self) -> None:
        from benchmarks.outcome_agent_scale_clusters import COUNTS, build

        report = build()
        self.assertEqual(report["agent_counts"], [3, 5, 10, 25, 50])
        summary = report["summary"]
        tasks = {row["unique_tasks"] for row in summary.values()}
        clusters = {row["clusters"] for row in summary.values()}
        self.assertEqual(len(tasks), 1)
        self.assertEqual(len(clusters), 1)
        for count in COUNTS:
            row = summary[str(count)]
            self.assertEqual(row["attempts_per_unique_task"], float(count))
        self.assertEqual(report["status"], "EXPLORATORY")

    def test_the_registered_run_keeps_its_counts(self) -> None:
        from benchmarks.agent_scale import AGENT_COUNTS, run

        self.assertEqual(AGENT_COUNTS, (5, 10, 25, 50, 100))
        with self.assertRaises(ValueError):
            run(701, 3)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
