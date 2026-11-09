from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest

from memory_fabric import MemoryFabric, RevisionConflictError

TEMP_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp"
TEMP_ROOT.mkdir(exist_ok=True)


class RevisionConflictTests(unittest.TestCase):
    def test_competing_corrections_to_same_version_never_silently_overwrite(self) -> None:
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            database = Path(directory) / "shared.sqlite3"
            seed = MemoryFabric(database, seed=0)
            try:
                memory_id = seed.remember("seed", "Valve V7 opens at 4 bar.")
            finally:
                seed.close()

            barrier = threading.Barrier(2)

            def correction(content: str) -> tuple[str, int | None]:
                fabric = MemoryFabric(database, seed=0)
                try:
                    # Both handles observe v1 before racing to commit a correction.
                    self.assertEqual(fabric.get(memory_id).version, 1)
                    barrier.wait(timeout=10)
                    try:
                        revised = fabric.revise(
                            memory_id, content, agent_id="reviewer", reason="correction",
                            expected_version=1,
                        )
                        return ("accepted", revised.version)
                    except RevisionConflictError as exc:
                        return ("conflict", exc.actual_version)
                finally:
                    fabric.close()

            candidates = (
                "Valve V7 opens at 5 bar.",
                "Valve V7 opens at 6 bar.",
            )
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(correction, candidates))

            self.assertCountEqual([kind for kind, _ in outcomes], ["accepted", "conflict"])
            self.assertEqual({version for _, version in outcomes}, {2})
            check = MemoryFabric(database, seed=0)
            try:
                current = check.get(memory_id)
                self.assertEqual(current.version, 2)
                self.assertIn(current.content, candidates)
                version_events = [
                    event for event in check.log.read()
                    if event.type == "MemoryVersioned"
                ]
                self.assertEqual(len(version_events), 1)
                self.assertTrue(check.log.chain.verify(check.log.read()).ok)
            finally:
                check.close()

    def test_each_independent_order_reports_the_stale_correction_as_conflict(self) -> None:
        for first, second in (("5 bar", "6 bar"), ("6 bar", "5 bar")):
            with self.subTest(first=first, second=second):
                with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
                    database = Path(directory) / "ordered.sqlite3"
                    fabric = MemoryFabric(database, seed=0)
                    try:
                        memory_id = fabric.remember("seed", "Valve V7 opens at 4 bar.")
                        accepted = fabric.revise(
                            memory_id, f"Valve V7 opens at {first}.", agent_id="a",
                            reason="first correction", expected_version=1,
                        )
                        self.assertEqual(accepted.version, 2)
                        with self.assertRaises(RevisionConflictError) as raised:
                            fabric.revise(
                                memory_id, f"Valve V7 opens at {second}.", agent_id="b",
                                reason="concurrent correction", expected_version=1,
                            )
                        self.assertEqual(raised.exception.expected_version, 1)
                        self.assertEqual(raised.exception.actual_version, 2)
                        self.assertEqual(fabric.get(memory_id).content, accepted.content)
                        version_events = [
                            event for event in fabric.log.read()
                            if event.type == "MemoryVersioned"
                        ]
                        self.assertEqual(len(version_events), 1)
                    finally:
                        fabric.close()

    def test_expected_version_must_be_a_positive_integer(self) -> None:
        fabric = MemoryFabric(":memory:", seed=0)
        try:
            memory_id = fabric.remember("seed", "Valve V7 opens at 4 bar.")
            for invalid in (0, -1, True, 1.0):
                with self.subTest(invalid=invalid), self.assertRaisesRegex(
                    ValueError, "expected_version must be a positive integer"
                ):
                    fabric.revise(memory_id, "Valve V7 opens at 5 bar.", "a", "fix",
                                  expected_version=invalid)  # type: ignore[arg-type]
        finally:
            fabric.close()


if __name__ == "__main__":
    unittest.main()
