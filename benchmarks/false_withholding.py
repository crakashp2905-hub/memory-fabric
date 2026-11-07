"""Reproduce local false-withholding cases and dry-run individual guard ablations."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from benchmarks.manifest import capture_environment, head
from benchmarks.stats import wilson
from experiments.p3b_teams import extract
from experiments.teamworld import build_memory, build_world
from memory_fabric.actions import ActionGate, ActionPolicy, ActionRequest, ToolRule

SEEDS = (101, 102, 103, 104, 105)
AGENTS = 50
ROOT = Path(__file__).resolve().parents[1]
PREREG = "research/prereg/r2-false-withholding-v1.md"
TOOL = "publish"
ABLATIONS = ("live", "no_independence_floor", "allow_suspicious",
             "allow_provisional", "untrusted_authority")


def _cause(reason: str, miss: str) -> list[str]:
    causes = []
    if "ranking" in miss or miss in ("not_visible", "not_available_to_agent"):
        causes.append("retrieval")
    if "authority" in reason:
        causes.append("authority")
    if "instruction" in reason or "external_origin" in reason or "imported" in reason:
        causes.append("provenance")
    if "independent" in reason:
        causes.append("independence")
    if "fresh" in reason or "version" in reason:
        causes.append("freshness")
    if "withdraw" in reason or "withdraw" in miss:
        causes.extend(("freshness", "poisoning_or_contestation"))
    if "unvalidated" in miss:
        causes.append("provisional_validation")
    if "suspicious" in reason or "provisional" in reason or "contested" in reason or "conflict" in miss:
        causes.append("poisoning_or_contestation")
    if "dependency" in reason or "support" in reason:
        causes.append("missing_dependency")
    if not causes:
        causes.append("other_policy_or_lifecycle")
    return causes


def _gate(fabric, grants, rule: ToolRule) -> ActionGate:
    # Suppress ACTION_GATED audit writes: the diagnostic must not mutate the
    # live fixture or create a persisted authorization receipt.
    return ActionGate(fabric, ActionPolicy(tools={TOOL: rule}, grants=grants), audit=False)


def _decisions(fabric, agent: str, cert, target: str, value: str) -> dict[str, dict[str, Any]]:
    options = {
        "live": ToolRule(TOOL),
        "allow_suspicious": ToolRule(TOOL, refuse_suspicious=False),
        "allow_provisional": ToolRule(TOOL, refuse_provisional=False),
        "untrusted_authority": ToolRule(TOOL, min_authority="untrusted"),
        "no_independence_floor": ToolRule(TOOL, min_independent_sources=0),
    }
    grants = {agent: frozenset({TOOL})}
    result = {}
    watermark = fabric.log.head_seq
    for name, rule in options.items():
        decision = _gate(fabric, grants, rule).authorize(
            TOOL, agent, cert, request=ActionRequest(target=target, parameters={"value": value}))
        result[name] = {"allowed": decision.allowed,
                        "reason_codes": list(decision.reason_codes)}
        if fabric.log.head_seq != watermark:
            raise RuntimeError("dry-run gate evaluation mutated the evidence log")
    return result


def run_seed(seed: int) -> dict[str, Any]:
    if seed not in SEEDS:
        raise ValueError("seed is not preregistered")
    world = build_world(seed, agents=AGENTS, rounds=60)
    # The blanket arm is a positive control. The diagnostic corpus itself is
    # made only from task traces where the current Memory Fabric backend held
    # the exact current fact but did not return it.
    cases: list[dict[str, Any]] = []
    arm_rows: dict[str, list[dict[str, Any]]] = {}
    for arm in ("shared_blanket", "fabric"):
        memory = build_memory(arm, world)
        task_index = 0
        withheld_rows = []
        try:
            for event in world.schedule:
                if event.kind in ("discover", "duplicate", "contradict"):
                    memory.write(event.agent, event.fact.statement(), event.fact.key)
                    if event.kind == "discover":
                        world.current[event.fact.key] = event.fact
                elif event.kind == "correct":
                    old_truth = world.current.get(event.fact.key)
                    old_ids = list(getattr(memory, "by_key", {}).get(event.fact.key, ()))
                    old_id = old_ids[0] if old_ids else None
                    old_content = (memory.fabric.state.memories[old_id].content
                                   if arm == "fabric" and old_id in memory.fabric.state.memories
                                   else None) if old_id else None
                    memory.correct(event.agent, event.fact, "re-measured after the move")
                    world.current[event.fact.key] = event.fact
                    if arm == "fabric" and old_truth is not None and old_id is not None:
                        cert = memory.fabric.certify(f"s{seed}-stale-{task_index}",
                                                     [old_id], event.agent)
                        decisions = _decisions(memory.fabric, event.agent, cert,
                                               event.fact.question(), old_truth.value)
                        old_memory = memory.fabric.state.memories[old_id]
                        cases.append({
                            "case_id": f"s{seed}-stale-{task_index}", "seed": seed,
                            "task_index": task_index, "agent": event.agent,
                            "action": {"tool": TOOL, "target": event.fact.question(),
                                       "attempted_value": old_truth.value},
                            "oracle_supported": False, "evidence": old_content,
                            "evidence_ids": [old_id], "returned_evidence_ids": [],
                            "valid_evidence_withheld": False,
                            "backend_miss_reason": "withdrawn_or_correction_fallout",
                            "actual_blocker_reason": decisions["live"]["reason_codes"][0],
                            "live_gate": decisions["live"], "counterfactuals": decisions,
                            "causal_labels": ["freshness", "poisoning_or_contestation"],
                            "evidence_lifecycle_at_attempt": old_memory.lifecycle_state.value,
                            "dry_run_only": True})
                elif event.kind == "task":
                    truth = world.truth(event.fact.key)
                    if truth is None:
                        task_index += 1
                        continue
                    query = event.fact.question()
                    returned = memory.read(event.agent, query, k=5)
                    contents = [content for _, content in returned]
                    answer = extract(contents, event.fact)
                    rediscovered = False
                    if answer is None and event.fact.key in world.reproducible:
                        rediscovered = True
                        memory.write(event.agent, truth.statement(), truth.key)
                        returned = memory.read(event.agent, query, k=5)
                        contents = [content for _, content in returned]
                        answer = extract(contents, event.fact)
                    had_correct = any(truth.value in content for content in contents)
                    valid = not had_correct and memory.holds(event.agent, truth.value)
                    reason = memory.miss_reason(event.agent, truth.statement(), returned) if valid else None
                    row = {"case_id": f"s{seed}-t{task_index}", "seed": seed,
                           "task_index": task_index, "agent": event.agent,
                           "action": {"tool": TOOL, "target": query, "expected_value": truth.value},
                           "oracle_supported": True, "evidence": truth.statement(),
                           "rediscovered": rediscovered,
                           "evidence_ids": [mid for mid, content in returned if content == truth.statement()],
                           "returned_evidence_ids": [mid for mid, _ in returned],
                           "valid_evidence_withheld": valid, "backend_miss_reason": reason,
                           "actual_blocker_reason": reason if valid else ("answered" if answer else "no_valid_evidence")}
                    arm_rows.setdefault(arm, []).append(row)
                    if valid:
                        withheld_rows.append(row)
                        if arm == "fabric":
                            ids = [mid for mid in getattr(memory, "by_key", {}).get(event.fact.key, ())
                                   if (mid in memory.fabric.state.memories
                                       and truth.value in memory.fabric.state.memories[mid].content)]
                            cert = memory.fabric.certify(row["case_id"], ids, event.agent)
                            decisions = _decisions(memory.fabric, event.agent, cert, query, truth.value)
                            states = [memory.fabric.state.memories[mid].lifecycle_state.value
                                      for mid in ids if mid in memory.fabric.state.memories]
                            row = {**row, "evidence_ids": ids,
                                   "live_gate": decisions["live"],
                                   "actual_blocker_reason": decisions["live"]["reason_codes"][0],
                                   "counterfactuals": decisions,
                                   "causal_labels": _cause(decisions["live"]["reason_codes"][0], reason or ""),
                                   "evidence_lifecycle_at_attempt": states,
                                   "dry_run_only": True}
                            cases.append(row)
                    task_index += 1
        finally:
            fabric = getattr(memory, "fabric", None)
            if fabric is not None:
                fabric.close()

    rules_wire = {"live": {"min_authority": "unverified", "refuse_suspicious": True,
                            "refuse_provisional": False, "min_independent_sources": 1},
                  "allow_suspicious": {"min_authority": "unverified", "refuse_suspicious": False,
                                       "refuse_provisional": False, "min_independent_sources": 1},
                  "allow_provisional": {"min_authority": "unverified", "refuse_suspicious": True,
                                        "refuse_provisional": False, "min_independent_sources": 1},
                  "untrusted_authority": {"min_authority": "untrusted", "refuse_suspicious": True,
                                          "refuse_provisional": False, "min_independent_sources": 1},
                  "no_independence_floor": {"min_authority": "unverified", "refuse_suspicious": True,
                                            "refuse_provisional": False, "min_independent_sources": 0}}
    return {"seed": seed, "population": "synthetic_scripted",
            "task_denominator": len(arm_rows.get("fabric", [])),
            "blanket_withheld": sum(r["valid_evidence_withheld"] for r in arm_rows.get("shared_blanket", [])),
            "memory_fabric_withheld": sum(r["valid_evidence_withheld"] for r in arm_rows.get("fabric", [])),
            "cases": cases, "policy_rules": rules_wire}


def build_report() -> dict[str, Any]:
    seeds = [run_seed(seed) for seed in SEEDS]
    cases = [case for seed in seeds for case in seed["cases"]]
    category_names = ("provenance", "authority", "independence", "freshness",
                      "poisoning_or_contestation", "provisional_validation", "retrieval", "missing_dependency",
                      "other_policy_or_lifecycle")
    categories: dict[str, int] = {name: 0 for name in category_names}
    for case in cases:
        for category in case["causal_labels"]:
            categories[category] = categories.get(category, 0) + 1
    n = len(cases)
    labelled = sum(bool(case["causal_labels"]) for case in cases)
    ambiguous = sum(len(case["causal_labels"]) > 1 for case in cases)
    category_rates = {name: {"count": count, "unique_case_denominator": n,
                             "rate": count / n if n else 0}
                      for name, count in sorted(categories.items())}
    gate_reasons = Counter(case["actual_blocker_reason"] for case in cases)
    lifecycle_states = Counter(
        state for case in cases for state in
        (case["evidence_lifecycle_at_attempt"] if isinstance(case["evidence_lifecycle_at_attempt"], list)
         else [case["evidence_lifecycle_at_attempt"]]))
    ablations = {}
    for arm in ABLATIONS:
        releases = sum(case["counterfactuals"][arm]["allowed"] and not case["counterfactuals"]["live"]["allowed"]
                       for case in cases)
        recovered = sum(case["valid_evidence_withheld"]
                        and case["counterfactuals"][arm]["allowed"]
                        and not case["counterfactuals"]["live"]["allowed"]
                        for case in cases)
        unsafe = sum(case["counterfactuals"][arm]["allowed"] and not case["oracle_supported"]
                     for case in cases)
        lo, hi = wilson(recovered, sum(c["valid_evidence_withheld"] for c in cases))
        unsafe_lo, unsafe_hi = wilson(unsafe, sum(not c["oracle_supported"] for c in cases))
        if recovered == 0:
            lo = 0.0
        if unsafe == 0:
            unsafe_lo = 0.0
        ablations[arm] = {"attempted": n, "recovered_valid_tasks": recovered,
                          "counterfactual_gate_releases": releases,
                          "additional_unsafe_actions": unsafe,
                          "recovery_denominator": sum(c["valid_evidence_withheld"] for c in cases),
                          "recovery_rate": recovered / sum(c["valid_evidence_withheld"] for c in cases) if any(c["valid_evidence_withheld"] for c in cases) else 0,
                          "recovery_wilson95": [lo, hi],
                          "unsafe_wilson95": [unsafe_lo, unsafe_hi],
                          "live_policy_mutated": False, "executor_calls": 0}
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip())
    inputs = ("benchmarks/false_withholding.py", PREREG,
              "experiments/p3b_teams.py", "experiments/teamworld.py",
              "research/results/grand-50-agent-baseline-reproduction-v2.json")
    return {"schema": "mf-false-withholding-ablation/1", "decision": "DESCRIPTIVE",
            "acceptance_status": "PASS" if n > 0 else "FAIL",
            "population": "synthetic_scripted", "repo_commit": head(), "dirty": dirty,
            "environment": capture_environment(), "seeds": list(SEEDS), "agents_per_seed": AGENTS,
            "upstream_provenance": {"source": "PR #30 baseline reproduction v2",
                "candidate_sha": "12c612ea37980f92d206fe2b343b217603d1b3cc",
                "published_withholding_rate": 0.168, "exact_upstream_rows_available": False,
                "local_corpus_is_exact_upstream_import": False},
            "attempted_case_denominator": n,
            "attribution_unique_case_denominator": n,
            "attribution_labelled_unique_cases": labelled,
            "ambiguous_multi_causal_cases": ambiguous,
            "attempted_valid_case_denominator": sum(c["valid_evidence_withheld"] for c in cases),
            "attempted_unsafe_case_denominator": sum(not c["oracle_supported"] for c in cases),
            "causal_category_counts_multilabel": categories,
            "causal_category_rates_multilabel": category_rates,
            "shared_blanket_valid_withheld": sum(s["blanket_withheld"] for s in seeds),
            "memory_fabric_valid_withheld": sum(c["valid_evidence_withheld"] for c in cases),
            "actual_gate_reason_counts": dict(sorted(gate_reasons.items())),
            "evidence_lifecycle_counts": dict(sorted(lifecycle_states.items())),
            "ablations": ablations, "cases": cases,
            "live_policy_sha256": hashlib.sha256(json.dumps(seeds[0]["policy_rules"], sort_keys=True).encode()).hexdigest() if seeds else None,
            "input_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in inputs},
            "limitations": ["Local cases are generated from the registered deterministic teamworld; they are not the unavailable individual PR #30 withheld rows.",
                            "Guard ablations vary one ActionGate rule against current evidence state; they do not explain caller-side retrieval choices.",
                            "No counterfactual policy is installed and no action executor is invoked."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research/results/r2-false-withholding-ablation.json")
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "status": report["acceptance_status"],
                      "cases": report["attempted_valid_case_denominator"],
                      "categories": report["causal_category_counts_multilabel"]}))
    return int(report["acceptance_status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
