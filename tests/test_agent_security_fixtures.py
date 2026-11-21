"""Poisoning fixtures, false-corroboration stress and tenant existence probes (W16-02, W16-04, W16-06)."""

from __future__ import annotations

import unittest

from benchmarks import outcome_poisoning as poisoning
from benchmarks.outcome_tenant_probe import run as probe


class PoisoningFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = poisoning.run()

    def test_every_attack_family_has_a_control_it_fools(self) -> None:
        families = {row["family"] for row in self.report["families"]}
        self.assertEqual(families, set(poisoning.FAMILIES))
        for row in self.report["families"]:
            self.assertTrue(row["control_fooled"], row["family"])

    def test_the_governed_path_resists_every_family(self) -> None:
        self.assertEqual(self.report["governed_fooled"], [])

    def test_copies_never_amplify_corroboration_at_any_scale(self) -> None:
        for row in self.report["amplification_stress"]:
            with self.subTest(colluders=row["colluders"]):
                self.assertEqual(row["statements_false"], row["colluders"] + 1)
                self.assertEqual(row["roots_false"], 1)
                self.assertTrue(row["control_fooled"])
                self.assertFalse(row["governed_fooled"])


class TenantExistenceProbe(unittest.TestCase):
    def test_foreign_and_missing_ids_get_the_same_visible_refusal(self) -> None:
        report = probe(trials=20)
        self.assertTrue(report["payloads_identical"])
        (payload,) = report["payload_variants"]["foreign"]
        self.assertIn('"reason_code": "not_found"', payload)
        self.assertIn('"has_memory": false', payload)

    def test_timing_is_reported_as_a_residual_not_claimed_equal(self) -> None:
        report = probe(trials=10)
        self.assertIn("RESIDUAL_DOCUMENTED", report["timing_claim"])
        self.assertEqual(set(report["median_seconds"]), {"foreign", "missing"})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
