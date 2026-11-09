from __future__ import annotations

import json
import unittest
from pathlib import Path

from memory_fabric import MemoryFabric
from research.bench.retrieval_errors_v1.build import LABELS, SEEDS, build

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research" / "bench" / "retrieval_errors_v1" / "cases.json"


class RetrievalErrorTaxonomy(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(DATA.read_text(encoding="utf-8"))

    def test_committed_dataset_is_exact_generator_output(self) -> None:
        self.assertEqual(self.data, build())

    def test_each_stable_label_has_five_distinct_seeded_cases(self) -> None:
        self.assertEqual(tuple(self.data["oracle_labels"]), LABELS)
        self.assertEqual(tuple(self.data["seeds"]), SEEDS)
        self.assertEqual(len(self.data["cases"]), 30)
        for label in LABELS:
            rows = [c for c in self.data["cases"] if c["oracle_label"] == label]
            self.assertEqual(len(rows), 5, label)
            self.assertEqual({c["seed"] for c in rows}, set(SEEDS), label)
            self.assertEqual(len({c["id"] for c in rows}), 5, label)

    def test_every_counterexample_has_an_executable_oracle(self) -> None:
        for case in self.data["cases"]:
            with self.subTest(case=case["id"]):
                fabric = MemoryFabric(":memory:", auto_activate=True, seed=case["seed"])
                try:
                    aliases: dict[str, str] = {}
                    for record in case["memories"]:
                        parents = [aliases[name] for name in record.get("parents", [])]
                        if parents:
                            mid = fabric.derive(
                                record["agent"], record["content"], parents,
                                scope=record["scope"], auto_activate=True,
                            )
                        else:
                            mid = fabric.remember(
                                record["agent"], record["content"],
                                scope=record["scope"], auto_activate=True,
                            )
                        aliases[record["alias"]] = mid
                        if "revision" in record:
                            fabric.revise(
                                mid, record["revision"], agent_id=record["agent"],
                                reason="taxonomy fixture correction",
                            )

                    oracle = [aliases[name] for name in case["oracle_aliases"]]
                    self.assertEqual(len(oracle), len(case["oracle_aliases"]))
                    for alias, version in case.get("oracle_versions", {}).items():
                        self.assertEqual(fabric.get(aliases[alias]).version, version)
                    for alias in case.get("forbidden_aliases", []):
                        self.assertNotIn(aliases[alias], oracle)
                        if case["oracle_label"] == "WRONG_SCOPE":
                            decision = fabric.use(
                                aliases[alias], agent_id=case["query_agent"], audit=False
                            )
                            self.assertFalse(decision.usable)
                    for alias in case.get("mandatory_aliases", []):
                        mid = aliases[alias]
                        self.assertIn(mid, oracle)
                        children = fabric.state.children.get(mid, set())
                        self.assertTrue(children, f"{alias} is not an intermediate")
                finally:
                    fabric.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
