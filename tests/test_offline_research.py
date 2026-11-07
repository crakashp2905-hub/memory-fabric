from __future__ import annotations

import copy
import unittest

from benchmarks import offline_research as research


class OfflineResearch(unittest.TestCase):
    def test_split_generation_is_deterministic_schema_valid_and_disjoint(self) -> None:
        worlds = [research.generate_split(split) for split in research.SPLITS]
        self.assertEqual(worlds[0], research.generate_split("train"))
        self.assertTrue(all(research.validate_world(world) == [] for world in worlds))
        self.assertEqual(research.leakage(worlds), [])
        self.assertTrue(all(world["sha256"] for world in worlds))

    def test_leakage_detector_rejects_duplicate_entity_template_topology_and_seed(self) -> None:
        train = research.generate_split("train")
        test = research.generate_split("test")
        for key in ("entity_ids", "template_id", "topology_id", "motif_signature", "seed"):
            mutated = copy.deepcopy(test)
            mutated["cases"][0][key] = train["cases"][0][key]
            self.assertTrue(any(key in issue for issue in research.leakage([train, mutated])), key)

    def test_negative_controls_detect_planted_failures(self) -> None:
        worlds = [research.generate_split("test")]
        report = research.control_report(worlds)
        self.assertEqual(report["population"], "synthetic_scripted")
        self.assertTrue(report["arms"]["negative_controls_detected"])
        self.assertEqual(report["arms"]["oracle"]["correct"], report["arms"]["oracle"]["attempted"])


if __name__ == "__main__":
    unittest.main()
