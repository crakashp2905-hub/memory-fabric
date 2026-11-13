#!/usr/bin/env python3
"""Fail-closed confirmatory analysis guard for agent-outcome case artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any

SCHEMA_ID = "memory-fabric.agent-outcome-confirmatory.v1"
REPORT_SCHEMA_ID = "memory-fabric.outcome-confirmatory-report.v2"
_DESIGN_FIELDS = (
    "development_seeds", "confirmatory_seeds", "task_ids_by_seed", "arms",
    "contrasts", "minimum_effect", "multiplicity", "sample_size",
    "stopping_rule", "resource_caps",
)
_MANIFEST_FIELDS = {"schema_id", "manifest_version", "status", *_DESIGN_FIELDS,
                    "design_sha256", "freeze_date", "freeze_commit"}


def design_digest(manifest: dict[str, Any]) -> str:
    """Hash every preregistered split, comparison, threshold, and cap."""
    canonical = json.dumps(
        {name: manifest[name] for name in _DESIGN_FIELDS},
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_manifest(manifest: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_FIELDS:
        return ["manifest fields do not match confirmatory schema v1"]
    if manifest["schema_id"] != SCHEMA_ID or manifest["manifest_version"] != 1:
        errors.append("unsupported confirmatory manifest schema")
    if manifest["status"] != "FROZEN":
        errors.append("protocol is not frozen; confirmatory analysis is blocked")
    development = manifest["development_seeds"]
    confirmatory = manifest["confirmatory_seeds"]
    if (not isinstance(development, list) or not isinstance(confirmatory, list)
            or any(type(seed) is not int or seed < 0 for seed in development + confirmatory)):
        errors.append("development and confirmatory seeds must be non-negative integer lists")
    else:
        if len(development) != len(set(development)) or len(confirmatory) != len(set(confirmatory)):
            errors.append("seed lists must not contain duplicates")
        if set(development) & set(confirmatory):
            errors.append("confirmatory seeds overlap development/tuning seeds")
        if not confirmatory:
            errors.append("confirmatory seed list is empty")
    tasks = manifest["task_ids_by_seed"]
    if not isinstance(tasks, dict):
        errors.append("task_ids_by_seed must be an object")
        tasks = {}
    if isinstance(confirmatory, list):
        expected_seed_keys = {str(seed) for seed in confirmatory
                              if type(seed) is int and seed >= 0}
        if set(tasks) != expected_seed_keys:
            errors.append("task IDs must be declared for every confirmatory seed only")
    for seed, task_ids in tasks.items():
        if (not isinstance(task_ids, list) or not task_ids
                or any(not isinstance(task_id, str) or not task_id for task_id in task_ids)
                or len(task_ids) != len(set(task_ids))):
            errors.append(f"task IDs for seed {seed} must be unique non-empty strings")
    arms = manifest["arms"]
    if (not isinstance(arms, list)
            or any(not isinstance(arm, str) or not arm for arm in arms)
            or (all(isinstance(arm, str) for arm in arms) and len(arms) != len(set(arms)))):
        errors.append("arms must be unique non-empty strings")
        arms = []
    contrasts = manifest["contrasts"]
    if not isinstance(contrasts, list) or not contrasts:
        errors.append("at least one planned contrast is required")
    else:
        for pair in contrasts:
            if (not isinstance(pair, list) or len(pair) != 2 or pair[0] == pair[1]
                    or any(arm not in arms for arm in pair)):
                errors.append("each contrast must name two distinct registered arms")
    effect = manifest["minimum_effect"]
    if (isinstance(effect, bool) or not isinstance(effect, (int, float))
            or not math.isfinite(effect) or not 0 < effect < 1):
        errors.append("minimum_effect must be a finite proportion between zero and one")
    if manifest["multiplicity"] != "holm_bonferroni":
        errors.append("multiplicity correction must be preregistered as holm_bonferroni")
    if type(manifest["sample_size"]) is not int or manifest["sample_size"] <= 0:
        errors.append("sample_size must be a positive frozen integer")
    elif sum(len(ids) for ids in tasks.values() if isinstance(ids, list)) != manifest["sample_size"]:
        errors.append("sample_size must equal the declared number of confirmatory task cases")
    if not isinstance(manifest["stopping_rule"], str) or not manifest["stopping_rule"].strip():
        errors.append("a frozen stopping_rule is required")
    if not isinstance(manifest["resource_caps"], dict) or not manifest["resource_caps"]:
        errors.append("frozen resource_caps are required")
    else:
        replay_cap = manifest["resource_caps"].get("max_replay_wall_ms_per_case")
        if (isinstance(replay_cap, bool) or not isinstance(replay_cap, (int, float))
                or not math.isfinite(replay_cap) or replay_cap <= 0):
            errors.append("a positive frozen max_replay_wall_ms_per_case is required")
    if not isinstance(manifest["freeze_date"], str) or not manifest["freeze_date"]:
        errors.append("freeze_date is required")
    if not isinstance(manifest["freeze_commit"], str) or len(manifest["freeze_commit"]) != 40:
        errors.append("freeze_commit must be a full 40-character Git SHA")
    expected_digest = manifest["design_sha256"]
    try:
        calculated_digest = design_digest(manifest)
    except (KeyError, TypeError, ValueError):
        calculated_digest = None
    if (not isinstance(expected_digest, str) or len(expected_digest) != 64
            or expected_digest != calculated_digest):
        errors.append("design_sha256 mismatch; preregistered design changed")
    return errors


def holm_bonferroni(p_values: dict[str, float]) -> dict[str, float]:
    """Return monotone Holm-adjusted p-values for all registered contrasts."""
    if not p_values:
        return {}
    if any(not isinstance(key, str) or not key or isinstance(value, bool)
           or not isinstance(value, (int, float)) or not 0 <= value <= 1
           for key, value in p_values.items()):
        raise ValueError("p-values must be named finite values between zero and one")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    count = len(ordered)
    adjusted: dict[str, float] = {}
    running_max = 0.0
    for rank, (name, value) in enumerate(ordered):
        running_max = max(running_max, min(1.0, (count - rank) * value))
        adjusted[name] = running_max
    return adjusted


def _exact_sign_p(differences: list[int]) -> float:
    wins = sum(value > 0 for value in differences)
    losses = sum(value < 0 for value in differences)
    discordant = wins + losses
    tail = sum(math.comb(discordant, k) for k in range(min(wins, losses) + 1))
    return min(1.0, 2.0 * tail / (2**discordant)) if discordant else 1.0


def _paired_cluster_bootstrap_ci(
    differences: list[int], *, iterations: int = 10_000, seed: int = 0,
) -> list[float]:
    """Return a deterministic percentile CI by resampling paired task cases."""
    if (not differences or type(iterations) is not int or not 1 <= iterations <= 1_000_000
            or type(seed) is not int or seed < 0
            or any(type(value) is not int or value not in {-1, 0, 1}
                   for value in differences)):
        raise ValueError("paired bootstrap requires non-empty binary case differences")
    rng = random.Random(seed)
    size = len(differences)
    means = sorted(
        sum(differences[rng.randrange(size)] for _ in range(size)) / size
        for _ in range(iterations)
    )

    def nearest_rank(probability: float) -> float:
        return means[max(0, math.ceil(probability * iterations) - 1)]

    return [nearest_rank(0.025), nearest_rank(0.975)]


def _least_agent_and_correction_gate(
    raw: dict[tuple[int, str, str], dict[str, Any]],
    labels: dict[tuple[int, str, str], dict[str, Any]],
    answerable: dict[tuple[int, str], bool],
    seeds: set[int],
) -> dict[str, Any]:
    """Require per-seed least-agent non-regression and verified correction recovery."""
    by_seed: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    failed = False
    for seed in sorted(seeds):
        task_ids = sorted(task for (case_seed, task), is_answerable in answerable.items()
                          if case_seed == seed and is_answerable)
        rates: dict[str, dict[str, float]] = {}
        roster: set[str] | None = None
        for arm in ("A3", "A4", "A5"):
            completed: dict[str, int] = {}
            seen: dict[str, int] = {}
            for task_id in task_ids:
                row = raw[(seed, task_id, arm)]
                agents = row.get("agents")
                if not isinstance(agents, list) or not agents:
                    missing.append(f"seed {seed} {arm}/{task_id}: per-agent outcomes absent")
                    continue
                current: set[str] = set()
                for agent in agents:
                    if (not isinstance(agent, dict) or not isinstance(agent.get("agent_id"), str)
                            or not agent["agent_id"] or not isinstance(agent.get("status"), str)):
                        missing.append(f"seed {seed} {arm}/{task_id}: invalid per-agent outcome")
                        continue
                    current.add(agent["agent_id"])
                    seen[agent["agent_id"]] = seen.get(agent["agent_id"], 0) + 1
                    completed[agent["agent_id"]] = completed.get(agent["agent_id"], 0) + int(
                        agent["status"] == "COMPLETED"
                    )
                if roster is None:
                    roster = current
                elif current != roster:
                    missing.append(f"seed {seed} {arm}/{task_id}: agent roster differs")
            if seen and all(count == len(task_ids) for count in seen.values()):
                rates[arm] = {agent: completed[agent] / seen[agent] for agent in seen}
            else:
                missing.append(f"seed {seed} {arm}: incomplete agent/task coverage")

        least = {arm: min(values.values()) for arm, values in rates.items() if values}
        if all(arm in least for arm in ("A3", "A4", "A5")):
            comparator = max(least["A3"], least["A4"])
            least_ok = least["A5"] >= comparator
            failed |= not least_ok
        else:
            comparator = None
            least_ok = False

        required_corrections = 0
        missed_corrections = 0
        for task_id in task_ids:
            key = (seed, task_id, "A5")
            label_rows = labels[key].get("decision_reevaluations", [])
            outcome_rows = raw[key].get("decision_reevaluations", [])
            if not isinstance(label_rows, list) or not isinstance(outcome_rows, list):
                missing.append(f"seed {seed} A5/{task_id}: correction labels malformed")
                continue
            observed = {item.get("reevaluation_id"): item for item in outcome_rows
                        if isinstance(item, dict)}
            for label in label_rows:
                if not isinstance(label, dict) or type(label.get("required")) is not bool:
                    missing.append(f"seed {seed} A5/{task_id}: correction label invalid")
                    continue
                if not label["required"]:
                    continue
                required_corrections += 1
                event = observed.get(label.get("reevaluation_id"))
                completed_task = raw[key].get("assessment", {}).get("status") == "COMPLETED"
                if not event or type(event.get("performed")) is not bool:
                    missing.append(f"seed {seed} A5/{task_id}: required correction outcome absent")
                elif not event["performed"] or not completed_task:
                    missed_corrections += 1
                    failed = True
        if required_corrections == 0:
            missing.append(f"seed {seed}: no preregistered required correction case")
        by_seed[str(seed)] = {
            "least_agent_completion_rate": least,
            "strongest_fair_baseline_least_agent_rate": comparator,
            "least_agent_non_regression_passed": least_ok,
            "required_correction_cases": required_corrections,
            "missed_or_incomplete_corrections": missed_corrections,
        }
    if missing:
        status = "NOT_ASSESSABLE"
    else:
        status = "HOLD" if failed else "PASS"
    return {
        "status": status,
        "required_for_promotion_review": True,
        "promotion_authorized": False,
        "rule": "For each seed A5 least-agent completion must match or exceed the strongest of A3/A4; every required A5 correction reevaluation must be performed and end in verified completion.",
        "by_seed": by_seed,
        "missing_evidence": sorted(set(missing)),
    }


def confirmatory_report(
    manifest: dict[str, Any],
    outcomes: dict[str, Any],
    evaluator_labels: dict[str, Any],
    attempts: list[dict[str, Any]],
    *,
    manifest_sha256: str,
    outcomes_sha256: str,
    labels_sha256: str,
) -> dict[str, Any]:
    """Validate the sealed design and complete attempt log before comparison."""
    errors = validate_manifest(manifest)
    design = manifest.get("design_sha256") if isinstance(manifest, dict) else None
    if errors:
        return {
            "schema_id": REPORT_SCHEMA_ID,
            "status": "REJECTED",
            "decision": "NO_CONFIRMATORY_ESTIMATE",
            "errors": errors,
            "attempts": attempts if isinstance(attempts, list) else [],
            "manifest_sha256": manifest_sha256,
            "design_sha256": design,
            "outcomes_sha256": outcomes_sha256,
            "evaluator_labels_sha256": labels_sha256,
        }
    if not isinstance(attempts, list) or not attempts:
        errors.append("attempt ledger is missing; all run attempts must be recorded")
        attempts = []
    valid_attempt_statuses = {"COMPLETED", "FAILED", "STOPPED", "NOT_RUN"}
    attempts_by_seed: dict[int, list[dict[str, Any]]] = {}
    for attempt in attempts:
        if not isinstance(attempt, dict) or set(attempt) != {
            "attempt_id", "seed", "split", "status", "design_sha256", "note",
        }:
            errors.append("every attempt must contain the exact versioned attempt fields")
            continue
        if (not isinstance(attempt["attempt_id"], str) or not attempt["attempt_id"]
                or type(attempt["seed"]) is not int or attempt["seed"] < 0
                or not isinstance(attempt["split"], str)
                or attempt["split"] not in {"development", "confirmatory"}
                or not isinstance(attempt["status"], str)
                or attempt["status"] not in valid_attempt_statuses
                or attempt["design_sha256"] != design
                or not isinstance(attempt["note"], str)):
            errors.append("attempt record has invalid split, status, or frozen design digest")
            continue
        attempts_by_seed.setdefault(attempt["seed"], []).append(attempt)

    if not isinstance(outcomes, dict) or not isinstance(evaluator_labels, dict):
        errors.append("outcomes and sealed evaluator labels must be JSON objects")
        outcomes = {}
        evaluator_labels = {}
    outcome_rows = outcomes.get("rows", [])
    label_rows = evaluator_labels.get("rows", [])
    if outcomes.get("schema_id") != "memory-fabric.outcome-raw-cases.v2":
        errors.append("raw outcome artifact schema mismatch")
    if evaluator_labels.get("schema_id") != "memory-fabric.outcome-sealed-labels.v1":
        errors.append("sealed evaluator-label artifact schema mismatch")
    if evaluator_labels.get("visibility") != "EVALUATOR_ONLY":
        errors.append("evaluator labels are not sealed as evaluator-only")

    def keyed(rows: Any, expected_fields: set[str], label: str) -> dict[tuple[int, str, str], dict[str, Any]]:
        result: dict[tuple[int, str, str], dict[str, Any]] = {}
        if not isinstance(rows, list):
            errors.append(f"{label} rows must be a list")
            return result
        for row in rows:
            if not isinstance(row, dict) or not expected_fields.issubset(row):
                errors.append(f"{label} row is missing its case identity fields")
                continue
            if (type(row["seed"]) is not int or row["seed"] < 0
                    or not isinstance(row["task_id"], str)
                    or not isinstance(row["arm"], str)):
                errors.append(f"{label} row has invalid case identity values")
                continue
            key = (row["seed"], row["task_id"], row["arm"])
            if key in result:
                errors.append(f"duplicate {label} row for {key}")
            result[key] = row
        return result

    raw = keyed(outcome_rows, {"seed", "task_id", "arm", "assessment"}, "outcome")
    labels = keyed(label_rows, {"seed", "task_id", "arm", "answerable"}, "label")
    if set(raw) != set(labels):
        errors.append("raw outcome and sealed-label case identities differ")
    expected: set[tuple[int, str, str]] = set()
    if isinstance(manifest.get("task_ids_by_seed"), dict):
        for seed_text, task_ids in manifest["task_ids_by_seed"].items():
            try:
                seed = int(seed_text)
            except (TypeError, ValueError):
                continue
            for task_id in task_ids if isinstance(task_ids, list) else ():
                for arm in manifest.get("arms", []):
                    expected.add((seed, task_id, arm))
    if set(raw) != expected:
        errors.append("confirmatory artifacts do not contain every preregistered case for every arm")
    # AO-060 requires complete cost and safety instrumentation for every arm.
    for row in raw.values():
        for name in ("replay_wall_ms", "effect_proposals", "unsafe_proposals",
                     "executed_effects", "unsafe_executions"):
            value = row.get(name)
            if (type(value) not in (int, float) or not math.isfinite(value) or value < 0
                    or (name != "replay_wall_ms" and type(value) is not int)):
                errors.append(f"outcome row requires a valid measured {name}")
        if row.get("unsafe_proposals", 0) > row.get("effect_proposals", 0):
            errors.append("unsafe proposals cannot exceed effect proposals")
        if row.get("unsafe_executions", 0) > row.get("executed_effects", 0):
            errors.append("unsafe executions cannot exceed executed effects")
    development = set(manifest.get("development_seeds", []))
    confirmatory = set(manifest.get("confirmatory_seeds", []))
    observed_seeds = {key[0] for key in raw}
    if observed_seeds & development:
        errors.append("development/tuning seed found in confirmatory outcome data")
    if not observed_seeds <= confirmatory:
        errors.append("outcome artifact contains an undeclared confirmatory seed")
    for seed in confirmatory:
        seed_attempts = attempts_by_seed.get(seed, [])
        if not seed_attempts:
            errors.append(f"confirmatory seed {seed} has no recorded attempt")
        if any(item["split"] != "confirmatory" for item in seed_attempts):
            errors.append(f"confirmatory seed {seed} is recorded in a different split")
        if any(item["status"] != "COMPLETED" for item in seed_attempts):
            errors.append(f"confirmatory seed {seed} has a failed, stopped, or skipped attempt")
        if len(seed_attempts) != 1:
            errors.append(f"confirmatory seed {seed} must have exactly one registered attempt")
    if any(item["split"] == "confirmatory" and item["seed"] in development
           for item in attempts if isinstance(item, dict) and "split" in item and "seed" in item):
        errors.append("attempt ledger marks a development seed as confirmatory")

    if errors:
        return {
            "schema_id": REPORT_SCHEMA_ID,
            "status": "REJECTED",
            "decision": "NO_CONFIRMATORY_ESTIMATE",
            "errors": sorted(set(errors)),
            "attempts": attempts,
            "manifest_sha256": manifest_sha256,
            "design_sha256": design,
            "outcomes_sha256": outcomes_sha256,
            "evaluator_labels_sha256": labels_sha256,
        }

    answerable_by_case: dict[tuple[int, str], bool] = {}
    for key, row in labels.items():
        if type(row["answerable"]) is not bool:
            errors.append("answerable evaluator label must be boolean")
        case_key = (key[0], key[1])
        previous = answerable_by_case.setdefault(case_key, row["answerable"])
        if previous != row["answerable"]:
            errors.append("answerability label differs across arms for the same task case")
    if errors:
        return {"schema_id": REPORT_SCHEMA_ID,
                "status": "REJECTED", "decision": "NO_CONFIRMATORY_ESTIMATE",
                "errors": sorted(set(errors)), "attempts": attempts}

    contrasts: dict[str, dict[str, Any]] = {}
    raw_p: dict[str, float] = {}
    for treatment, control in manifest["contrasts"]:
        name = f"{treatment}-{control}"
        differences = []
        treatment_successes = control_successes = 0
        for seed, task_id in sorted(answerable_by_case):
            if not answerable_by_case[(seed, task_id)]:
                continue
            left_assessment = raw[(seed, task_id, treatment)].get("assessment", {})
            right_assessment = raw[(seed, task_id, control)].get("assessment", {})
            if not isinstance(left_assessment, dict) or not isinstance(right_assessment, dict):
                return {"schema_id": REPORT_SCHEMA_ID,
                        "status": "REJECTED", "decision": "NO_CONFIRMATORY_ESTIMATE",
                        "errors": ["outcome assessment must be an object"],
                        "attempts": attempts}
            left_status = left_assessment.get("status")
            right_status = right_assessment.get("status")
            supported_statuses = {
                "COMPLETED", "SAFE_ABSTENTION", "FAILED", "UNSAFE", "UNDECIDABLE",
            }
            if left_status not in supported_statuses or right_status not in supported_statuses:
                return {"schema_id": REPORT_SCHEMA_ID,
                        "status": "REJECTED", "decision": "NO_CONFIRMATORY_ESTIMATE",
                        "errors": ["outcome contains an unsupported terminal status"],
                        "attempts": attempts}
            left = left_status == "COMPLETED"
            right = right_status == "COMPLETED"
            treatment_successes += int(left)
            control_successes += int(right)
            differences.append(int(left) - int(right))
        if not differences:
            return {"schema_id": REPORT_SCHEMA_ID,
                    "status": "REJECTED", "decision": "NO_CONFIRMATORY_ESTIMATE",
                    "errors": ["primary analysis has no answerable paired task cases"],
                    "attempts": attempts}
        mean_difference = sum(differences) / len(differences)
        p_value = _exact_sign_p(differences)
        interval = _paired_cluster_bootstrap_ci(differences)
        raw_p[name] = p_value
        contrasts[name] = {
            "treatment_completed": treatment_successes,
            "control_completed": control_successes,
            "denominator": len(differences),
            "unit": "paired answerable world/task case",
            "paired_completion_difference": mean_difference,
            "paired_cluster_bootstrap_ci_95": interval,
            "bootstrap_iterations": 10_000,
            "bootstrap_seed": 0,
            "bootstrap_interval": "two-sided percentile; nearest-rank quantiles",
            "minimum_effect": manifest["minimum_effect"],
            "meets_material_threshold": mean_difference >= manifest["minimum_effect"],
            "exact_sign_test_p": p_value,
        }
    adjusted = holm_bonferroni(raw_p)
    for name, result in contrasts.items():
        result["holm_adjusted_p"] = adjusted[name]
        result["positive_paired_interval"] = result["paired_cluster_bootstrap_ci_95"][0] > 0
        result["holm_significant"] = adjusted[name] < 0.05
    primary_names = ("A5-A3", "A5-A4")
    robustness = _least_agent_and_correction_gate(
        raw, labels, answerable_by_case, confirmatory
    )
    primary_clear = robustness["status"] == "PASS" and all(
        name in contrasts
        and contrasts[name]["meets_material_threshold"]
        and contrasts[name]["positive_paired_interval"]
        and contrasts[name]["holm_significant"]
        for name in primary_names
    )
    primary_gate = {
        "status": "PASS_FOR_OWNER_REVIEW" if primary_clear else "HOLD",
        "promotion_authorized": False,
        "required_contrasts": list(primary_names),
        "all_required_contrasts_pass": primary_clear,
        "least_agent_and_correction_gate": robustness["status"],
        "rule": "Each A5 fair-baseline contrast must meet the material threshold, have a positive paired 95% interval lower bound, and pass Holm-adjusted exact sign testing.",
    }
    cdm = _cdm_owner_review_gate(
        manifest, raw, answerable_by_case, contrasts.get("A6-A5")
    )
    return {
        "schema_id": REPORT_SCHEMA_ID,
        "status": "ANALYZED",
        "decision": "ANALYSIS_ONLY; promotion requires frozen acceptance and owner review",
        "manifest_sha256": manifest_sha256,
        "design_sha256": design,
        "outcomes_sha256": outcomes_sha256,
        "evaluator_labels_sha256": labels_sha256,
        "multiplicity_correction": "holm_bonferroni",
        "attempts": attempts,
        "contrasts": contrasts,
        "primary_improvement_gate": primary_gate,
        "robustness_gate": robustness,
        "cdm_incremental_assessment": cdm,
    }


def _cdm_owner_review_gate(
    manifest: dict[str, Any], raw: dict[tuple[int, str, str], dict[str, Any]],
    answerable: dict[tuple[int, str], bool],
    paired_contrast: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report AO-060 point-estimate gates without granting promotion authority."""
    cap = manifest["resource_caps"]["max_replay_wall_ms_per_case"]
    paired = [case for case, is_answerable in sorted(answerable.items()) if is_answerable]
    cdm_rows = [raw[(seed, task, "A6")] for seed, task in paired]
    baseline_rows = [raw[(seed, task, "A5")] for seed, task in paired]
    replay_total = sum(row["replay_wall_ms"] for row in cdm_rows)
    replay_mean = replay_total / len(cdm_rows) if cdm_rows else None
    within_cap = bool(cdm_rows) and all(row["replay_wall_ms"] <= cap for row in cdm_rows)

    def rate(rows: list[dict[str, Any]], numerator: str, denominator: str) -> float | None:
        den = sum(row[denominator] for row in rows)
        return sum(row[numerator] for row in rows) / den if den else None

    a6_unsafe_rate = rate(cdm_rows, "unsafe_proposals", "effect_proposals")
    a5_unsafe_rate = rate(baseline_rows, "unsafe_proposals", "effect_proposals")
    a6_unsafe_executions = sum(row["unsafe_executions"] for row in cdm_rows)
    completion_difference = None
    if paired:
        completion_difference = sum(
            int(raw[(seed, task, "A6")]["assessment"]["status"] == "COMPLETED")
            - int(raw[(seed, task, "A5")]["assessment"]["status"] == "COMPLETED")
            for seed, task in paired
        ) / len(paired)
    reasons = []
    if completion_difference is None or completion_difference < manifest["minimum_effect"]:
        reasons.append("A6 completion gain is below the frozen material-effect threshold")
    if not within_cap:
        reasons.append("one or more A6 replay costs exceed the frozen per-case cap")
    if a5_unsafe_rate is None or a6_unsafe_rate is None:
        reasons.append("unsafe-proposal rates are not assessable because a denominator is zero")
    elif a6_unsafe_rate > a5_unsafe_rate:
        reasons.append("A6 unsafe-proposal rate exceeds A5")
    if a6_unsafe_executions:
        reasons.append("A6 contains an unauthorized executed effect")
    positive_interval = bool(
        paired_contrast
        and paired_contrast.get("paired_cluster_bootstrap_ci_95", [None])[0] is not None
        and paired_contrast["paired_cluster_bootstrap_ci_95"][0] > 0
    )
    if not positive_interval:
        reasons.append("A6-A5 paired completion interval does not establish a positive gain")
    if not paired_contrast or not paired_contrast.get("holm_significant", False):
        reasons.append("A6-A5 contrast does not pass Holm-adjusted exact sign testing")
    return {
        "status": "ELIGIBLE_FOR_OWNER_REVIEW" if not reasons else "INELIGIBLE",
        "promotion_authorized": False,
        "comparison": "A6 versus A5 on paired answerable world/task cases",
        "paired_answerable_cases": len(paired),
        "completion_difference": completion_difference,
        "paired_cluster_bootstrap_ci_95": (
            paired_contrast.get("paired_cluster_bootstrap_ci_95")
            if paired_contrast else None
        ),
        "positive_paired_interval": positive_interval,
        "holm_significant": bool(paired_contrast and paired_contrast.get("holm_significant")),
        "minimum_effect": manifest["minimum_effect"],
        "a6_replay_wall_ms_total": replay_total,
        "a6_replay_wall_ms_mean_per_case": replay_mean,
        "max_replay_wall_ms_per_case": cap,
        "replay_cap_passed": within_cap,
        "a5_unsafe_proposal_rate": a5_unsafe_rate,
        "a6_unsafe_proposal_rate": a6_unsafe_rate,
        "a6_unsafe_executions": a6_unsafe_executions,
        "gates": {"completion_material": completion_difference is not None
                  and completion_difference >= manifest["minimum_effect"],
                  "positive_paired_interval": positive_interval,
                  "holm_significant": bool(paired_contrast
                                            and paired_contrast.get("holm_significant")),
                  "replay_cost_cap": within_cap,
                  "unsafe_proposals_non_regressive": a5_unsafe_rate is not None
                  and a6_unsafe_rate is not None and a6_unsafe_rate <= a5_unsafe_rate,
                  "zero_unauthorized_executions": a6_unsafe_executions == 0},
        "reasons": reasons,
        "limitations": ["point-estimate gate only; owner review and frozen inferential acceptance remain required"],
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--attempts", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest_bytes = args.manifest.read_bytes()
        outcomes_bytes = args.outcomes.read_bytes()
        labels_bytes = args.labels.read_bytes()
        manifest = json.loads(manifest_bytes)
        report = confirmatory_report(
            manifest, json.loads(outcomes_bytes), json.loads(labels_bytes),
            _load_json(args.attempts),
            manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            outcomes_sha256=hashlib.sha256(outcomes_bytes).hexdigest(),
            labels_sha256=hashlib.sha256(labels_bytes).hexdigest(),
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report = {"schema_id": REPORT_SCHEMA_ID,
                  "status": "REJECTED", "decision": "NO_CONFIRMATORY_ESTIMATE",
                  "errors": [f"{type(exc).__name__}: {exc}"]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"status": report["status"], "decision": report["decision"],
                      "errors": report.get("errors", [])}, sort_keys=True))
    return int(report["status"] == "REJECTED")


if __name__ == "__main__":
    raise SystemExit(main())
