from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.context_map import ContextMap
from memory_fabric.context_receipt import build_context, explain_receipt


def open_set(fabric: MemoryFabric, left: str, right: str, *, agent: str = "ops") -> str:
    first = fabric.remember(agent, left, scope="team")
    second = fabric.remember("inspector", right, scope="team")
    return fabric.challenge([first, second], evidence="unresolved contradictory readings")


class DisagreementBudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = MemoryFabric(auto_activate=True, hold_suspicious=False)
        self.addCleanup(self.fabric.close)

    def test_relevant_open_set_is_atomic_and_preserves_each_alternative(self) -> None:
        set_id = open_set(
            self.fabric,
            "Pump P9 restart pressure is 6 bar.",
            "Pump P9 restart pressure is 9 bar.",
        )
        bundle = build_context(
            self.fabric, "reader", "Pump P9 restart pressure", mode="exact",
            budget=300, disagreement_budget=200,
        )

        self.assertEqual(len(bundle.plan.items), 1)
        self.assertEqual(bundle.plan.items[0].kind, "disagreement")
        self.assertIn("6 bar", bundle.text)
        self.assertIn("9 bar", bundle.text)
        self.assertEqual(bundle.plan.uncertainty[0]["id"], set_id)
        self.assertEqual(bundle.plan.uncertainty[0]["status"], "PRESERVED")
        self.assertLessEqual(bundle.plan.disagreement_tokens, 200)

    def test_oversized_set_returns_marker_instead_of_a_partial_winner(self) -> None:
        long_suffix = " calibrated by the night shift with repeated instrument verification" * 18
        set_id = open_set(
            self.fabric,
            "Pump P9 restart pressure is 6 bar." + long_suffix,
            "Pump P9 restart pressure is 9 bar." + long_suffix,
        )
        bundle = build_context(
            self.fabric, "reader", "Pump P9 restart pressure", mode="exact",
            budget=300, disagreement_budget=50,
        )

        self.assertEqual([item.kind for item in bundle.plan.items], ["insufficiency"])
        self.assertIn("INSUFFICIENT", bundle.text)
        self.assertIn("No alternative was selected", bundle.text)
        self.assertNotIn("6 bar", bundle.text)
        self.assertNotIn("9 bar", bundle.text)
        self.assertEqual(bundle.plan.uncertainty[0]["id"], set_id)
        self.assertEqual(bundle.plan.uncertainty[0]["status"], "INSUFFICIENT_DISAGREEMENT_BUDGET")
        self.assertLessEqual(bundle.plan.tokens, 300)
        self.assertLessEqual(bundle.plan.disagreement_tokens, 50)

    def test_non_numeric_negation_conflict_is_not_collapsed(self) -> None:
        open_set(
            self.fabric,
            "Valve V2 is enabled.",
            "Valve V2 is not enabled.",
        )
        bundle = build_context(
            self.fabric, "reader", "Valve V2 enabled", mode="exact",
            budget=300, disagreement_budget=200,
        )
        self.assertEqual(bundle.plan.uncertainty[0]["status"], "PRESERVED")
        self.assertIn("is enabled", bundle.text)
        self.assertIn("is not enabled", bundle.text)

    def test_unrelated_disagreement_does_not_enter_the_prompt(self) -> None:
        open_set(
            self.fabric,
            "Pump P9 restart pressure is 6 bar.",
            "Pump P9 restart pressure is 9 bar.",
        )
        bundle = build_context(
            self.fabric, "reader", "Valve V2 opens at 4 bar", mode="exact",
            budget=300,
        )
        self.assertEqual(bundle.plan.uncertainty, [])
        self.assertFalse(any(item.kind in {"disagreement", "insufficiency"}
                             for item in bundle.plan.items))

    def test_inaccessible_alternative_yields_insufficiency_without_leaking_text(self) -> None:
        visible = self.fabric.remember(
            "ops", "Pump P9 restart pressure is 6 bar.", scope="team"
        )
        private = self.fabric.remember(
            "ops", "Pump P9 restart pressure is 9 bar.", scope="private"
        )
        set_id = self.fabric.challenge([visible, private], evidence="access-limited conflict")
        bundle = build_context(
            self.fabric, "reader", "Pump P9 restart pressure", mode="exact",
            budget=300, disagreement_budget=200,
        )

        self.assertEqual([item.kind for item in bundle.plan.items], ["insufficiency"])
        self.assertIn("INSUFFICIENT", bundle.text)
        self.assertNotIn("6 bar", bundle.text)
        self.assertNotIn("9 bar", bundle.text)
        self.assertEqual(bundle.plan.uncertainty[0]["id"], set_id)
        self.assertEqual(bundle.plan.uncertainty[0]["status"], "INSUFFICIENT")

    def test_selected_disagreement_receipt_tracks_all_sources_and_current_access(self) -> None:
        open_set(
            self.fabric,
            "Pump P9 restart pressure is 6 bar.",
            "Pump P9 restart pressure is 9 bar.",
        )
        bundle = build_context(
            self.fabric, "reader", "Pump P9 restart pressure", mode="exact",
            budget=300, disagreement_budget=200,
        )
        selected = bundle.receipt["selected"]
        self.assertEqual(bundle.receipt["schema"], "memory-fabric-context-receipt/2")
        self.assertEqual(selected[0]["kind"], "disagreement")
        self.assertEqual(len(selected[0]["expanded_sources"]), 2)
        self.assertNotIn("6 bar", str(bundle.receipt))
        explained = explain_receipt(self.fabric, bundle.receipt["receipt_id"])
        self.assertTrue(explained["selected"][0]["admissible_now"])

    def test_invalid_disagreement_budget_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ContextMap(self.fabric).plan("reader", "pump p9", disagreement_budget=-1)
        with self.assertRaises(ValueError):
            ContextMap(self.fabric).plan("reader", "pump p9", disagreement_budget=True)

    def test_marker_that_cannot_fit_is_explicit_in_receipt_metadata(self) -> None:
        open_set(
            self.fabric,
            "Pump P9 restart pressure is 6 bar.",
            "Pump P9 restart pressure is 9 bar.",
        )
        bundle = build_context(
            self.fabric, "reader", "Pump P9 restart pressure", mode="exact",
            budget=20, disagreement_budget=0,
        )
        self.assertEqual(bundle.plan.items, [])
        self.assertEqual(
            bundle.receipt["uncertainty"][0]["status"],
            "INSUFFICIENT_MARKER_NOT_FIT",
        )
        self.assertEqual(bundle.receipt["disagreement_tokens_estimated"], 0)

    def test_legacy_v1_context_receipt_remains_readable(self) -> None:
        from memory_fabric import events

        legacy = {
            "receipt_id": "ctx_legacy_v1",
            "tenant_id": "tn_default",
            "agent_id": "reader",
            "branch": "main",
            "selected": [],
            "excluded": [],
        }
        self.fabric._emit(events.context_built(self.fabric.now(), "reader", legacy))
        explained = explain_receipt(self.fabric, "ctx_legacy_v1")
        self.assertEqual(explained["schema"], "memory-fabric-context-receipt/1")
        self.assertEqual(explained["uncertainty"], [])
        self.assertEqual(explained["disagreement_budget"], 0)
        self.assertEqual(explained["selected"], [])


if __name__ == "__main__":
    unittest.main()
