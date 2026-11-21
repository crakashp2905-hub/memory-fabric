"""Performance measurements, retrieval reuse and overload behaviour (W18)."""

from __future__ import annotations

import unittest

from benchmarks import outcome_performance as perf


class LatencyBreakdown(unittest.TestCase):
    def test_stages_never_sum_past_the_total_and_model_time_is_not_invented(self) -> None:
        report = perf.latency_breakdown()
        attributed = sum(report["stages_wall_s"].values())
        self.assertLessEqual(attributed, report["total_wall_s"] + 1e-3)
        self.assertGreaterEqual(report["unattributed_wall_s"], -1e-3)
        self.assertIn("NOT_MEASURED", report["model_inference_s"])
        self.assertIn("verify", report["stages_wall_s"])
        self.assertIn("total_cpu_s", report)


class Measurements(unittest.TestCase):
    def test_worker_contention_reports_every_count_with_its_components(self) -> None:
        report = perf.worker_contention(workers=(1, 2), episodes=2, trials=1)
        for row in report["by_workers"].values():
            for key in ("process_start_s_median", "queue_wait_s_p50", "service_s_p50",
                        "speedup_vs_first"):
                self.assertIn(key, row)
        self.assertIn("not claimed to help", report["claim"])

    def test_dependence_first_review_costs_fewer_replays_than_always_on(self) -> None:
        report = perf.cdm_cost(seeds=1)
        self.assertLess(report["dependence_first"]["replays"], report["always_on"]["replays"])
        self.assertGreater(report["wasted_replays_always_on"], 0)

    def test_replay_profile_states_what_it_measured(self) -> None:
        report = perf.replay_profile((2_000,))
        self.assertEqual(set(report["by_size"]), {"2000"})
        self.assertGreater(report["by_size"]["2000"]["peak_python_bytes"], 0)

    def test_agent_stress_reports_tails_starvation_and_fairness(self) -> None:
        report = perf.agent_stress(agent_counts=(1, 5), ops=50)
        for row in report["by_agents"].values():
            self.assertTrue(row["completed_all_scheduled"])
            self.assertEqual(row["starved_agents"], 0)
            self.assertIsNotNone(row["p99_s"])

    def test_batched_verification_never_coalesces_principals(self) -> None:
        report = perf.batched_verification(principals=3, per_principal=2)
        self.assertTrue(report["same_results"])
        self.assertTrue(report["coalescing_two_principals_refused"])


class RetrievalReuse(unittest.TestCase):
    def setUp(self) -> None:
        from memory_fabric import MemoryFabric
        from memory_fabric.outcome_typed.retrieval_cache import RetrievalCache

        self.f = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(self.f.close)
        self.m = self.f.remember("ana", "pump P-4 relief limit is 6 bar", scope="team")
        self.cache = RetrievalCache(self.f, "policy-1")

    def ask(self, **kwargs):
        return self.cache.retrieve("ops", "pump P-4 relief limit", **kwargs)

    def test_an_unchanged_store_reuses_the_answer(self) -> None:
        first, second = self.ask(), self.ask()
        self.assertEqual(first, second)
        self.assertEqual((self.cache.hits, self.cache.misses), (1, 1))

    def test_revision_retraction_and_tenant_change_invalidate(self) -> None:
        self.ask()
        self.f.revise(self.m, "pump P-4 relief limit is 7 bar", "ana", "vendor update")
        self.assertEqual(self.ask()[0][1], 2)
        self.f.quarantine(self.m, reason="wrong", actor="op")
        self.assertEqual(self.ask(), ())
        self.ask(tenant_id="tn_other")
        self.assertEqual(self.cache.hits, 0)

    def test_policy_is_part_of_the_key_and_entries_hold_no_content(self) -> None:
        from memory_fabric.outcome_typed.retrieval_cache import RetrievalCache

        self.ask()
        other = RetrievalCache(self.f, "policy-2")
        other.retrieve("ops", "pump P-4 relief limit")
        self.assertEqual(other.hits, 0)
        for value in self.cache._entries.values():
            for memory_id, version in value:
                self.assertNotIn("bar", memory_id)


class Overload(unittest.TestCase):
    def test_a_full_spool_abstains_and_the_gate_stays_correct(self) -> None:
        from memory_fabric import MemoryFabric
        from memory_fabric.actions_typed import EXECUTED, REFUSED, ActionGate, ActionPolicy, ToolRule
        from memory_fabric.outcome_typed.spool import JobSpool, SpoolFull

        spool = JobSpool(max_depth=2)
        self.addCleanup(spool.close)
        spool.enqueue("a", {})
        spool.enqueue("b", {})
        with self.assertRaises(SpoolFull):
            spool.enqueue("c", {"replay": "secret payload"})
        self.assertEqual(spool.depth(), 2)
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        memory = fabric.remember("ana", "valve 7 safe below 4 bar", scope="team")
        gate = ActionGate(fabric, ActionPolicy(tools={"open_valve": ToolRule("open_valve")},
                                               grants={"ops": frozenset({"open_valve"})}))
        self.assertEqual(gate.execute("open_valve", "ops", lambda k: "ok",
                                      fabric.certify("c", [memory], "ops"), key="k1").outcome, EXECUTED)
        fabric.quarantine(memory, reason="wrong", actor="op")
        self.assertEqual(gate.execute("open_valve", "ops", lambda k: "ok",
                                      fabric.certify("c", [memory], "ops"), key="k2").outcome, REFUSED)


class Envelope(unittest.TestCase):
    def test_the_envelope_names_its_commands_host_and_never_infers_model_capacity(self) -> None:
        from pathlib import Path

        text = (Path(__file__).resolve().parents[1] / "docs" / "AGENT_OPERATING_ENVELOPE.md").read_text()
        self.assertIn("python -m benchmarks.outcome_performance", text)
        self.assertIn("NOT_MEASURED", text)
        self.assertIn("16 GB laptop", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
