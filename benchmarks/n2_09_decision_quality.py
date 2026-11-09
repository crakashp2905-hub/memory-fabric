"""Held-out answerability-baseline versus typed evidence-gate qualification."""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

from benchmarks.manifest import capture_environment, head
from memory_fabric import MemoryFabric, parse_requirement_graph
from memory_fabric.actions import ActionGate, ActionPolicy, ClaimPredicate, ToolRule
from memory_fabric.answerability import ANSWERABLE

ROOT = Path(__file__).resolve().parents[1]
PREREG = "research/prereg/n2-09-answerability-vs-evidence-gate-v1.md"
SEEDS = (101, 103, 107, 109, 113)
CASES = (
    "safe_single", "safe_corroborated", "safe_paraphrase", "wrong_value",
    "unstructured", "missing", "conflicting", "copied", "withdrawn",
)
POSITIVE = frozenset({"safe_single", "safe_corroborated", "safe_paraphrase"})
TOOL = "set_pressure_limit"


def case_manifest(seed: int) -> list[dict[str, Any]]:
    """Frozen held-out cases; IDs encode the held-out entity namespace."""
    return [{"task_id": f"n2-09-{seed}-{name}", "seed": seed, "case": name,
             "expected": "ALLOW" if name in POSITIVE else "ABSTAIN",
             "min_sources": 2 if name in {"safe_corroborated", "safe_paraphrase", "copied"} else 1}
            for name in CASES]


def _percentile(values: list[int], probability: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1,
                       max(0, math.ceil((len(ordered) - 1) * probability)))]


def _content_tokens(text: str) -> int:
    return max(1, math.ceil(len(text.encode("utf-8")) / 4))


def _put(fabric: MemoryFabric, agent: str, text: str, subject: str,
         value: int | None, *, structured: bool = True) -> str:
    metadata = ({"claims": [{"subject": subject, "predicate": "relief_pressure",
                             "value": value, "unit": "psi"}]}
                if structured and value is not None else None)
    return fabric.remember(agent, text, scope="team", structured=metadata)


def _populate(fabric: MemoryFabric, task: dict[str, Any]) -> tuple[str, str, list[str]]:
    case = task["case"]
    entity = f"P-{task['seed']}-{CASES.index(case):02d}"
    subject = f"pump-{entity.lower()}"
    ids: list[str] = []
    if case == "safe_single":
        ids.append(_put(fabric, "source-a", f"Pump {entity} relief pressure is 30 psi; calibrated transducer report alpha.",
                        subject, 30))
    elif case == "safe_corroborated":
        ids.append(_put(fabric, "source-a", f"Pump {entity} relief pressure recorded as 30 psi from certified transducer alpha.",
                        subject, 30))
        ids.append(_put(fabric, "source-b", f"For pump {entity}, relief pressure remained 30 psi in independent maintenance ledger beta.",
                        subject, 30))
    elif case == "safe_paraphrase":
        ids.append(_put(fabric, "source-a", f"Unit {entity} safety trip threshold is 30 psi according to transducer alpha.",
                        subject, 30))
        ids.append(_put(fabric, "source-b", f"{entity} valve release setting remains 30 psi in maker sheet beta.",
                        subject, 30))
    elif case == "wrong_value":
        ids.append(_put(fabric, "source-a", f"Pump {entity} relief pressure is 70 psi; calibrated transducer report alpha.",
                        subject, 70))
    elif case == "unstructured":
        ids.append(_put(fabric, "source-a", f"Pump {entity} relief pressure is 30 psi; service note alpha.",
                        subject, 30, structured=False))
    elif case == "conflicting":
        ids.append(_put(fabric, "source-a", f"Pump {entity} relief pressure is 30 psi; calibrated transducer alpha.",
                        subject, 30))
        ids.append(_put(fabric, "source-b", f"Pump {entity} relief pressure is 70 psi; independent gauge beta.",
                        subject, 70))
    elif case == "copied":
        original = f"Pump {entity} relief pressure is 30 psi; calibrated transducer report alpha."
        ids.append(_put(fabric, "source-a", original, subject, 30))
        ids.append(_put(fabric, "forwarder-b", original + " (forwarded copy one).", subject, 30))
        ids.append(_put(fabric, "forwarder-c", original + " (archive duplicate two).", subject, 30))
        roots = {fabric.source_root(memory_id) for memory_id in ids}
        if len(roots) != 1:
            raise RuntimeError(f"copy fixture did not share one source root: {roots}")
    elif case == "withdrawn":
        memory_id = _put(fabric, "source-a", f"Pump {entity} relief pressure is 30 psi; calibrated transducer report alpha.",
                         subject, 30)
        fabric.quarantine(memory_id, actor="reviewer", reason="withdrawn fixture",
                          basis="contradicted")
        ids.append(memory_id)
    # Missing is intentionally an empty evidence set.
    return entity, subject, ids


def _one_case(task: dict[str, Any]) -> dict[str, Any]:
    query = f"What is the relief pressure of pump P-{task['seed']}-{CASES.index(task['case']):02d}?"
    with MemoryFabric(":memory:", auto_activate=True, recognise_copies=True,
                      encrypt_content=False, hold_suspicious=False) as fabric:
        entity, subject, evidence_ids = _populate(fabric, task)
        result = fabric.retrieve("reader", query, k=20, within=evidence_ids,
                                 min_relevance=0.0, group_by_source_root=False)

        baseline_started = time.perf_counter_ns()
        baseline_result = fabric.retrieve("reader", query, k=20, within=evidence_ids,
                                          min_relevance=0.0, group_by_source_root=False)
        answerability = baseline_result.answerability(query)
        baseline_latency = time.perf_counter_ns() - baseline_started
        baseline_allowed = answerability.verdict == ANSWERABLE
        baseline_ids = sorted(answerability.covering)[:1] if baseline_allowed else []
        content_by_id = {item.id: item.content for item in result.exposed}
        baseline_tokens = sum(_content_tokens(content_by_id[mid])
                              for mid in baseline_ids if mid in content_by_id)

        graph = parse_requirement_graph({
            "schema": "memory-fabric-requirement-graph/1",
            "graph_id": "n2-09-pressure-safe-v1",
            "root": {"op": "claim", "claim_id": "pressure_safe"},
        })
        rule = ToolRule(
            TOOL,
            min_independent_sources=task["min_sources"],
            requirement_graph=graph,
            claim_predicates={
                "pressure_safe": ClaimPredicate(subject, "relief_pressure", "<=", 40, "psi")
            },
        )
        gate = ActionGate(fabric, ActionPolicy(
            tools={TOOL: rule}, grants={"operator": frozenset({TOOL})}), audit=False)
        candidate_started = time.perf_counter_ns()
        certificates = {}
        if evidence_ids:
            certificates["pressure_safe"] = fabric.certify(
                "pressure_safe", evidence_ids, "operator")
        candidate = gate.authorize(TOOL, "operator", claim_certificates=certificates)
        candidate_latency = time.perf_counter_ns() - candidate_started
        candidate_ids = list(evidence_ids) if certificates else []
        candidate_tokens = sum(_content_tokens(fabric.get(mid).content)
                               for mid in candidate_ids)

        expected = task["expected"] == "ALLOW"
        return {
            **task,
            "entity": entity,
            "query": query,
            "exposed_evidence_ids": [item.id for item in result.exposed],
            "source_roots": {mid: fabric.source_root(mid) for mid in evidence_ids},
            "arms": {
                "answerability_baseline": {
                    "decision": "ALLOW" if baseline_allowed else "ABSTAIN",
                    "verdict": answerability.verdict,
                    "correct": baseline_allowed == expected,
                    "false_abstention": expected and not baseline_allowed,
                    "false_authorization": not expected and baseline_allowed,
                    "latency_ns": baseline_latency,
                    "supporting_records": len(baseline_ids),
                    "content_token_estimate": baseline_tokens,
                },
                "typed_evidence_gate": {
                    "decision": "ALLOW" if candidate.allowed else "ABSTAIN",
                    "reason_codes": list(candidate.reason_codes),
                    "correct": candidate.allowed == expected,
                    "false_abstention": expected and not candidate.allowed,
                    "false_authorization": not expected and candidate.allowed,
                    "latency_ns": candidate_latency,
                    "supporting_records": len(candidate_ids),
                    "content_token_estimate": candidate_tokens,
                    "certificate_digest": (certificates["pressure_safe"].digest()
                                           if certificates else None),
                },
            },
        }


def _summarize(rows: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    outcomes = [row["arms"][arm] for row in rows]
    positive = [item for row, item in zip(rows, outcomes) if row["expected"] == "ALLOW"]
    negative = [item for row, item in zip(rows, outcomes) if row["expected"] == "ABSTAIN"]
    latencies = [item["latency_ns"] for item in outcomes]
    return {
        "attempted": len(rows),
        "correct": sum(item["correct"] for item in outcomes),
        "task_success_rate": sum(item["correct"] for item in outcomes) / len(outcomes),
        "false_abstentions": sum(item["false_abstention"] for item in positive),
        "false_abstention_denominator": len(positive),
        "false_authorizations": sum(item["false_authorization"] for item in negative),
        "false_authorization_denominator": len(negative),
        "latency_p50_ns": _percentile(latencies, 0.50),
        "latency_p95_ns": _percentile(latencies, 0.95),
        "mean_supporting_records_on_oracle_allow": statistics.fmean(
            item["supporting_records"] for item in positive),
        "mean_content_token_estimate_on_oracle_allow": statistics.fmean(
            item["content_token_estimate"] for item in positive),
    }


def build_report() -> dict[str, Any]:
    manifests = {str(seed): case_manifest(seed) for seed in SEEDS}
    rows = [_one_case(task) for seed in SEEDS for task in manifests[str(seed)]]
    ids = [row["task_id"] for row in rows]
    expected_ids = {task_id for tasks in manifests.values() for task in tasks
                    for task_id in [task["task_id"]]}
    failures = []
    if len(rows) != len(SEEDS) * len(CASES) or len(ids) != len(set(ids)):
        failures.append("case_count_or_duplicate_id")
    if set(ids) != expected_ids:
        failures.append("case_manifest_mismatch")
    if any({row["seed"] for row in tasks} != {int(seed)} for seed, tasks in manifests.items()):
        failures.append("seed_namespace_overlap")
    for row in rows:
        if row["case"] in POSITIVE and row["expected"] != "ALLOW":
            failures.append(f"invalid_oracle:{row['task_id']}")
        if row["case"] not in POSITIVE and row["expected"] != "ABSTAIN":
            failures.append(f"invalid_oracle:{row['task_id']}")
        if row["case"] == "copied" and len(set(row["source_roots"].values())) != 1:
            failures.append(f"copy_roots:{row['task_id']}")

    baseline = _summarize(rows, "answerability_baseline")
    candidate = _summarize(rows, "typed_evidence_gate")
    allow_rows = [row for row in rows if row["expected"] == "ALLOW"]
    extra_records = [row["arms"]["typed_evidence_gate"]["supporting_records"]
                     - row["arms"]["answerability_baseline"]["supporting_records"]
                     for row in allow_rows]
    extra_tokens = [row["arms"]["typed_evidence_gate"]["content_token_estimate"]
                    - row["arms"]["answerability_baseline"]["content_token_estimate"]
                    for row in allow_rows]
    source_paths = ("benchmarks/n2_09_decision_quality.py", PREREG)
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip())
    return {
        "schema": "mf-n2-09-decision-quality/1",
        "decision": "DESCRIPTIVE",
        "acceptance_status": "PASS" if not failures else "FAIL",
        "population": "synthetic_scripted",
        "repo_commit": head(),
        "dirty": dirty,
        "environment": capture_environment(),
        "protocol": PREREG,
        "preregistration_sha256": hashlib.sha256((ROOT / PREREG).read_bytes()).hexdigest(),
        "seeds": list(SEEDS),
        "cases_per_seed": list(CASES),
        "case_count": len(rows),
        "manifest_by_seed": manifests,
        "arms": {"answerability_baseline": baseline, "typed_evidence_gate": candidate},
        "comparison": {
            "task_success_difference": candidate["task_success_rate"] - baseline["task_success_rate"],
            "false_abstention_difference": (candidate["false_abstentions"]
                                             - baseline["false_abstentions"]),
            "false_authorization_difference": (candidate["false_authorizations"]
                                               - baseline["false_authorizations"]),
            "mean_extra_supporting_records_on_oracle_allow": statistics.fmean(extra_records),
            "mean_extra_content_token_estimate_on_oracle_allow": statistics.fmean(extra_tokens),
        },
        "invariant_failures": failures,
        "input_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                         for path in source_paths},
        "rows": rows,
        "limitations": [
            "Forty-five held-out synthetic scripted cases; not real-agent or language-model evidence.",
            "Answerability uses a one-record minimum-support proxy while the typed gate counts all certificate records; the reported difference is a transparent evidence-reference/token estimate, not billed inference cost.",
            "Latency is local in-process timing with scenario construction outside the timed decision paths; it is not a deployment or network latency claim.",
            "Structured assertions and source-root metadata are fixture inputs, not proof of real-world truth or source authority.",
        ],
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "research/results/n2-09-decision-quality.json")
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "status": report["acceptance_status"],
                      "cases": report["case_count"], "invariant_failures": len(report["invariant_failures"]),
                      "summary": report["arms"], "comparison": report["comparison"]}))
    return int(report["acceptance_status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
