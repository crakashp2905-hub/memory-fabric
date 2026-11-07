"""Regenerate the PR #30 withheld-case corpus from its exact candidate checkout."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPECTED_HEAD = "12c612ea37980f92d206fe2b343b217603d1b3cc"
EXPECTED_BASE = "79a77f43c9e376968163c2164ee277052ed4117e"
SEEDS = (101, 102, 103, 104, 105)

_EXTRACT = r'''
import hashlib, json
from pathlib import Path
from experiments.p3b_teams import run_one
from experiments.teamworld import build_world
seeds=(101,102,103,104,105)
rows=[]
for seed in seeds:
    world=build_world(seed, agents=50, rounds=60)
    truth={}
    task_events=[]
    for event in world.schedule:
        if event.kind in ('discover','correct'):
            truth[event.fact.key]=event.fact
        elif event.kind=='task':
            task_events.append((event, truth.get(event.fact.key)))
    result=run_one('fabric',seed,agents=50,rounds=60)
    assert len(result.tasks)==len(task_events)==100
    for ix,(outcome,(event,current)) in enumerate(zip(result.tasks,task_events)):
        if not outcome.valid_evidence_withheld:
            continue
        assert current is not None and outcome.evidence_miss_reason
        rows.append({
            'case_id':f'pr30-{seed}-task-{ix:03d}','seed':seed,'task_index':ix,
            'agent':event.agent,
            'action':{'tool':'answer','target':current.question(),'asked_for':'current_value'},
            'evidence':{'claim':current.statement(),'memory_available_to_backend':True,
                        'returned_to_agent':False},
            'blocker_reason':outcome.evidence_miss_reason,'oracle_supported':True,
            'oracle_value':current.value,'observed_answer':outcome.answered,
        })
root=Path.cwd()
sha=lambda p:hashlib.sha256((root/p).read_bytes()).hexdigest()
print(json.dumps({'source_sha256':{'experiments/p3b_teams.py':sha('experiments/p3b_teams.py'),
                                    'experiments/teamworld.py':sha('experiments/teamworld.py')},
                  'cases':rows},sort_keys=True))
'''


def extract(source_root: Path) -> dict[str, Any]:
    source_root = source_root.resolve()
    if not (source_root / "experiments/p3b_teams.py").is_file():
        raise ValueError("source root does not contain PR #30 TeamWorld benchmark")
    git = ["git", "-C", str(source_root)]
    head = subprocess.run(git + ["rev-parse", "HEAD"], cwd=source_root,
                          capture_output=True, text=True, check=True).stdout.strip()
    base = subprocess.run(git + ["rev-parse", "HEAD^"], cwd=source_root,
                          capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(git + ["status", "--porcelain", "--untracked-files=all"], cwd=source_root,
                                capture_output=True, text=True, check=True).stdout.strip())
    if head != EXPECTED_HEAD or base != EXPECTED_BASE or dirty:
        raise ValueError("source checkout must be clean at the registered PR #30 candidate and base")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source_root / "src") + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run([sys.executable, "-c", _EXTRACT], cwd=source_root,
                            env=env, capture_output=True, text=True, check=True, timeout=300)
    payload = json.loads(result.stdout)
    rows = payload["cases"]
    counts = {seed: sum(row["seed"] == seed for row in rows) for seed in SEEDS}
    expected_counts = {101: 10, 102: 15, 103: 19, 104: 21, 105: 19}
    if counts != expected_counts or len(rows) != 84:
        raise ValueError(f"PR #30 replay mismatch: {counts} / {len(rows)}")
    if any(not row["action"] or not row["evidence"]["claim"] or
           not row["blocker_reason"] or row["oracle_supported"] is not True for row in rows):
        raise ValueError("an extracted case is missing required acceptance fields")
    return {
        "schema": "mf-pr30-withheld-cases/1", "population": "synthetic_scripted",
        "source_commit": head, "base_commit": base, "worktree_clean": True,
        "seeds": list(SEEDS), "agents": 50, "tasks_per_seed": 100,
        "attempted": 500, "valid_withheld": len(rows), "withholding_rate": len(rows) / 500,
        "published_withholding_rate": 0.168,
        "all_cases_oracle_supported": all(row["oracle_supported"] for row in rows),
        "cases_per_seed": counts, "blocker_counts": {
            code: sum(row["blocker_reason"] == code for row in rows)
            for code in sorted({row["blocker_reason"] for row in rows})},
        "source_sha256": payload["source_sha256"], "cases": rows,
        "limitations": [
            "Cases are regenerated from the exact PR #30 candidate source and deterministic seeds; the PR did not publish row-level serialized examples.",
            "This is the local scripted TeamWorld experiment, not real-model evidence.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path("research/results/pr30-withheld-cases.json"))
    args = parser.parse_args()
    report = extract(args.source_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "cases": report["valid_withheld"],
                      "withholding_rate": report["withholding_rate"],
                      "source_commit": report["source_commit"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
