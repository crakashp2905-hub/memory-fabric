#!/usr/bin/env python3
"""Reproducibility capsule for the scripted agent-outcome results (W22-09).

    python tools/repro_capsule.py --write research/results/agent-outcomes/REPRO_CAPSULE.json
    python tools/repro_capsule.py --verify research/results/agent-outcomes/REPRO_CAPSULE.json

The capsule records the source commit, the digest of every fixture and harness
file the results depend on, the environment, and a digest of each deterministic
output (per-case rows included). ``--verify`` regenerates every output in a
fresh process and compares digests, so another offline checkout can confirm the
stored results. No local model is involved: every listed output is scripted,
so the model digest is recorded as ``none``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "src", ROOT):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))
SCHEMA_ID = "memory-fabric.repro-capsule.v1"
SOURCES = ("benchmarks/outcome_episode.py", "benchmarks/outcome_arms.py",
           "benchmarks/outcome_ablation.py", "benchmarks/outcome_worlds_extra.py",
           "benchmarks/outcome_retrieval_baselines.py", "benchmarks/outcome_poisoning.py",
           "benchmarks/outcome_worlds_typed.py", "src/memory_fabric/outcome_typed/episode.py",
           "src/memory_fabric/outcome_typed/cdm_dispatch.py")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def outputs(seeds: int = 2) -> dict[str, Callable[[], Any]]:
    from benchmarks import outcome_ablation, outcome_poisoning, outcome_retrieval_baselines
    from benchmarks.outcome_arms import run as arms
    from benchmarks.outcome_worlds_extra import run_multihop, run_temporal

    def scrub(report: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in report.items() if k not in {"elapsed_s"}}

    return {
        "arms_rows": lambda: arms(seeds=seeds)["rows"],
        "ablation_factorial": lambda: scrub(outcome_ablation.factorial(seeds))["by_scope"],
        "temporal_rows": lambda: run_temporal(seeds)["rows"],
        "multihop_rows": lambda: run_multihop(seeds)["rows"],
        "retrieval_baseline_rows": lambda: [
            {k: v for k, v in r.items()} for r in outcome_retrieval_baselines.run(seeds)["rows"]],
        "poisoning": lambda: outcome_poisoning.run(),
    }


def build(seeds: int = 2) -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                            text=True).stdout.strip() or None
    return {"schema_id": SCHEMA_ID, "commit": commit, "seeds": seeds,
            "environment": {"python": platform.python_version(), "platform": platform.platform()},
            "model_digest": "none (scripted outputs only)",
            "sources": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                        for path in SOURCES},
            "outputs": {name: _digest(make()) for name, make in outputs(seeds).items()}}


def verify(capsule: dict[str, Any]) -> list[str]:
    problems = []
    for path, digest in capsule["sources"].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            problems.append(f"source changed since the capsule: {path}")
    fresh = subprocess.run([sys.executable, str(Path(__file__)), "--emit",
                            "--seeds", str(capsule["seeds"])], cwd=ROOT, capture_output=True,
                           text=True, timeout=1800)
    if fresh.returncode != 0:
        return problems + [f"regeneration failed: {fresh.stderr[-300:]}"]
    regenerated = json.loads(fresh.stdout)["outputs"]
    for name, digest in capsule["outputs"].items():
        if regenerated.get(name) != digest:
            problems.append(f"output differs from the capsule: {name}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write")
    parser.add_argument("--verify")
    parser.add_argument("--emit", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--seeds", type=int, default=2)
    args = parser.parse_args(argv)
    if args.emit:
        print(json.dumps(build(args.seeds)))
        return 0
    if args.write:
        Path(args.write).write_text(json.dumps(build(args.seeds), indent=1, sort_keys=True) + "\n",
                                    encoding="utf-8")
        print(f"wrote {args.write}")
        return 0
    if args.verify:
        problems = verify(json.loads(Path(args.verify).read_text(encoding="utf-8")))
        for problem in problems:
            print(problem)
        print("capsule verified" if not problems else "capsule FAILED")
        return 1 if problems else 0
    parser.error("pass --write PATH or --verify PATH")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
