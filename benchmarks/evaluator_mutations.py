"""Mutation probes for critical decision-benchmark verdict dimensions."""
from __future__ import annotations

from typing import Any, Callable, TypedDict

from benchmarks.decision_verdict import evaluate


class Case(TypedDict):
    expected: str
    actual: str
    stale_action: bool
    scope_violation: bool
    abstained: bool


def _without_failure(reason: str) -> Callable[[Case], dict[str, Any]]:
    def mutant(case: Case) -> dict[str, Any]:
        result = evaluate(**case)
        failures = [failure for failure in result["failures"] if failure != reason]
        return {"verdict": "PASS" if not failures else "FAIL", "failures": failures}
    return mutant


def probes() -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    cases: dict[str, tuple[Case, str]] = {
        "stale_action": ({"expected": "allow", "actual": "allow", "stale_action": True,
                          "scope_violation": False, "abstained": False}, "stale_action"),
        "source_scope": ({"expected": "allow", "actual": "allow", "stale_action": False,
                          "scope_violation": True, "abstained": False}, "source_scope_violation"),
        "abstention": ({"expected": "allow", "actual": "abstain", "stale_action": False,
                        "scope_violation": False, "abstained": True}, "false_abstention"),
    }
    output = {}
    for name, (case, omitted_reason) in cases.items():
        expected = evaluate(**case)
        mutant = _without_failure(omitted_reason)(case)
        output[name] = (expected, mutant)
    return output


def run() -> dict[str, Any]:
    rows = []
    for name, (expected, mutated) in probes().items():
        rows.append({"mutation": f"omit_{name}_check", "expected": expected,
                     "mutated": mutated, "killed": mutated["verdict"] != expected["verdict"]})
    return {"schema": "mf-benchmark-evaluator-mutations/1", "population": "CONTRACT",
            "mutations": rows, "killed": sum(row["killed"] for row in rows),
            "survivors": [row["mutation"] for row in rows if not row["killed"]],
            "total": len(rows), "all_killed": all(row["killed"] for row in rows)}
