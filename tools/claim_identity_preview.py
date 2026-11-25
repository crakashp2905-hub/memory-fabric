#!/usr/bin/env python3
"""Dry-run the claim-identity change from v1 to v2 over a store (VEGA next W03-09).

    python tools/claim_identity_preview.py STORE.db [--tenant TENANT] [--out report.json]

Reads the store, writes nothing. For every current memory it compares the v1 and v2
identifiers from ``conflicts.claim`` and reports:

* ``changed``: memories whose identifier set differs;
* ``collisions_resolved``: pairs that were one claim under v1 (same identifiers, same
  parameter words, different values) and are two claims under v2;
* ``collisions_created``: pairs that become one claim only under v2 (expected empty).

Rollback is exact: set ``MEMORY_FABRIC_CLAIM_IDENTITY=v1`` and restart; the claim index
is an in-memory cache rebuilt from the projection, so no stored data changes either way.
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric.conflicts import claim, contradicts  # noqa: E402


def _same(a: tuple, b: tuple) -> bool:
    return bool(a[0]) and a[0] == b[0] and len(a[1] & b[1]) >= min(2, len(a[1]), len(b[1])) and a[2] != b[2]


def preview(contents: dict[str, str]) -> dict[str, Any]:
    v1 = {m: claim(t, "v1") for m, t in contents.items()}
    v2 = {m: claim(t, "v2") for m, t in contents.items()}
    changed = sorted(m for m in contents if v1[m][0] != v2[m][0])
    resolved, created = [], []
    for a, b in combinations(sorted(contents), 2):
        before, after = _same(v1[a], v1[b]), _same(v2[a], v2[b])
        if before and not after:
            resolved.append([a, b])
        elif after and not before:
            created.append([a, b])
    return {"memories": len(contents), "changed": len(changed), "changed_ids": changed[:200],
            "collisions_resolved": resolved[:200], "collisions_resolved_count": len(resolved),
            "collisions_created": created[:200], "collisions_created_count": len(created),
            "contradictions_v2_sample": sum(contradicts(contents[a], contents[b]) for a, b in resolved[:200]),
            "rollback": "MEMORY_FABRIC_CLAIM_IDENTITY=v1; no stored data changes"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("store")
    parser.add_argument("--tenant")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    from memory_fabric import MemoryFabric

    fabric = MemoryFabric(args.store)
    try:
        contents = {mid: m.content for mid, m in fabric.state.memories.items()
                    if args.tenant is None or m.tenant_id == args.tenant}
    finally:
        fabric.close()
    report = preview(contents)
    text = json.dumps(report, indent=1, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
