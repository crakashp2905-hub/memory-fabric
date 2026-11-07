"""Build the deterministic retrieval-error counterexample taxonomy."""
from __future__ import annotations

import json
from pathlib import Path

LABELS = (
    "ABSENT",
    "NEAR_MISS",
    "WRONG_VERSION",
    "MISSING_INTERMEDIATE",
    "WRONG_SCOPE",
    "OVERBLOCKING",
)
SEEDS = (3101, 3102, 3103, 3104, 3105)
OUT = Path(__file__).with_name("cases.json")


def build() -> dict:
    cases: list[dict] = []
    for index, seed in enumerate(SEEDS, start=1):
        target = f"PX-{index}"
        other = f"QZ-{index}"
        cases.extend(
            [
                {
                    "id": f"absent-{index}",
                    "seed": seed,
                    "oracle_label": "ABSENT",
                    "query_agent": "reader",
                    "query": f"What is the torque limit for absent actuator {target}?",
                    "memories": [
                        {"alias": "unrelated", "agent": "writer", "scope": "team",
                         "content": f"Actuator {other} has a vibration limit of {index + 2} mm/s."}
                    ],
                    "oracle_aliases": [],
                    "minimal_counterexample": "No stored record concerns the queried entity or property.",
                },
                {
                    "id": f"near-miss-{index}",
                    "seed": seed,
                    "oracle_label": "NEAR_MISS",
                    "query_agent": "reader",
                    "query": f"What is the pressure limit for pump {target}?",
                    "memories": [
                        {"alias": "answer", "agent": "writer", "scope": "team",
                         "content": f"Pump {target} has a pressure limit of {10 + index} bar."},
                        {"alias": "near", "agent": "writer", "scope": "team",
                         "content": f"Pump {other} has a pressure limit of {10 + index} bar."},
                    ],
                    "oracle_aliases": ["answer"],
                    "forbidden_aliases": ["near"],
                    "minimal_counterexample": "One distractor differs only in the entity identifier.",
                },
                {
                    "id": f"wrong-version-{index}",
                    "seed": seed,
                    "oracle_label": "WRONG_VERSION",
                    "query_agent": "reader",
                    "query": f"What is the current inspection interval for valve {target}?",
                    "memories": [
                        {"alias": "answer", "agent": "writer", "scope": "team",
                         "content": f"Valve {target} inspection interval is {30 + index} days.",
                         "revision": f"Valve {target} inspection interval is {10 + index} days."}
                    ],
                    "oracle_aliases": ["answer"],
                    "oracle_versions": {"answer": 2},
                    "minimal_counterexample": "One record has exactly one superseding correction.",
                },
                {
                    "id": f"missing-intermediate-{index}",
                    "seed": seed,
                    "oracle_label": "MISSING_INTERMEDIATE",
                    "query_agent": "reader",
                    "query": f"Why must actuator {target} be stopped before restart?",
                    "memories": [
                        {"alias": "source", "agent": "writer", "scope": "team",
                         "content": f"Sensor S-{index} reports reverse flow."},
                        {"alias": "bridge", "agent": "writer", "scope": "team",
                         "content": f"Reverse flow energizes relay R-{index}.",
                         "parents": ["source"]},
                        {"alias": "answer", "agent": "writer", "scope": "team",
                         "content": f"Relay R-{index} requires actuator {target} to stop before restart.",
                         "parents": ["bridge"]},
                    ],
                    "oracle_aliases": ["source", "bridge", "answer"],
                    "mandatory_aliases": ["bridge"],
                    "minimal_counterexample": "A three-node proof has one bridge with no query terms.",
                },
                {
                    "id": f"wrong-scope-{index}",
                    "seed": seed,
                    "oracle_label": "WRONG_SCOPE",
                    "query_agent": "reader",
                    "query": f"What is technician Alice's private code for panel {target}?",
                    "memories": [
                        {"alias": "private", "agent": "alice", "scope": "private",
                         "content": f"Panel {target} private maintenance code is C-{seed}."}
                    ],
                    "oracle_aliases": [],
                    "forbidden_aliases": ["private"],
                    "minimal_counterexample": "The exact answer exists once but is private to another agent.",
                },
                {
                    "id": f"overblocking-{index}",
                    "seed": seed,
                    "oracle_label": "OVERBLOCKING",
                    "query_agent": "reader",
                    "query": f"What is the approved restart delay for line {target}?",
                    "memories": [
                        {"alias": "answer", "agent": "writer", "scope": "team",
                         "content": f"Line {target} approved restart delay is {5 + index} minutes."}
                    ],
                    "oracle_aliases": ["answer"],
                    "minimal_counterexample": "One active in-scope exact answer must not be withheld.",
                },
            ]
        )
    return {
        "schema": "memory-fabric-retrieval-errors/1",
        "dataset": "retrieval_errors_v1",
        "seeds": list(SEEDS),
        "oracle_labels": list(LABELS),
        "cases": sorted(cases, key=lambda case: case["id"]),
    }


def main() -> None:
    OUT.write_text(json.dumps(build(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
