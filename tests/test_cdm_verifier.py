"""Independent verifier checks exact small-N attribution coalition tables."""

from __future__ import annotations

import itertools
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.causal_replay.attribution import exhaustive_shapley
from memory_fabric.causal_replay.certificates import issue
from memory_fabric.causal_replay.verifier import (verify_minimality_proof,
                                                   verify_small_n_shapley)


class TestAttributionVerifier(unittest.TestCase):
    def test_symmetric_and_interaction_matches_independent_verifier(self):
        players = ("left", "right")
        values = {tuple(sorted(group)): float(set(players) <= set(group))
                  for size in range(3) for group in itertools.combinations(players, size)}
        exact = exhaustive_shapley(players,
            lambda coalition: float(set(players) <= coalition))
        checked = verify_small_n_shapley(players, coalition_values=values,
                                         claimed_values=exact)
        self.assertTrue(checked.verified)
        self.assertEqual(dict(checked.recomputed_values), {"left": 0.5, "right": 0.5})

    def test_tampered_or_incomplete_table_is_rejected(self):
        players = ("a", "b")
        values = {(): 0.0, ("a",): 0.0, ("b",): 0.0, ("a", "b"): 1.0}
        self.assertEqual(verify_small_n_shapley(players, coalition_values=values,
            claimed_values={"a": 0.4, "b": 0.6}).code, "SHAPLEY_VALUE_MISMATCH")
        self.assertEqual(verify_small_n_shapley(players, coalition_values={(): 0.0},
            claimed_values={"a": 0.0, "b": 0.0}).code, "COALITION_TABLE_INCOMPLETE")


class TestMinimalityVerifier(unittest.TestCase):
    def setUp(self):
        self.players = ("a", "b", "c")
        self.table = {}
        for size in range(4):
            for group in itertools.combinations(self.players, size):
                self.table[group] = "approve" if "a" in group and "b" in group else "review"

    def test_sufficient_inclusion_minimal_and_cardinality_minimum(self):
        for claim in ("verified_sufficient_subset", "inclusion_minimal", "cardinality_minimum"):
            with self.subTest(claim=claim):
                result = verify_minimality_proof(self.players, coalition_proposals=self.table,
                    sufficient_subset=("a", "b"), target_proposal="approve", claim=claim)
                self.assertTrue(result.verified, result)
                self.assertEqual(result.checked_subsets, 8)
                self.assertEqual(len(result.proof_digest or ""), 64)

    def test_false_minimal_claim_and_incomplete_table_refuse(self):
        table = dict(self.table)
        table[("c",)] = "approve"
        result = verify_minimality_proof(self.players, coalition_proposals=table,
            sufficient_subset=("a", "b"), target_proposal="approve",
            claim="cardinality_minimum")
        self.assertEqual(result.code, "SMALLER_SUBSET_SUFFICIENT")
        self.assertEqual(verify_minimality_proof(self.players,
            coalition_proposals={(): "review"}, sufficient_subset=("a",),
            target_proposal="approve", claim="verified_sufficient_subset").code,
            "COALITION_TABLE_INCOMPLETE")


class TestReplayCertificateAuthorityBoundary(unittest.TestCase):
    def test_replay_certificate_cannot_execute_a_protected_tool(self):
        Path(".tmp").mkdir(exist_ok=True)
        with TemporaryDirectory(dir=".tmp") as directory:
            fabric = MemoryFabric(Path(directory) / "authority.db")
            try:
                policy = ActionPolicy(tools={"open_valve": ToolRule("open_valve")},
                    grants={"ag3": frozenset({"open_valve"})})
                gate = ActionGate(fabric, policy, audit=False)
                replay_certificate = issue(capture_digest="a" * 64,
                    intervention_digest="b" * 64, factual_fingerprint="c" * 64,
                    counterfactual_fingerprint="d" * 64, updater_id="updater-v1",
                    policy_id="policy-v1", status="EXACT", factual_proposal="monitor",
                    counterfactual_proposal="diagnose", complete=True)
                called = []
                result = gate.execute("open_valve", "ag3",
                    lambda key: called.append(key), replay_certificate.payload(),
                    key="replay-certificate-authority-forgery")
                self.assertEqual(result.outcome, "refused")
                self.assertEqual(called, [])
                self.assertIsNotNone(result.decision)
                self.assertFalse(result.decision.allowed)
            finally:
                fabric.close()


if __name__ == "__main__":
    unittest.main()
