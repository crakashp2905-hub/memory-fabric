"""Qualify reproducibility and propensity logging for randomized interventions."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import cast

try:
    from .intervention_harness import RandomizedInterventionHarness
except ImportError:  # Direct execution places benchmarks/, not the repository root, on sys.path.
    from intervention_harness import RandomizedInterventionHarness  # type: ignore[no-redef]

SEED = 20_261_109
UNITS = 10_000
TOLERANCE = 0.05


def records_for(seed: int) -> list[dict[str, object]]:
    harness = RandomizedInterventionHarness(seed)
    records = []
    for index in range(UNITS):
        difficulty = "easy" if index % 2 == 0 else "hard"
        p_treated = 0.7 if difficulty == "easy" else 0.3
        record = harness.assign_and_observe(
            f"unit-{index:04d}",
            probability_treated=p_treated,
            probability_observed_treated=0.8,
            probability_observed_control=0.9,
        )
        serialized = harness.serialize(record)
        serialized["difficulty"] = difficulty
        serialized["outcome_observed"] = (
            (0.75 if difficulty == "easy" else 0.25) + (0.15 if record.treated else 0.0)
            if record.observed
            else None
        )
        records.append(serialized)
    return records


def _digest(records: list[dict[str, object]]) -> str:
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def run() -> dict[str, object]:
    first = records_for(SEED)
    replay = records_for(SEED)
    alternate = records_for(SEED + 1)
    strata: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in first:
        strata[str(row["difficulty"])].append(row)

    rates: dict[str, dict[str, float | int]] = {}
    for difficulty, rows in sorted(strata.items()):
        rates[difficulty] = {
            "units": len(rows),
            "registered_probability_treated": cast(float, rows[0]["probability_treated"]),
            "observed_treatment_rate": sum(bool(row["treated"]) for row in rows) / len(rows),
            "registered_probability_observed_treated": 0.8,
            "registered_probability_observed_control": 0.9,
            "observation_rate_treated": sum(
                bool(row["observed"]) for row in rows if row["treated"]
            ) / sum(bool(row["treated"]) for row in rows),
            "observation_rate_control": sum(
                bool(row["observed"]) for row in rows if not row["treated"]
            ) / sum(not bool(row["treated"]) for row in rows),
        }

    propensity_rows_correct = all(
        cast(float, row["assignment_propensity"])
        == (cast(float, row["probability_treated"])
            if cast(bool, row["treated"])
            else 1.0 - cast(float, row["probability_treated"]))
        for row in first
    )
    rate_checks = all(
        abs(row["observed_treatment_rate"] - row["registered_probability_treated"]) <= TOLERANCE
        and abs(row["observation_rate_treated"] - row["registered_probability_observed_treated"]) <= TOLERANCE
        and abs(row["observation_rate_control"] - row["registered_probability_observed_control"]) <= TOLERANCE
        for row in rates.values()
    )
    result: dict[str, object] = {
        "schema": "memory-fabric-n3-05-intervention-harness/1",
        "seed": SEED,
        "unit_count": UNITS,
        "same_seed_replay_identical": first == replay,
        "different_seed_changes_sequence": _digest(first) != _digest(alternate),
        "record_digest_sha256": _digest(first),
        "all_realized_assignment_propensities_correct": propensity_rows_correct,
        "all_assignment_and_observation_rates_within_tolerance": rate_checks,
        "empirical_tolerance": TOLERANCE,
        "strata": rates,
        "rows": first,
        "limitations": [
            "SHA-256 domain-separated seeded draws are reproducible pseudorandomization, not a cryptographic entropy source.",
            "The fixture qualifies assignment and observation logging only; it does not establish effect recovery under missing data.",
        ],
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run()
    if args.output:
        rows = result.pop("rows")
        assert isinstance(rows, list)
        records_path = args.output.with_name(f"{args.output.stem}.ndjson")
        records_path.write_text(
            "".join(
                json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                for row in rows
            ),
            encoding="utf-8",
        )
        result["records_artifact"] = records_path.name
        result["record_count"] = len(rows)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(rendered, end="")
    checks = (
        "same_seed_replay_identical",
        "different_seed_changes_sequence",
        "all_realized_assignment_propensities_correct",
        "all_assignment_and_observation_rates_within_tolerance",
    )
    raise SystemExit(0 if all(bool(result[key]) for key in checks) else 1)
