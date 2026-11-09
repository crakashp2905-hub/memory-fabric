from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import adversarial_gate as gate  # noqa: E402

EXPECTED_FAMILIES = {
    "injection", "delayed_and_progressive_poisoning",
    "laundering_through_summaries_tools_federation", "false_corroboration",
    "cross_tenant_access_and_metadata_leakage", "stale_authorization_and_replay",
    "authority_and_elevation", "offline_peers_and_recovery",
    "key_rotation_and_retired_keys", "plain_false_claims",
    "authorization_across_access_paths", "actions_under_crashes_and_timeouts",
    "log_and_chain_rewrite_detection", "production_cryptography", "log_tampering",
    "privacy", "resource_exhaustion", "privilege_separation", "governed_code_mode",
    "backup_tamper_and_restore", "objective_filters_never_drop_safety_evidence",
}


class TestAdversarialRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(gate.REGISTRY_PATH.read_text(encoding="utf-8"))

    def test_frozen_registry_covers_exact_expected_attack_families(self) -> None:
        self.assertEqual(set(gate.FAMILIES), EXPECTED_FAMILIES)
        self.assertEqual({row["name"] for row in self.registry["families"]}, EXPECTED_FAMILIES)
        gate.validate_registry(gate.FAMILIES, self.registry)

    def test_a_removed_family_fails_registry_validation(self) -> None:
        broken = dict(gate.FAMILIES)
        del broken["injection"]
        with self.assertRaisesRegex(ValueError, "missing=.*injection"):
            gate.validate_registry(broken, self.registry)

    def test_a_changed_test_selector_fails_registry_validation(self) -> None:
        broken = copy.deepcopy(gate.FAMILIES)
        broken["injection"] = ()
        with self.assertRaisesRegex(ValueError, "selectors differ"):
            gate.validate_registry(broken, self.registry)

    def test_empty_and_duplicate_registry_rows_are_rejected(self) -> None:
        empty = copy.deepcopy(self.registry)
        empty["families"][0]["tests"] = []
        with self.assertRaisesRegex(ValueError, "one or more test selectors"):
            gate.validate_registry(gate.FAMILIES, empty)
        duplicate = copy.deepcopy(self.registry)
        duplicate["families"].append(copy.deepcopy(duplicate["families"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate attack family"):
            gate.validate_registry(gate.FAMILIES, duplicate)
