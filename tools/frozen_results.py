#!/usr/bin/env python3
"""Guard frozen result records against silent change or deletion (W23-07, W15-10).

    python tools/frozen_results.py --check
    python tools/frozen_results.py --freeze PATH --producer "python ..." --commit SHA
    python tools/frozen_results.py --supersede PATH --reason "..." --commit SHA

``research/results/agent-outcomes/FROZEN.json`` lists every frozen record (gate
runs at a commit, pass or fail, and other per-commit evidence) with its SHA-256,
the command that produced it and the commit. ``--check`` fails if a listed file
is missing (deleted runs are not allowed to vanish), if its bytes changed, if a
JSON record has no commit field, or if it holds a raw prompt or credential key.
Replacing a record is only possible through ``--supersede``, which keeps the old
digest and the reason in the entry's history.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "research" / "results" / "agent-outcomes" / "FROZEN.json"
SCHEMA_ID = "memory-fabric.frozen-results.v1"
COMMIT_FIELDS = ("candidate_commit_sha", "commit_sha", "source_sha", "gate_commit", "commit", "repo_commit")
FORBIDDEN_KEYS = frozenset({"prompt", "messages", "raw_prompt", "credential", "token", "secret",
                            "password"})


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(registry: Path = REGISTRY) -> dict[str, Any]:
    if not registry.is_file():
        return {"schema_id": SCHEMA_ID, "entries": []}
    data: dict[str, Any] = json.loads(registry.read_text(encoding="utf-8"))
    return data


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        found = {str(k).lower() for k in value}
        for item in value.values():
            found |= _keys(item)
        return found
    if isinstance(value, list):
        out: set[str] = set()
        for item in value:
            out |= _keys(item)
        return out
    return set()


def check(registry: Path = REGISTRY, root: Path = ROOT) -> list[str]:
    data = load(registry)
    problems = []
    if data.get("schema_id") != SCHEMA_ID:
        problems.append("registry schema_id mismatch")
    for entry in data.get("entries", []):
        path = root / entry["path"]
        if not path.is_file():
            problems.append(f"{entry['path']}: frozen record deleted")
            continue
        if _sha(path) != entry["sha256"]:
            problems.append(f"{entry['path']}: frozen record changed without --supersede")
        if not entry.get("producer") or not entry.get("commit"):
            problems.append(f"{entry['path']}: entry lacks producer or commit")
        if path.suffix == ".json":
            body = json.loads(path.read_text(encoding="utf-8"))
            keys = _keys(body)
            if not any(field in keys for field in COMMIT_FIELDS):
                problems.append(f"{entry['path']}: record carries no commit field")
            leaked = sorted(keys & FORBIDDEN_KEYS)
            if leaked:
                problems.append(f"{entry['path']}: record holds forbidden keys {leaked}")
    return problems


def freeze(path: str, producer: str, commit: str, registry: Path = REGISTRY,
           root: Path = ROOT) -> None:
    data = load(registry)
    if any(e["path"] == path for e in data["entries"]):
        raise SystemExit(f"{path} is already frozen; use --supersede with a reason")
    data["entries"].append({"path": path, "sha256": _sha(root / path), "producer": producer,
                            "commit": commit, "history": []})
    data["entries"].sort(key=lambda e: e["path"])
    registry.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def supersede(path: str, reason: str, commit: str, registry: Path = REGISTRY,
              root: Path = ROOT) -> None:
    data = load(registry)
    for entry in data["entries"]:
        if entry["path"] == path:
            entry["history"].append({"sha256": entry["sha256"], "commit": entry["commit"],
                                     "superseded_because": reason})
            entry["sha256"], entry["commit"] = _sha(root / path), commit
            registry.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            return
    raise SystemExit(f"{path} is not frozen")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--freeze")
    parser.add_argument("--supersede")
    parser.add_argument("--producer", default="")
    parser.add_argument("--reason", default="")
    parser.add_argument("--commit", default="")
    args = parser.parse_args(argv)
    if args.freeze:
        freeze(args.freeze, args.producer, args.commit)
    if args.supersede:
        if not args.reason:
            raise SystemExit("--supersede needs --reason")
        supersede(args.supersede, args.reason, args.commit)
    problems = check()
    for problem in problems:
        print(f"FROZEN: {problem}")
    if not problems:
        print(f"{len(load()['entries'])} frozen records intact")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
