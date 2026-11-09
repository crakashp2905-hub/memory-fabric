"""Evidence independence from exposure (S2): a paraphrase of what you were shown is not a second source."""

from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.federation import offer
from memory_fabric.governance.firewall import (Firewall, rule_capabilities_must_be_granted,
                                               rule_must_be_active, rule_restricted_stays_private)
from memory_fabric.independence import Independence, global_ref, independent_sources
from memory_fabric.model import Scope


def store() -> MemoryFabric:
    return MemoryFabric(":memory:", auto_activate=True, firewall=Firewall(rules=(
        rule_restricted_stays_private, rule_must_be_active, rule_capabilities_must_be_granted)))


REPORT = "Pump P4 at the north site is leaking oil from its seal."
PARAPHRASE = "There is an oil leak at the north site: the seal on pump P4 has failed."
OWN = "North site walk-round: pump P4 seal weeping oil, about a cup an hour."


class InOneStore(unittest.TestCase):
    def setUp(self) -> None:
        self.f = store()
        self.addCleanup(self.f.close)
        self.a = self.f.remember("ana", REPORT, scope="team")

    def test_a_paraphrase_by_someone_shown_the_report_is_not_independent(self) -> None:
        shown = self.f.retrieve("ben", "pump P4 north site leak", k=3)
        self.assertIn(self.a, [m.id for m in shown.exposed])
        b = self.f.remember("ben", PARAPHRASE, scope="team")
        self.assertEqual(independent_sources(self.f, [self.a, b]), 1)
        self.assertIn(global_ref(self.f, self.a), Independence(self.f).informed_by(b))

    def test_the_same_words_from_someone_never_shown_it_are_independent(self) -> None:
        b = self.f.remember("cara", PARAPHRASE, scope="team")
        self.assertEqual(independent_sources(self.f, [self.a, b]), 2)

    def test_being_shown_it_afterwards_does_not_reach_back(self) -> None:
        b = self.f.remember("cara", OWN, scope="team")
        self.f.retrieve("cara", "pump P4 north site leak", k=3)
        self.assertEqual(independent_sources(self.f, [self.a, b]), 2)

    def test_a_summary_of_two_real_reports_does_not_merge_them(self) -> None:
        b = self.f.remember("cara", OWN, scope="team")
        self.f.retrieve("dev", "pump P4 north site seal oil", k=5, group_by_source_root=False)
        summary = self.f.remember("dev", "P4 north: seal leaking (two reports).", scope="team")
        self.assertEqual(independent_sources(self.f, [self.a, b, summary]), 2)

    def test_it_is_transitive(self) -> None:
        self.f.retrieve("ben", "pump P4 north site leak", k=3)
        b = self.f.remember("ben", PARAPHRASE, scope="team")
        # dev is shown only ben's paraphrase: ana's report is withdrawn first,
        # so retrieval cannot show it (independence does not look at lifecycle)
        self.f.quarantine(self.a, reason="test", actor="op")
        result = self.f.retrieve("dev", "oil leak seal failed", k=5, group_by_source_root=False)
        self.assertIn(b, [m.id for m in result.exposed])
        self.f.retrieve("dev", "nothing about pumps at all", k=1)
        seen = {r.memory_id for r in self.f.state.exposures if r.agent_id == "dev" and r.exposed}
        c = self.f.remember("dev", "P4's seal has gone at north; oil on the floor.", scope="team")
        self.assertNotIn(self.a, seen)
        self.assertTrue(Independence(self.f).dependent(self.a, c))
        self.assertEqual(independent_sources(self.f, [self.a, b, c]), 1)


class AcrossStores(unittest.TestCase):
    def test_laundering_through_a_second_store_is_still_one_source(self) -> None:
        s0, s1, s2 = store(), store(), store()
        for s in (s0, s1, s2):
            self.addCleanup(s.close)
        a = s0.remember("ana", REPORT, scope="team")
        s0.share(a, Scope.FEDERATED, actor="op")
        a_at_1 = offer(s0, a, s1, recipient_agent="ben", activate=True).imported_memory_id
        a_at_2 = offer(s0, a, s2, recipient_agent="x", activate=True).imported_memory_id
        s1.retrieve("ben", "pump P4 north site leak", k=3)
        p = s1.remember("ben", PARAPHRASE, scope="team")
        s1.share(p, Scope.FEDERATED, actor="op")
        p_at_2 = offer(s1, p, s2, recipient_agent="x", activate=True).imported_memory_id
        self.assertEqual(global_ref(s1, a_at_1), (s0.store_id, a))
        self.assertEqual(global_ref(s2, a_at_2), (s0.store_id, a))
        self.assertEqual(independent_sources(s2, [a_at_2, p_at_2]), 1)

    def test_an_independent_report_from_another_store_still_counts(self) -> None:
        s0, s1, s2 = store(), store(), store()
        for s in (s0, s1, s2):
            self.addCleanup(s.close)
        a = s0.remember("ana", REPORT, scope="team")
        s0.share(a, Scope.FEDERATED, actor="op")
        a_at_2 = offer(s0, a, s2, recipient_agent="x", activate=True).imported_memory_id
        own = s1.remember("ben", OWN, scope="team")
        s1.share(own, Scope.FEDERATED, actor="op")
        own_at_2 = offer(s1, own, s2, recipient_agent="x", activate=True).imported_memory_id
        self.assertEqual(independent_sources(s2, [a_at_2, own_at_2]), 2)

    def test_parallel_multihop_relays_keep_one_root_and_block_return_cycle(self) -> None:
        # Two independent relay paths carry the same origin observation into
        # one receiver. Copies remain one global source despite distinct
        # immediate senders, and forwarding either path home is refused.
        a, b, c, d, e, receiver = [store() for _ in range(6)]
        stores = (a, b, c, d, e, receiver)
        for fabric in stores:
            self.addCleanup(fabric.close)

        original = a.remember("origin", REPORT, scope="team")
        a.share(original, Scope.FEDERATED, actor="operator")

        first_b = offer(a, original, b, recipient_agent="b", activate=True)
        first_d = offer(a, original, d, recipient_agent="d", activate=True)
        self.assertTrue(first_b.accepted)
        self.assertTrue(first_d.accepted)
        b_copy = first_b.imported_memory_id
        d_copy = first_d.imported_memory_id
        b.share(b_copy, Scope.FEDERATED, actor="operator")
        d.share(d_copy, Scope.FEDERATED, actor="operator")

        second_c = offer(b, b_copy, c, recipient_agent="c", activate=True)
        second_e = offer(d, d_copy, e, recipient_agent="e", activate=True)
        self.assertTrue(second_c.accepted)
        self.assertTrue(second_e.accepted)
        c_copy = second_c.imported_memory_id
        e_copy = second_e.imported_memory_id
        c.share(c_copy, Scope.FEDERATED, actor="operator")
        e.share(e_copy, Scope.FEDERATED, actor="operator")

        via_c = offer(c, c_copy, receiver, recipient_agent="receiver", activate=True)
        via_e = offer(e, e_copy, receiver, recipient_agent="receiver", activate=True)
        self.assertTrue(via_c.accepted)
        self.assertTrue(via_e.accepted)
        c_at_receiver = via_c.imported_memory_id
        e_at_receiver = via_e.imported_memory_id

        expected_root = (a.store_id, original)
        self.assertEqual(global_ref(b, b_copy), expected_root)
        self.assertEqual(global_ref(c, c_copy), expected_root)
        self.assertEqual(global_ref(e, e_copy), expected_root)
        self.assertEqual(global_ref(receiver, c_at_receiver), expected_root)
        self.assertEqual(global_ref(receiver, e_at_receiver), expected_root)
        self.assertEqual(independent_sources(receiver, [c_at_receiver, e_at_receiver]), 1)

        cycle = offer(e, e_copy, a, recipient_agent="origin", activate=True)
        self.assertFalse(cycle.accepted)
        self.assertTrue(any("already on this memory's provenance chain" in reason
                            for reason in cycle.reasons))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
