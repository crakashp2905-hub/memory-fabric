"""Causal hypotheses with epistemic labels and typed constraints (VEGA next W07)."""

from __future__ import annotations

import dataclasses
import unittest

from memory_fabric.causal_replay.semantic import graph
from memory_fabric.causal_replay.semantic.graph import CandidateGraph, Edge, GraphError, Node

T = "tn_plant"
R = "r" * 64


def battery_graph() -> CandidateGraph:
    g = CandidateGraph(T)
    for nid, kind, t, inter in (("obs-ta1", "observation", 1000, False), ("obs-tb2", "observation", 1015, False),
                                ("belief-hot", "belief", 1016, False), ("dec", "decision", 1020, False),
                                ("act-cool", "action", 1021, True), ("future", "observation", 2000, False)):
        g.add_node(Node(nid, kind, T, nid, 1, t, intervenable=inter))
    return g


class Tiers(unittest.TestCase):
    def test_no_method_upcasts_a_tier_and_edges_are_immutable(self):
        g = battery_graph()
        e = g.propose("obs-ta1", "belief-hot", "HYPOTHESIZED_CAUSE", ["m1@1"], R)
        self.assertEqual(e.tier, "HYPOTHETICAL_EFFECT")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            e.kind = "VERIFIED_COUNTERFACTUAL_EFFECT"  # type: ignore[misc]
        public = [m for m in dir(CandidateGraph) if not m.startswith("_")]
        self.assertFalse([m for m in public if "promote" in m or "upgrade" in m or "verify" in m])
        self.assertEqual(g.identifiability("obs-ta1", "belief-hot"), "NOT_ESTABLISHED")

    def test_edges_carry_versions_authorization_policy_and_confidence_provenance(self):
        g = battery_graph()
        e = g.propose("obs-ta1", "belief-hot", "SUPPORTS", ["m1@1"], R, auth_epoch=7, policy_digest="p" * 64,
                      origin_root="st/m1")
        self.assertEqual((e.auth_epoch, e.policy_digest, e.confidence_source), (7, "p" * 64, f"advisor:{R}"))
        with self.assertRaises(GraphError):
            Edge("obs-ta1", "belief-hot", "SUPPORTS", ("m1",), R, "advisor")  # unversioned reference


class Alternatives(unittest.TestCase):
    def test_sensor_bias_and_real_overheating_coexist_as_hypotheses(self):
        g = battery_graph()
        g.add_node(Node("h-bias", "claim", T, "hyp", 0, 1016))
        g.add_node(Node("h-heat", "claim", T, "hyp", 0, 1016))
        g.propose("h-bias", "obs-ta1", "HYPOTHESIZED_CAUSE", ["m1@1"], R)
        g.propose("h-heat", "obs-ta1", "HYPOTHESIZED_CAUSE", ["m1@1"], R)
        causes = {e.source for e in g.edges if e.target == "obs-ta1" and e.kind == "HYPOTHESIZED_CAUSE"}
        self.assertEqual(causes, {"h-bias", "h-heat"})

    def test_future_observations_cannot_explain_earlier_decisions(self):
        g = battery_graph()
        with self.assertRaises(GraphError):
            g.propose("future", "dec", "HYPOTHESIZED_CAUSE", ["m9@1"], R)

    def test_latent_confounding_blocks_a_causal_conclusion(self):
        g = battery_graph()
        g.propose("obs-ta1", "dec", "HYPOTHESIZED_CAUSE", ["m1@1"], R)
        g.declare_latent("obs-ta1", "dec", "ambient_heat")
        self.assertEqual(g.identifiability("obs-ta1", "dec"), "CAUSAL_UNIDENTIFIABLE")


class Provenance(unittest.TestCase):
    def test_twenty_paraphrases_from_one_origin_are_one_edge(self):
        g = battery_graph()
        for i in range(20):
            g.propose("obs-ta1", "belief-hot", "SUPPORTS", [f"m{i}@1"], f"{i:064d}", origin_root="tool/run-1")
        self.assertEqual(len([e for e in g.edges if e.kind == "SUPPORTS"]), 1)
        g.propose("obs-ta1", "belief-hot", "SUPPORTS", ["mx@1"], R, origin_root="tool/run-2")
        self.assertEqual(len([e for e in g.edges if e.kind == "SUPPORTS"]), 2)

    def test_hypotheses_need_authorized_evidence_and_erasure_removes_them(self):
        g = battery_graph()
        g.propose("obs-ta1", "belief-hot", "HYPOTHESIZED_CAUSE", ["m1@1"], R)
        self.assertEqual(g.view(set(), T), {"edges": [], "nodes": 0})  # unreadable evidence: invisible
        g.invalidate("m1", None)
        self.assertEqual([e for e in g.edges if "m1@1" in e.evidence_refs], [])

    def test_only_registered_intervenable_nodes_can_be_targeted(self):
        g = battery_graph()
        self.assertIsNone(g.check_intervention("act-cool"))
        self.assertIn("not registered as intervenable", g.check_intervention("obs-ta1") or "")
        self.assertIn("not a node", g.check_intervention("nowhere") or "")

    def test_rationale_is_content_safe(self):
        g = battery_graph()
        e = g.propose("obs-ta1", "belief-hot", "HYPOTHESIZED_CAUSE", ["m1@1"], R)
        text = g.explain(e)
        self.assertIn("not a verified effect", text)
        self.assertIn("m1@1", text)
        self.assertNotIn("reads", text)


class Worlds(unittest.TestCase):
    def test_copy_invariance_temporal_reversal_and_confounding_stay_hypotheses(self):
        g = battery_graph()
        g.add_node(Node("copy", "observation", T, "obs-ta1", 1, 1001))
        g.propose("copy", "belief-hot", "SUPPORTS", ["m1c@1"], R, origin_root="st/m1")
        g.propose("obs-ta1", "belief-hot", "SUPPORTS", ["m1@1"], R, origin_root="st/m1")
        self.assertEqual(len({e.origin_root for e in g.edges if e.kind == "SUPPORTS"}), 1)
        self.assertTrue(all(e.tier != "VALIDATED_COUNTERFACTUAL" for e in g.edges))
        with self.assertRaises(GraphError):
            g.add_verified_effect("obs-ta1", "dec", ["m1@1"], {"accepted": True})  # no certificate
        ok = g.add_verified_effect("obs-ta1", "dec", ["m1@1"], {"accepted": True, "certificate": "c" * 64})
        self.assertEqual(ok.tier, graph.TIER_OF["VERIFIED_COUNTERFACTUAL_EFFECT"])


if __name__ == "__main__":
    unittest.main()
