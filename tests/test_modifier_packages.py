from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.chains import tokens
from memory_fabric.relations import RelationKind


class MultiHopModifierPackages(unittest.TestCase):
    def _fixture(self, seed: int):
        fabric = MemoryFabric(":memory:", auto_activate=True, encrypt_content=False)
        self.addCleanup(fabric.close)
        crane = f"crane-{seed}"
        axle = f"heavy-axle-{seed}"
        site = f"depot-{seed}"
        source = fabric.remember(
            "engineer", f"{crane} is fitted with {axle}.", scope="team"
        )
        rule = fabric.derive(
            "engineer",
            f"{axle} winter tyre pressure baseline is {3 + seed / 10:.1f} bar.",
            [source],
            scope="team",
            auto_activate=True,
        )
        answer = fabric.derive(
            "engineer",
            f"{crane} winter tyre pressure uses the {axle} baseline.",
            [rule],
            scope="team",
            auto_activate=True,
            context={"base_bar": 3 + seed / 10},
        )
        modifier = fabric.remember(
            "site-lead",
            f"At {site}, add a {0.2 + seed / 100:.2f} bar salt margin to the axle-set figure.",
            scope="team",
            context={"add_bar": 0.2 + seed / 100},
        )
        fabric.relate(modifier, RelationKind.QUALIFIES, answer, actor="site-lead")
        query = f"What is the winter tyre pressure for {crane}?"
        return fabric, answer, modifier, query

    @staticmethod
    def _result(fabric: MemoryFabric, memory_ids: tuple[str, ...]) -> float:
        base = 0.0
        adjustment = 0.0
        for memory_id in memory_ids:
            context = fabric.get(memory_id).context
            base += float(context.get("base_bar", 0.0))
            adjustment += float(context.get("add_bar", 0.0))
        return round(base + adjustment, 6)

    def test_modifiers_change_results_without_repeating_the_question(self) -> None:
        for seed in range(1, 6):
            with self.subTest(seed=seed):
                fabric, answer, modifier, query = self._fixture(seed)
                plain = fabric.reconstruct("reader", query, k=8, follow_relations=False)
                package = fabric.reconstruct("reader", query, k=8, follow_relations=True)

                self.assertIn(answer, plain.memory_ids)
                self.assertNotIn(modifier, plain.memory_ids)
                self.assertIn(modifier, package.memory_ids)
                modifier_step = next(s for s in package.steps if s.memory_id == modifier)
                self.assertEqual(modifier_step.covers, ())
                self.assertTrue(modifier_step.necessary)
                self.assertTrue(
                    set(tokens(fabric.get(modifier).content)).isdisjoint(tokens(query)),
                    "modifier unexpectedly restates query terms",
                )

                base_result = self._result(fabric, plain.memory_ids)
                modified_result = self._result(fabric, package.memory_ids)
                self.assertNotEqual(base_result, modified_result)
                expected = round(3 + seed / 10 + 0.2 + seed / 100, 6)
                self.assertEqual(modified_result, expected)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
