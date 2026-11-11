"""Independent-world allocation rejects known forms of split leakage."""

from __future__ import annotations

import unittest

from benchmarks.outcome_worlds import (
    InsufficientSplitComponents,
    OutcomeWorldSpec,
    SplitLeakageError,
    TransitionSkeleton,
    seeded_world_splits,
    validate_split_disjointness,
)


def _case(
    index: int,
    *,
    template: str | None = None,
    fact: str | None = None,
    source_roots: tuple[str, ...] = (),
    exact_ids: tuple[str, ...] = (),
    text: str | None = None,
    skeleton: TransitionSkeleton | None = None,
) -> OutcomeWorldSpec:
    return OutcomeWorldSpec(
        case_key=f"case-{index:03d}",
        template_family_id=template or f"template-{index:03d}",
        fact_family_id=fact or f"fact-{index:03d}",
        transition=skeleton or TransitionSkeleton(
            ((f"event-{index:03d}", 0),), legal_effects=(f"effect-{index:03d}",)),
        source_root_ids=source_roots,
        exact_identifiers=exact_ids,
        surface_texts=() if text is None else (text,),
    )


class TestOutcomeWorldSplits(unittest.TestCase):
    def test_seeded_assignment_is_stable_order_independent_and_nonempty(self) -> None:
        cases = [_case(index) for index in range(18)]
        first = seeded_world_splits(cases, split_seed=0xA017)
        second = seeded_world_splits(list(reversed(cases)), split_seed=0xA017)

        def projection(result):
            return {
                name: tuple((item.spec.case_key, item.case_id, item.world_seed)
                            for item in worlds)
                for name, worlds in result.items()
            }
        self.assertEqual(projection(first), projection(second))
        self.assertEqual(set(first), {"train", "dev", "heldout"})
        self.assertTrue(all(first[name] for name in first))
        case_ids = [item.case_id for worlds in first.values() for item in worlds]
        self.assertEqual(len(case_ids), len(set(case_ids)))
        seeds = [item.world_seed for worlds in first.values() for item in worlds]
        self.assertEqual(len(seeds), len(set(seeds)))

    def test_linked_template_and_fact_families_stay_in_one_component(self) -> None:
        linked = [
            _case(0, template="template-shared"),
            _case(1, template="template-shared", fact="fact-bridge"),
            _case(2, fact="fact-bridge"),
        ]
        worlds = seeded_world_splits(linked + [_case(i) for i in range(3, 8)],
                                     split_seed=12)
        assignment = {
            item.spec.case_key: item.split
            for split_worlds in worlds.values()
            for item in split_worlds
        }
        self.assertEqual(len({assignment[f"case-{index:03d}"] for index in range(3)}), 1)

    def test_exact_identifier_collisions_are_kept_together_and_rejected_if_split(self) -> None:
        first = _case(0, exact_ids=("evidence-record-4",))
        second = _case(1, exact_ids=("evidence-record-4",))
        worlds = seeded_world_splits([first, second, *[_case(i) for i in range(2, 7)]],
                                     split_seed=91)
        assigned = {
            item.spec.case_key: item.split
            for split_worlds in worlds.values()
            for item in split_worlds
        }
        self.assertEqual(assigned[first.case_key], assigned[second.case_key])
        with self.assertRaisesRegex(SplitLeakageError, "exact_identifier"):
            validate_split_disjointness({"train": [first], "heldout": [second]})

    def test_shuffled_token_duplicate_is_detected(self) -> None:
        first = _case(0, text="Battery sensor calibration is fresh")
        second = _case(1, text="Fresh calibration sensor battery is")
        with self.assertRaisesRegex(SplitLeakageError, "surface_text_bag"):
            validate_split_disjointness({"train": [first], "heldout": [second]})
        grouped = seeded_world_splits([first, second, *[_case(i) for i in range(2, 7)]],
                                      split_seed=21)
        assigned = {
            item.spec.case_key: item.split
            for split_worlds in grouped.values()
            for item in split_worlds
        }
        self.assertEqual(assigned[first.case_key], assigned[second.case_key])

    def test_same_provenance_catches_reworded_paraphrase_leakage(self) -> None:
        first = _case(0, source_roots=("source-root-19",), text="A calibrated sensor")
        paraphrase = _case(1, source_roots=("source-root-19",),
                           text="The instrument passed its reference check")
        with self.assertRaisesRegex(SplitLeakageError, "source_root"):
            validate_split_disjointness({"train": [first], "heldout": [paraphrase]})

    def test_surface_free_transition_signature_is_checked(self) -> None:
        skeleton = TransitionSkeleton(
            (("observation", 0), ("correction", 2), ("action", 3)),
            dependencies=((0, 1), (1, 2)),
            legal_effects=("inspect", "set_target"),
        )
        first = _case(0, skeleton=skeleton, text="Sensor reading ten")
        same_structure = _case(1, skeleton=skeleton, text="Instrument reports a value")
        with self.assertRaisesRegex(SplitLeakageError, "transition_signature"):
            validate_split_disjointness({"train": [first], "heldout": [same_structure]})

    def test_distinct_effect_skeletons_are_allowed_across_splits(self) -> None:
        first = _case(0, skeleton=TransitionSkeleton(
            (("observation", 0), ("action", 1)), legal_effects=("inspect",)))
        second = _case(1, skeleton=TransitionSkeleton(
            (("observation", 0), ("correction", 1), ("rollback", 3)),
            dependencies=((0, 1), (1, 2)), legal_effects=("rollback", "notify")))
        validate_split_disjointness({"train": [first], "heldout": [second]})

    def test_insufficient_independent_components_fail_closed(self) -> None:
        linked = [_case(0, template="one-template"),
                  _case(1, template="one-template"), _case(2)]
        with self.assertRaises(InsufficientSplitComponents):
            seeded_world_splits(linked, split_seed=3)

    def test_case_keys_must_be_unique(self) -> None:
        first = _case(0)
        duplicate = OutcomeWorldSpec(
            case_key=first.case_key,
            template_family_id="another-template",
            fact_family_id="another-fact",
            transition=TransitionSkeleton((("another-event", 0),),
                                          legal_effects=("another-action",)),
        )
        with self.assertRaisesRegex(ValueError, "globally unique"):
            seeded_world_splits([first, duplicate, _case(1)], split_seed=4)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
