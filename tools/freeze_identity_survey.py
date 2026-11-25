"""Run the claim-identity v1->v2 preview over representative corpora and a backed-up store (freeze F03-02).

    python tools/freeze_identity_survey.py --out qualification/identity-survey.json

Corpora: every next-study world (three splits, ten families, seeds 0-9), every PR #41 Vega
world (seeds 0-7), the operations handbook used by the examples, and the literal memories
written by the example programs. Each world is previewed as its own store, then all text is
previewed together. One real store is written from the combined corpus, backed up with the
CLI, previewed from the backup, and reopened under v1 and v2 to show rollback changes no
stored byte. Any created collision is listed for review; the gate needs zero unreviewed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from benchmarks import vega_cdm_worlds, vega_next_worlds  # noqa: E402
from claim_identity_preview import preview  # noqa: E402

LITERAL = re.compile(r"""remember\(\s*["'][^"']+["']\s*,\s*["']([^"']{8,})["']""")


def corpora() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for split in vega_next_worlds.SPLITS:
        for family in vega_next_worlds.FAMILIES:
            for seed in range(10):
                w = vega_next_worlds.build(family, seed, split)
                out[f"next/{split}/{family}/{seed}"] = {f"{i}": item.text for i, item in enumerate(w.items)}
    for family in vega_cdm_worlds.FAMILIES:
        for seed in range(8):
            w = vega_cdm_worlds.build(family, seed)
            out[f"pr41/{family}/{seed}"] = {f"{i}": item.text for i, item in enumerate(w.items)}
    handbook = [ln.strip("-* ").strip() for ln in (ROOT / "examples/project-handbook.md").read_text(
        encoding="utf-8").splitlines() if len(ln.strip()) > 20 and not ln.startswith("#")]
    out["examples/handbook"] = {f"{i}": t for i, t in enumerate(handbook)}
    literals = [m.group(1) for p in sorted((ROOT / "examples").glob("*.py"))
                for m in LITERAL.finditer(p.read_text(encoding="utf-8"))]
    out["examples/literals"] = {f"{i}": t for i, t in enumerate(literals)}
    return out


def store_round_trip(texts: list[str]) -> dict[str, Any]:
    from memory_fabric import MemoryFabric
    from memory_fabric.cli import main as cli

    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d) / "store.db", Path(d) / "backup.db"
        f = MemoryFabric(str(src), auto_activate=True)
        try:
            for t in texts:
                f.remember("survey", t, scope="team")
        finally:
            f.close()
        backup_rc = cli(["--db", str(src), "backup", str(dst)])
        digests = {}
        for version in ("v1", "v2", "v1"):
            os.environ["MEMORY_FABRIC_CLAIM_IDENTITY"] = version
            g = MemoryFabric(str(dst))
            try:
                contents = {mid: m.content for mid, m in g.state.memories.items()}
            finally:
                g.close()
            digests.setdefault(version, []).append(hashlib.sha256(dst.read_bytes()).hexdigest())
        os.environ.pop("MEMORY_FABRIC_CLAIM_IDENTITY", None)
        report = preview(contents)
    stable = len({d for ds in digests.values() for d in ds}) == 1
    return {"memories": len(contents), "backup_exit": backup_rc, "preview_from_backup": {
        k: report[k] for k in ("changed", "collisions_resolved_count", "collisions_created_count")},
        "store_bytes_identical_across_v1_v2_v1": stable}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default="qualification/identity-survey.json")
    args = p.parse_args(argv)
    per_store, created, resolved, memories = {}, [], 0, 0
    allc = corpora()
    for name, contents in allc.items():
        r = preview(contents)
        memories += r["memories"]
        resolved += r["collisions_resolved_count"]
        per_store[name] = {k: r[k] for k in ("memories", "changed", "collisions_resolved_count",
                                             "collisions_created_count")}
        created += [{"store": name, "pair": [contents[a], contents[b]]} for a, b in r["collisions_created"]]
    unique = sorted({t for c in allc.values() for t in c.values()})
    combined = preview({f"{i}": t for i, t in enumerate(unique)})
    created += [{"store": "combined", "pair": [unique[int(a)], unique[int(b)]]} for a, b in combined["collisions_created"]]
    trip = store_round_trip(unique)
    report = {"schema_id": "memory-fabric.freeze-identity-survey.v1", "stores": len(per_store),
              "memories": memories, "unique_texts": len(unique),
              "collisions_resolved": resolved + combined["collisions_resolved_count"],
              "collisions_created": created, "collisions_created_count": len(created),
              "combined": {k: combined[k] for k in ("memories", "changed", "collisions_resolved_count",
                                                    "collisions_created_count")},
              "backup_round_trip": trip, "per_store": per_store,
              "rollback": "MEMORY_FABRIC_CLAIM_IDENTITY=v1; the claim index is rebuilt in memory, no stored byte changes",
              "verdict": "PASS" if not created and trip["store_bytes_identical_across_v1_v2_v1"]
              and trip["backup_exit"] == 0 else "REVIEW_REQUIRED"}
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("stores", "memories", "unique_texts", "collisions_resolved",
                                             "collisions_created_count", "verdict")}))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
