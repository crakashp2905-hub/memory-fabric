"""Read-only agent-outcome views for operators (W21-01 .. W21-10).

The view model is built from committed, frozen result files (the directory is
configured with ``MEMORY_FABRIC_OUTCOME_ARTIFACTS``) plus, for lineage, the live
store. It is served by the observability server, which answers every
non-GET method with 405, and it offers no controls: nothing here can mutate
evidence, policy or action authorization.

Rules every view follows:

* a metric that was not measured renders ``NOT_MEASURED`` and an arm that was
  not run renders ``NOT_RUN``, never zero;
* every view carries its provenance (source SHA, evidence type, model digest,
  population, seeds), and the ``real-agent`` badge appears only for local-model
  evidence with a model digest;
* counterfactual replay is labelled hypothetical, never a verified cause;
* views carry ids, codes, digests and aggregates, never memory content,
  prompts, credentials or evaluator truth (``assert_content_safe``).
"""

from __future__ import annotations

__stability__ = "experimental"

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_ID = "memory-fabric.agent-outcome-console.v1"
FILES = {"scorecard": "scripted-scorecard-dev.json", "arms": "scripted-arms-dev.json",
         "decision": "LAUNCH_DECISION.json", "performance": "performance-dev.json",
         "poisoning": "poisoning-dev.json", "tenant_probe": "tenant-probe-dev.json",
         "episode": "demo-episode-trace.json"}
FORBIDDEN_KEYS = frozenset({"content", "text", "prompt", "messages", "credential", "token",
                            "secret", "hidden_truth", "oracle_payload", "truth", "password"})
NOT_MEASURED, NOT_RUN = "NOT_MEASURED", "NOT_RUN"
COMPARISON_ARMS = ("A3", "A4", "A5", "A6")
HYPOTHETICAL = "HYPOTHETICAL_REPLAY: a policy re-run on changed evidence; not a verified real-world cause"


def _load(directory: Path | None, key: str) -> dict[str, Any] | None:
    if directory is None:
        return None
    path = directory / FILES[key]
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _value(metric: Any) -> Any:
    if isinstance(metric, Mapping):
        metric = metric.get("value")
    return NOT_MEASURED if metric in (None, "NOT_RECORDED") else metric


def provenance(scorecard: Mapping[str, Any] | None, arms: Mapping[str, Any] | None) -> dict[str, Any]:
    evidence = (scorecard or {}).get("evidence_type") or NOT_MEASURED
    digest = None
    if arms and isinstance(arms.get("model"), Mapping):
        digest = arms["model"].get("digest")
    badge = "real-agent" if evidence == "local_model" and digest else (
        "scripted" if evidence in {"scripted", "fake_backend"} else "unlabelled")
    return {"source_sha": (scorecard or {}).get("source_sha") or NOT_MEASURED,
            "evidence_type": evidence, "model_digest": digest or "none (no model ran)",
            "population": (arms or {}).get("population", NOT_MEASURED),
            "seeds": (arms or {}).get("seeds", NOT_MEASURED), "badge": badge}


def summary_view(scorecard: Mapping[str, Any] | None) -> dict[str, Any]:
    if not scorecard:
        return {"status": NOT_RUN}
    rows = {}
    for arm, metrics in scorecard.get("arms", {}).items():
        resources = metrics.get("resources", {})
        rows[arm] = {"completion": _value(metrics.get("completion")),
                     "failures_blocked_or_incomplete": NOT_MEASURED,
                     "false_withholding": _value(metrics.get("false_withholding")),
                     "unsafe_attempts_refused_by_gate": _value(metrics.get("gate_refused_attempts")),
                     "unsafe_executed": _value(metrics.get("unsafe_executed")),
                     "steps": resources.get("steps", NOT_MEASURED),
                     "tool_calls": resources.get("tool_calls", NOT_MEASURED),
                     "model_tokens": _value(resources.get("model_tokens"))}
    return {"status": "RUN", "by_arm": rows, "decision": scorecard.get("decision", NOT_MEASURED)}


def comparison_view(scorecard: Mapping[str, Any] | None,
                    arms: Mapping[str, Any] | None) -> dict[str, Any]:
    present = set((scorecard or {}).get("arms", {}))
    uncertainty = (scorecard or {}).get("uncertainty", NOT_MEASURED)
    rows: dict[str, dict[str, Any]] = {}
    for arm in COMPARISON_ARMS:
        if arm not in present:
            rows[arm] = {"status": NOT_RUN}
            continue
        metrics = scorecard["arms"][arm]  # type: ignore[index]
        by_family = (scorecard or {}).get("by_family", {}).get(arm, {})
        cost = ((arms or {}).get("coordination", {}).get("by_arm", {}).get(arm, {})
                .get("steps_mean", NOT_MEASURED))
        rows[arm] = {"status": "RUN", "safe_success": _value(metrics.get("safe_success")),
                     "interval": (uncertainty.get(arm, {}).get("safe_success_wilson95", NOT_MEASURED)
                                  if isinstance(uncertainty, Mapping) else uncertainty),
                     "by_family": {f: _value(v.get("safe_success")) for f, v in by_family.items()},
                     "cost_steps_mean": cost}
    return {"arms": rows}


def diagnosis_panel(arms: Mapping[str, Any] | None) -> dict[str, Any]:
    """Separate safe abstention, incomplete work and policy denial per arm."""
    if not arms:
        return {"status": NOT_RUN}
    out: dict[str, dict[str, int]] = {}
    for row in arms.get("rows", []):
        bucket = out.setdefault(row["arm"], {"completed": 0, "safe_abstain": 0, "incomplete": 0,
                                             "policy_denial": 0, "unsafe": 0})
        reason = str(row.get("host_reason", ""))
        if row.get("terminal_status") == "COMPLETED":
            bucket["completed"] += 1
        elif row.get("terminal_status") == "UNSAFE_EXECUTED":
            bucket["unsafe"] += 1
        elif any(code in reason for code in ("not_granted", "permission", "wrong_tenant", "not_visible")):
            bucket["policy_denial"] += 1
        elif row.get("terminal_status") == "SAFE_ABSTAINED" and row.get("justified_abstention"):
            bucket["safe_abstain"] += 1
        else:
            bucket["incomplete"] += 1
    return {"status": "RUN", "by_arm": out,
            "legend": {"safe_abstain": "nothing authorized acting, and the agent did not act",
                       "incomplete": "the task stopped without its objective (blocked, budget, "
                                     "unjustified abstention)",
                       "policy_denial": "the caller's own permission refused the action"}}


def replay_view(arms: Mapping[str, Any] | None) -> dict[str, Any]:
    cdm = (arms or {}).get("cdm")
    if not cdm or cdm.get("status") != "RUN":
        return {"status": NOT_RUN, "label": HYPOTHETICAL}
    utility = cdm.get("utility", {})
    return {"status": "RUN", "label": HYPOTHETICAL,
            "policy_flips": cdm.get("flips"),
            "observed_completion_difference": utility.get("completion_difference", NOT_MEASURED),
            "observed_safety_difference": utility.get("safety_difference", NOT_MEASURED),
            "replay_cost": utility.get("replay_cost", NOT_MEASURED),
            "net_utility": utility.get("net_utility", NOT_MEASURED),
            "promotion": cdm.get("promotion"),
            "skip_reasons": cdm.get("reasons", {}),
            "physical_causality": cdm.get("physical_causality", "NOT_ESTABLISHED")}


def timeline_view(episode: Mapping[str, Any] | None) -> dict[str, Any]:
    """Observation -> retrieval -> plan -> verification -> recovery -> effect, by sequence."""
    if not episode:
        return {"status": NOT_RUN}
    steps = []
    for index, event in enumerate(episode.get("events", [])):
        payload = event.get("payload", {})
        refs = {key: payload[key] for key in ("event_ids", "evidence", "reason_codes", "ok",
                                              "outcome", "commitment", "intent", "phase",
                                              "host_outcome", "reason", "fingerprint")
                if key in payload}
        if "recorded" in payload:
            refs["recorded"] = [{"event_id": r.get("event_id"), "memory_id": r.get("memory_id"),
                                 "version": r.get("version")} for r in payload["recorded"]]
        steps.append({"seq": index, "audit_ref": event.get("event_id"), "kind": event.get("kind"),
                      "role": event.get("role"), "refs": refs})
    return {"status": "RUN", "task_id": episode.get("task_id"), "digest": episode.get("digest"),
            "time": "sequence order; no wall clock recorded", "steps": steps}


def budget_view(performance: Mapping[str, Any] | None,
                arms: Mapping[str, Any] | None) -> dict[str, Any]:
    perf = performance or {}
    cdm_cost = perf.get("cdm_cost", {})
    return {"queue_depth": NOT_MEASURED,
            "queue_depth_cap": "bounded by JobSpool.max_depth; refuses new work when full",
            "replay_cost": {"dependence_first": cdm_cost.get("dependence_first", NOT_MEASURED),
                            "always_on": cdm_cost.get("always_on", NOT_MEASURED)},
            "retries": {arm: v.get("recoveries_mean", NOT_MEASURED) for arm, v in
                        (arms or {}).get("coordination", {}).get("by_arm", {}).items()},
            "host": perf.get("host", NOT_MEASURED)}


def red_team_view(poisoning: Mapping[str, Any] | None,
                  probe: Mapping[str, Any] | None) -> dict[str, Any]:
    scenarios = []
    for row in (poisoning or {}).get("families", []):
        scenarios.append({"scenario": f"contaminated evidence: {row['family']}",
                          "naive_control_fooled": row.get("control_fooled"),
                          "governed_fooled": row.get("governed_fooled")})
    scenarios.append({"scenario": "revoked principal",
                      "outcome": "the next call is refused on every access path",
                      "test": "tests/test_access_matrix.py::Matrix::test_a_revoked_credential_is_refused_at_the_next_call"})
    scenarios.append({"scenario": "erased memory",
                      "outcome": "erased content is diagnosed withdrawn and never returned",
                      "test": "tests/test_erasure_residue.py::ErasureLeavesNoResidue"})
    if probe:
        scenarios.append({"scenario": "cross-tenant existence probe",
                          "payloads_identical": probe.get("payloads_identical"),
                          "residual_timing_s": probe.get("median_difference_seconds")})
    return {"scenarios": scenarios, "controls": [],
            "note": "walkthrough only: there is no retry or override control in this view"}


def lineage_view(fabric: Any, memory_ids: Iterable[str]) -> list[dict[str, Any]]:
    """Source root, copies, exact version, trust state and retraction per memory (W21-03)."""
    from ..independence import global_ref, independent_sources

    rows = []
    for memory_id in memory_ids:
        memory = fabric.get(memory_id)
        root = global_ref(fabric, memory_id)
        same_root = [m for m in fabric.state.memories if global_ref(fabric, m) == root]
        rows.append({"memory_id": memory_id, "version": memory.version,
                     "trust_state": str(getattr(memory.lifecycle_state, "value", memory.lifecycle_state)),
                     "retracted": str(getattr(memory.lifecycle_state, "value", "")) in
                     {"quarantined", "deprecated", "deleted"},
                     "source_root": list(root), "copies_of_root": len(same_root),
                     "independent_roots_with_copies": independent_sources(fabric, same_root),
                     "independent_endorsement": False if len(same_root) > 1 else None})
    return rows


def assert_content_safe(value: Any, path: str = "") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"forbidden key {key!r} at {path or '/'}")
            assert_content_safe(item, f"{path}/{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_content_safe(item, f"{path}[{index}]")


def build_view(directory: str | Path | None) -> dict[str, Any]:
    if directory is None:
        return {"schema_id": SCHEMA_ID, "status": "NOT_CONFIGURED", "read_only": True,
                "controls": [],
                "detail": "set MEMORY_FABRIC_OUTCOME_ARTIFACTS to a directory of frozen results"}
    base = Path(directory)
    loaded = {key: _load(base, key) for key in FILES}
    view = {"schema_id": SCHEMA_ID, "status": "RUN", "read_only": True, "controls": [],
            "provenance": provenance(loaded["scorecard"], loaded["arms"]),
            "summary": summary_view(loaded["scorecard"]),
            "comparison": comparison_view(loaded["scorecard"], loaded["arms"]),
            "diagnosis": diagnosis_panel(loaded["arms"]),
            "replay": replay_view(loaded["arms"]),
            "timeline": timeline_view(loaded["episode"]),
            "budgets": budget_view(loaded["performance"], loaded["arms"]),
            "red_team": red_team_view(loaded["poisoning"], loaded["tenant_probe"]),
            "decision": {k: (loaded["decision"] or {}).get(k, {}).get("decision", NOT_MEASURED)
                         for k in ("engineering", "deployment")},
            "missing_inputs": sorted(k for k, v in loaded.items() if v is None)}
    assert_content_safe(view)
    return view
