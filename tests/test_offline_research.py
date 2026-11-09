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
        self.assertTrue(all(any(case["evidence_features"]["indirect_but_supported"]
                                and case["evidence_features"]["lexical_overlap"] is False
                                for case in world["cases"]) for world in worlds))
        self.assertTrue(all(any(case["oracle"] == "ABSTAIN" for case in world["cases"])
                            for world in worlds))

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
        self.assertTrue(all(report["by_family"]["negative_controls_detected"].values()))
        self.assertEqual(report["arms"]["oracle"]["correct"], report["arms"]["oracle"]["attempted"])
        oracle = report["arms"]["oracle"]
        self.assertEqual(oracle["attempted"], 20)
        self.assertEqual(oracle["unsafe_actions"], 0)
        self.assertGreater(oracle["zero_unsafe_rate_upper_95"], 0)
        self.assertEqual(oracle["unsafe_action_denominator"], 5)
        self.assertEqual(set(report["by_family"]) - {"negative_controls_detected"}, set(research.FAMILIES))


if __name__ == "__main__":
    unittest.main()
