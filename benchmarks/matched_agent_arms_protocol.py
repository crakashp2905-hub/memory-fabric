"""Matched local-only, pooled, blanket, governed, and oracle agent arms."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from collections import Counter, defaultdict
from statistics import fmean
from pathlib import Path
from typing import Any

from benchmarks.agent_scale import (
    AGENT_COUNTS, FAMILIES, ROOT, SEEDS, task_manifest,
)
from benchmarks.manifest import capture_environment, head
from memory_fabric import MemoryFabric
from memory_fabric.outcome_protocol.eligibility import EvidenceFailure, EvidenceFailureKind
from memory_fabric.outcome_protocol.recovery import RecoveryEpisode
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.identity import DEFAULT_TENANT

ARMS = ("isolated", "pooled_shared", "blanket_retraction", "memory_fabric", "oracle")
TOOL = "publish"
TOOL_CATALOG = ("publish", "archive", "notify")
FAILURE_CLASSES = ("retrieval", "insufficient_evidence", "policy_refusal", "coordination", "tool_error")
HIGH_RISK_FAMILIES = frozenset({"corrected", "contested"})
WALL_TIME_BUDGET_MS_PER_RUN = 10_000


class _CaseScopedFabric:
    """Restrict a recovery lookup to evidence registered for the current task."""

    def __init__(self, fabric: MemoryFabric, candidate_ids: tuple[str, ...]) -> None:
        self._fabric = fabric
        self._candidate_ids = candidate_ids

    def __getattr__(self, name: str) -> Any:
        return getattr(self._fabric, name)

    def retrieve(self, *args: Any, **kwargs: Any) -> Any:
        kwargs["within"] = self._candidate_ids
        return self._fabric.retrieve(*args, **kwargs)


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int((len(ordered) - 1) * p + 0.999999)))]


def classify_failure(arm: str, family: str, allowed: bool, expected: bool, reason: str) -> list[str]:
    """Attribute a mismatched action to all observable contributing failure classes."""
    if allowed == expected:
        return []
    if allowed:
        return ["insufficient_evidence", "policy_refusal"]
    if family == "supported" and arm == "pooled_shared":
        return ["retrieval"]
    if family == "supported" and reason in {"evidence_not_usable", "evidence_suspicious"}:
        return ["retrieval", "policy_refusal"]
    return ["policy_refusal"]


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def randomized_agent_ids(seed: int, count: int) -> list[str]:
    """Opaque, seed-specific identities; no ordinal encodes an agent outcome."""
    import random

    rng = random.Random(seed ^ 0xA61D)
    ids = [f"agent-{rng.getrandbits(64):016x}" for _ in range(count)]
    if len(set(ids)) != count:
        raise RuntimeError("agent identity collision")
    rng.shuffle(ids)
    return ids


def randomized_tool_catalog(seed: int) -> list[str]:
    """Vary registry insertion order while preserving the sole runtime grant."""
    import random

    tools = list(TOOL_CATALOG)
    random.Random(seed ^ 0x7001).shuffle(tools)
    return tools


def run(seed: int, agent_count: int, arm: str, *, randomize_order: bool = True,
        task_cases: list[dict[str, str]] | None = None) -> dict[str, Any]:
    if agent_count not in AGENT_COUNTS or arm not in (*ARMS, "no_memory",
                                                       "pooled_shared_plus_recovery",
                                                       "memory_fabric_recovery"):
        raise ValueError("unknown agent count or arm")
    agents = (randomized_agent_ids(seed, agent_count) if randomize_order else
              [f"agent-{index:03d}" for index in range(agent_count)])
    tool_order = randomized_tool_catalog(seed) if randomize_order else list(TOOL_CATALOG)
    tasks = task_cases if task_cases is not None else task_manifest(seed)
    families = tuple(dict.fromkeys((*FAMILIES, *(task["family"] for task in tasks))))
    result: dict[str, dict[str, Any]] = {family: {"attempted": 0, "correct": 0, "unsafe_actions": 0,
                       "stale_actions": 0, "false_abstentions": 0,
                       "failure_classes": {name: 0 for name in FAILURE_CLASSES}}
             for family in families}
    details = []
    retrieval_calls = 0
    recovery_search_calls = 0
    recovery_alternates_found = 0
    recovery_trace: list[dict[str, Any]] = []
    recovery_candidates: dict[str, tuple[str, ...]] = {}
    context_items_exposed = 0
    per_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    blanket_source_withdrawn = False
    started = time.perf_counter()
    # A file, not ":memory:": the storage measurement below is SQLite page
    # metadata, and file-path stores stay on SQLite even in the Postgres test job.
    scratch = tempfile.TemporaryDirectory()
    with MemoryFabric(str(Path(scratch.name) / "arm.db"), recognise_copies=False, encrypt_content=False,
                      hold_suspicious=False) as fabric:
        policy = ActionPolicy(tools={tool: ToolRule(tool) for tool in tool_order},
                              grants={agent: frozenset({TOOL}) for agent in agents})
        gate = ActionGate(fabric, policy)
        for task in tasks:
            family = task["family"]
            case_key = task["task_id"].replace("-", "").upper()
            evidence_text = f"Record {case_key} status code is 1." if family != "missing" else None
            evidence_id = None
            certificates = {}
            if evidence_text is not None:
                evidence_id = fabric.remember("source", evidence_text, scope="team", auto_activate=True)
                fabric.elevate(evidence_id, approver="reviewer", reason="fixture source checked")
            initial_exposure_ids = []
            for agent in agents:
                exposed = fabric.retrieve(agent, f"Record {case_key}",
                                          within=[evidence_id] if evidence_id else [],
                                          min_relevance=0.0).exposed
                retrieval_calls += 1
                ids = [memory.id for memory in exposed]
                initial_exposure_ids.append(ids)
                if ids != ([evidence_id] if evidence_id else []):
                    raise RuntimeError("matched arm initial evidence exposure failed")
                context_items_exposed += len(ids)
            if evidence_id:
                certificates = {agent: fabric.certify(task["task_id"], [evidence_id], agent)
                                for agent in agents}
            if family == "contested" and evidence_id:
                conflict = fabric.remember("conflict", f"Record {case_key} status code is 0.",
                                           scope="team", auto_activate=True)
                fabric.elevate(conflict, approver="reviewer", reason="fixture conflict checked")
                fabric.challenge([evidence_id, conflict], evidence="contradictory fixture",
                                 detector_id="matched-agent-arms-v1")
            if family in {"corrected", "recoverable"} and evidence_id:
                fabric.quarantine(evidence_id, actor="reviewer", reason="source correction",
                                  basis="contradicted")
                blanket_source_withdrawn = True
                if family == "recoverable":
                    replacement_id = fabric.remember(
                        "independent-reviewer",
                        f"Current verified Record {case_key} status code is 0.",
                        scope="team", auto_activate=True,
                    )
                    fabric.elevate(replacement_id, approver="reviewer",
                                   reason="independent current source checked")
                    recovery_candidates[task["task_id"]] = (replacement_id,)

            # Every arm receives the same second retrieval opportunity and
            # operation budget after the task's lifecycle updates. Only
            # pooled_shared consumes the result.
            fresh_retrieval = {}
            for agent in agents:
                fresh_retrieval[agent] = fabric.retrieve(
                    agent, f"Record {case_key}", within=[evidence_id] if evidence_id else [],
                    min_relevance=0.0).exposed
                retrieval_calls += 1

            expected = family in {"supported", "recoverable"}
            family_result = result[family]
            reason_codes: Counter[str] = Counter()
            failure_class_counts: Counter[str] = Counter()
            allowed_count = 0
            false_abstentions = 0
            unsafe_actions = 0
            stale_actions = 0
            mismatched_agents = 0
            for agent in agents:
                reason = ""
                decision_started = time.perf_counter()
                try:
                    if arm == "no_memory":
                        allowed = False
                        reason = "no_memory_context"
                    elif arm == "isolated":
                        allowed = evidence_id is not None
                        reason = "cached_initial_evidence" if allowed else "no_initial_evidence"
                    elif arm == "pooled_shared":
                        current = fresh_retrieval[agent]
                        allowed = bool(current)
                        reason = "shared_retrieval_hit" if allowed else "shared_retrieval_miss"
                    elif arm == "pooled_shared_plus_recovery":
                        current = fresh_retrieval[agent]
                        if current:
                            allowed = True
                            reason = "shared_retrieval_hit"
                        elif family in {"corrected", "recoverable"} and evidence_id is not None:
                            episode = RecoveryEpisode(task["task_id"], enabled=True)
                            alternate = episode.search_alternate_sources(
                                EvidenceFailure(EvidenceFailureKind.STALE,
                                                "stale_revision_epoch"),
                                _CaseScopedFabric(
                                    fabric,
                                    candidate_ids=recovery_candidates.get(task["task_id"], ()),
                                ),
                                query=f"Record {case_key}",
                                agent_id=agent,
                                tenant_id=DEFAULT_TENANT,
                                existing_evidence_ids=(evidence_id,),
                                limit=5,
                            )
                            recovery_search_calls += 1
                            retrieval_calls += 1
                            recovery_alternates_found += len(alternate)
                            if alternate:
                                episode.record("re_retrieve", {
                                    "progress_key": f"alternate:{task['task_id']}:{agent}",
                                    "candidate_count": len(alternate),
                                })
                                allowed = True
                                reason = "authorized_alternate_found"
                            else:
                                episode.record("evidence_blocked", {"reason": "NO_ALTERNATE"})
                                episode.record("abstain", {"reason": "NO_AUTHORIZED_ALTERNATE"})
                                allowed = False
                                reason = "no_authorized_alternate"
                            recovery_trace.append({
                                "task_id": task["task_id"],
                                "alternate_count": len(alternate),
                                "status": episode.status.value,
                                "steps": episode.steps,
                                "search_attempts": episode.alternate_search_attempts,
                            })
                        else:
                            allowed = bool(current)
                            reason = "shared_retrieval_miss"
                    elif arm == "blanket_retraction":
                        allowed = (evidence_id is not None and family == "supported"
                                   and not blanket_source_withdrawn)
                        reason = "blanket_source_withheld" if not allowed else "source_clear"
                    elif arm == "memory_fabric":
                        decision = gate.authorize(TOOL, agent, certificates.get(agent))
                        reason_codes[decision.reason_code] += 1
                        reason = decision.reason_code
                        allowed = decision.allowed
                    elif arm == "memory_fabric_recovery":
                        decision = gate.authorize(TOOL, agent, certificates.get(agent))
                        reason_codes[decision.reason_code] += 1
                        reason = decision.reason_code
                        allowed = decision.allowed
                        if (not allowed and family in {"corrected", "recoverable"}
                                and evidence_id is not None):
                            episode = RecoveryEpisode(task["task_id"], enabled=True)
                            episode.record("evidence_blocked", {
                                "cause_code": "EVIDENCE_STALE",
                                "source_id": evidence_id,
                            })
                            alternate = episode.search_alternate_sources(
                                EvidenceFailure(EvidenceFailureKind.STALE,
                                                "stale_revision_epoch"),
                                _CaseScopedFabric(
                                    fabric,
                                    candidate_ids=recovery_candidates.get(task["task_id"], ()),
                                ),
                                query=f"Record {case_key}",
                                agent_id=agent,
                                tenant_id=DEFAULT_TENANT,
                                existing_evidence_ids=(evidence_id,),
                                limit=5,
                            )
                            recovery_search_calls += 1
                            retrieval_calls += 1
                            recovery_alternates_found += len(alternate)
                            if alternate:
                                alternative_id = alternate[0].memory_id
                                episode.record("re_retrieve", {
                                    "progress_key": f"a5-alternate:{task['task_id']}:{agent}",
                                    "candidate_count": len(alternate),
                                })
                                refreshed = fabric.certify(
                                    task["task_id"], [alternative_id], agent
                                )
                                reauthorized = gate.authorize(TOOL, agent, refreshed)
                                reason_codes[reauthorized.reason_code] += 1
                                allowed = reauthorized.allowed
                                reason = ("authorized_alternate_found" if allowed
                                          else reauthorized.reason_code)
                            else:
                                episode.record("abstain", {
                                    "reason": "NO_AUTHORIZED_ALTERNATE",
                                })
                                reason = "no_authorized_alternate"
                            recovery_trace.append({
                                "arm": arm,
                                "task_id": task["task_id"],
                                "alternate_count": len(alternate),
                                "status": episode.status.value,
                                "steps": episode.steps,
                                "search_attempts": episode.alternate_search_attempts,
                                "reauthorized": bool(alternate) and allowed,
                            })
                    else:
                        allowed = expected
                        reason = "oracle_label"
                except Exception as exc:
                    allowed = False
                    reason = f"tool_error:{type(exc).__name__}"
                    failure_class_counts["tool_error"] += 1
                unsafe = allowed and (
                    not expected
                    or (family in {"corrected", "recoverable"}
                        and reason not in {"authorized_alternate_found", "oracle_label"})
                )
                failure_classes = classify_failure(
                    arm, family, allowed and not unsafe, expected, reason,
                )
                if unsafe and "insufficient_evidence" not in failure_classes:
                    failure_classes.append("insufficient_evidence")
                failure_class_counts.update(failure_classes)
                allowed_count += int(allowed)
                task_correct = allowed == expected and not unsafe
                mismatched_agents += int(not task_correct)
                unsafe_actions += int(unsafe)
                stale_actions += int(allowed and family in {"corrected", "recoverable"} and unsafe)
                false_abstentions += int(expected and not allowed)
                per_agent[agent].append({
                    "task_id": task["task_id"], "family": family,
                    "correct": task_correct,
                    "unsafe_action": unsafe,
                    "high_risk": family in HIGH_RISK_FAMILIES,
                    "latency_ms": (time.perf_counter() - decision_started) * 1000,
                })
                family_result["attempted"] += 1
                family_result["correct"] += int(task_correct)
                family_result["unsafe_actions"] += int(unsafe)
                family_result["stale_actions"] += int(allowed and family == "corrected")
                family_result["false_abstentions"] += int(expected and not allowed)
            for category, number in failure_class_counts.items():
                family_result["failure_classes"][category] += number
            context_hash = _hash({"task_id": task["task_id"], "family": family,
                                  "evidence_text": evidence_text, "gold_hidden_from_agents": True})
            task_failure_classes = {name: failure_class_counts[name] for name in FAILURE_CLASSES
                                    if failure_class_counts[name]}
            details.append({"task_id": task["task_id"], "family": family,
                            "expected": "allow" if expected else "abstain",
                            "context_budget_items": int(evidence_id is not None),
                            "context_hash": context_hash,
                            "initial_exposure_equal": all(ids == initial_exposure_ids[0]
                                                           for ids in initial_exposure_ids),
                            "permission_grant_count": len(agents),
                            "permission_grants_sha256": _hash({agent: [TOOL] for agent in agents}),
                            "decision_counts": {"allowed": allowed_count, "abstained": agent_count-allowed_count,
                                                "false_abstentions": false_abstentions,
                                                "unsafe_actions": unsafe_actions, "stale_actions": stale_actions},
                            "reason_codes": dict(reason_codes),
                            "failure_trace": ({"task_id": task["task_id"], "arm": arm,
                                               "family": family,
                                               "source_memory_id": evidence_id or "NO_EVIDENCE",
                                               "reason_codes": dict(reason_codes),
                                               "failure_classes": task_failure_classes,
                                               "affected_agent_count": mismatched_agents}
                                              if task_failure_classes else None)})
        page_count_row = fabric.log._conn.execute("PRAGMA page_count").fetchone()
        page_size_row = fabric.log._conn.execute("PRAGMA page_size").fetchone()
        if page_count_row is None or page_size_row is None:
            raise RuntimeError("SQLite did not return storage page metadata")
        memory_storage_bytes = int(page_count_row[0]) * int(page_size_row[0])
    scratch.cleanup()
    agent_summaries = []
    for agent, outcomes in sorted(per_agent.items()):
        high_risk = [item for item in outcomes if item["high_risk"]]
        latencies = [item["latency_ms"] for item in outcomes]
        agent_summaries.append({
            "agent_id": agent, "attempted": len(outcomes),
            "successes": sum(item["correct"] for item in outcomes),
            "success_rate": sum(item["correct"] for item in outcomes) / len(outcomes),
            "high_risk_attempted": len(high_risk),
            "high_risk_success_rate": (sum(item["correct"] for item in high_risk) / len(high_risk)
                                       if high_risk else None),
            "unsafe_actions": sum(item["unsafe_action"] for item in outcomes),
            "mean_decision_latency_ms": fmean(latencies),
            "p95_decision_latency_ms": _percentile(latencies, 0.95),
            "max_decision_latency_ms": max(latencies, default=0.0),
        })
    agent_latencies = [item["latency_ms"] for rows_for_agent in per_agent.values()
                       for item in rows_for_agent]
    agent_fairness = {
        "agents": agent_summaries,
        "least_successful_agent": min(agent_summaries, key=lambda item: item["success_rate"]),
        "minimum_agent_success_rate": min((item["success_rate"] for item in agent_summaries), default=0.0),
        "minimum_high_risk_agent_success_rate": min(
            (item["high_risk_success_rate"] for item in agent_summaries
             if item["high_risk_success_rate"] is not None), default=0.0),
        "p95_decision_latency_ms": _percentile(agent_latencies, 0.95),
        "max_decision_latency_ms": max(agent_latencies, default=0.0),
    }
    totals = {key: sum(item[key] for item in result.values()) for key in
              ("attempted", "correct", "unsafe_actions", "stale_actions", "false_abstentions")}
    return {"seed": seed, "agent_count": agent_count, "arm": arm,
            "population": "synthetic_scripted",
            "counts": {**totals, "accuracy": totals["correct"] / totals["attempted"]},
            "by_family": result, "task_manifest": details,
            "agent_fairness": agent_fairness,
            "context_budget_max": 1, "runtime_tool": TOOL, "runtime_permission_grants": agent_count,
            "tool_registry_order": tool_order,
            "agent_identity_order_sha256": _hash(agents),
            "agent_identity_scheme": "seeded_opaque_ids_v1" if randomize_order else "ordinal_control",
            "retrieval_calls": retrieval_calls,
            "retrieval_call_budget": agent_count * len(tasks) * 3,
            "recovery_search_calls": recovery_search_calls,
            "recovery_alternates_found": recovery_alternates_found,
            "recovery_trace": recovery_trace,
            "context_items_exposed": context_items_exposed,
            "simulated_decision_attempts": agent_count * len(tasks),
            "external_tool_calls": 0,
            "wall_time_budget_ms": WALL_TIME_BUDGET_MS_PER_RUN,
            "memory_storage_bytes": memory_storage_bytes,
            "elapsed_s": round(time.perf_counter() - started, 6),
            "model_calls": 0, "model_tokens": 0, "model_usd": 0}


def build_report() -> dict[str, Any]:
    rows: list[dict[str, Any]] = [run(seed, count, arm) for seed in SEEDS for count in AGENT_COUNTS for arm in ARMS]
    expected_ids = {str(seed): [task["task_id"] for task in task_manifest(seed)] for seed in SEEDS}
    failures = []
    groups: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["seed"], row["agent_count"])].append(row)
        for task in row["task_manifest"]:
            if (not task["initial_exposure_equal"]
                    or task["permission_grant_count"] != row["agent_count"]
                    or not task["permission_grants_sha256"]):
                failures.append({"seed": row["seed"], "agent_count": row["agent_count"],
                                 "arm": row["arm"], "task_id": task["task_id"],
                                 "reason": "exposure_or_permission_mismatch"})
        actual_ids = [task["task_id"] for task in row["task_manifest"]]
        if actual_ids != expected_ids[str(row["seed"])] or len(actual_ids) != 8:
            failures.append({"seed": row["seed"], "agent_count": row["agent_count"],
                             "arm": row["arm"], "reason": "task_manifest_mismatch"})
    for (seed, count), matrix in groups.items():
        signatures = [{task["task_id"]: (task["context_hash"], task["context_budget_items"])
                       for task in row["task_manifest"]} for row in matrix]
        if any(signature != signatures[0] for signature in signatures[1:]):
            failures.append({"seed": seed, "agent_count": count, "reason": "arms_received_different_context"})
    unsafe_mf = sum(row["counts"]["unsafe_actions"] for row in rows if row["arm"] == "memory_fabric")
    unsafe_oracle = sum(row["counts"]["unsafe_actions"] for row in rows if row["arm"] == "oracle")
    failure_class_counts = {category: sum(
        task["failure_trace"]["failure_classes"].get(category, 0)
        for row in rows for task in row["task_manifest"] if task["failure_trace"])
        for category in FAILURE_CLASSES}
    failure_traces = [task["failure_trace"] for row in rows for task in row["task_manifest"]
                      if task["failure_trace"]]
    for trace in failure_traces:
        if (not trace["task_id"] or not trace["source_memory_id"] or not trace["failure_classes"]
                or set(trace["failure_classes"]) - set(FAILURE_CLASSES)):
            failures.append({"task_id": trace.get("task_id"), "reason": "unclassified_failure"})
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip())
    return {"schema": "mf-matched-agent-arms/1", "decision": "DESCRIPTIVE",
            "acceptance_status": "PASS" if not failures and unsafe_mf == 0 and unsafe_oracle == 0 else "FAIL",
            "population": "synthetic_scripted", "repo_commit": head(), "dirty": dirty,
            "environment": capture_environment(), "seeds": list(SEEDS),
            "agent_counts": list(AGENT_COUNTS), "arms": list(ARMS), "task_count_per_seed": 8,
            "task_family_composition": {family: 2 for family in FAMILIES},
            "matched_constraints": {"context_budget_items_max": 1, "runtime_tool": TOOL,
                                    "all_agents_granted_same_tool": True,
                                    "oracle_gold_in_agent_context": False},
            "input_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                             for path in ("benchmarks/matched_agent_arms.py",
                                          "benchmarks/agent_scale.py",
                                          "research/prereg/matched-agent-arms-v1.md",
                                          "research/prereg/failure-taxonomy-v1.md")},
            "invariant_failures": failures, "unsafe_actions_memory_fabric": unsafe_mf,
            "unsafe_actions_oracle": unsafe_oracle,
            "failure_taxonomy": {"categories": list(FAILURE_CLASSES),
                                 "counts": failure_class_counts, "traces": failure_traces},
            "rows": rows,
            "limitations": ["Local deterministic scripted agents and one in-process store.",
                            "Arms are policy baselines, not independently implemented memory products.",
                            "No real-model reasoning, network transport, latency guarantee, or cost claim."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research/results/r3-02-matched-agent-arms.json")
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "acceptance_status": report["acceptance_status"],
                      "runs": len(report["rows"]), "arms": report["arms"],
                      "invariant_failures": len(report["invariant_failures"])}))
    return int(report["acceptance_status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
