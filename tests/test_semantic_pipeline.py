"""Contract tests for the semantic CDM pipeline (VEGA S02-S08, S10, S15).

The advisor here is :class:`ScriptedAdvisor`, a fixed rule set labelled SCRIPTED:
these tests show what the host code permits and refuses, not what a model knows.
Expected labels come from the fixtures, never from an advisor.
"""

from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.causal_replay.bayes import BinaryNode
from memory_fabric.causal_replay.intervention import ReplacementFixture
from memory_fabric.causal_replay.policy import ThresholdPolicy
from memory_fabric.causal_replay.replay import DeterministicSimulator
from memory_fabric.causal_replay.semantic import (beliefs, cache, calibration, effects, graph,
                                                 interventions, packets, scheduler, support, taxonomy)
from memory_fabric.causal_replay.semantic.advice import Answer, Question
from memory_fabric.causal_replay.semantic.scripted import ScriptedAdvisor
from memory_fabric.causal_replay.state import Observation
from memory_fabric.causal_replay.types import CDMError

T = "tn_plant"


def battery_store() -> tuple[MemoryFabric, dict[str, str]]:
    """10:00 probe A hot, 10:15 probe B normal on the same pack, 10:30 calibration note.

    Sensor bias and real overheating are both possible: nothing here makes them exclusive.
    """
    fabric = MemoryFabric(":memory:", auto_activate=True)
    ids = {
        "a": fabric.remember("ops", "10:00 pack P-7 probe A reads 61 C", scope="team", tenant_id=T,
                             valid_from=1000, source_episodes=("ep-a",)),
        "b": fabric.remember("tech", "10:15 pack P-7 probe B reads 38 C", scope="team", tenant_id=T,
                             valid_from=1015, source_episodes=("ep-b",)),
        "c": fabric.remember("lab", "10:30 probe A on pack P-7 was last calibrated 2 years ago, drift possible",
                             scope="team", tenant_id=T, valid_from=1030, source_episodes=("ep-c",)),
    }
    return fabric, ids


class Taxonomy(unittest.TestCase):
    def test_a_model_output_cannot_claim_more_than_a_hypothesis(self):
        self.assertEqual(taxonomy.model_tier("HYPOTHETICAL_EFFECT"), "HYPOTHETICAL_EFFECT")
        for tier in ("VALIDATED_COUNTERFACTUAL", "REAL_WORLD_CAUSAL"):
            with self.assertRaises(taxonomy.TaxonomyError):
                taxonomy.model_tier(tier)

    def test_reports_that_overstate_their_level_fail_validation(self):
        self.assertTrue(taxonomy.check_report_level({"evidence_level": "SCRIPTED",
                                                     "verdict": "EFFECT_SUPPORTED"}))
        self.assertTrue(taxonomy.check_report_level({"evidence_level": "VEGA_MODEL_SMOKE"}))
        self.assertTrue(taxonomy.check_report_level({"evidence_level": "CONFIRMATORY", "model_digest": "x",
                                                     "real_inference": True}))
        self.assertEqual(taxonomy.check_report_level({"evidence_level": "SCRIPTED", "verdict": "HOLD"}), [])


class Packets(unittest.TestCase):
    def setUp(self):
        self.fabric, self.ids = battery_store()

    def tearDown(self):
        self.fabric.close()

    def test_packets_come_from_authorized_retrieval_with_full_provenance(self):
        bundle = packets.from_retrieval(self.fabric, "ops", "pack P-7 probe reads", tenant_id=T)
        self.assertEqual(bundle.status, "COMPLETE")
        self.assertEqual(len(bundle.packets), 3)
        for p in bundle.packets:
            self.assertEqual(p.tenant_id, T)
            self.assertEqual(p.content_hash, packets.sha256_text(self.fabric.get(p.evidence_id).content))
            self.assertIn("/", p.origin_root)
        foreign = packets.from_retrieval(self.fabric, "ops", "pack P-7 probe reads", tenant_id="tn_other")
        self.assertEqual(foreign.status, "EMPTY")

    def test_chronology_is_preserved_and_both_diagnoses_stay_open(self):
        bundle = packets.from_retrieval(self.fabric, "ops", "pack P-7 probe", tenant_id=T)
        self.assertEqual([p.valid_at for p in bundle.packets], [1000, 1015, 1030])
        advisor = ScriptedAdvisor()
        result = support.assess_hypotheses(bundle, ["pack P-7 is overheating",
                                                    "probe A on pack P-7 has drifted"], advisor)
        self.assertEqual(set(result), {"pack P-7 is overheating", "probe A on pack P-7 has drifted"})

    def test_erased_and_foreign_evidence_drop_out_on_recheck(self):
        bundle = packets.from_retrieval(self.fabric, "ops", "pack P-7 probe reads", tenant_id=T)
        self.fabric.erase_content(self.ids["b"], "ops", "privacy request")
        again = packets.recheck(self.fabric, bundle, agent_id="ops", tenant_id=T)
        self.assertNotIn(self.ids["b"], {p.evidence_id for p in again.packets})
        self.assertEqual(packets.recheck(self.fabric, bundle, agent_id="ops", tenant_id="tn_other").packets, ())

    def test_copies_of_one_origin_share_a_correlation_group(self):
        copy = self.fabric.derive("ops", "pack P-7 probe A reads 61 C (copied)", [self.ids["a"]])
        bundle = packets.from_retrieval(self.fabric, "ops", "pack P-7 probe A reads 61 C", tenant_id=T)
        refs = {p.evidence_id: p.origin_root for p in bundle.packets}
        if copy in refs:
            self.assertEqual(refs[copy], refs[self.ids["a"]])
        self.assertLessEqual(bundle.independent_root_count(), 3)

    def test_source_kinds_roundtrip_and_sealed_fields_are_refused(self):
        bundle = packets.from_retrieval(self.fabric, "ops", "pack P-7", tenant_id=T)
        for p in bundle.packets:
            self.assertEqual(packets.SemanticEvidencePacket.from_dict(p.to_dict()), p)
        data = bundle.packets[0].to_dict() | {"oracle_value": 61}
        with self.assertRaises(packets.PacketError):
            packets.SemanticEvidencePacket.from_dict(data)
        bad = bundle.packets[0].to_dict() | {"visible_text": "tampered"}
        with self.assertRaises(packets.PacketError):
            packets.SemanticEvidencePacket.from_dict(bad)

    def test_canonical_json_is_stable_and_refuses_non_finite_numbers(self):
        a = packets.from_retrieval(self.fabric, "ops", "pack P-7", tenant_id=T)
        b = packets.from_retrieval(self.fabric, "ops", "pack P-7", tenant_id=T)
        self.assertEqual(a.digest, b.digest)
        with self.assertRaises(packets.PacketError):
            packets.canonical_json({"x": float("nan")})

    def test_over_budget_bundles_say_they_are_truncated(self):
        bundle = packets.from_retrieval(self.fabric, "ops", "pack P-7", tenant_id=T,
                                        limits=packets.PacketLimits(max_packets=2))
        self.assertEqual(bundle.status, "TRUNCATED_NOT_VALIDATED")
        self.assertIn("were not shown", bundle.state_text())

    def test_secrets_are_scrubbed_before_any_state_text(self):
        key = "AKIA" + "QWERTYUIOPASDFGH"
        text, count = packets.scrub_secrets(f"probe log uploaded with key {key}")
        self.assertGreaterEqual(count, 1)
        self.assertNotIn(key, text)


class Support(unittest.TestCase):
    def test_exact_guards_keep_identifiers_and_quantities_apart(self):
        self.assertEqual(support.exact_guard("unit-7 reads 61 C", "unit-17 reads 61 C"), "incomparable")
        self.assertEqual(support.exact_guard("pack P-7 reads 61 C", "pack P-7 reads 16 C"), "not_supported")
        self.assertIsNone(support.exact_guard("pack P-7 reads 61 C", "the P-7 pack shows 61 C on probe A"))
        self.assertEqual(support.exact_guard("pack P-7 is not at 61 C", "pack P-7 is at 61 C"),
                         "not_supported")

    def _bundle(self, *texts, root=None):
        ps = [packets.SemanticEvidencePacket(T, "ops", f"m{i}", 1, packets.sha256_text(t),
                                             root or f"s/m{i}", 1000 + i, 1000 + i, "active",
                                             "observation", t) for i, t in enumerate(texts)]
        return packets.bundle(ps)

    def test_a_model_supported_label_cannot_survive_a_quantity_mismatch(self):
        advisor = ScriptedAdvisor({"claim_support": {"choice": "supported", "probs": {
            "supported": 0.9, "contradicted": 0.04, "unknown": 0.03, "incomparable": 0.03},
            "prediction_set": ["supported"], "abstain": False}})
        out = support.assess(self._bundle("pack P-7 reads 16 C"), "pack P-7 reads 61 C", advisor)
        self.assertEqual(out[0].label, "unknown")
        self.assertEqual(out[0].route, "retrieve_more")

    def test_ambiguous_abstained_or_unavailable_answers_force_no_winner(self):
        probs = {"supported": 0.45, "contradicted": 0.45, "unknown": 0.05, "incomparable": 0.05}
        for raw in ({"choice": "supported", "probs": probs, "prediction_set": ["supported", "contradicted"],
                     "abstain": False},
                    {"choice": "supported", "probs": probs, "prediction_set": ["supported"], "abstain": True},
                    {"choice": "supported", "probs": probs, "prediction_set": ["supported"], "abstain": False,
                     "unbound": True},
                    {"garbage": 1}):
            with self.subTest(raw=raw):
                out = support.assess(self._bundle("pack P-7 reads 61 C"), "pack P-7 reads 61 C",
                                     ScriptedAdvisor({"claim_support": raw}))
                self.assertEqual((out[0].label, out[0].route), ("unknown", "retrieve_more"))

    def test_paraphrased_copies_of_one_root_count_once(self):
        b = self._bundle("pack P-7 reads 61 C", "the P-7 pack is at 61 C", "61 C measured on pack P-7",
                         root="s/origin")
        yes = {"choice": "supported", "probs": {"supported": 0.9, "contradicted": 0.04, "unknown": 0.03,
                                                "incomparable": 0.03},
               "prediction_set": ["supported"], "abstain": False}
        out = support.assess(b, "pack P-7 reads 61 C", ScriptedAdvisor({"claim_support": yes}))
        self.assertEqual([p.label for p in out], ["supported"] * 3)
        self.assertEqual(support.corroboration(out), {"supported": 1})

    def test_the_lexical_prefilter_skips_the_advisor_for_unrelated_evidence(self):
        advisor = ScriptedAdvisor()
        out = support.assess(self._bundle("cafeteria menu for Tuesday"), "the pack is overheating", advisor)
        self.assertEqual(advisor.calls, 0)
        self.assertEqual(out[0].source, "lexical_prefilter")

    def test_the_structural_backstop_drops_unreadable_evidence(self):
        out = support.assess(self._bundle("pack P-7 reads 61 C"), "pack P-7 reads 61 C", ScriptedAdvisor())
        self.assertEqual(support.backstop(out, set()), [])

    def test_edge_cases_are_labelled_by_the_fixture_oracle(self):
        oracle = {("unit-7 failed", "unit-17 failed"): "incomparable",
                  ("valve V-2 open at 40 %", "valve V-2 open at 4 %"): "not_supported",
                  ("pump-3 is not running", "pump-3 is running"): None}
        for (claim, ev), expected in oracle.items():
            got = support.exact_guard(claim, ev)
            if expected is None:
                self.assertIn(got, (None, "not_supported"))
            else:
                self.assertEqual(got, expected)


class Graph(unittest.TestCase):
    def setUp(self):
        self.g = graph.CandidateGraph(T)
        for nid, kind, t in (("obs-a", "observation", 1000), ("obs-b", "observation", 1015),
                             ("dec", "decision", 1020), ("late", "observation", 1100)):
            self.g.add_node(graph.Node(nid, kind, T, nid, 1, t))

    def test_a_model_cannot_add_dependence_or_a_verified_effect(self):
        for kind in ("RELIED_ON", "VERIFIED_COUNTERFACTUAL_EFFECT"):
            with self.subTest(kind=kind), self.assertRaises(graph.GraphError):
                self.g.propose("obs-a", "dec", kind, ["m1@1"], "r" * 64)
        edge = self.g.propose("obs-a", "dec", "HYPOTHESIZED_CAUSE", ["m1@1"], "r" * 64)
        self.assertEqual(edge.tier, "HYPOTHETICAL_EFFECT")
        with self.assertRaises(graph.GraphError):
            self.g.add_verified_effect("obs-a", "dec", ["m1@1"], {"accepted": False})

    def test_edges_cite_versions_causal_edges_stay_acyclic_and_post_hoc_evidence_is_refused(self):
        with self.assertRaises(graph.GraphError):
            self.g.propose("obs-a", "dec", "SUPPORTS", ["m1"], "r" * 64)
        self.g.propose("obs-a", "obs-b", "HYPOTHESIZED_CAUSE", ["m1@1"], "r" * 64)
        with self.assertRaises(graph.GraphError):
            self.g.propose("obs-b", "obs-a", "HYPOTHESIZED_CAUSE", ["m2@1"], "r" * 64)
        self.g.propose("obs-b", "obs-a", "SUPPORTS", ["m2@1"], "r" * 64)  # associations may cycle
        with self.assertRaises(graph.GraphError):
            self.g.propose("late", "dec", "HYPOTHESIZED_CAUSE", ["m9@1"], "r" * 64)

    def test_latent_confounding_makes_the_effect_unidentifiable(self):
        self.g.propose("obs-a", "dec", "HYPOTHESIZED_CAUSE", ["m1@1"], "r" * 64)
        self.assertEqual(self.g.identifiability("obs-a", "dec"), "NOT_ESTABLISHED")
        self.g.declare_latent("obs-a", "dec", "ambient_heat")
        self.assertEqual(self.g.identifiability("obs-a", "dec"), "CAUSAL_UNIDENTIFIABLE")

    def test_revisions_and_erasure_invalidate_and_views_leak_nothing(self):
        self.g.add_dependence("obs-a", "dec", "RELIED_ON", ["m1@1"], "d" * 64)
        self.g.propose("obs-b", "dec", "SUPPORTS", ["m2@1"], "r" * 64)
        self.assertEqual(self.g.invalidate("m1", 2), 1)
        self.assertEqual(len(self.g.view({"m2@1"}, T)["edges"]), 1)
        self.assertEqual(self.g.view({"m2@1"}, "tn_other"), {"edges": [], "nodes": 0})
        self.assertEqual(self.g.view(set(), T), {"edges": [], "nodes": 0})


NODES = (BinaryNode("hot", (), {(): 0.2}),
         BinaryNode("reading_high", ("hot",), {(False,): 0.1, (True,): 0.9}))


def high(packet):
    return [("reading_high", "61 C" in packet.visible_text)] if "C" in packet.visible_text else []


class Beliefs(unittest.TestCase):
    def _bundle(self, rows):
        return packets.bundle([packets.SemanticEvidencePacket(T, "ops", eid, 1, packets.sha256_text(t), root,
                                                              known, valid, "active", "observation", t)
                               for eid, t, root, known, valid in rows])

    def test_the_exact_belief_matches_the_registered_enumerator(self):
        b = self._bundle([("m1", "probe reads 61 C", "s/a", 1000, 1000)])
        snap = beliefs.reconstruct(b, NODES, high, known_at=2000)
        self.assertEqual(snap.status, "EXACT")
        self.assertAlmostEqual(snap.posterior["hot"], beliefs.exact_oracle(NODES, {"reading_high": True})["hot"])

    def test_paraphrased_copies_from_one_root_add_no_support(self):
        one = beliefs.reconstruct(self._bundle([("m1", "probe reads 61 C", "s/a", 1000, 1000)]),
                                  NODES, high, known_at=2000)
        many = beliefs.reconstruct(self._bundle([("m1", "probe reads 61 C", "s/a", 1000, 1000),
                                                 ("m2", "61 C on the probe", "s/a", 1001, 1000),
                                                 ("m3", "it read 61 C", "s/a", 1002, 1000)]),
                                   NODES, high, known_at=2000)
        self.assertAlmostEqual(one.posterior["hot"], many.posterior["hot"])

    def test_time_travel_uses_known_time_and_admits_late_earlier_valid_evidence(self):
        b = self._bundle([("m1", "probe reads 61 C", "s/a", 1000, 1000),
                          ("m2", "earlier reading 38 C", "s/b", 1500, 900)])
        before = beliefs.reconstruct(b, NODES, high, known_at=1200)
        after = beliefs.reconstruct(b, NODES, high, known_at=1600)
        self.assertEqual(len(before.observations), 1)
        self.assertEqual(len(after.observations), 2)
        self.assertIn("reading_high", after.conflicts)

    def test_undeclared_likelihoods_and_unregistered_continuations_are_refused(self):
        answer = Answer("x", "boolean", "OK", 0.7, {"true": 0.7, "false": 0.3}, ("true",), False, False)
        with self.assertRaises(beliefs.BeliefError):
            beliefs.propose_likelihood("ambient_heat", answer, frozenset({"reading_high"}), None)
        proposal = beliefs.propose_likelihood("reading_high", answer, frozenset({"reading_high"}), "r")
        snap = beliefs.reconstruct(self._bundle([("m1", "probe reads 61 C", "s/a", 1000, 1000)]), NODES, high,
                                   known_at=2000, proposals=[proposal])
        self.assertEqual(snap.status, "APPROXIMATE")
        self.assertEqual(beliefs.continue_hypothetically(snap, "open_vent", {}), "UNDEFINED_CONTINUATION")


class Interventions(unittest.TestCase):
    def setUp(self):
        self.bundle = packets.bundle([packets.SemanticEvidencePacket(T, "ops", "m1", 1,
                                      packets.sha256_text("probe reads 61 C"), "s/a", 1000, 1000, "active",
                                      "observation", "probe reads 61 C")])
        self.obs = {"m1@1": "o1"}

    def test_every_kind_compiles_to_an_existing_operation_or_unsupported(self):
        ledger = interventions.Ledger()
        props = [interventions.InterventionProposal("WITHHOLD", "m1@1", "r", None),
                 interventions.InterventionProposal("DUPLICATE", "m1@1", "r", None),
                 interventions.InterventionProposal("REORDER_ALLOWED", "m1@1", "r", None),
                 interventions.InterventionProposal("NO_OP", None, "r", None)]
        out = interventions.compile_all(props, self.bundle, readable_refs={"m1@1"}, ledger=ledger,
                                        observation_ids=self.obs)
        self.assertEqual([c.status for c in out], ["COMPILED", "UNSUPPORTED", "UNSUPPORTED", "COMPILED"])
        self.assertEqual(out[0].intervention.operation, "suppress")
        with self.assertRaises(CDMError):
            interventions.InterventionProposal("EXECUTE_SHELL", None, "r", None)

    def test_unreadable_unexposed_and_generated_replacements_are_refused(self):
        refused = interventions.compile_proposal(interventions.InterventionProposal("WITHHOLD", "m1@1", "r", None),
                                                 self.bundle, readable_refs=set(), observation_ids=self.obs)
        self.assertEqual(refused.status, "REJECTED")
        hidden = interventions.compile_proposal(interventions.InterventionProposal("WITHHOLD", "m9@1", "r", None),
                                                self.bundle, readable_refs={"m9@1"}, observation_ids=self.obs)
        self.assertEqual(hidden.status, "REJECTED")
        generated = interventions.compile_proposal(
            interventions.InterventionProposal("REPLACE", "m1@1", "r", None, fixture_id="made-up"),
            self.bundle, readable_refs={"m1@1"}, observation_ids=self.obs, fixtures={})
        self.assertIn("prevalidated", generated.reason)
        fixture = ReplacementFixture("fx", Observation("o1", "reading_high", False, "s/a", 1000))
        ok = interventions.compile_proposal(
            interventions.InterventionProposal("REPLACE", "m1@1", "r", None, fixture_id="fx"),
            self.bundle, readable_refs={"m1@1"}, observation_ids=self.obs, fixtures={"fx": fixture})
        self.assertEqual(ok.status, "COMPILED")

    def test_budget_exhaustion_and_contradictory_batches_stop_safely_with_accounting(self):
        ledger = interventions.Ledger()
        props = [interventions.InterventionProposal("WITHHOLD", "m1@1", f"r{i}", None) for i in range(3)]
        out = interventions.compile_all(props, self.bundle, readable_refs={"m1@1"}, ledger=ledger,
                                        observation_ids=self.obs, budget=interventions.Budget(max_candidates=1))
        self.assertEqual([c.status for c in out], ["COMPILED", "REJECTED", "REJECTED"])
        self.assertEqual(ledger.by_state(), {"COMPILED": 1, "REJECTED": 2})
        withhold = out[0]
        delay = interventions.compile_proposal(interventions.InterventionProposal("DELAY", "m1@1", "d", None,
                                                                                  delay_until=5000),
                                               self.bundle, readable_refs={"m1@1"}, observation_ids=self.obs)
        with self.assertRaises(CDMError):
            interventions.compile_batch([withhold, delay])

    def test_controls_exist_for_every_family(self):
        ctl = interventions.controls(self.bundle, ["m1@1"])
        self.assertEqual([c.kind for c in ctl], ["NO_OP", "WITHHOLD"])
        self.assertTrue(all(c.expected_change == "none_expected" for c in ctl))


class Effects(unittest.TestCase):
    def setUp(self):
        self.sim = DeterministicSimulator(NODES)
        self.policy = ThresholdPolicy("hot", investigate_above=0.35, diagnose_above=0.6)
        self.obs = (Observation("o1", "reading_high", True, "s/a", 1),)

    def _target(self):
        from memory_fabric.causal_replay.types import BeliefReference
        return BeliefReference("o1", 1, T, "0" * 64)

    def test_a_verified_flip_is_reported_with_separate_fields(self):
        from memory_fabric.causal_replay.intervention import create
        fixture = ReplacementFixture("fx", Observation("o1", "reading_high", False, "s/a", 1))
        result = effects.evaluate(self.obs, create(self._target(), "replace", replacement=fixture),
                                  simulator=self.sim, policy=self.policy)
        self.assertEqual(result.status, "VALIDATED_EFFECT")
        self.assertTrue(result.policy_flip)
        self.assertEqual(result.terminal_improvement, "NOT_GRADED")
        self.assertEqual(result.tier, "VALIDATED_COUNTERFACTUAL")

    def test_a_noop_has_no_effect_and_an_empty_world_is_unknown_not_zero(self):
        from memory_fabric.causal_replay.intervention import create
        self.assertEqual(effects.evaluate(self.obs, create(None, "noop"), simulator=self.sim,
                                          policy=self.policy).status, "NO_EFFECT")
        gone = effects.evaluate(self.obs, create(self._target(), "suppress"), simulator=self.sim,
                                policy=self.policy)
        self.assertEqual(gone.status, "UNKNOWN")

    def test_grouped_leave_one_out_ablates_copies_together(self):
        obs = (Observation("o1", "reading_high", True, "s/a", 1), Observation("o2", "reading_high", True, "s/a", 2))
        self.assertEqual(set(effects.grouped_leave_one_out(obs, simulator=self.sim, policy=self.policy)), {"s/a"})

    def test_intervals_are_clustered_by_world_seed(self):
        self.assertEqual(effects.paired_interval({0: [1.0]})["status"], "NOT_ASSESSABLE: fewer than two clusters")
        est = effects.paired_interval({0: [1.0, 1.0], 1: [0.0], 2: [1.0]}, draws=500)
        self.assertEqual(est["clusters"], 3)
        self.assertLessEqual(est["interval"][0], est["mean"])


class Scheduler(unittest.TestCase):
    def test_routing_skips_independents_settles_exact_cases_and_never_replays_on_doubt(self):
        ok = Answer("flip", "boolean", "OK", 0.9, {"true": 0.9, "false": 0.1}, ("true",), False, False)
        low = Answer("flip", "boolean", "OK", 0.02, {"true": 0.02, "false": 0.98}, ("false",), False, False)
        doubt = Answer("flip", "boolean", "ABSTAIN", 0.5, {"true": 0.5, "false": 0.5}, ("true", "false"), True, False)
        c = scheduler.ReplayCandidate("d1", True, 2, 1, 0.1)
        self.assertEqual(scheduler.route(scheduler.ReplayCandidate("d0", False, 0, 1, 0.1), ok).route,
                         "skip_independent")
        self.assertEqual(scheduler.route(scheduler.ReplayCandidate("d2", True, 1, 1, 0.1), None).route, "exact_path")
        self.assertEqual(scheduler.route(c, ok).route, "replay")
        self.assertEqual(scheduler.route(c, low).route, "short_circuit")
        self.assertEqual(scheduler.route(c, doubt).route, "new_observation")
        self.assertEqual(scheduler.route(c, None).route, "review")

    def test_selectors_share_candidates_and_budget_and_waste_is_reported(self):
        cands = [scheduler.ReplayCandidate(f"d{i}", i % 2 == 0, 2, i, 0.1 * i) for i in range(6)]
        pivotal = {"d0", "d4"}
        cost = {c.decision_id: c.replay_cost for c in cands}
        rows = {name: scheduler.score_selection(sel(cands, 2), pivotal, budget=2, cost=cost)
                for name, sel in {**scheduler.SELECTORS,
                                  "advisor": scheduler.advisor_selector({"d4": 0.9, "d0": 0.8})}.items()}
        self.assertEqual(rows["advisor"]["regret"], 0)
        self.assertTrue(all(r["selected"] == 2 for r in rows.values()))
        self.assertIn("wasted_replays", rows["recency"])


class Calibration(unittest.TestCase):
    def _rows(self, n=40, prefix="c"):
        out = []
        for i in range(n):
            right = i % 4 != 0
            p = 0.9 if right else 0.6
            out.append(calibration.CalibrationRow(f"{prefix}{i}", "battery", f"t{prefix}{i % 3}", f"s/{prefix}{i}",
                                                  {"yes": p, "no": 1 - p}, ("yes",), False,
                                                  "yes" if right else "no"))
        return out

    def test_metrics_name_their_population_and_a_fitted_artifact_is_pinned(self):
        m = calibration.metrics(self._rows())
        self.assertEqual(m["population"], 40)
        self.assertEqual(m["top1"], 0.75)
        art = calibration.fit_threshold(self._rows())
        self.assertEqual(len(art.fitted_on), 40)
        self.assertEqual(len(art.digest), 64)

    def test_split_leakage_and_transfer_failure_are_caught(self):
        self.assertTrue(calibration.leakage(self._rows(), self._rows()))
        self.assertEqual(calibration.leakage(self._rows(prefix="c"), self._rows(prefix="x")), [])
        art = calibration.fit_threshold(self._rows(), target_risk=0.05)
        shifted = [calibration.CalibrationRow(f"x{i}", "other", "tx", f"s/x{i}", {"yes": 0.95, "no": 0.05},
                                              ("yes",), False, "no") for i in range(10)]
        self.assertEqual(calibration.transfer_check(art, shifted)["mode"], "REVIEW_ONLY")

    def test_online_learning_is_off_and_only_evaluator_feedback_after_the_outcome_counts(self):
        self.assertEqual(calibration.ONLINE_LEARNING, "DISABLED")
        self.assertTrue(calibration.admissible_feedback({"source": "evaluator", "label_at": 5, "outcome_at": 4}))
        for bad in ({"source": "agent", "label_at": 5, "outcome_at": 4},
                    {"source": "evaluator", "label_at": 3, "outcome_at": 4}):
            self.assertFalse(calibration.admissible_feedback(bad))


class Cache(unittest.TestCase):
    def test_keys_bind_principal_and_entries_invalidate_on_every_change(self):
        q = {"x": Question("x", "boolean", "?", {"true": "y", "false": "n"})}
        base = dict(tenant_id=T, bundle_digest="b", questions=q, model={"engine": "e1"}, policy_version="p1")
        k1 = cache.key(principal="ops", **base)
        k2 = cache.key(principal="intern", **base)
        self.assertNotEqual(k1, k2)
        c = cache.AdviceCache()
        advice = ScriptedAdvisor().decide("s", q)
        for trigger in ({"evidence_id": "m1"}, {"principal": "ops"}, {"engine": "e2"}, {"policy_version": "p2"}):
            c.put(k1, advice, tenant_id=T, principal="ops", evidence_ids=frozenset({"m1"}), engine="e1",
                  policy_version="p1")
            with self.subTest(trigger=trigger):
                self.assertEqual(c.invalidate(**trigger), 1)
                self.assertIsNone(c.get(k1))


if __name__ == "__main__":
    unittest.main()
