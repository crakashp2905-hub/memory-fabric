"""Exercise package upgrade and rollback against a persistent store."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
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
corrected, withdrawn = expected["ids"][:2]
events = list(fabric.log.read())
chain = fabric.log.chain.verify(events)
head_seq, head_digest = fabric.log.chain.head()
actual = {"event_count": len(events), "chain_ok": chain.ok,
          "chain_head": [head_seq, head_digest],
          "corrected_version": fabric.get(corrected).version,
          "corrected_content": fabric.get(corrected).content,
          "withdrawn_state": fabric.get(withdrawn).lifecycle_state.value,
          "grant_events": [dict(e.payload) for e in events if e.type == "GrantIssued"]}
if len(expected["ids"]) > 2:
    actual["added_state"] = fabric.get(expected["ids"][2]).lifecycle_state.value
assert actual["event_count"] == expected["event_count"], actual
assert actual["chain_head"] == expected["chain_head"] and actual["chain_ok"], actual
assert actual["corrected_version"] == expected.get("corrected_version", 2), actual
assert actual["corrected_content"] == expected.get("corrected_content", "Pump P1 purge is 30 seconds."), actual
assert actual["withdrawn_state"] == expected.get("withdrawn_state", "quarantined"), actual
if "added_state" in expected:
    assert actual["added_state"] == expected["added_state"], actual
assert actual["grant_events"] == expected.get("grant_events", []), actual
print(json.dumps(actual))
fabric.close()
'''

POST_UPGRADE_WRITE = r'''
import json, sys
from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
fabric = MemoryFabric(sys.argv[1])
expected = json.loads(sys.argv[2])
corrected, withdrawn = expected["ids"]
fabric.revise(corrected, "Pump P1 purge is 45 seconds.", agent_id="upgrade-agent",
              reason="post-upgrade correction")
added = fabric.remember("upgrade-agent", "Pump P3 purge is 20 seconds.")
fabric.validate(added, actor="reviewer")
policy = ActionPolicy(tools={"publish": ToolRule("publish", requires_grant=True)},
                     grants={"upgrade-agent": frozenset({"publish"})},
                     policy_id="upgrade-rollback-smoke")
gate = ActionGate(fabric, policy)
certificate = fabric.certify("publish-purge-setting", [corrected], "upgrade-agent")
grant = gate.issue_grant("publish", "upgrade-agent", "host", certificate=certificate)
events = list(fabric.log.read())
chain = fabric.log.chain.verify(events)
head_seq, head_digest = fabric.log.chain.head()
updated = {"ids": [corrected, withdrawn, added], "event_count": len(events),
           "chain_ok": chain.ok, "chain_head": [head_seq, head_digest],
           "corrected_version": fabric.get(corrected).version,
           "corrected_content": fabric.get(corrected).content,
           "withdrawn_state": fabric.get(withdrawn).lifecycle_state.value,
           "added_state": fabric.get(added).lifecycle_state.value,
           "grant_id": grant.grant_id,
           "grant_events": [dict(event.payload) for event in events
                            if event.type == "GrantIssued"]}
print(json.dumps(updated))
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
    temp_root = ROOT / ".test-tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="upgrade-rollback-", dir=temp_root)).resolve()
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
    post_upgrade_script = scratch / "post_upgrade_write.py"
    seed_script.write_text(SEED, encoding="utf-8")
    verify_script.write_text(VERIFY, encoding="utf-8")
    post_upgrade_script.write_text(POST_UPGRADE_WRITE, encoding="utf-8")
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
    post_upgrade = json.loads(run([str(python), str(post_upgrade_script), str(db), json.dumps(seed)],
                                  cwd=scratch, env=env))
    post_upgrade_state = json.loads(run([str(python), str(verify_script), str(db),
                                         json.dumps(post_upgrade)], cwd=scratch, env=env))
    run([str(python), "-m", "pip", "install", "--no-deps", "--force-reinstall", str(baseline)],
        cwd=scratch, env=env)
    rollback_meta = run([str(python), "-c", "import memory_fabric; print(memory_fabric.__version__)"],
                        cwd=scratch, env=env)
    rollback_state = json.loads(run([str(python), str(verify_script), str(db), json.dumps(post_upgrade)],
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
        "post_upgrade_write": post_upgrade,
        "post_upgrade_readback": post_upgrade_state,
        "rollback_readback": rollback_state,
        "upgrade_passed": upgraded_meta != baseline_meta and upgrade_state["chain_ok"],
        "rollback_passed": rollback_meta == baseline_meta and rollback_state == post_upgrade_state,
        "scope_limitations": [
            "The v0.11.0 baseline uses host-configured ActionPolicy grants, not durable grant events. Grant persistence across package upgrade cannot be demonstrated from this baseline.",
            "Post-upgrade writes exercise correction, append, validation, quarantine/tombstone, event-chain and content readback; they do not exercise every event type or external side effect."
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["upgrade_passed"] and report["rollback_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
