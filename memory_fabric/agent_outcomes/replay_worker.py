"""Fixed, isolated worker entry point for bounded counterfactual replay."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

__stability__ = "experimental"


def _limits(cpu_ms: int) -> bool:
    if os.name != "posix":
        return False
    resource_api: Any = __import__("resource")
    cpu_seconds = max(1, (cpu_ms + 999) // 1000)
    resource_api.setrlimit(resource_api.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
    if hasattr(resource_api, "RLIMIT_AS"):
        resource_api.setrlimit(resource_api.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    if hasattr(resource_api, "RLIMIT_FSIZE"):
        resource_api.setrlimit(resource_api.RLIMIT_FSIZE, (32_768, 32_768))
    if hasattr(resource_api, "RLIMIT_NOFILE"):
        resource_api.setrlimit(resource_api.RLIMIT_NOFILE, (16, 16))
    return True


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        return 2
    request_path, response_path, cpu_ms_text = argv[1:]
    try:
        cpu_ms = int(cpu_ms_text)
        os_limits_enforced = _limits(cpu_ms)
        request: dict[str, Any] = json.loads(Path(request_path).read_text(encoding="utf-8"))
        if request.get("worker_id") != "proposal_echo":
            return 3
        decision = request["decision"]
        alternative = request["alternative"]
        result = {
            "status": "proposal_changed",
            "proposal": alternative,
            "decision_sha256": __import__("hashlib").sha256(
                json.dumps(decision, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False).encode("utf-8")
            ).hexdigest(),
        }
        resource_api: Any = __import__("resource") if os.name == "posix" else None
        result["_worker_cpu_ms"] = int(resource_api.getrusage(
            resource_api.RUSAGE_SELF).ru_utime * 1000) if resource_api else 0
        result["_worker_os_limits_enforced"] = os_limits_enforced
        Path(response_path).write_text(json.dumps(
            result, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ), encoding="utf-8")
        return 0
    except Exception:
        return 4


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
