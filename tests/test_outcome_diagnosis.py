"""Evidence diagnosis before refusal (W06-01, W06-02, W06-03, W06-07, W06-09, W06-10)."""

from __future__ import annotations

import unittest
from unittest import mock

from memory_fabric.outcome_typed.diagnosis import (
    AXIS, CODE_MAP, NOT_A_REFUSAL, Diagnosis, Rung, availability, classify, search_ladder,
)
from memory_fabric.reasons import REASONS


class Taxonomy(unittest.TestCase):
    def test_every_refusal_code_has_exactly_one_diagnosis(self) -> None:
        unmapped = [code for code in REASONS if code not in CODE_MAP and code not in NOT_A_REFUSAL]
        self.assertEqual(unmapped, [])
        with self.assertRaises(ValueError):
            classify(["a_code_nobody_declared"])

    def test_the_nine_cases_are_distinct_and_relevance_is_not_authority(self) -> None:
        cases = {d for d in Diagnosis if d is not Diagnosis.ANSWERABLE}
        self.assertEqual(len(cases), 9)
        relevance = {d for d in cases if AXIS[d] == "relevance"}
        authority = {d for d in cases if AXIS[d] == "authority"}
        self.assertEqual(relevance, {Diagnosis.RETRIEVAL_MISS, Diagnosis.NO_EVIDENCE})
        self.assertEqual(authority, {Diagnosis.UNTRUSTED, Diagnosis.NO_PERMISSION})
        self.assertFalse(relevance & authority)

    def test_authority_is_reported_before_validity_before_relevance(self) -> None:
        self.assertEqual(classify(["evidence_withdrawn", "wrong_tenant"]), Diagnosis.NO_PERMISSION)
        self.assertEqual(classify(["no_supporting_evidence", "evidence_version_moved"]),
                         Diagnosis.SUPERSEDED)
        self.assertEqual(classify(["ok"]), Diagnosis.ANSWERABLE)


class Availability(unittest.TestCase):
    def test_the_four_facts_stay_separate_for_the_evaluator(self) -> None:
        record = availability(exists=True, retrieved=False, authorized=True, answers=True)
        view = record.to_evaluator()
        self.assertEqual((view["exists"], view["retrieved"], view["authorized"], view["answers"]),
                         (True, False, True, True))
        self.assertEqual(record.diagnosis, Diagnosis.RETRIEVAL_MISS)

    def test_a_private_source_is_indistinguishable_from_absence_to_the_actor(self) -> None:
        private = availability(exists=True, retrieved=False, authorized=False, answers=False)
        absent = availability(exists=False, retrieved=False, authorized=False, answers=False)
        self.assertEqual(private.diagnosis, Diagnosis.NO_PERMISSION)
        self.assertEqual(private.to_actor(), absent.to_actor())
        self.assertEqual(private.to_actor()["diagnosis"], "not_available")

    def test_availability_is_advisory_and_the_gate_refuses_it_as_a_certificate(self) -> None:
        from memory_fabric import MemoryFabric
        from memory_fabric.actions_typed import REFUSED, ActionGate, ActionPolicy, ToolRule

        record = availability(exists=True, retrieved=True, authorized=True, answers=True,
                              reason_codes=["ok"], evidence=[("m1", 1)])
        self.assertFalse(record.authorizes_effects)
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        gate = ActionGate(fabric, ActionPolicy(tools={"open_valve": ToolRule("open_valve")},
                                               grants={"ops": frozenset({"open_valve"})}))
        ran: list[str] = []
        result = gate.execute("open_valve", "ops", ran.append, record, key="k")  # type: ignore[arg-type]
        self.assertEqual(result.outcome, REFUSED)
        self.assertEqual(ran, [])


class Ladder(unittest.TestCase):
    def test_rungs_run_in_order_until_one_answers_and_costs_are_recorded(self) -> None:
        calls: list[str] = []

        def rung(name: str, hits: list[str]):
            return Rung(name, lambda q: calls.append(name) or hits)

        result = search_ladder("q", [rung("exact", []), rung("lexical", ["x"]), rung("hybrid", ["y"])],
                               budget=5)
        self.assertEqual((result.rung, result.results, calls), ("lexical", ("x",), ["exact", "lexical"]))
        self.assertEqual([c["rung"] for c in result.costs], ["exact", "lexical"])
        self.assertEqual(result.spent, 2)

    def test_unqualified_hybrid_is_skipped_budget_is_respected_and_empty_abstains(self) -> None:
        empty = Rung("exact", lambda q: [])
        hybrid = Rung("hybrid", lambda q: ["never"], qualified=False)
        result = search_ladder("q", [empty, Rung("lexical", lambda q: [], cost=5), hybrid], budget=2)
        self.assertTrue(result.abstained)
        self.assertEqual([c.get("skipped") for c in result.costs], [None, "budget", "not_qualified"])

    def test_order_is_fixed(self) -> None:
        with self.assertRaises(ValueError):
            search_ladder("q", [Rung("hybrid", lambda q: []), Rung("exact", lambda q: [])], budget=3)


class OracleBenchmark(unittest.TestCase):
    def test_no_false_allow_and_the_known_false_denial_is_reported(self) -> None:
        from benchmarks.outcome_diagnosis import run

        report = run(seeds=1)
        self.assertEqual(report["false_allow"], 0)
        self.assertEqual(report["release"], "ALLOWED")
        self.assertEqual(report["false_deny_labels"], ["retrieval_miss"])
        self.assertEqual(set(report["confusion_by_family"]), {"relevance", "validity", "authority"})

    def test_a_diagnoser_that_allows_withdrawn_evidence_blocks_release(self) -> None:
        import benchmarks.outcome_diagnosis as bench

        real = bench.availability

        def lenient(**kwargs):
            kwargs["reason_codes"] = ["ok"]
            return real(**kwargs)

        with mock.patch.object(bench, "availability", lenient):
            report = bench.run(seeds=1)
        self.assertGreater(report["false_allow"], 0)
        self.assertEqual(report["release"], "BLOCKED")
        self.assertEqual(bench.run(seeds=1, baseline={"false_allow": 0})["release"], "ALLOWED")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
