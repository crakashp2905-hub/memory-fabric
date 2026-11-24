"""Matched arms with a local-model team instead of the scripted one (W12-04/05/07/09, W12-10).

    python -m benchmarks.outcome_model_team --model qwen2.5:1.5b --seeds 1 --out DIR/model-team.json

Every role (observer, planner, executor) is a :class:`ModelActor` over the same
pinned model and configuration, through the same canonical episode runtime,
worlds, tools and budgets as the scripted arms. Only the memory affordance and
recovery vary between arms (A3/A4/A5; A6 runs only in the scripted harness and is listed as
not run). A fresh actor serves each episode so call budgets never leak.

The model must already be installed on a loopback runtime. If the preflight
cannot see it, the report says ``REAL_AGENT_NOT_RUN`` with the reason, no
episode runs, and nothing scripted takes its place (exit 3). An injected
backend (tests) is labelled ``FAKE_BACKEND`` and can never produce
local-model evidence.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from memory_fabric.adapters.ollama import DEFAULT_HOST, OllamaClient
from memory_fabric.outcome_typed.model_actor import ChatBackend, ModelActor, ModelConfig

from .outcome_arms import ARMS, FAMILIES, NOT_RUN_ARMS, build_task, paired_difference, run_arm

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ID = "memory-fabric.agent-outcome-model-team.v1"
MODEL_ARMS = ("A3", "A4", "A5")


def _preflight(host: str, model: str) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("_mf_model_preflight",
                                                  ROOT / "tools" / "model_preflight.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report: dict[str, Any] = module.preflight(host, [model])
    return report


def _commit() -> str | None:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else None


def not_run(reason: str, preflight: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"schema_id": SCHEMA_ID, "status": "REAL_AGENT_NOT_RUN", "reason": reason,
            "evidence_type": None, "local_model_evidence": "REAL_AGENT_NOT_RUN",
            "scripted_substitute_used": False, "rows": [], "preflight": dict(preflight or {})}


def run_model_team(model: str, *, arms: Sequence[str] = MODEL_ARMS, seeds: int = 1,
                   families: Sequence[str] = FAMILIES, host: str = DEFAULT_HOST,
                   backend: ChatBackend | None = None, config: ModelConfig | None = None,
                   timeout: float = 120.0) -> dict[str, Any]:
    unknown = [arm for arm in arms if arm not in ARMS]
    if unknown:
        raise ValueError(f"not an actor arm: {unknown}")
    fake = backend is not None
    preflight: dict[str, Any] = {}
    if not fake:
        from .fake_local_model import is_fake

        preflight = _preflight(host, model)
        if preflight.get("status") != "MODELS_AVAILABLE":
            return not_run(str(preflight.get("reason")), preflight)
        names = [entry["name"] for entry in preflight["models"]]
        resolved = OllamaClient.resolve(model, names)
        entry = next(item for item in preflight["models"] if item["name"] == resolved)
        if not preflight.get("runtime_version"):
            return not_run("RUNTIME_VERSION_UNAVAILABLE", preflight)
        config = config or ModelConfig(model=str(resolved), digest=str(entry["digest"]),
                                       runtime_version=str(preflight["runtime_version"]),
                                       quantization=entry.get("quantization"))
        backend = OllamaClient(host=preflight["host"], retries=0, timeout=timeout)
        # A declared fake server is plumbing, never inference (W20-08).
        fake = is_fake(preflight.get("runtime_version"), entry.get("digest"))
    assert backend is not None
    config = config or ModelConfig(model=model, digest="fake", runtime_version="fake")
    rows = []
    for arm in arms:
        for family in families:
            for seed in range(seeds):
                actor = ModelActor(backend, config)
                row = run_arm(ARMS[arm], build_task(family, seed), decide=actor)
                usage = actor.usage()
                row["model_usage"] = usage
                row["model_calls"] = len(actor.calls)
                row["inference_backed_steps"] = sum(1 for c in actor.calls if c["outcome"] == "ok")
                rows.append(row)
    fingerprints = sorted({row["model_usage"]["config_fingerprint"] for row in rows})
    substantive = bool(rows) and all(row["inference_backed_steps"] > 0 for row in rows)
    evidence = ("FAKE_BACKEND_NOT_EVIDENCE" if fake
                else "LOCAL_MODEL_EVIDENCE_AVAILABLE" if substantive else "REAL_AGENT_NOT_RUN")
    return {
        "schema_id": SCHEMA_ID,
        "status": "FAKE_BACKEND" if fake else "LOCAL_MODEL_DEVELOPMENT",
        "evidence_type": "fake_backend" if fake else "local_model",
        "local_model_evidence": evidence,
        "scripted_substitute_used": False,
        "candidate_commit_sha": _commit(),
        "model": {"name": config.model, "digest": config.digest,
                  "runtime_version": config.runtime_version, "quantization": config.quantization},
        "config_fingerprints": fingerprints,
        "arms": list(arms), "not_run_arms": {**dict(NOT_RUN_ARMS), **{
            arm: "not part of this model-team run" for arm in ("A3", "A4", "A5", "A6")
            if arm not in arms}}, "families": list(families),
        "seeds": seeds, "preflight": preflight,
        "summary": summarize(rows),
        "contrasts": [paired_difference(rows, left, right)
                      for left, right in (("A5", "A3"), ("A5", "A4"))
                      if left in arms and right in arms],
        "promotion": "NOT_ASSESSED",
        "rows": rows,
    }


def summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per-arm rates over every scheduled episode; incomplete ones stay in the denominator."""
    out: dict[str, Any] = {}
    for arm in sorted({row["arm"] for row in rows}):
        mine = [row for row in rows if row["arm"] == arm]
        reasons: dict[str, int] = {}
        for row in mine:
            if row["host_outcome"] in {"FAILED", "BUDGET_EXHAUSTED"}:
                key = f"{row['host_outcome']}:{row['host_reason']}"
                reasons[key] = reasons.get(key, 0) + 1
        out[arm] = {
            "episodes": len(mine),
            "completion_rate": sum(r["completed"] for r in mine) / len(mine),
            "safe_success_rate": sum(r["safe_success"] for r in mine) / len(mine),
            "unsafe_rate": sum(r["unsafe"] for r in mine) / len(mine),
            "incomplete": reasons,
            "model_calls": sum(r["model_calls"] for r in mine),
            "inference_backed_steps": sum(r["inference_backed_steps"] for r in mine),
        }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--arms", default=",".join(MODEL_ARMS))
    parser.add_argument("--seeds", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run_model_team(args.model, arms=[a for a in args.arms.split(",") if a],
                            seeds=args.seeds, host=args.host)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{report['status']}: {report.get('reason') or report['local_model_evidence']}")
    return 3 if report["status"] == "REAL_AGENT_NOT_RUN" else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
