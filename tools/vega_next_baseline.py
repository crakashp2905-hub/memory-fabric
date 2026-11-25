#!/usr/bin/env python3
"""Freeze the two baselines for the next Vega checklist (VEGA next W01-01).

    python tools/vega_next_baseline.py --write

Binds, for the merged main commit and for the PR #41 head it merged: the commit and
tree SHAs, whether the working tree was dirty, the Python runtime, the recorded
vega-U model pins and the SHA-256 of every benchmark input and recorded result the
next checklist builds on. Nothing here is recomputed later; the manifest is
compared, never rewritten (``--check``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "results" / "vega-cdm" / "next" / "baseline-manifest.json"
BASELINES = {"merged_main": "6314a7a8cba5b1d57103e73e05366b5426b980c0",
             "pr41_head": "1015a33447a1692457d33067b9e79066a5fbd7b0"}
INPUTS = ("benchmarks/vega_cdm_worlds.py", "benchmarks/vega_cdm_matched_arms.py",
          "src/memory_fabric/adapters/vega_u.py", "src/memory_fabric/conflicts.py",
          "src/memory_fabric/validation.py", "research/results/vega-cdm/development/vega-0.8b.json",
          "research/results/vega-cdm/development/scripted.json", "research/prereg/vega-cdm-v1.json",
          "tests/fixtures/vega_u/decide-0.19.0.json")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def build() -> dict:
    baselines = {}
    for name, sha in BASELINES.items():
        files = {}
        for rel in INPUTS:
            blob = subprocess.run(["git", "show", f"{sha}:{rel}"], cwd=ROOT, capture_output=True).stdout
            files[rel] = hashlib.sha256(blob).hexdigest() if blob else None
        baselines[name] = {"commit": sha, "tree": _git("rev-parse", f"{sha}^{{tree}}"), "inputs_sha256": files}
    fixture = json.loads((ROOT / "tests/fixtures/vega_u/decide-0.19.0.json").read_text())
    return {"schema_id": "memory-fabric.vega-next-baseline.v1", "baselines": baselines,
            "working_tree_differs_from_baseline_inputs": bool(_git("status", "--porcelain", "--", *INPUTS)),
            "python": platform.python_version(), "platform": platform.platform(),
            "model": {"runtime": "vegaml 0.19.0", "reader": fixture["model"]["audit"]["reader"],
                      "engine_sha256": fixture["model"]["audit"]["engine_sha256"],
                      "hub_revision": fixture["checkpoint"]["revision"],
                      "files_sha256": fixture["checkpoint"]["files_sha256"]},
            "note": "Both baselines carry identical inputs: PR #41 merged without further change."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(build(), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.check:
        stored = json.loads(OUT.read_text())
        fresh = build()
        same = stored["baselines"] == fresh["baselines"] and stored["model"] == fresh["model"]
        print("baseline manifest matches" if same else "baseline manifest DIFFERS")
        return 0 if same else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
