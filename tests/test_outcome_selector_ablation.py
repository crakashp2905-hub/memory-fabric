from __future__ import annotations

from benchmarks.outcome_matched_arms import build_selector_ablation
from benchmarks.outcome_selector_ablation import ARMS


def test_selector_ablation_pairs_context_and_caps_budgeted_replay() -> None:
    seeds = (801, 802, 803, 804, 805)
    report = build_selector_ablation(seeds=seeds)
    assert report["status"] == "DEVELOPMENT_ONLY_PROTOCOL_DRAFT"
    assert report["promotion_status"] == "NOT_ASSESSED"
    assert report["paired_context_verified"] is True
    assert set(report["arms"]) == set(ARMS)
    assert len(report["rows"]) == len(seeds) * len(ARMS)
    for seed in seeds:
        rows = [row for row in report["rows"] if row["seed"] == seed]
        assert len({tuple(row["evidence_ids"]) for row in rows}) == 1
        assert {row["answer_context_items"] for row in rows} == {3}
        assert {row["removal_budget"] for row in rows} == {1}
        assert {row["matched_posterior_evaluations"] for row in rows} == {8}
        assert {row["matched_posterior_evaluation_budget"] for row in rows} == {8}
        assert all(row["truth_hidden_until_proposal"] for row in rows)
        assert all(row["complete"] for row in rows)
    budgeted = [row for row in report["rows"] if row["arm"] == "budgeted_replay"]
    assert all(row["replay_budget"] == {
        "max_events": 3, "max_attempts": 1, "max_nodes": 4,
        "max_wall_seconds": 5.0, "max_cpu_seconds": 5.0, "max_tool_calls": 0,
    } for row in budgeted)
    assert report["comparison_contract"]["equalized_compute_count_per_arm"] == 8
    assert report["comparison_contract"]["equalized_compute_unit"] == (
        "posterior updates over the same evidence subsets"
    )


def test_selector_ablation_rejects_unfrozen_small_or_duplicate_seed_sets() -> None:
    for seeds in ((1, 2, 3, 4), (1, 2, 3, 4, 4)):
        try:
            build_selector_ablation(seeds=seeds)
        except ValueError:
            continue
        raise AssertionError("invalid seed set was accepted")
