"""Install a wheel into an isolated target and audit production-safe defaults."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKER = r'''
import json, socket, sys, threading
from pathlib import Path
binds = []
original_bind = socket.socket.bind
def watched_bind(sock, address):
    binds.append(str(address))
    return original_bind(sock, address)
socket.socket.bind = watched_bind
threads_before = {t.ident for t in threading.enumerate()}
sys.path.insert(0, sys.argv[1])
import inspect
import memory_fabric
from memory_fabric import MemoryFabric
from memory_fabric.adapters.mcp import McpServer
from memory_fabric.agent_api import build_agent_server
from memory_fabric.governance.firewall import Firewall
from memory_fabric.observability.server import build_server as build_dashboard
from memory_fabric.transport import serve as serve_peers

fabric = MemoryFabric(":memory:")
defaults = {
    "package_path": str(Path(memory_fabric.__file__).resolve()),
    "claim_checker_off": fabric.claim_checker is None,
    "reranker_off": fabric.rerank is False,
    "firewall_model_screen_off": Firewall().model_screen is None,
    "mcp_extended_off": inspect.signature(McpServer).parameters["extended"].default is False,
    "mcp_trusted_local_off": inspect.signature(McpServer).parameters["trusted_local"].default is False,
    "agent_api_loopback": inspect.signature(build_agent_server).parameters["host"].default == "127.0.0.1",
    "dashboard_loopback": inspect.signature(build_dashboard).parameters["host"].default == "127.0.0.1",
    "federation_loopback": inspect.signature(serve_peers).parameters["host"].default == "127.0.0.1",
    "no_import_bind_calls": not binds,
    "no_import_threads": {t.ident for t in threading.enumerate()} == threads_before,
}
fabric.close()
print(json.dumps(defaults, sort_keys=True))
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--report", type=Path,
                        default=ROOT / "research/results/h5-09-production-defaults.json")
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise SystemExit("provide one built .whl artifact")
    scratch = ROOT / ".test-tmp"
    scratch.mkdir(exist_ok=True)
    for name in ("TEMP", "TMP", "TMPDIR"):
        os.environ[name] = str(scratch)
    tempfile.tempdir = str(scratch)
    with tempfile.TemporaryDirectory(prefix="mf-default-audit-") as temp:
        target = Path(temp) / "fresh-install"
        install = subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps",
                                  "--no-compile", "--target", str(target), str(wheel)],
                                 cwd=Path(temp), capture_output=True, text=True, timeout=90)
        if install.returncode:
            raise SystemExit("fresh wheel install failed: " + install.stderr[-2000:])
        probe = subprocess.run([sys.executable, "-I", "-c", WORKER, str(target)],
                               cwd=Path(temp), capture_output=True, text=True, timeout=30)
        if probe.returncode:
            raise SystemExit("isolated defaults probe failed: " + probe.stderr[-3000:])
        defaults: dict[str, Any] = json.loads(probe.stdout.strip().splitlines()[-1])
        defaults["package_path"] = Path(defaults["package_path"]).relative_to(target).as_posix()
    checks = {name: bool(value) for name, value in defaults.items()
              if name != "package_path"}
    input_paths = ["tools/audit_production_defaults.py", "pyproject.toml",
                   "tests/data/default_features.json", "src/memory_fabric/_fabric/core.py",
                   "src/memory_fabric/agent_api.py", "src/memory_fabric/adapters/mcp.py",
                   "src/memory_fabric/governance/firewall.py",
                   "src/memory_fabric/observability/server.py", "src/memory_fabric/transport.py"]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.strip()
    report = {"schema": "memory-fabric-production-defaults-audit/1",
              "source_commit": commit,
              "source_worktree_dirty": bool(subprocess.run(
                  ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                  text=True, check=True).stdout.strip()),
              "wheel": wheel.name,
              "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
              "install": "pip install --no-deps --target, then python -I isolated probe",
              "defaults": defaults, "checks": checks, "passed": all(checks.values()),
              "input_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                               for name in input_paths},
              "limitations": [
                  "This audit checks a fresh wheel install and code defaults; it does not inspect deployment firewall rules or remote infrastructure.",
                  "No default listener is started by import; listener-factory bind defaults are loopback.",
              ]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.report), "checks_passed": sum(checks.values()),
                      "checks_total": len(checks), "passed": report["passed"]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
