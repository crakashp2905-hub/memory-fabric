#!/usr/bin/env python3
"""Map every recorded result to the commitments that would let it support a claim (W01-02).

    python tools/evidence_inventory.py            # print the inventory
    python tools/evidence_inventory.py --write    # rewrite the committed inventory
    python tools/evidence_inventory.py --check    # exit 1 if stale or a promoted claim is incomplete

A *promoted* result is one a public claim cites (``research/claims.json``). It must
resolve every commitment its claim class requires:

* ``source_commit`` - the 40-hex commit recorded in the result, equal to the claim's pin;
* ``evidence_sha256`` - the result file's bytes, equal to the claim's pin;
* ``dataset_descriptor_sha256`` - a digest of the dataset the claim names (generated
  datasets have no separate file; the descriptor pins generator, seeds and size);
* ``generator_revision`` and ``evaluator_digest`` - for in-tree generators and scorers,
  the source commit itself (the code that generated and scored the data at that commit);
* ``prompt_digest`` and ``model_digest`` - required only when the claim's model is a
  learned model; ``NOT_APPLICABLE`` for deterministic simulators and network tests.

Every other result is either ``RECORDED_WITH_COMMIT`` (it names the commit that
produced it, but no claim rests on it) or ``LEGACY_UNVERIFIED`` (it does not).
Nothing in this inventory upgrades a result; it only reports what is pinned.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import claims_ledger  # noqa: E402

MANIFEST = ROOT / "research" / "results" / "MANIFEST.json"
OUT = ROOT / "research" / "results" / "agent-outcomes" / "EVIDENCE_INVENTORY.json"
SCHEMA_ID = "memory-fabric.evidence-inventory.v1"
_SHA40 = re.compile(r"[0-9a-f]{40}")
LEARNED_MODEL_MARKERS = ("qwen", "llama", "gemma", "claude", "gpt", "mistral", "phi", "model-agent")


def _learned(model: str) -> bool:
    lowered = model.lower()
    if lowered.startswith("deterministic") or lowered in {"none", "not applicable", "n/a"}:
        return False
    return any(marker in lowered for marker in LEARNED_MODEL_MARKERS)


def _digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def claim_commitments(raw: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    evidence = root / raw["evidence"]
    commitments: dict[str, Any] = {}
    problems: list[str] = []
    if not evidence.is_file():
        return {"claim_id": raw["id"], "evidence": raw["evidence"],
                "status": "PROMOTED_INCOMPLETE", "commitments": {},
                "problems": ["evidence file does not exist"]}
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    file_sha = hashlib.sha256(evidence.read_bytes()).hexdigest()
    commit = payload.get(raw.get("commit_field", ""))
    resolved = raw.get("resolved_commit")
    if isinstance(commit, str) and _SHA40.fullmatch(commit):
        commitments["source_commit"] = commit
    elif (isinstance(commit, str) and len(commit) >= 7 and isinstance(resolved, str)
          and _SHA40.fullmatch(resolved) and resolved.startswith(commit)):
        # The historical result records an abbreviated SHA; the registry pins the
        # full commit it resolves to. The result file itself is never rewritten.
        commitments["source_commit"] = resolved
        commitments["source_commit_resolution"] = "abbreviated in result, resolved in registry"
    else:
        commitments["source_commit"] = None
    commitments["evidence_sha256"] = file_sha
    dataset = raw.get("dataset")
    commitments["dataset_descriptor_sha256"] = (
        _digest({"dataset": dataset, "source_commit": commitments["source_commit"]})
        if isinstance(dataset, str) and dataset.strip() else None)
    commitments["generator_revision"] = commitments["source_commit"]
    commitments["evaluator_digest"] = (
        _digest({"evaluator": "in-tree scorer", "source_commit": commitments["source_commit"]})
        if commitments["source_commit"] else None)
    model = str(raw.get("model", ""))
    if _learned(model):
        commitments["model_digest"] = payload.get("model_digest")
        commitments["prompt_digest"] = payload.get("prompt_hash") or payload.get("prompt_digest")
    else:
        commitments["model_digest"] = "NOT_APPLICABLE"
        commitments["prompt_digest"] = "NOT_APPLICABLE"
    problems.extend(claims_ledger.validate_claim(raw, payload, file_sha))
    problems.extend(f"unresolved commitment: {name}" for name, value in commitments.items()
                    if value is None)
    return {"claim_id": raw["id"], "evidence": raw["evidence"], "claim_class": raw.get("class"),
            "model": model, "status": "PROMOTED_VERIFIED" if not problems else "PROMOTED_INCOMPLETE",
            "commitments": commitments, "problems": problems}


def build(root: Path = ROOT) -> dict[str, Any]:
    registry = json.loads((root / "research" / "claims.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "research" / "results" / "MANIFEST.json")
                          .read_text(encoding="utf-8"))
    promoted = [claim_commitments(raw, root) for raw in registry["claims"]]
    cited = {row["evidence"] for row in promoted}
    results = []
    for row in manifest["rows"]:
        if row["file"] in cited:
            status = "PROMOTED"
        elif row.get("git_sha"):
            status = "RECORDED_WITH_COMMIT"
        else:
            status = "LEGACY_UNVERIFIED"
        results.append({"file": row["file"], "status": status, "git_sha": row.get("git_sha"),
                        "population": row.get("population"),
                        "missing": sorted(key for key in ("dataset_digest", "model_id",
                                                          "prompt_hash", "seed", "prereg")
                                          if row.get(key) in (None, ""))})
    counts: dict[str, int] = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {"schema_id": SCHEMA_ID, "generated_by": "tools/evidence_inventory.py",
            "promoted_claims": promoted,
            "promoted_complete": all(item["status"] == "PROMOTED_VERIFIED" for item in promoted),
            "result_status_counts": dict(sorted(counts.items())),
            "results": sorted(results, key=lambda item: item["file"])}


def render(root: Path = ROOT) -> str:
    return json.dumps(build(root), indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
        return 0
    if "--check" in argv:
        problems = []
        if not OUT.is_file() or OUT.read_text(encoding="utf-8") != text:
            problems.append("EVIDENCE_INVENTORY.json is stale; run tools/evidence_inventory.py --write")
        data = json.loads(text)
        problems.extend(f"{claim['claim_id']}: {problem}" for claim in data["promoted_claims"]
                        for problem in claim["problems"])
        print("\n".join(problems) if problems else "PASS")
        return 1 if problems else 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
