"""Hermetic stdlib-only acceptance gate for the experimental CDM subsystem."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("requests", "httpx", "torch", "numpy", "networkx", "transformers")


def source_manifest() -> tuple[str, int, list[dict[str, str]]]:
    rows = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if path.suffix in {".pyc", ".pyo"} or relative.startswith("research/results/cdm/"):
            continue
        parts = path.relative_to(ROOT).parts
        if any(part in {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
                        "build", "dist"} or part.startswith(".tmp")
               or part.endswith(".egg-info") for part in parts):
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
        rows.append({"path": relative, "sha256": digest})
    body = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest(), len(rows), rows


def run_step(name: str, command: list[str], cwd: Path = ROOT) -> dict[str, Any]:
    started = time.perf_counter()
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    return {"name": name, "command": command, "returncode": result.returncode,
            "seconds": round(time.perf_counter() - started, 4),
            "stdout": result.stdout, "stderr": result.stderr}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", required=True,
                        help="required: run the complete local hermetic qualification")
    parser.add_argument("--seed", type=int, default=20261108)
    parser.add_argument("--out", default="research/results/cdm/offline-qualification")
    args = parser.parse_args(argv)
    try:
        checkout = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT,
                                  capture_output=True, text=True, check=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as exc:
        parser.error(f"qualification requires an accessible local Git checkout: {exc}")
    if Path(checkout.stdout.strip()).resolve() != ROOT.resolve():
        parser.error("qualification script root must match the local Git checkout root")
    out = (ROOT / args.out).resolve()
    if ROOT not in out.parents:
        parser.error("output directory must be inside the repository")
    out.mkdir(parents=True, exist_ok=True)

    digest, file_count, rows = source_manifest()
    if any(name in sys.modules for name in FORBIDDEN):
        print("FAIL: forbidden optional dependency already imported", file=sys.stderr)
        return 1
    tests = ["tests.test_cdm_types", "tests.test_cdm_bayes", "tests.test_cdm_capture",
             "tests.test_cdm_api", "tests.test_cdm_checkpoints",
             "tests.test_cdm_interventions", "tests.test_cdm_visualization",
             "tests.test_cdm_replay", "tests.test_cdm_privacy",
             "tests.test_cdm_scheduler", "tests.test_cdm_evaluator",
             "tests.test_cdm_attribution"]
    tests.append("tests.test_cdm_trace_world")
    tests.append("tests.test_cdm_efficiency")
    tests.append("tests.test_cdm_report")
    tests.append("tests.test_cdm_verifier")
    tests.append("tests.test_cdm_tame")
    tests.append("tests.test_cdm_attribution_bench")
    tests.append("tests.test_cdm_replay_overhead")
    tests.append("tests.test_cdm_environment")
    tests.append("tests.test_cdm_governance_ablation")
    tests.append("tests.test_cdm_intervention_vs_loo")
    tests.append("tests.test_cdm_trust_feedback_ablation")
    tests.append("tests.test_cdm_architecture_superiority")
    tests.append("tests.test_cdm_dependency_frontier")
    tests.append("tests.test_cdm_checkpoint_granularity")
    tests.append("tests.test_cdm_budgeted_inference")
    tests.append("tests.test_cdm_timeout_teardown")
    tests.append("tests.test_cdm_dependency_shapes")
    tests.append("tests.test_cdm_federated_provenance")
    tests.append("tests.test_cdm_correction_comparison")
    tests.append("tests.test_cdm_correction_utility")
    tests.append("tests.test_cdm_task_inventory")
    tests.append("tests.test_cdm_tempfiles")
    tests.append("tests.test_cdm_in_process_compatibility")
    tests.append("tests.test_cdm_architecture_superiority")
    steps = [run_step("CDM focused unit suite", [sys.executable, "-m", "unittest", *tests]),
             run_step("battery demonstrator", [sys.executable, "-m", "benchmarks.cdm_battery_world",
                                                 "--seed", str(args.seed)]),
             run_step("multi-agent trace worlds", [sys.executable, "-m", "benchmarks.cdm_trace_world",
                         "--seed", str(args.seed)]),
             run_step("efficiency scaling", [sys.executable, "-m", "benchmarks.cdm_efficiency",
                         "--seeds", str(args.seed), str(args.seed + 1),
                         "--out", str(out / "efficiency-smoke")]),
             run_step("certificate acceptance report", [sys.executable, "-m", "benchmarks.cdm_report",
                         "--out", str(out / "certificate-acceptance")]),
             run_step("governance-aware capture ablation", [sys.executable,
                         "-m", "benchmarks.cdm_governance_ablation",
                         "--out", str(out / "governance-ablation-r10")]),
             run_step("intervention versus LOO ablation", [sys.executable,
                         "-m", "benchmarks.cdm_intervention_vs_loo",
                         "--out", str(out / "intervention-vs-loo-r11")]),
             run_step("trust annotation and evaluator feedback ablation", [sys.executable,
                         "-m", "benchmarks.cdm_trust_feedback_ablation",
                         "--out", str(out / "trust-feedback-ablation-r12")]),
             run_step("R5 v3 architecture development preflight", [sys.executable,
                         "-m", "benchmarks.cdm_architecture_superiority", "--split", "development",
                         "--out", str(out / "architecture-superiority-r5v3-development")]),
             run_step("R5 v3 architecture confirmatory comparison", [sys.executable,
                         "-m", "benchmarks.cdm_architecture_superiority", "--split", "confirmatory",
                         "--out", str(out / "architecture-superiority-r5v3-confirmatory"),
                         "--development-manifest",
                         str(out / "architecture-superiority-r5v3-development" / "manifest.json")]),
             run_step("TAME-inspired prequential comparison", [sys.executable,
                         "-m", "benchmarks.cdm_tame_inspired",
                         "--out", str(out / "tame-inspired")]),
             run_step("matched attribution architecture comparison", [sys.executable,
                         "-m", "benchmarks.cdm_attribution_bench", "--seeds",
                         *[str(20261401 + offset) for offset in range(20)],
                         "--out", str(out / "attribution-benchmark-r8")]),
             run_step("paired synthetic benchmark", [sys.executable, "-m", "benchmarks.cdm_bench",
                         "--seeds", *[str(args.seed + offset) for offset in range(10)],
                         "--out", str(out / "benchmark-smoke")]),
             run_step("checkpoint granularity measurement", [sys.executable,
                         "-m", "benchmarks.cdm_checkpoint_granularity",
                         "--out", str(out / "checkpoint-granularity" / "report.json")]),
             run_step("matched-budget exact versus approximate inference", [sys.executable,
                         "-m", "benchmarks.cdm_budgeted_inference",
                         "--out", str(out / "budgeted-inference" / "report.json")]),
             run_step("wall-time interruption teardown", [sys.executable,
                         "-m", "benchmarks.cdm_timeout_teardown",
                         "--out", str(out / "timeout-teardown" / "report.json")]),
             run_step("competing-evidence dependency shapes", [sys.executable,
                         "-m", "benchmarks.cdm_dependency_shapes",
                         "--out", str(out / "dependency-shapes" / "report.json")]),
             run_step("federated CDM provenance preservation", [sys.executable,
                         "-m", "unittest", "tests.test_cdm_federated_provenance"]),
             run_step("correction review strategy comparison", [sys.executable,
                         "-m", "unittest", "tests.test_cdm_correction_comparison"]),
             run_step("frozen correction-aware utility contract", [sys.executable,
                         "-m", "unittest", "tests.test_cdm_correction_utility"]),
             run_step("240-task evidence inventory", [sys.executable,
                         "-m", "tools.cdm_task_inventory"])]
    # Import gate: normal MemoryFabric import remains usable and import is inert
    # with respect to network sockets and filesystem state.
    steps.append(run_step("inert package import", [sys.executable, "-c",
        "import socket;\n"
        "def fail(*a, **k): raise AssertionError('network attempted')\n"
        "socket.socket = fail\n"
        "import memory_fabric.causal_replay\n"
        "print('PASS: imported without socket construction')\n"]))
    passed = all(step["returncode"] == 0 for step in steps)
    git_state = _git_state()
    manifest = {"schema": "cdm-offline-qualification-v1", "status": "PASS" if passed else "FAIL",
        "seed": args.seed, "python": sys.version, "platform": platform.platform(),
        "source_tree_sha256": digest, "source_file_count": file_count,
        "git_head": git_state.get("head"), "git_ref": git_state.get("ref"),
        "uncommitted_paths": git_state.get("paths", []),
        "uncommitted_path_count": len(git_state.get("paths", [])),
        "remote_state": "unknown; no network access performed",
        "dependencies": "Python standard library only for this gate",
        "steps": steps}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                        encoding="utf-8")
    (out / "report.md").write_text(
        f"# CDM offline qualification\n\nStatus: **{manifest['status']}**\n\n"
        f"Source SHA-256: `{digest}` ({file_count} files)\n\nPython: `{sys.version.split()[0]}`\n\n"
        + "\n".join(f"- {'PASS' if s['returncode'] == 0 else 'FAIL'}: {s['name']} ({s['seconds']}s)"
                      for s in steps) + "\n\nSynthetic-only evidence; no physical-world or external validation claim.\n",
        encoding="utf-8")
    print(f"{manifest['status']}: wrote {out / 'report.md'}")
    for step in steps:
        print(f"{'PASS' if step['returncode'] == 0 else 'FAIL'} {step['name']}")
        if step["returncode"]:
            print(step["stdout"][-4000:], step["stderr"][-4000:], file=sys.stderr)
    return 0 if passed else 1


def _git_head() -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _git_state() -> dict[str, Any]:
    """Read only local Git metadata; never query a remote."""
    state: dict[str, Any] = {"head": _git_head(), "ref": None, "paths": []}
    try:
        ref = subprocess.run(["git", "symbolic-ref", "--short", "-q", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, timeout=5)
        state["ref"] = ref.stdout.strip() if ref.returncode == 0 else "detached"
        status = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all"],
                                cwd=ROOT, capture_output=True, text=True, timeout=5)
        if status.returncode == 0:
            state["paths"] = [line[3:].strip() for line in status.stdout.splitlines()]
    except (OSError, subprocess.SubprocessError):
        pass
    return state


if __name__ == "__main__":
    raise SystemExit(main())
