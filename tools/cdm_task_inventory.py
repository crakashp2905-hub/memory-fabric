"""Build a local hash inventory for every task row in the CDM ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from tools.cdm_offline_gate import source_manifest

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "CDM_TASK_LEDGER.md"
OUTPUT = ROOT / "research" / "results" / "cdm" / "task-evidence-inventory.json"
PATH_RE = re.compile(r"(?<![\w.-])((?:docs|research|src|tests|benchmarks|tools)/[A-Za-z0-9_./-]+)")
MODULE_RE = re.compile(r"\b(tests|benchmarks)\.([a-zA-Z0-9_]+)\b")
FILE_RE = re.compile(r"(?:^|[\s`'(])((?:\.\./)?[A-Za-z0-9_./-]+\.(?:py|md|json|csv|html|yaml|yml|toml|txt))(?:$|[\s`'):,])")
SOURCE_BUNDLES = (
    (1, 40, "contracts-capture", (
        "docs/CAUSAL_REPLAY_API.md", "docs/CAUSAL_REPLAY_SECURITY.md",
        "src/memory_fabric/causal_replay/types.py",
        "src/memory_fabric/causal_replay/capture.py",
        "tests/test_cdm_types.py", "tests/test_cdm_capture.py", "tests/test_cdm_api.py",
    )),
    (41, 80, "belief-replay", (
        "src/memory_fabric/causal_replay/bayes.py",
        "src/memory_fabric/causal_replay/state.py",
        "src/memory_fabric/causal_replay/executor.py",
        "src/memory_fabric/causal_replay/replay.py",
        "tests/test_cdm_bayes.py", "tests/test_cdm_replay.py",
        "tests/test_cdm_checkpoints.py",
    )),
    (81, 120, "interventions-certificates", (
        "src/memory_fabric/causal_replay/intervention.py",
        "src/memory_fabric/causal_replay/certificates.py",
        "src/memory_fabric/causal_replay/verifier.py",
        "tests/test_cdm_interventions.py", "tests/test_cdm_replay.py",
        "tests/test_cdm_verifier.py",
    )),
    (121, 140, "attribution-evaluator", (
        "src/memory_fabric/causal_replay/attribution.py",
        "src/memory_fabric/causal_replay/evaluator.py",
        "tests/test_cdm_attribution.py", "tests/test_cdm_attribution_bench.py",
        "tests/test_cdm_evaluator.py", "benchmarks/cdm_attribution_bench.py",
    )),
    (141, 160, "architecture-comparisons", (
        "benchmarks/cdm_architecture_superiority.py",
        "benchmarks/cdm_tame_inspired.py", "benchmarks/cdm_bench.py",
        "tests/test_cdm_architecture_superiority.py", "tests/test_cdm_tame.py",
        "tests/test_cdm_attribution_bench.py",
    )),
    (161, 180, "scheduler-efficiency", (
        "src/memory_fabric/causal_replay/scheduler.py",
        "src/memory_fabric/causal_replay/checkpoints.py",
        "benchmarks/cdm_efficiency.py", "benchmarks/cdm_budgeted_inference.py",
        "tests/test_cdm_scheduler.py", "tests/test_cdm_efficiency.py",
        "tests/test_cdm_checkpoints.py",
    )),
    (181, 200, "correction-federation", (
        "src/memory_fabric/influence.py", "src/memory_fabric/dependence.py",
        "benchmarks/cdm_trace_world.py", "benchmarks/cdm_correction_utility.py",
        "tests/test_cdm_trace_world.py", "tests/test_cdm_correction_utility.py",
        "tests/test_cdm_federated_provenance.py",
    )),
    (201, 220, "privacy-security", (
        "docs/CAUSAL_REPLAY_SECURITY.md", "src/memory_fabric/causal_replay/capture.py",
        "src/memory_fabric/causal_replay/api.py",
        "tests/test_cdm_privacy.py", "tests/test_cdm_api.py",
        "tests/test_cdm_tempfiles.py", "tests/test_action_fence.py",
    )),
    (221, 240, "demo-product-qualification", (
        "docs/COUNTERFACTUAL_DECISION_MEMORY.md",
        "src/memory_fabric/causal_replay/viewer.py",
        "src/memory_fabric/causal_replay/api.py",
        "benchmarks/cdm_battery_world.py", "benchmarks/cdm_trace_world.py",
        "tools/cdm_offline_gate.py", "tests/test_cdm_visualization.py",
        "tests/test_cdm_in_process_compatibility.py",
    )),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_paths(text: str, file_index: dict[str, list[str]]) -> list[str]:
    candidates = set(PATH_RE.findall(text))
    candidates.update(FILE_RE.findall(text))
    for package, module in MODULE_RE.findall(text):
        candidates.add(f"{package}/{module}.py")
    resolved: set[str] = set()
    for candidate in candidates:
        clean = candidate.lstrip("./").rstrip(".,;:)")
        path = (ROOT / clean).resolve()
        if path.is_relative_to(ROOT) and path.is_file():
            resolved.add(path.relative_to(ROOT).as_posix())
        elif "/" not in clean and len(file_index.get(clean, ())) == 1:
            resolved.add(file_index[clean][0])
    return sorted(resolved)


def _git_output(*args: str) -> str | None:
    try:
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                                text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def build_inventory() -> dict[str, Any]:
    lines = LEDGER.read_text(encoding="utf-8").splitlines()
    source_tree_sha256, _source_file_count, _source_rows = source_manifest()
    git_head = _git_output("rev-parse", "HEAD")
    git_status = _git_output("status", "--porcelain=v1", "--untracked-files=all")
    commit_by_path: dict[str, str | None] = {}
    file_index: dict[str, list[str]] = {}
    for path in ROOT.rglob("*"):
        # Build output holds copies of source files; a bare file name would match
        # both copies and stop resolving, so only tracked source is indexed.
        if (path.is_file() and not any(part in {".git", ".tmp", ".tmp-cdm", "__pycache__", "build", "dist"}
                                       for part in path.relative_to(ROOT).parts)):
            file_index.setdefault(path.name, []).append(path.relative_to(ROOT).as_posix())
    source_bundles: dict[str, dict[str, Any]] = {}
    artifact_cache: dict[str, dict[str, Any]] = {}

    def artifact_record(relative: str) -> dict[str, Any]:
        if relative not in artifact_cache:
            artifact = (ROOT / relative).resolve()
            if not artifact.is_relative_to(ROOT) or not artifact.is_file():
                raise ValueError(f"source bundle artifact is missing: {relative}")
            if relative not in commit_by_path:
                commit_by_path[relative] = _git_output("log", "-1", "--format=%H", "--", relative)
            artifact_cache[relative] = {"path": relative,
                "sha256": sha256(artifact.read_bytes()),
                "last_committed_revision": commit_by_path[relative]}
        return artifact_cache[relative]

    for first, last, bundle_id, paths in SOURCE_BUNDLES:
        source_bundles[bundle_id] = {"task_range": [first, last],
            "artifacts": [artifact_record(path) for path in paths]}
    section = ""
    entries: list[dict[str, Any]] = []
    for line in lines:
        if line.startswith("## Complete at this checkpoint"):
            section = "complete"
        elif line.startswith("## Partial"):
            section = "partial"
        elif line.startswith("## Open"):
            section = "open"
        match = re.match(r"^\| CDM-(\d{3}) \|(.+?)\|\s*$", line)
        if match is None:
            continue
        task_id, body = match.groups()
        task_number = int(task_id)
        bundle = next((row for row in SOURCE_BUNDLES
                       if row[0] <= task_number <= row[1]), None)
        if bundle is None:
            raise ValueError(f"task {task_id} has no source bundle")
        artifact_paths = _artifact_paths(body, file_index)
        artifacts = []
        for relative in artifact_paths:
            # The generated inventory cannot contain its own content hash.
            if relative == OUTPUT.relative_to(ROOT).as_posix():
                continue
            artifacts.append(artifact_record(relative))
        entries.append({"task_id": f"CDM-{task_id}", "status": section,
            "source_bundle_id": bundle[2],
            "evidence_row_sha256": sha256(line.encode("utf-8")),
            "source_snapshot": {"git_head": git_head,
                "source_tree_sha256": source_tree_sha256,
                "working_tree_dirty": bool(git_status)},
            "referenced_artifacts": artifacts})
    ids = [item["task_id"] for item in entries]
    expected = {f"CDM-{number:03d}" for number in range(1, 241)}
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError("task ledger must contain each CDM-001..240 ID exactly once")
    counts = {status: sum(item["status"] == status for item in entries)
              for status in ("complete", "partial", "open")}
    all_artifacts = {item["path"]: item for item in artifact_cache.values()}
    return {"schema": "cdm-task-evidence-inventory-v1", "ledger": "docs/CDM_TASK_LEDGER.md",
        "git_head": git_head, "source_tree_sha256": source_tree_sha256,
        "working_tree_dirty": bool(git_status),
        "task_count": len(entries), "status_counts": counts,
        "source_bundle_count": len(source_bundles),
        "artifact_count": len(all_artifacts), "source_bundles": source_bundles,
        "tasks": sorted(entries, key=lambda item: item["task_id"])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = args.out.resolve()
    if not output.is_relative_to(ROOT):
        parser.error("output must stay inside the local checkout")
    inventory = build_inventory()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(f"PASS: inventoried {inventory['task_count']} tasks and "
          f"{inventory['artifact_count']} existing evidence artifacts at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
