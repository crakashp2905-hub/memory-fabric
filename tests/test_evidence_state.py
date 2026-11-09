from __future__ import annotations

import unittest

from memory_fabric.evidence_state import EvidenceState, named_states


class EvidenceStateLattice(unittest.TestCase):
    def test_named_evidence_states_are_distinct(self) -> None:
        states = named_states()
        self.assertEqual(set(states), {
            "unknown", "disputed", "withdrawn", "stale", "supported", "independently_corroborated"
        })
        self.assertEqual(len(set(states.values())), 6)

    def test_partial_order_and_bounds(self) -> None:
        states = list(named_states().values())
        for left in states:
            self.assertLessEqual(left, left)
            for right in states:
                self.assertFalse(left <= right and right <= left and left != right)
                join = left.join(right)
                meet = left.meet(right)
                self.assertLessEqual(left, join)
                self.assertLessEqual(right, join)
                self.assertLessEqual(meet, left)
                self.assertLessEqual(meet, right)

    def test_disputed_and_withdrawn_are_incomparable_and_join_preserves_both(self) -> None:
        states = named_states()
        disputed, withdrawn = states["disputed"], states["withdrawn"]
        self.assertFalse(disputed <= withdrawn)
        self.assertFalse(withdrawn <= disputed)
        self.assertEqual(disputed.join(withdrawn), EvidenceState(disputed=True, withdrawn=True))


if __name__ == "__main__":
    unittest.main()
