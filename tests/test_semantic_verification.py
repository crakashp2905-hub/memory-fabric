"""The verification boundary between evidence, model proposals and decisions (VEGA next W04)."""

from __future__ import annotations

import unittest

from memory_fabric.causal_replay.semantic import cache, packets
from memory_fabric.causal_replay.semantic.advice import Answer, Question
from memory_fabric.causal_replay.semantic.entities import battery_registry
from memory_fabric.causal_replay.semantic.observations import Predicate
from memory_fabric.causal_replay.semantic.verified_observations import cross_check, verify

T = "tn_plant"
TA1, TB2 = "pack:p-7/sensor:ta1", "pack:p-7/sensor:tb2"
HOT = Predicate("temperature", "gt", 50.0)


def pk(text, i=0, status="active", known_at=None, version=1):
    return packets.SemanticEvidencePacket(T, "ops", f"m{i}", version, packets.sha256_text(text), f"s/m{i}",
                                          known_at if known_at is not None else 1000 + i, 1000 + i, status,
                                          "observation", text)


def answer(p_true, decisive=True):
    return Answer("hot", "boolean", "OK" if decisive else "ABSTAIN", p_true,
                  {"true": p_true, "false": 1 - p_true}, ("true" if p_true > 0.5 else "false",) if decisive
                  else ("true", "false"), not decisive, False)


class Findings(unittest.TestCase):
    def setUp(self):
        self.r = battery_registry()

    def test_each_sensor_gets_one_finding_with_evidence_refs(self):
        v = verify([pk("10:00 pack P-7 sensor TA1 reads 61 C", 0), pk("10:15 pack P-7 sensor TB2 reads 41 C", 1)],
                   self.r, HOT, required=(TA1, TB2))
        self.assertEqual((v.findings[TA1].status, v.findings[TA1].value), ("VERIFIED", "TRUE"))
        self.assertEqual((v.findings[TB2].status, v.findings[TB2].value), ("VERIFIED", "FALSE"))
        self.assertEqual(v.findings[TA1].evidence_refs, ("m0@1",))
        self.assertEqual(v.aggregate(), "CONTESTED")  # sensors disagree; no winner is chosen

    def test_unknown_findings_name_a_recovery_step_never_no_action(self):
        v = verify([pk("TB2 display on P-7 garbled", 0)], self.r, HOT, required=(TA1, TB2))
        self.assertEqual((v.findings[TB2].status, v.findings[TB2].next_step), ("UNKNOWN", "CHECK_SOURCE"))
        self.assertEqual((v.findings[TA1].status, v.findings[TA1].next_step), ("UNKNOWN", "RE_RETRIEVE"))
        self.assertTrue(all(f.next_step in ("RE_RETRIEVE", "CHECK_SOURCE", "ASK") for f in v.findings.values()))

    def test_same_sensor_disagreement_at_one_time_is_disputed(self):
        v = verify([pk("10:00 pack P-7 sensor TA1 reads 61 C", 0), pk("10:00 pack P-7 sensor TA1 reads 38 C", 1)],
                   self.r, HOT, required=(TA1,))
        self.assertEqual((v.findings[TA1].status, v.findings[TA1].next_step), ("DISPUTED", "ASK"))

    def test_present_day_ignores_corrected_versions_and_history_uses_known_time(self):
        old = pk("10:15 pack P-7 sensor TB2 reads 64 C", 1, status="corrected", known_at=1015)
        new = pk("10:15 pack P-7 sensor TB2 reads 41 C", 2, known_at=1050, version=2)
        now = verify([old, new], self.r, HOT, required=(TB2,))
        self.assertEqual(now.findings[TB2].value, "FALSE")
        then = verify([old, new], self.r, HOT, required=(TB2,), known_at=1020)
        self.assertEqual(then.findings[TB2].value, "TRUE")

    def test_ambiguous_identity_and_other_packs_are_not_counted(self):
        v = verify([pk("TA1 and TB2 both read 61 C", 0), pk("10:05 pack P-9 sensor TB9 reads 64 C", 1)],
                   self.r, HOT, required=(TA1, TB2))
        self.assertEqual(v.findings[TA1].status, "UNKNOWN")
        self.assertNotIn("pack:p-9/sensor:tb9", [s for s, f in v.findings.items() if s in (TA1, TB2) and f.value == "TRUE"])


class Proposals(unittest.TestCase):
    def setUp(self):
        self.r = battery_registry()
        self.v = verify([pk("At 10:00 the A-side thermistor TA1 on pack P-7 was showing sixty-one degrees", 0)],
                        self.r, HOT, required=(TA1, TB2))

    def test_a_confident_wrong_proposal_is_rejected_and_the_finding_is_unchanged(self):
        before = self.v.findings[TA1]
        check = cross_check(self.v, TA1, answer(0.02), {"receipt_digest": "r"})
        self.assertEqual(check.outcome, "REJECTED_CONTRADICTS_VERIFIED")
        self.assertIs(self.v.findings[TA1], before)
        self.assertEqual(self.v.findings[TA1].value, "TRUE")

    def test_a_proposal_cannot_verify_an_unknown_finding(self):
        check = cross_check(self.v, TB2, answer(0.99))
        self.assertEqual(check.outcome, "NOT_USED_UNVERIFIABLE")
        self.assertEqual(self.v.findings[TB2].status, "UNKNOWN")

    def test_undecided_and_consistent_proposals_are_recorded(self):
        self.assertEqual(cross_check(self.v, TA1, answer(0.6, decisive=False)).outcome, "UNDECIDED")
        self.assertEqual(cross_check(self.v, TA1, answer(0.9)).outcome, "CONSISTENT")
        self.assertEqual(len(self.v.checks), 2)

    def test_relevance_alone_never_satisfies_a_typed_predicate(self):
        v = verify([pk("TA1 on pack P-7 is very relevant to the overheating question", 0)], self.r, HOT,
                   required=(TA1,))
        self.assertEqual(v.findings[TA1].status, "UNKNOWN")


class Binding(unittest.TestCase):
    def test_changing_an_evidence_version_or_model_identity_changes_the_receipt_key(self):
        q = {"hot": Question("hot", "boolean", "?", {"true": "y", "false": "n"})}
        b1 = packets.bundle([pk("TA1 reads 61 C", 0)])
        b2 = packets.bundle([pk("TA1 reads 61 C", 0, version=2)])
        base = dict(tenant_id=T, principal="planner", questions=q, policy_version="p1")
        k = {cache.key(bundle_digest=b.digest, model={"engine": e}, **base) for b in (b1, b2) for e in ("e1", "e2")}
        self.assertEqual(len(k), 4)


if __name__ == "__main__":
    unittest.main()
