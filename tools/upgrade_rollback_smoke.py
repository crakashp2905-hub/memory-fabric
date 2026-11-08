"""Exercise a read-only package upgrade and rollback against a persistent store.

This drill intentionally does not write new events after upgrade, so rollback
tests whether the installed baseline can still read the upgraded store state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import venv
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SEED = r'''
import json, sys
from memory_fabric import MemoryFabric
fabric = MemoryFabric(sys.argv[1], auto_activate=True)
corrected = fabric.remember("seed-agent", "Pump P1 purge is 10 seconds.")
fabric.validate(corrected, actor="reviewer")
fabric.revise(corrected, "Pump P1 purge is 30 seconds.", agent_id="seed-agent", reason="bulletin correction")
withdrawn = fabric.remember("seed-agent", "Pump P2 purge is 5 seconds.")
fabric.validate(withdrawn, actor="reviewer")
fabric.quarantine(withdrawn, reason="superseded bulletin", actor="reviewer", basis="superseded")
events = list(fabric.log.read())
chain = fabric.log.chain.verify(events)
head_seq, head_digest = fabric.log.chain.head()
print(json.dumps({"ids": [corrected, withdrawn], "event_count": len(events),
                  "chain_ok": chain.ok, "chain_head": [head_seq, head_digest],
                  "corrected_version": fabric.get(corrected).version,
                  "withdrawn_state": fabric.get(withdrawn).lifecycle_state.value}))
fabric.close()
'''

VERIFY = r'''
import json, sys
from memory_fabric import MemoryFabric
expected = json.loads(sys.argv[2])
fabric = MemoryFabric(sys.argv[1])
corrected, withdrawn = expected["ids"]
events = list(fabric.log.read())
chain = fabric.log.chain.verify(events)
head_seq, head_digest = fabric.log.chain.head()
actual = {"event_count": len(events), "chain_ok": chain.ok,
          "chain_head": [head_seq, head_digest],
          "corrected_version": fabric.get(corrected).version,
          "corrected_content": fabric.get(corrected).content,
          "withdrawn_state": fabric.get(withdrawn).lifecycle_state.value}
assert actual["event_count"] == expected["event_count"], actual
assert actual["chain_head"] == expected["chain_head"] and actual["chain_ok"], actual
assert actual["corrected_version"] == 2, actual
assert actual["corrected_content"] == "Pump P1 purge is 30 seconds.", actual
assert actual["withdrawn_state"] == "quarantined", actual
print(json.dumps(actual))
fabric.close()
'''


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    done = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(f"command failed: {command!r}\n{done.stdout}\n{done.stderr}")
    return done.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline_wheel", type=Path)
    parser.add_argument("candidate_wheel", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scratch = ROOT / ".test-tmp" / "upgrade-rollback"
    scratch.mkdir(parents=True, exist_ok=True)
    scratch = scratch.resolve()
    venv_path = scratch / "venv"
    venv.EnvBuilder(with_pip=True).create(venv_path)
    bindir = venv_path / ("Scripts" if os.name == "nt" else "bin")
    python = bindir / ("python.exe" if os.name == "nt" else "python")
    env = {key: value for key, value in os.environ.items()
           if key not in {"PYTHONPATH", "PYTHONHOME"}}
    env["TEMP"] = str(scratch)
    env["TMP"] = str(scratch)
    env["TMPDIR"] = str(scratch)
    db = scratch / "persistent.db"
    seed_script, verify_script = scratch / "seed.py", scratch / "verify.py"
    seed_script.write_text(SEED, encoding="utf-8")
    verify_script.write_text(VERIFY, encoding="utf-8")
    baseline = args.baseline_wheel.resolve()
    candidate = args.candidate_wheel.resolve()
    run([str(python), "-m", "pip", "install", "--no-deps", str(baseline)], cwd=scratch, env=env)
    baseline_meta = run([str(python), "-c", "import memory_fabric; print(memory_fabric.__version__)"],
                        cwd=scratch, env=env)
    seed = json.loads(run([str(python), str(seed_script), str(db)], cwd=scratch, env=env))
    run([str(python), "-m", "pip", "install", "--no-deps", "--upgrade", str(candidate)],
        cwd=scratch, env=env)
    upgraded_meta = run([str(python), "-c", "import memory_fabric; print(memory_fabric.__version__)"],
                        cwd=scratch, env=env)
    upgrade_state = json.loads(run([str(python), str(verify_script), str(db), json.dumps(seed)],
                                   cwd=scratch, env=env))
    run([str(python), "-m", "pip", "install", "--no-deps", "--force-reinstall", str(baseline)],
        cwd=scratch, env=env)
    rollback_meta = run([str(python), "-c", "import memory_fabric; print(memory_fabric.__version__)"],
                        cwd=scratch, env=env)
    rollback_state = json.loads(run([str(python), str(verify_script), str(db), json.dumps(seed)],
                                    cwd=scratch, env=env))
    report: dict[str, Any] = {
        "schema": "mf-upgrade-rollback-smoke/1",
        "driver_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                         capture_output=True, text=True, check=True).stdout.strip(),
        "driver_worktree_clean": not bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
            text=True, check=True).stdout.strip()),
        "baseline_wheel": baseline.name,
        "baseline_wheel_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest(),
        "candidate_wheel": candidate.name,
        "candidate_wheel_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
        "versions": {"baseline": baseline_meta, "upgraded": upgraded_meta, "rolled_back": rollback_meta},
        "baseline_seed": seed,
        "upgrade_readback": upgrade_state,
        "rollback_readback": rollback_state,
        "upgrade_passed": upgraded_meta != baseline_meta and upgrade_state["chain_ok"],
        "rollback_passed": rollback_meta == baseline_meta and rollback_state == upgrade_state,
        "scope_limitations": [
            "This drill performs no writes after upgrade; rollback with newer-schema writes is not tested.",
            "The v0.11.0 baseline uses host-configured ActionPolicy grants, not durable grant events. Grant persistence across package upgrade cannot be demonstrated from this baseline.",
            "Only correction, quarantine/tombstone, event-chain and content readback are asserted."
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["upgrade_passed"] and report["rollback_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
