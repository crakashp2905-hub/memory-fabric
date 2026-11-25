"""Sensor and component identity in claims, validation and resolution (VEGA next W01-06, W03)."""

from __future__ import annotations

import unittest

import memory_fabric.conflicts as conflicts
from memory_fabric import MemoryFabric
from memory_fabric.causal_replay.semantic.entities import EntityError, Registry, battery_registry
from memory_fabric.conflicts import claim, contradicts

T = "tn_plant"


def write_world(version: str):
    """The PR #41 collision: probe A established by copies, then probe B written."""
    old = conflicts.CLAIM_IDENTITY
    conflicts.CLAIM_IDENTITY = version
    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        a = fabric.remember("ops", "10:00 pack P-7 probe A reads 61 C", scope="team", tenant_id=T,
                            source_episodes=("ea",))
        for i in range(2):
            fabric.derive(f"relay{i}", "10:00 pack P-7 probe A reads 61 C (relayed)", [a], scope="team", tenant_id=T)
        fabric.remember("ops", "cafeteria menu for Tuesday: soup", scope="team", tenant_id=T, source_episodes=("ei",))
        b = fabric.remember("tech", "10:15 pack P-7 probe B reads 64 C", scope="team", tenant_id=T,
                            source_episodes=("eb",))
        return fabric, a, b
    finally:
        conflicts.CLAIM_IDENTITY = old


class Collision(unittest.TestCase):
    def test_the_old_rule_withholds_the_second_sensor_and_the_new_rule_does_not(self):
        fabric, a, b = write_world("v1")
        self.addCleanup(fabric.close)
        self.assertEqual(fabric.state.memories[b].lifecycle_state.value, "candidate", f"v1 should hold {b}")
        self.assertEqual(fabric.state.memories[a].lifecycle_state.value, "active")
        fixed, _, b2 = write_world("v2")
        self.addCleanup(fixed.close)
        self.assertEqual(fixed.state.memories[b2].lifecycle_state.value, "active")
        found = fixed.retrieve("planner", "pack P-7 probe B reads", tenant_id=T, k=8)
        self.assertIn(b2, {m.id for m in found.exposed})

    def test_distinct_sensors_do_not_collide_and_the_same_sensor_stays_comparable(self):
        self.assertNotEqual(claim("pack P-7 probe A reads 61 C")[0], claim("pack P-7 probe B reads 64 C")[0])
        self.assertNotEqual(claim("pack P-7 sensor P7-A reads 61 C")[0], claim("pack P-7 sensor P7-B reads 64 C")[0])
        self.assertFalse(contradicts("pack P-7 probe A reads 61 C", "pack P-7 probe B reads 64 C"))
        self.assertTrue(contradicts("pack P-7 probe A reads 61 C", "pack P-7 probe A reads 58 C"))
        self.assertTrue(contradicts("pack P-7 sensor P7-A reads 61 C", "pack P-7 sensor P7-A reads 58 C"))

    def test_existing_identities_are_unchanged(self):
        for text, ids in (("hoist H-14 part number is FP-1458", {"h14"}),
                          ("billing-api listens on port 8443", {"billing-api"}),
                          ("valve V-3 pressure is 41 bar", {"v3"})):
            self.assertEqual(claim(text)[0], frozenset(ids))

    def test_v1_is_the_exact_rollback(self):
        corpus = ["pack P-7 probe A reads 61 C", "hoist H-14 part number is FP-1458", "billing-api on 8443",
                  "pack P-7 sensor P7-A reads 61 C", "cell 3 voltage is 3.9 V"]
        for text in corpus:
            v1 = claim(text, "v1")
            self.assertNotIn("probe-a", v1[0])
            self.assertNotIn("p7-a", v1[0])
        self.assertEqual(claim("pack P-7 probe A reads 61 C", "v1")[0], frozenset({"p7"}))
        self.assertEqual(conflicts.CLAIM_IDENTITY_VERSIONS, ("v1", "v2"))


class Registry_(unittest.TestCase):
    def setUp(self):
        self.r = battery_registry()

    def test_hierarchy_and_typed_claim_keys(self):
        self.assertEqual(self.r.ancestors("pack:p-7/sensor:ta1"), ["pack:p-7", "site:plant"])
        self.assertNotEqual(self.r.claim_key("pack:p-7/sensor:ta1", "temperature"),
                            self.r.claim_key("pack:p-7/sensor:tb2", "temperature"))
        with self.assertRaises(EntityError):
            self.r.add("pack:p-7/sensor:ta1", "sensor", parent="pack:p-7")
        with self.assertRaises(EntityError):
            self.r.add("x", "sensor", parent="pack:nope")

    def test_aliases_map_to_one_sensor_and_two_sensors_are_ambiguous(self):
        for text in ("TA1 reads 61 C", "the A-side thermistor shows sixty-one degrees", "Probe A: 61 C",
                     "sensor P7-A reads 61 C", "ＴＡ１ reads 61 C"):
            self.assertEqual(self.r.resolve(text).canonical, "pack:p-7/sensor:ta1", text)
        both = self.r.resolve("TA1 and TB2 both read 61 C")
        self.assertIsNone(both.canonical)
        self.assertEqual(len(both.candidates), 2)

    def test_near_miss_and_unregistered_identifiers_are_never_guessed(self):
        for text in ("TA10 reads 61 C", "XTA1 reads 61 C", "sensor TA reads 61 C", "pack P-7 reads 61 C"):
            self.assertIsNone(self.r.resolve(text).canonical, text)

    def test_copies_and_aliases_from_one_origin_stay_one_root(self):
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        origin = fabric.remember("ops", "pack P-7 probe A reads 61 C", scope="team", tenant_id=T)
        alias = fabric.derive("relay", "TA1 on P-7 at 61 C", [origin], scope="team", tenant_id=T)
        self.assertEqual(fabric.source_root(alias), fabric.source_root(origin))

    def test_reindexing_keeps_tenant_and_lifecycle_restrictions(self):
        fabric, _, b = write_world("v2")
        self.addCleanup(fabric.close)
        foreign = fabric.retrieve("planner", "pack P-7 probe B reads", tenant_id="tn_other", k=8)
        self.assertEqual(foreign.exposed, [])
        fabric.erase_content(b, "tech", "request")
        again = fabric.retrieve("planner", "pack P-7 probe B reads", tenant_id=T, k=8)
        self.assertNotIn(b, {m.id for m in again.exposed})

    def test_registry_is_independent_of_the_claim_rule(self):
        empty = Registry()
        self.assertIsNone(empty.resolve("TA1 reads 61 C").canonical)


if __name__ == "__main__":
    unittest.main()


class Preview(unittest.TestCase):
    def test_the_dry_run_reports_resolved_collisions_and_creates_none(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        import claim_identity_preview as preview
        report = preview.preview({"a": "10:00 pack P-7 probe A reads 61 C", "b": "10:15 pack P-7 probe B reads 64 C",
                                  "c": "hoist H-14 part number is FP-1458", "d": "hoist H-14 part number is FP-1460"})
        self.assertEqual(report["collisions_resolved"], [["a", "b"]])
        self.assertEqual(report["collisions_created_count"], 0)
        self.assertEqual(report["changed"], 2)
