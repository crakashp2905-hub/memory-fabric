#!/usr/bin/env python3
"""One offline command that qualifies the agent-outcome stack end to end (W23-01, W23-02).

    python tools/agent_outcome_end_to_end_gate.py --offline --all --out DIR
    python tools/agent_outcome_end_to_end_gate.py --offline --all --out DIR --local-model qwen2.5:1.5b

Stages, in order (each writes ``DIR/<stage>.log``; the report is written even
when a later stage fails):

``source``      the candidate is a clean git commit (required)
``contracts``   outcome contract, episode, arms, canonical-package and ledger tests (required)
``security``    the frozen adversarial gate and the secret scanner (required)
``demo``        one governed episode from a blank store to a COMPLETED receipt (required)
``arms``        scripted matched arms: parity valid, no arm above the A7 ceiling, and the
                scorecard (``benchmarks.outcome_scorecard``) neither FAIL nor INVALID (required)
``provenance``  baseline manifest, evidence inventory, claim scanner, task ledger
                (history and test resolution) and current-state versions (required)
``local_model`` only with ``--local-model``: loopback preflight, then the model team
                (``benchmarks.outcome_model_team``) at this commit; with no runtime or
                model, ``REAL_AGENT_NOT_RUN`` - never a scripted substitute, never a failure

The report renders a release-evidence matrix in which each gate carries only its
own evidence type (``memory_fabric.outcome_typed.evidence``): this gate can make
the synthetic outcome gate ``SCRIPTED_PASS``, and nothing else. Main CI, model
attacks, real agents, confirmatory evidence and independent review stay
``NOT_RUN`` unless their own evidence is supplied. Exit 1 if a required stage
failed, else 0.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from memory_fabric.outcome_typed.evidence import (  # noqa: E402
    EvidenceType, GateEvidence, OutcomeEvidenceStatus, release_evidence_matrix,
)

SCHEMA_ID = "memory-fabric.agent-outcome-end-to-end-gate.v1"
PY = sys.executable
CONTRACT_TESTS = [
    "tests/test_outcome_episode.py", "tests/test_outcome_arms.py",
    "tests/test_outcome_canonical_package.py", "tests/test_outcome_evidence_status.py",
    "tests/test_agent_validation_w01.py", "tests/test_outcome_runtime.py",
    "tests/test_outcome_oracle_isolation_typed.py", "tests/test_action_fence_typed.py",
    "tests/test_outcome_world_engine.py", "tests/test_outcome_alternate_sources.py",
    "tests/test_outcome_model_actor.py", "tests/test_outcome_scorecard.py",
    "tests/test_outcome_prereg.py", "tests/test_outcome_ablation.py",
    "tests/test_outcome_evaluator_mutation.py", "tests/test_agent_outcome_end_to_end_gate.py",
]


def _run(argv: list[str], log: Path, timeout: int = 1800) -> tuple[int, float]:
    started = time.monotonic()
    try:
        done = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                              encoding="utf-8", errors="replace")
        code, output = done.returncode, done.stdout + done.stderr
    except subprocess.TimeoutExpired as exc:
        code, output = 124, f"timed out after {timeout}s: {exc}"
    log.write_text(f"$ {' '.join(argv)}\n{output}", encoding="utf-8")
    return code, round(time.monotonic() - started, 2)


def _git(*args: str) -> str:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else ""


def stage_source(out: Path) -> dict[str, Any]:
    sha = _git("rev-parse", "HEAD")
    dirty = _git("status", "--porcelain", "--untracked-files=no")
    ok = len(sha) == 40 and not dirty
    (out / "source.log").write_text(f"commit {sha}\ndirty: {bool(dirty)}\n{dirty}\n",
                                    encoding="utf-8")
    return {"status": "PASS" if ok else "FAIL", "commit_sha": sha or None,
            "reason": "clean commit" if ok else "the candidate must be a clean commit"}


def stage_commands(name: str, commands: list[list[str]], out: Path) -> dict[str, Any]:
    results, seconds = [], 0.0
    log = out / f"{name}.log"
    log.write_text("", encoding="utf-8")
    for index, argv in enumerate(commands):
        part = out / f"{name}.{index}.log"
        code, took = _run(argv, part)
        seconds += took
        results.append({"argv": argv, "exit_code": code, "seconds": took})
        with log.open("a", encoding="utf-8") as handle:
            handle.write(part.read_text(encoding="utf-8") + "\n")
        part.unlink()
    ok = all(item["exit_code"] == 0 for item in results)
    return {"status": "PASS" if ok else "FAIL", "commands": results, "seconds": round(seconds, 2)}


def stage_arms(out: Path) -> dict[str, Any]:
    report_path = out / "arms.json"
    code, took = _run([PY, "-m", "benchmarks.outcome_arms", "--seeds", "2", "--out",
                       str(report_path)], out / "arms.log")
    if code != 0 or not report_path.is_file():
        return {"status": "FAIL", "seconds": took, "reason": "arms run failed"}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    problems = list(report["parity"]["problems"])
    if report["arms_above_oracle"]:
        problems.append(f"arms above the oracle ceiling: {report['arms_above_oracle']}")
    card_path = out / "scorecard.json"
    code, more = _run([PY, "-m", "benchmarks.outcome_scorecard", "--arms", str(report_path),
                       "--evidence-type", "scripted", "--out-json", str(card_path),
                       "--out-md", str(out / "SCORECARD.md")], out / "scorecard.log")
    card = json.loads(card_path.read_text(encoding="utf-8")) if card_path.is_file() else {}
    if card.get("decision") not in {"HOLD", "PASS"}:
        problems.append(f"scorecard decision {card.get('decision')}: {card.get('decision_reasons')}")
    return {"status": "FAIL" if problems else "PASS", "seconds": round(took + more, 2),
            "problems": problems, "parity": report["parity"]["status"],
            "missing_arms": report["parity"]["missing_arms"],
            "evidence_status": report["evidence_status"], "promotion": report["promotion"],
            "scorecard_decision": card.get("decision")}


def stage_demo(out: Path) -> dict[str, Any]:
    code, took = _run([PY, "-m", "benchmarks.outcome_episode", "--seed", "1"], out / "demo.log")
    text = (out / "demo.log").read_text(encoding="utf-8")
    ok = code == 0 and "evaluator: COMPLETED" in text
    return {"status": "PASS" if ok else "FAIL", "seconds": took}


def stage_local_model(model: str, out: Path, sha: str | None) -> dict[str, Any]:
    """Preflight, then run the model team at this commit (W12-10).

    ``LOCAL_MODEL_EVIDENCE_AVAILABLE`` only when this candidate ran episodes in
    which every row has at least one inference-backed step; historical JSON is
    never read. Without a model the stage is ``REAL_AGENT_NOT_RUN``.
    """
    preflight = out / "local_model_preflight.json"
    code, took = _run([PY, "tools/model_preflight.py", "--require", model, "--out", str(preflight)],
                      out / "local_model.log", timeout=120)
    report = json.loads(preflight.read_text(encoding="utf-8")) if preflight.is_file() else {}
    if report.get("status") != "MODELS_AVAILABLE":
        return {"status": "REAL_AGENT_NOT_RUN", "required": False, "seconds": took,
                "reason": report.get("reason", "preflight did not complete"),
                "scripted_substitute_used": False}
    team_path = out / "model_team.json"
    code, more = _run([PY, "-m", "benchmarks.outcome_model_team", "--model", model, "--seeds", "1",
                       "--out", str(team_path)], out / "local_model_team.log", timeout=7200)
    team = json.loads(team_path.read_text(encoding="utf-8")) if team_path.is_file() else {}
    evidence = team.get("local_model_evidence", "REAL_AGENT_NOT_RUN")
    if code != 0 or team.get("candidate_commit_sha") != sha:
        evidence = "REAL_AGENT_NOT_RUN"
    return {"status": evidence, "required": False, "seconds": round(took + more, 2),
            "reason": "model team ran at this commit" if evidence == "LOCAL_MODEL_EVIDENCE_AVAILABLE"
            else team.get("reason", "model team did not produce substantive episodes"),
            "model": team.get("model"), "summary": team.get("summary"),
            "scripted_substitute_used": False}


def build_matrix(stages: dict[str, Any], sha: str | None) -> dict[str, Any]:
    synthetic_ok = all(stages[name]["status"] == "PASS"
                       for name in ("contracts", "demo", "arms", "provenance") if name in stages)
    entries = [GateEvidence(
        "synthetic_outcome_gate",
        OutcomeEvidenceStatus.SCRIPTED_PASS if synthetic_ok and sha else OutcomeEvidenceStatus.FAILED,
        EvidenceType.SCRIPTED, sha if synthetic_ok and sha else None,
        "scripted contracts, episode demo, matched arms and provenance at this commit"
        if synthetic_ok else "a required scripted stage failed")]
    model = stages.get("local_model")
    if model is not None and model["status"] == "LOCAL_MODEL_EVIDENCE_AVAILABLE" and sha:
        entries.append(GateEvidence("real_agent", OutcomeEvidenceStatus.LOCAL_MODEL_PASS,
                                    EvidenceType.LOCAL_MODEL, sha,
                                    "development episodes with a local model at this commit; "
                                    "not confirmatory",
                                    model_digest=(model.get("model") or {}).get("digest")))
    elif model is not None:
        entries.append(GateEvidence("real_agent", OutcomeEvidenceStatus.NOT_RUN,
                                    EvidenceType.LOCAL_MODEL, None, model["reason"]))
    return release_evidence_matrix(entries)


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Agent-outcome end-to-end gate", "",
             f"- commit: `{report['candidate_commit_sha']}`",
             f"- overall: **{report['status']}**", "", "| stage | status | seconds |",
             "|---|---|---:|"]
    for name, stage in report["stages"].items():
        lines.append(f"| {name} | {stage['status']} | {stage.get('seconds', '')} |")
    lines += ["", "## Release-evidence matrix", "", "| gate | status | evidence type |",
              "|---|---|---|"]
    for row in report["release_matrix"]["rows"]:
        lines.append(f"| {row['gate_id']} | {row['status']} | {row['evidence_type'] or '-'} |")
    lines += ["", "No row is a production qualification. NOT_RUN means no evidence of that "
              "gate's own type exists for this commit."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", required=True,
                        help="run without network access (required; the gate has no online mode)")
    parser.add_argument("--all", action="store_true", help="run every required stage")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--local-model", metavar="MODEL")
    parser.add_argument("--skip", action="append", default=[], help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.all:
        parser.error("--all is required: partial runs cannot qualify a candidate")
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    stages: dict[str, Any] = {}
    stages["source"] = stage_source(out)
    sha = stages["source"].get("commit_sha")
    plan = {
        "contracts": lambda: stage_commands("contracts", [
            [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", *CONTRACT_TESTS]], out),
        "security": lambda: stage_commands("security", [
            [PY, "tools/adversarial_gate.py"], [PY, "tools/scan_secrets.py"]], out),
        "demo": lambda: stage_demo(out),
        "arms": lambda: stage_arms(out),
        "provenance": lambda: stage_commands("provenance", [
            [PY, "tools/baseline_manifest.py", "--verify",
             "research/results/agent-outcomes/baseline-70e34c8/manifest.json"],
            [PY, "tools/evidence_inventory.py", "--check"],
            [PY, "tools/claim_scanner.py"],
            [PY, "tools/checklist_ledger.py", "--check", "--history", "--resolve-tests"],
            [PY, "tools/status_at_head.py", "--check"]], out),
    }
    for name, run in plan.items():
        if name in args.skip:
            stages[name] = {"status": "NOT_RUN", "reason": "skipped by request"}
            continue
        try:
            stages[name] = run()
        except Exception as exc:  # noqa: BLE001 - one broken stage must not lose the report
            stages[name] = {"status": "FAIL", "reason": f"{type(exc).__name__}: {exc}"}
    if args.local_model:
        stages["local_model"] = stage_local_model(args.local_model, out, sha)
    required = [name for name in ("source", *plan) if name not in args.skip]
    failed = [name for name in required if stages[name]["status"] != "PASS"]
    report = {"schema_id": SCHEMA_ID, "candidate_commit_sha": sha,
              "status": "FAIL" if failed else "PASS", "failed_stages": failed,
              "stages": stages, "release_matrix": build_matrix(stages, sha),
              "production_qualified": False}
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                     encoding="utf-8")
    (out / "REPORT.md").write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
