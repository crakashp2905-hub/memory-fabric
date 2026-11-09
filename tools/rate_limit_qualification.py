"""Run the no-network agent API rate-limit/quota contract and write evidence."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests import test_agent_api_rate_limit as contracts  # noqa: E402

RESULT = ROOT / "research/results/h5-08-rate-limit-qualification.json"
SOURCES = ("src/memory_fabric/agent_api.py", "src/memory_fabric/limits.py",
           "tests/test_agent_api_rate_limit.py", "tools/rate_limit_qualification.py")


def main() -> int:
    contracts.OBSERVED.clear()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(contracts.AgentApiRateLimits)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    report = {
        "schema": "memory-fabric-agent-api-rate-limit-qualification/1",
        "source_commit": commit,
        "source_worktree_dirty": bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
            text=True, check=True).stdout.strip()),
        "tests_run": result.testsRun,
        "tests_passed": result.wasSuccessful(),
        "scenarios": contracts.OBSERVED,
        "input_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                         for path in SOURCES},
        "passed": result.wasSuccessful() and result.testsRun == 3
        and len(contracts.OBSERVED) == 3
        and all(scenario.get("rejections_changed_store") is False
                for scenario in contracts.OBSERVED.values()),
    }
    RESULT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": str(RESULT.relative_to(ROOT)), "passed": report["passed"],
                      "tests_run": report["tests_run"]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
