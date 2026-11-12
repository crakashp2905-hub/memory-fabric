from __future__ import annotations

from dataclasses import replace

import pytest

from benchmarks.outcome_worlds import (
    TaskCase, WorldTemplate, generate_seeded_splits, split_leakage_issues,
    validate_split_isolation,
)


def templates() -> tuple[WorldTemplate, ...]:
    return tuple(
        WorldTemplate(
            template_id=f"case-template-{index}",
            template_family_id=f"world-family-{index}",
            fact_family_id=f"fact-family-{index}",
            instruction=f"Inspect pump {index} and report the safe status.",
            visible_facts=(f"sensor reading {index} is stable",),
        )
        for index in range(32)
    )


def test_seeded_split_assignment_is_deterministic_and_reproducible() -> None:
    first = generate_seeded_splits(templates(), seed=20261113)
    second = generate_seeded_splits(templates(), seed=20261113)

    assert first == second
    assert {case.split for case in first} == {"dev", "heldout"}
    validate_split_isolation(first)


def test_related_template_and_fact_lineage_stay_in_one_split() -> None:
    source = (
        WorldTemplate("template-a", "maintenance-family", "pump-facts",
                      "Check pump pressure and report a status."),
        WorldTemplate("template-b", "maintenance-family", "valve-facts",
                      "Inspect valve response and report a status."),
        WorldTemplate("template-c", "incident-family", "pump-facts",
                      "Review the pump alert and report a status."),
    )

    cases = generate_seeded_splits(source, seed=19)

    assert len({case.split for case in cases}) == 1


def test_validator_rejects_paraphrase_leak_by_template_lineage() -> None:
    base = TaskCase("case:1:a", 1, "dev", "a", "battery-family", "battery-facts",
                    "Inspect the battery sensor and determine its condition.", ())
    paraphrase = replace(
        base,
        case_id="case:1:b",
        split="heldout",
        template_id="b",
        instruction="Assess the battery detector to identify its current state.",
    )

    assert split_leakage_issues((base, paraphrase)) == [
        "TEMPLATE_OR_FACT_FAMILY_CROSSES_SPLITS"
    ]
    with pytest.raises(ValueError, match="TEMPLATE_OR_FACT_FAMILY_CROSSES_SPLITS"):
        validate_split_isolation((base, paraphrase))


def test_validator_rejects_word_shuffled_text_with_distinct_lineage() -> None:
    left = TaskCase("case:1:left", 1, "dev", "left", "family-left", "facts-left",
                    "Review valve status after the latest correction.", ())
    shuffled = TaskCase("case:1:right", 1, "heldout", "right", "family-right", "facts-right",
                        "correction latest the after status valve Review", ())

    assert "NORMALIZED_TEXT_CROSSES_SPLITS" in split_leakage_issues((left, shuffled))


def test_generator_rejects_duplicate_template_identifiers() -> None:
    template = templates()[0]
    with pytest.raises(ValueError, match="template IDs must be unique"):
        generate_seeded_splits((template, template), seed=1)
