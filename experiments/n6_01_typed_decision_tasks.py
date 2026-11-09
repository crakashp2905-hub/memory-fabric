"""Evaluate typed proposals, abstention and escalation on frozen new tasks."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric.decision_models import (  # noqa: E402
    DecisionContext,
    DecisionOption,
    DeterministicDecisionModel,
    EscalationPolicy,
    route_decision,
)

CASES = ROOT / "research" / "bench" / "n6_01_decision_tasks" / "cases.json"


def evaluate() -> dict[str, Any]:
    payload = json.loads(CASES.read_text(encoding="utf-8"))
    observations = []
    for row in payload["cases"]:
        options = tuple(DecisionOption(item["id"], item["id"], item.get("action"))
                        for item in row["options"])
        context = DecisionContext(row["query"], options)
        proposal = route_decision(
            DeterministicDecisionModel(row["scores"]), context,
            EscalationPolicy(min_confidence=row["min_confidence"],
                             max_entropy=row["max_entropy"],
                             consequential_actions=frozenset(row["consequential_actions"])),
        )
        checks = {
            "selected_matches": proposal.selected == row["expected_selected"],
            "abstention_matches": proposal.abstained == row["expected_abstained"],
            "system2_matches": proposal.requires_system2 == row["expected_system2"],
            "probabilities_valid": set(proposal.probabilities) == {item.id for item in options}
            and abs(sum(proposal.probabilities.values()) - 1.0) <= 1e-6,
        }
        observations.append({
            "case_id": row["id"], "selected": proposal.selected,
            "abstained": proposal.abstained, "confidence": proposal.confidence,
            "probabilities": dict(proposal.probabilities),
            "requires_system2": proposal.requires_system2,
            "checks": checks, "passed": all(checks.values()),
        })
    failed = [row["case_id"] for row in observations if not row["passed"]]
    return {
        "schema": "memory-fabric-n6-01-decision-evaluation/1",
        "task_id": "N6-01", "acceptance_passed": not failed,
        "evidence_level": "CONTRACT",
        "dataset": {"path": CASES.relative_to(ROOT).as_posix(),
                    "sha256": hashlib.sha256(CASES.read_bytes()).hexdigest(),
                    "cases": len(observations)},
        "source": {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                               check=True, capture_output=True,
                                               text=True).stdout.strip(),
                   "dirty_before_result_write": bool(subprocess.run(
                       ["git", "status", "--porcelain"], cwd=ROOT, check=True,
                       capture_output=True, text=True).stdout.strip()),
                   "experiment_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "passed": len(observations) - len(failed), "failed": failed,
        "observations": observations,
        "limitations": [
            "Cases are deterministic API contracts authored for this fixture; they are not a distributional estimate of agent performance.",
            "The experiment evaluates proposal validation and escalation routing only. It does not execute or authorize the selected action.",
        ],
    }


def write_result(result: dict[str, Any]) -> None:
    out = ROOT / "research" / "results" / "n6-01-decision-evaluation.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    report = evaluate()
    write_result(report)
    print(json.dumps({"task_id": report["task_id"], "passed": report["passed"],
                      "failed": report["failed"],
                      "acceptance_passed": report["acceptance_passed"]}, indent=2))
