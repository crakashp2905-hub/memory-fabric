"""Preregistration v2 for the real confirmatory study (W14-01 .. W14-10).

    python -m benchmarks.outcome_prereg --check research/prereg/agent-outcome-confirmatory-v2.json

Version 2 keeps every v1 rule (``benchmarks.outcome_confirmatory.validate_manifest``:
frozen status, disjoint seed splits, Holm correction, design digest, stopping
rule, resource caps) and adds the commitments a learned-agent study needs:

* the task population and family mixture, with every task's family declared
  (no family can be added to the denominator later);
* the primary contrasts A5-A3 and A5-A4, with A6-A5 only secondary;
* digests of the generator, prompt template, model weights and runtime, the
  actor policy, the evaluator source and the tool schema;
* power from pilot paired discordance, with the minimum effect no larger than
  the oracle headroom the pilot measured (AGENTS.md 8a) and the frozen sample
  size at least the pairs that power needs;
* the world seed cluster as the sampling unit, with cases and repeated agent
  decisions per cluster recorded separately;
* a safety non-inferiority margin, per-family bounds and the zero-event rule;
* a digest over the runtime source files, re-computed at analysis time, so
  changing the code after the freeze invalidates the comparison.

A manifest that is not ``FROZEN`` reports the first rule that blocks analysis;
it is never an analysis pass.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from memeval.power import absence_bound, pairs_needed

from .outcome_confirmatory import SCHEMA_ID as V1_SCHEMA_ID
from .outcome_confirmatory import design_digest as v1_design_digest
from .outcome_confirmatory import validate_manifest as validate_v1

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ID = "memory-fabric.agent-outcome-confirmatory.v2"
PRIMARY_CONTRASTS = (["A5", "A3"], ["A5", "A4"])
SECONDARY_CONTRASTS = (["A6", "A5"],)
ZERO_EVENT_RULES = frozenset({"exact_binomial_upper_95"})
COMMITMENTS = ("generator_digest", "prompt_template_sha256", "model_digest",
               "runtime_version", "policy_sha256", "evaluator_source_sha256",
               "tool_schema_sha256")
V2_FIELDS = ("population", "commitments", "power", "sampling", "safety", "frozen_source")


def source_digest(paths: Sequence[str], root: Path = ROOT) -> str:
    """SHA-256 over the named files' paths and bytes, in sorted order."""
    digest = hashlib.sha256()
    for name in sorted(paths):
        digest.update(name.encode("utf-8") + b"\0")
        digest.update((root / name).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def design_digest(manifest: Mapping[str, Any]) -> str:
    """v1's design digest extended with every v2 commitment."""
    v1 = v1_design_digest(dict(manifest))
    extra = json.dumps({name: manifest[name] for name in V2_FIELDS}, sort_keys=True,
                       separators=(",", ":"), allow_nan=False)
    return hashlib.sha256((v1 + extra).encode("utf-8")).hexdigest()


def _hex(value: Any, length: int = 64) -> bool:
    return isinstance(value, str) and len(value) == length and all(
        c in "0123456789abcdef" for c in value)


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate(manifest: Any, root: Path = ROOT) -> list[str]:
    """Every reason this manifest cannot back a confirmatory analysis; empty means it can."""
    if not isinstance(manifest, dict) or manifest.get("schema_id") != SCHEMA_ID:
        return ["manifest is not a confirmatory v2 registration"]
    missing = [name for name in V2_FIELDS if name not in manifest]
    if missing:
        return [f"v2 fields missing: {missing}"]
    # v1 rules on the v1 fields, with the v2 digest substituted for v1's own.
    v1 = {k: v for k, v in manifest.items() if k not in V2_FIELDS}
    v1["schema_id"] = V1_SCHEMA_ID
    v1_check = copy.deepcopy(v1)
    try:
        v1_check["design_sha256"] = v1_design_digest(v1_check)
    except (KeyError, TypeError, ValueError):
        pass
    errors = validate_v1(v1_check)
    try:
        if manifest.get("design_sha256") != design_digest(manifest):
            errors.append("design_sha256 mismatch; preregistered design changed")
    except (KeyError, TypeError, ValueError):
        errors.append("design_sha256 cannot be computed")

    population = manifest["population"]
    families = population.get("families") if isinstance(population, dict) else None
    task_families = population.get("task_families") if isinstance(population, dict) else None
    if not isinstance(families, dict) or not families or not all(
            _number(w) and w > 0 for w in families.values()):
        errors.append("population.families must map each family to a positive weight")
        families = {}
    elif abs(sum(families.values()) - 1.0) > 1e-9:
        errors.append("population family weights must sum to 1")
    declared = [t for ids in (manifest.get("task_ids_by_seed") or {}).values()
                if isinstance(ids, list) for t in ids]
    if not isinstance(task_families, dict) or set(task_families) != set(declared):
        errors.append("population.task_families must name the family of every declared task, "
                      "and only those")
    elif any(family not in families for family in task_families.values()):
        errors.append("a confirmatory task belongs to a family outside the declared mixture")

    contrasts = manifest.get("contrasts") or []
    if contrasts[:2] != list(PRIMARY_CONTRASTS):
        errors.append("the primary contrasts must be A5-A3 then A5-A4")
    if any(pair not in (*PRIMARY_CONTRASTS, *SECONDARY_CONTRASTS) for pair in contrasts):
        errors.append("only A6-A5 may be registered as a secondary contrast")

    commitments = manifest["commitments"]
    for name in COMMITMENTS:
        value = commitments.get(name) if isinstance(commitments, dict) else None
        if not (isinstance(value, str) and value.strip()):
            errors.append(f"commitment {name} is missing")
        elif name != "runtime_version" and not (_hex(value) or (
                value.startswith("sha256:") and _hex(value[7:]))):
            errors.append(f"commitment {name} must be a SHA-256 digest")

    power = manifest["power"]
    raw_effect = manifest.get("minimum_effect")
    effect = float(raw_effect) if isinstance(raw_effect, (int, float)) and _number(raw_effect) else None
    if not isinstance(power, dict) or not all(
            _number(power.get(k)) for k in ("pilot_discordance", "oracle_headroom")):
        errors.append("power needs pilot_discordance and oracle_headroom from a pilot")
    else:
        discordance, headroom = power["pilot_discordance"], power["oracle_headroom"]
        if not 0 < discordance <= 1 or not 0 <= headroom <= 1:
            errors.append("pilot discordance and oracle headroom must be proportions")
        elif effect is not None and effect > headroom:
            errors.append("minimum_effect exceeds the oracle headroom; the target is impossible")
        elif effect is not None and effect > 0:
            needed = pairs_needed(effect, discordance)
            clusters = len(manifest.get("confirmatory_seeds") or [])
            if power.get("pairs_required") != needed:
                errors.append(f"pairs_required must equal pairs_needed(effect, discordance) = {needed}")
            if not isinstance(manifest.get("sample_size"), int) or manifest["sample_size"] < needed:
                errors.append(f"sample_size is below the {needed} pairs power requires")
            sampling_rule = manifest.get("sampling")
            per_cluster = (sampling_rule.get("cases_per_cluster")
                           if isinstance(sampling_rule, dict) else None)
            if isinstance(per_cluster, int) and per_cluster > 0 and needed > clusters * per_cluster:
                errors.append("power needs more paired cases than the seed clusters hold; repeated "
                              "agent decisions on one case are not extra pairs")

    sampling = manifest["sampling"]
    if not isinstance(sampling, dict) or sampling.get("unit") != "world_seed_cluster":
        errors.append("the sampling unit must be the world seed cluster")
    else:
        for key in ("cases_per_cluster", "agent_decisions_per_case"):
            if not isinstance(sampling.get(key), int) or sampling[key] <= 0:
                errors.append(f"sampling.{key} must be a positive integer")

    safety = manifest["safety"]
    margin = safety.get("non_inferiority_margin") if isinstance(safety, dict) else None
    if not (isinstance(margin, (int, float)) and _number(margin) and 0 < margin < 1):
        errors.append("safety.non_inferiority_margin must be a proportion")
    if not isinstance(safety, dict) or safety.get("zero_event_rule") not in ZERO_EVENT_RULES:
        errors.append(f"safety.zero_event_rule must be one of {sorted(ZERO_EVENT_RULES)}")
    bounds = safety.get("per_family_bounds") if isinstance(safety, dict) else None
    if not isinstance(bounds, dict) or set(bounds) != set(families) or not all(
            _number(b) and 0 < b < 1 for b in bounds.values()):
        errors.append("safety.per_family_bounds must bound every declared family")

    frozen = manifest["frozen_source"]
    paths = frozen.get("paths") if isinstance(frozen, dict) else None
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
        errors.append("frozen_source.paths must list the runtime files the freeze covers")
    else:
        try:
            current = source_digest(paths, root)
        except OSError:
            current = None
        if current is None or current != frozen.get("sha256"):
            errors.append("runtime source changed after the freeze; this comparison is invalid "
                          "and a new confirmatory campaign must be registered")
    return errors


CDM_SCHEMA_ID = "memory-fabric.agent-outcome-cdm-a6.v1"
CDM_FIELDS = ("contrast", "estimand", "cost_per_replay", "unsafe_weight", "flip_credit",
              "minimum_net_utility", "safety_non_inferiority_margin", "interval", "decision",
              "depends_on")


def cdm_design_digest(manifest: Mapping[str, Any]) -> str:
    body = json.dumps({k: manifest[k] for k in CDM_FIELDS}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def validate_cdm(manifest: Any) -> list[str]:
    """The A6-A5 net-utility test, registered before any evaluation (W22-03)."""
    if not isinstance(manifest, dict) or manifest.get("schema_id") != CDM_SCHEMA_ID:
        return ["not an A6-A5 net-utility registration"]
    errors = []
    if manifest.get("status") != "FROZEN":
        errors.append("protocol is not frozen; the A6-A5 test is blocked")
    if manifest.get("contrast") != ["A6", "A5"]:
        errors.append("the contrast must be A6-A5")
    if manifest.get("flip_credit") != 0:
        errors.append("policy flips must earn no credit")
    for name in ("cost_per_replay", "minimum_net_utility"):
        if not _number(manifest.get(name)) or not manifest[name] > 0:
            errors.append(f"{name} must be a positive number")
    if not _number(manifest.get("unsafe_weight")) or manifest["unsafe_weight"] < 1:
        errors.append("unsafe_weight must be at least 1")
    if (manifest.get("depends_on") or {}).get("requires") != "A5 promoted on its primary contrasts":
        errors.append("A6 must depend on A5's promotion")
    if not manifest.get("registered_before_evaluation"):
        errors.append("the test must be registered before evaluation")
    if not (isinstance(manifest.get("freeze_commit"), str) and len(manifest["freeze_commit"]) == 40):
        errors.append("freeze_commit must be a full 40-character Git SHA")
    try:
        if manifest.get("design_sha256") != cdm_design_digest(manifest):
            errors.append("design_sha256 mismatch; registered design changed")
    except KeyError:
        errors.append("registration is missing design fields")
    return errors


def zero_event_upper_bound(n: int) -> float:
    """The frozen zero-event rule: exact one-sided 95% binomial upper bound."""
    return absence_bound(n, 0.95)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", type=Path, required=True)
    args = parser.parse_args(argv)
    errors = validate(json.loads(args.check.read_text(encoding="utf-8")))
    for error in errors:
        print(f"BLOCKED: {error}")
    if not errors:
        print("FROZEN: registration can back a confirmatory analysis")
    return 1 if errors else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
