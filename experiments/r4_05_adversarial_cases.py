"""Generate a separate-stream adversarial retrieval set and score shortcut controls.

This is synthetic harness evidence, not model-agent evaluation. It checks that
surface templates, answer position, and lexicographic identifiers alone do not
encode the correct outcome.
"""
from __future__ import annotations

import hashlib
import json
import random
import statistics
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK_SEED = 45051
DISTRACTOR_SEED = 45052
IDENTIFIER_SEED = 45053
N_CASES = 256
N_OPTIONS = 4


def build_cases() -> list[dict[str, Any]]:
    """Build exact-template cases; distractor and identifier RNGs are independent."""
    task_rng = random.Random(TASK_SEED)
    distractor_rng = random.Random(DISTRACTOR_SEED)
    identifier_rng = random.Random(IDENTIFIER_SEED)
    cases = []
    for index in range(N_CASES):
        entity = f"asset-{index:04d}"
        attribute = ("pressure", "temperature", "status", "interval")[index % 4]
        correct = f"v{task_rng.randrange(10000, 99999)}"
        wrong = f"v{task_rng.randrange(10000, 99999)}"
        while wrong == correct:
            wrong = f"v{task_rng.randrange(10000, 99999)}"
        distractors = set()
        while len(distractors) < 2:
            value = f"v{distractor_rng.randrange(10000, 99999)}"
            if value not in {correct, wrong}:
                distractors.add(value)
        # One plausible stale near miss shares the target entity and attribute;
        # two semantic distractors mention sibling entities with same attribute.
        rows = [
            {"entity": entity, "attribute": attribute, "value": correct,
             "version": "current", "source": "approved"},
            {"entity": entity, "attribute": attribute, "value": wrong,
             "version": "superseded", "source": "approved"},
        ]
        for sibling, value in enumerate(sorted(distractors)):
            rows.append({"entity": f"asset-{(index + sibling + 1) % N_CASES:04d}",
                         "attribute": attribute, "value": value,
                         "version": "current", "source": "approved"})
        task_rng.shuffle(rows)
        # IDs use a separate random stream and bear no relation to answer/order.
        for row in rows:
            row["id"] = f"mem-{identifier_rng.getrandbits(64):016x}"
            row["text"] = (f"Record {row['entity']} {row['attribute']} value {row['value']} "
                           f"version {row['version']} source {row['source']}.")
        answer_position = next(i for i, row in enumerate(rows)
                               if row["entity"] == entity and row["version"] == "current")
        cases.append({"case_id": f"case-{index:04d}", "entity": entity,
                      "attribute": attribute, "answer": correct,
                      "answer_position": answer_position, "options": rows})
    return cases


def shortcut_results(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    first_correct = sum(case["options"][0]["value"] == case["answer"] for case in cases)
    id_first = sum(min(case["options"], key=lambda row: row["id"])["value"] == case["answer"]
                   for case in cases)
    position_counts = {str(i): sum(case["answer_position"] == i for case in cases)
                       for i in range(N_OPTIONS)}
    # A naive repeated-template shortcut that selects the first seen value is
    # equivalent to first-position ranking because surface templates are fixed.
    rate = first_correct / total
    return {
        "n": total,
        "answer_position_counts": position_counts,
        "first_position_shortcut": {"correct": first_correct, "accuracy": rate},
        "lexicographic_identifier_shortcut": {
            "correct": id_first, "accuracy": id_first / total},
        "surface_template_count": 1,
        "same_entity_attribute_near_miss_cases": total,
        "irrelevant_distractor_count": 2 * total,
        "chance_accuracy": 1 / N_OPTIONS,
        "shortcut_ceiling": 0.35,
        "shortcut_gate_passed": rate <= 0.35 and id_first / total <= 0.35,
        "position_standard_deviation": statistics.pstdev(position_counts.values()),
    }


def build_report() -> dict[str, Any]:
    cases = build_cases()
    hashes = {"case_manifest_sha256": hashlib.sha256(
        json.dumps(cases, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip())
    return {
        "schema": "mf-r4-05-adversarial-cases/1",
        "decision": "DESCRIPTIVE",
        "population": "synthetic_shortcut_controls",
        "seeds": {"task": TASK_SEED, "distractor": DISTRACTOR_SEED,
                  "identifier": IDENTIFIER_SEED},
        "stream_independence": "three independently initialized RNG streams",
        "dataset": {"cases": len(cases), "options_per_case": N_OPTIONS,
                    "task_families": ["correction_near_miss", "irrelevant_distractor"]},
        "shortcut_evaluation": shortcut_results(cases),
        "inputs": {**hashes,
                   "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "preregistration_sha256": hashlib.sha256(
                       (ROOT / "research/prereg/r4-05-adversarial-cases-v1.md").read_bytes()
                   ).hexdigest()},
        "repo_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       capture_output=True, text=True, check=True).stdout.strip(),
        "dirty": dirty,
        "cases": cases,
        "limitations": ["No language model or production retrieval policy is evaluated.",
                        "Shortcut controls only test first-position and lexicographic-ID heuristics.",
                        "Surface templates are intentionally repeated; semantic generalization requires an independently authored text paraphrase set."],
    }


def main() -> int:
    out = ROOT / "research/results/r4-05-adversarial-cases.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    report = build_report()
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "cases": report["dataset"]["cases"],
                      "shortcut_gate_passed": report["shortcut_evaluation"]["shortcut_gate_passed"]}))
    return int(not report["shortcut_evaluation"]["shortcut_gate_passed"])


if __name__ == "__main__":
    raise SystemExit(main())
