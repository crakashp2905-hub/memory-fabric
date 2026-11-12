"""Run the versioned, offline outcome-agent qualification gate.

The report distinguishes a passing scripted gate from model and deployment
evidence. Checks are defined in the adjacent immutable JSON manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory_fabric.agent_outcomes import AgentStep  # noqa: E402
from benchmarks.outcome_report import (  # noqa: E402
    real_agent_failure_report_is_valid,
    real_agent_report_is_complete,
)

MANIFEST_PATH = Path(__file__).with_name("agent_outcome_gate_manifest.v76.json")
MANIFEST_SCHEMA = "memory-fabric.agent-outcome-gate.v76"


def read_manifest(path: Path = MANIFEST_PATH) -> tuple[dict[str, Any], str]:
    """Load and validate the checked-in manifest and return its content digest."""
    payload = path.read_bytes()
    manifest = json.loads(payload)
    if (manifest.get("schema_id") != MANIFEST_SCHEMA
            or manifest.get("manifest_version") != 76
            or not isinstance(manifest.get("checks"), list)):
        raise ValueError("unsupported or malformed agent outcome gate manifest")
    ids = [item.get("id") for item in manifest["checks"]]
    if len(ids) != len(set(ids)) or any(not isinstance(item, str) for item in ids):
        raise ValueError("manifest check ids must be unique strings")
    return manifest, hashlib.sha256(payload).hexdigest()


def overall_status(results: list[dict[str, Any]]) -> str:
    """Return the strict aggregate status for required scripted checks."""
    required = [result for result in results if result["required_for_scripted_qualification"]]
    if any(result["status"] == "FAIL" for result in required):
        return "FAIL"
    if any(result["status"] != "PASS" for result in required):
        return "NOT_RUN"
    return "SCRIPTED_QUALIFIED"


def replay_isolation_status() -> str:
    """Report whether this host can enforce worker OS resource limits."""
    return ("OS_LIMITS_AVAILABLE" if os.name == "posix"
            and _module_available("resource") else "OS_LIMITS_UNAVAILABLE")


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _run_check(check: dict[str, Any], *, timeout_s: int, run_full: bool) -> dict[str, Any]:
    check_id = check["id"]
    command = check.get("command")
    result = {"id": check_id,
              "required_for_scripted_qualification": bool(
                  check.get("required_for_scripted_qualification", False))}
    if command is None:
        if check_id == "local_model":
            return {**result, "status": "REAL_AGENT_NOT_RUN",
                    "reason": "no completed inference evidence was supplied"}
        return {**result, "status": "NOT_RUN", "reason": "requires separate real-world evidence"}
    if not isinstance(command, list) or not command:
        return {**result, "status": "FAIL", "reason": "invalid command in manifest"}
    if check_id == "full_repository" and not run_full:
        return {**result, "status": "NOT_RUN", "reason": "disabled by --skip-full"}
    if len(command) >= 3 and command[1] == "-m" and not _module_available(command[2]):
        return {**result, "status": "NOT_RUN", "reason": f"optional tool unavailable: {command[2]}"}
    executable = sys.executable if command[0] == "python" else command[0]
    try:
        completed = subprocess.run([executable, *command[1:]], cwd=ROOT,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return {**result, "status": "FAIL", "reason": f"timed out after {timeout_s}s"}
    except OSError as exc:
        return {**result, "status": "FAIL", "reason": type(exc).__name__}
    if completed.returncode == 0:
        return {**result, "status": "PASS"}
    return {**result, "status": "FAIL", "reason": f"exit code {completed.returncode}"}


def local_model_evidence_result(report_path: Path | None) -> dict[str, Any]:
    """Validate a separate real-agent report without substituting scripted data."""
    result = {"id": "local_model", "required_for_scripted_qualification": False}
    if report_path is None:
        return {**result, "status": "REAL_AGENT_NOT_RUN",
                "reason": "no completed inference evidence was supplied"}
    try:
        payload = report_path.read_bytes()
    except FileNotFoundError:
        return {**result, "status": "REAL_AGENT_NOT_RUN",
                "reason": "real-agent report file is missing"}
    except OSError as exc:
        return {**result, "status": "FAIL", "reason": type(exc).__name__}
    if len(payload) > 1_000_000:
        return {**result, "status": "FAIL", "reason": "real-agent report is too large"}
    try:
        report = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {**result, "status": "FAIL", "reason": "real-agent report is malformed JSON"}
    if isinstance(report, dict) and report.get("status") == "REAL_AGENT_NOT_RUN":
        return {**result, "status": "REAL_AGENT_NOT_RUN",
                "reason": str(report.get("reason", "inference was not completed"))}
    if real_agent_failure_report_is_valid(report):
        return {
            **result,
            "status": "FAIL",
            "reason": "real-agent attempt failed and counts as incomplete",
            "report_sha256": hashlib.sha256(payload).hexdigest(),
            "failure_reason": report["reason"],
            "failure_codes": report["failure_codes"],
            "terminal_failure_codes": report["terminal_failure_codes"],
            "failure_counts": report["failure_counts"],
            "retry_count": report["retry_count"],
            "prompt_injection_compliance": report["prompt_injection_compliance"],
            "counts_as_incomplete": True,
        }
    if not real_agent_report_is_complete(report):
        return {**result, "status": "FAIL", "reason": "real-agent evidence is incomplete"}
    inference = report["inference"]
    model = inference["model"]
    return {
        **result,
        "status": "PASS",
        "reason": "completed inference report validated",
        "report_sha256": hashlib.sha256(payload).hexdigest(),
        "model": model["name"],
        "model_digest": model["digest"],
        "quantization_level": model["quantization_level"],
        "model_calls": report["model_calls"],
        "model_tokens": report["model_tokens"],
        "retry_count": report.get("retry_count", 0),
        "prompt_injection_compliance": report.get("prompt_injection_compliance", "NOT_TESTED"),
        "failure_counts": report.get("failure_counts", {}),
    }


def real_agent_team_report_is_complete(report: Any) -> bool:
    """Check model provenance, distinct sequential roles, and the gated effect."""
    if not isinstance(report, dict):
        return False
    actor_ids = report.get("actor_ids")
    interactions = report.get("memory_service_interactions")
    raw_steps = report.get("model_steps")
    manifests = report.get("inference_manifests")
    task_id = report.get("task_id")
    if (not isinstance(interactions, dict)
            or set(interactions) != {
                "observer_writes", "planner_retrievals", "executor_certifications",
            }
            or any(type(value) is not int or value != 1 for value in interactions.values())):
        return False
    if (report.get("schema_id") != "memory-fabric.real-agent-team-report.v1"
            or report.get("population") != "REAL_AGENT" or report.get("status") != "PASS"
            or not isinstance(task_id, str) or not task_id
            or not isinstance(actor_ids, list) or len(actor_ids) != 3
            or any(not isinstance(actor_id, str) or not actor_id for actor_id in actor_ids)
            or len(set(actor_ids)) != 3 or report.get("orchestration") != "sequential"
            or report.get("shared_model_weights") is not True
            or type(report.get("max_concurrent_model_calls")) is not int
            or report["max_concurrent_model_calls"] != 1
            or not isinstance(raw_steps, list) or len(raw_steps) != 5
            or not isinstance(manifests, list) or len(manifests) != 5
            or report.get("model_calls") != 5
            or type(report.get("host_effect_invocations")) is not int
            or report["host_effect_invocations"] != 1
            or not isinstance(report.get("run_timestamp_utc"), str)
            or not report["run_timestamp_utc"]
            or not isinstance(report.get("disclosure"), str)
            or not report["disclosure"]):
        return False

    try:
        steps = [AgentStep.from_json(json.dumps(step, allow_nan=False))
                 for step in raw_steps]
    except (TypeError, ValueError):
        return False
    expected_actor_order = [actor_ids[0], actor_ids[1], actor_ids[1],
                            actor_ids[2], actor_ids[2]]
    if (any(step.task_id != task_id for step in steps)
            or [step.actor_id for step in steps] != expected_actor_order
            or len({step.step_id for step in steps}) != 5):
        return False
    observer, retrieval, proposal, certification, execution = steps
    if (observer.intent != "inspect"
            or observer.arguments.get("tool") != "remember_evidence"
            or retrieval.intent != "retrieve"
            or retrieval.arguments.get("tool") != "retrieve_evidence"
            or not retrieval.evidence_versions
            or proposal.intent != "propose"
            or proposal.arguments.get("tool") != "propose_action"
            or proposal.arguments.get("action_tool") != "set_target"
            or not isinstance(proposal.arguments.get("parameters"), Mapping)
            or not isinstance(proposal.arguments.get("claim"), str)
            or not proposal.arguments["claim"].strip()
            or certification.intent != "inspect"
            or certification.arguments.get("tool") != "certify_evidence"
            or execution.intent != "propose"
            or execution.arguments.get("tool") != "set_target"
            or not isinstance(execution.arguments.get("parameters"), Mapping)
            or any(step.evidence_versions != retrieval.evidence_versions
                   for step in (proposal, certification, execution))):
        return False
    proposal_parameters = proposal.to_dict()["arguments"]["parameters"]
    execution_parameters = execution.to_dict()["arguments"]["parameters"]
    if json.dumps(proposal_parameters, sort_keys=True, allow_nan=False) != json.dumps(
            execution_parameters, sort_keys=True, allow_nan=False):
        return False

    model_name = report.get("model")
    model_digest = report.get("model_digest")
    quantization = report.get("quantization_level")
    if (not isinstance(model_name, str) or not model_name
            or not isinstance(model_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", model_digest) is None
            or not isinstance(quantization, str) or not quantization):
        return False
    options_seen: list[dict[str, Any]] = []
    total_tokens = 0
    for manifest in manifests:
        if not isinstance(manifest, dict):
            return False
        model = manifest.get("model")
        options = manifest.get("options")
        usage = manifest.get("usage")
        if (not isinstance(model, dict) or model.get("name") != model_name
                or model.get("digest") != model_digest
                or model.get("quantization_level") != quantization
                or manifest.get("decoder") != "ollama:/api/chat"
                or not isinstance(manifest.get("nondeterminism_disclosure"), str)
                or not manifest["nondeterminism_disclosure"]
                or not isinstance(options, dict)
                or options.get("format") != "json_schema"
                or options.get("constrained") is not True
                or options.get("stream") is not False
                or not isinstance(usage, dict)):
            return False
        options_seen.append(options)
        for field in ("prompt_sha256", "system_prompt_sha256", "response_schema_sha256"):
            if not isinstance(manifest.get(field), str) or re.fullmatch(
                    r"[0-9a-f]{64}", manifest[field]) is None:
                return False
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        call_tokens = usage.get("total_tokens")
        if (not isinstance(prompt_tokens, int) or isinstance(prompt_tokens, bool)
                or prompt_tokens < 0 or not isinstance(completion_tokens, int)
                or isinstance(completion_tokens, bool) or completion_tokens < 0
                or not isinstance(call_tokens, int) or isinstance(call_tokens, bool)
                or call_tokens != prompt_tokens + completion_tokens):
            return False
        total_tokens += call_tokens
    if (not options_seen or any(options != options_seen[0] for options in options_seen)
            or not isinstance(report.get("model_tokens"), int)
            or isinstance(report["model_tokens"], bool)
            or report["model_tokens"] != total_tokens or total_tokens <= 0):
        return False
    effect = report.get("effect")
    effect_target = report.get("effect_target")
    approved_target = execution_parameters.get("value")
    return (
        isinstance(effect, dict) and effect.get("outcome") == "executed"
        and effect.get("ran") is True
        and isinstance(approved_target, (int, float))
        and not isinstance(approved_target, bool)
        and type(effect_target) is type(approved_target)
        and effect_target == approved_target
    )


def real_agent_team_evidence_result(report_path: Path | None) -> dict[str, Any]:
    """Validate a separate three-role real-model report without scripted fallback."""
    result = {"id": "real_agent_team", "required_for_scripted_qualification": False}
    if report_path is None:
        return {**result, "status": "REAL_AGENT_NOT_RUN",
                "reason": "no completed team inference evidence was supplied"}
    try:
        payload = report_path.read_bytes()
    except FileNotFoundError:
        return {**result, "status": "REAL_AGENT_NOT_RUN",
                "reason": "real-agent team report file is missing"}
    except OSError as exc:
        return {**result, "status": "FAIL", "reason": type(exc).__name__}
    if len(payload) > 1_000_000:
        return {**result, "status": "FAIL", "reason": "real-agent team report is too large"}
    try:
        report = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {**result, "status": "FAIL", "reason": "real-agent team report is malformed JSON"}
    if not real_agent_team_report_is_complete(report):
        return {**result, "status": "FAIL", "reason": "real-agent team evidence is incomplete"}
    return {
        **result,
        "status": "PASS",
        "reason": "sequential three-role model report validated",
        "report_sha256": hashlib.sha256(payload).hexdigest(),
        "model": report["model"],
        "model_digest": report["model_digest"],
        "quantization_level": report["quantization_level"],
        "actor_ids": report["actor_ids"],
        "model_calls": report["model_calls"],
        "model_tokens": report["model_tokens"],
    }


def build_report(
    *,
    skip_full: bool = False,
    timeout_s: int = 3600,
    real_agent_report_path: Path | None = None,
    real_agent_team_report_path: Path | None = None,
) -> dict[str, Any]:
    """Run manifest checks and return a content-safe evidence report."""
    manifest, manifest_sha256 = read_manifest()
    results = [_run_check(check, timeout_s=timeout_s, run_full=not skip_full)
               for check in manifest["checks"]]
    for index, check_result in enumerate(results):
        if check_result["id"] == "local_model":
            results[index] = local_model_evidence_result(real_agent_report_path)
        elif check_result["id"] == "real_agent_team":
            results[index] = real_agent_team_evidence_result(real_agent_team_report_path)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, check=False)
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, text=True, check=False)
    status = overall_status(results)
    return {
        "schema_id": MANIFEST_SCHEMA,
        "manifest_version": manifest["manifest_version"],
        "manifest_sha256": manifest_sha256,
        "candidate_sha": commit.stdout.strip() if commit.returncode == 0 else None,
        "working_tree_dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "evidence_levels": {
            "scripted": status,
            "local_model": next(
                result["status"] for result in results if result["id"] == "local_model"
            ),
            "real_agent_team": next(
                result["status"] for result in results if result["id"] == "real_agent_team"
            ),
            "deployment": "NOT_RUN",
            "replay_isolation": replay_isolation_status(),
        },
        "checks": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-full", action="store_true",
                        help="mark the full repository suite NOT_RUN")
    parser.add_argument("--timeout", type=int, default=3600,
                        help="per-check timeout in seconds (default: 3600)")
    parser.add_argument("--real-agent-report", type=Path,
                        help="validate a separate completed REAL_AGENT report")
    parser.add_argument("--real-team-report", type=Path,
                        help="validate a completed sequential three-role REAL_AGENT report")
    parser.add_argument("--out", help="write JSON report to this path instead of stdout")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    report = json.dumps(build_report(
        skip_full=args.skip_full, timeout_s=args.timeout,
        real_agent_report_path=args.real_agent_report,
        real_agent_team_report_path=args.real_team_report,
    ),
                        sort_keys=True, separators=(",", ":"), allow_nan=False)
    if args.out:
        Path(args.out).write_text(report + "\n", encoding="utf-8")
    else:
        sys.stdout.write(report + "\n")
    status = json.loads(report)["status"]
    return {"SCRIPTED_QUALIFIED": 0, "FAIL": 1, "NOT_RUN": 2}[status]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
