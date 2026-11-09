from __future__ import annotations

import unittest

from experiments.n5_06_byzantine_agents import (
    BEHAVIORS,
    ByzantineReport,
    _predict,
    generate,
    paired_bootstrap,
)


class ByzantineAgentTests(unittest.TestCase):
    def test_replay_is_deterministic_and_preserves_root_identity(self) -> None:
        first = generate(31, 20, "replay", 0.25)
        self.assertEqual(first, generate(31, 20, "replay", 0.25))
        replayed = [row for row in first.reports if row.byzantine]
        self.assertTrue(replayed)
        self.assertEqual({row.replay_index for row in replayed}, {0, 1, 2})
        groups: dict[tuple[int, int, int, int], list[ByzantineReport]] = {}
        for row in replayed:
            groups.setdefault((row.task_id, row.root_id, row.reporter, row.wave), []).append(row)
        self.assertTrue(all(len(rows) == 3 for rows in groups.values()))
        self.assertTrue(all(
            len({(row.root_id, row.value, row.quality, row.wave) for row in rows}) == 1
            and {row.replay_index for row in rows} == {0, 1, 2}
            for rows in groups.values()
        ))

    def test_fault_fractions_are_identity_level_with_explicit_rounding(self) -> None:
        ten = generate(1, 2, "lie", 0.10)
        twenty_five = generate(1, 2, "lie", 0.25)
        forty = generate(1, 2, "lie", 0.40)
        self.assertEqual(len(ten.faulty_reporters), 1)
        self.assertEqual(len(twenty_five.faulty_reporters), 4)
        self.assertEqual(len(forty.faulty_reporters), 6)
        self.assertTrue(set(ten.faulty_reporters) < set(twenty_five.faulty_reporters))
        self.assertTrue(set(twenty_five.faulty_reporters) < set(forty.faulty_reporters))

    def test_attack_conditions_share_exact_truth_and_underlying_source_draws(self) -> None:
        baseline = generate(88, 20, "lie", 0.0)
        attacked = generate(88, 20, "selective_withdrawal", 0.25)
        self.assertEqual(baseline.truths, attacked.truths)
        self.assertEqual(baseline.reporter_reputation, attacked.reporter_reputation)
        self.assertGreater(len(set(baseline.reporter_reputation)), 1)
        baseline_slots = {
            (r.task_id, r.root_id, r.reporter, r.quality, r.wave): r.value
            for r in baseline.reports
        }
        for report in attacked.reports:
            slot = (report.task_id, report.root_id, report.reporter, report.quality, report.wave)
            self.assertEqual(report.value, baseline_slots[slot])

    def test_calibration_is_independent_of_evaluation_task_count(self) -> None:
        short = generate(99, 20, "lie", 0.0)
        long = generate(99, 40, "copy", 0.40)
        self.assertEqual(short.reporter_reputation, long.reporter_reputation)

    def test_lie_is_opposite_truth_and_withdrawal_suppresses_correct_slots(self) -> None:
        lied = generate(4, 20, "lie", 0.25)
        for row in lied.reports:
            if row.byzantine:
                self.assertEqual(row.value, 1 - lied.truths[row.task_id])
        withdrawn = generate(4, 20, "selective_withdrawal", 0.25)
        self.assertFalse(any(
            row.byzantine and row.value == withdrawn.truths[row.task_id]
            for row in withdrawn.reports
        ))

    def test_copy_and_replay_keep_source_roots_instead_of_minting_independence(self) -> None:
        for behavior in ("copy", "replay"):
            dataset = generate(45, 20, behavior, 0.40)
            for task_id in range(20):
                rows = [row for row in dataset.reports if row.task_id == task_id]
                self.assertLessEqual(len({row.root_id for row in rows}), 8)

    def test_copy_attack_repeats_observed_majority_claim(self) -> None:
        copied = generate(48, 20, "copy", 0.40)
        source = generate(48, 20, "copy", 0.0)
        for task_id in range(20):
            source_rows = [row for row in source.reports if row.task_id == task_id]
            counts = [0, 0]
            for row in source_rows:
                counts[row.value] += 1
            observed_mode = 0 if counts[0] >= counts[1] else 1
            for row in copied.reports:
                if row.task_id == task_id and row.byzantine:
                    self.assertEqual(row.value, observed_mode)

    def test_predictions_do_not_read_truth_or_byzantine_metadata(self) -> None:
        dataset = generate(55, 20, "lie", 0.25)
        task_rows = tuple(row for row in dataset.reports if row.task_id == 0)
        action = _predict(task_rows, "independent_root", dataset.reporter_reputation)
        changed_metadata = tuple(
            row.__class__(row.task_id, row.root_id, row.reporter, row.quality,
                          row.value, row.wave, not row.byzantine, "honest", row.replay_index)
            for row in task_rows
        )
        self.assertEqual(action, _predict(changed_metadata, "independent_root", dataset.reporter_reputation))

    def test_bootstrap_is_paired_reproducible_and_reports_seed_count(self) -> None:
        behavior = "lie"
        datasets = [
            generate(seed, 20, behavior, fraction)
            for seed in (301, 302, 303, 304, 305)
            for fraction in (0.0, 0.25)
        ]
        first = paired_bootstrap(datasets, "majority", behavior, 0.25, replicates=500, seed=9)
        self.assertEqual(first, paired_bootstrap(
            datasets, "majority", behavior, 0.25, replicates=500, seed=9
        ))
        self.assertEqual(first["replicates"], 500)
        self.assertEqual(len(first["paired_change_95ci"]), 2)
        with self.assertRaises(ValueError):
            paired_bootstrap(datasets, "majority", behavior, 0.25, replicates=100, seed=9)

    def test_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            generate(1, 3, "lie", 0.1)
        with self.assertRaises(ValueError):
            generate(1, 2, "unknown", 0.1)
        with self.assertRaises(ValueError):
            generate(1, 2, BEHAVIORS[0], 0.7)


if __name__ == "__main__":
    unittest.main()
