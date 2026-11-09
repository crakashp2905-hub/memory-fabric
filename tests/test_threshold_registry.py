from __future__ import annotations

import unittest

from benchmarks.threshold_registry import REGISTRY, validate_registry


class ThresholdRegistryTests(unittest.TestCase):
    def test_registry_is_valid_and_has_primary_secondary_exploratory_tiers(self) -> None:
        validate_registry()
        self.assertIn("heldout_agent_qualification_v1", REGISTRY)
        heldout = REGISTRY["heldout_agent_qualification_v1"]
        self.assertTrue(heldout["primary"])
        self.assertTrue(heldout["secondary"])
        self.assertTrue(heldout["exploratory"])

    def test_registry_rejects_outcome_classified_twice(self) -> None:
        invalid = {"example": {"preregistration": "paper.md", "primary": {"score": 0.8},
                               "secondary": ["score"], "exploratory": []}}
        with self.assertRaisesRegex(ValueError, "multiple evidence tiers"):
            validate_registry(invalid)

    def test_registry_rejects_unfrozen_primary_margin(self) -> None:
        invalid = {"example": {"preregistration": "paper.md", "primary": {"score": None},
                               "secondary": [], "exploratory": []}}
        with self.assertRaisesRegex(ValueError, "unspecified"):
            validate_registry(invalid)


if __name__ == "__main__":
    unittest.main()
