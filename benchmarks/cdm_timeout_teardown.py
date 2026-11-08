"""Verify that wall-time interruption terminates a local worker and cleans files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


def run(timeout_seconds: float = 0.1) -> dict[str, Any]:
    if type(timeout_seconds) not in (int, float) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    repo_root = Path(__file__).resolve().parents[1]
    artifact_root = repo_root / "research" / "results" / "cdm"
    artifact_root.mkdir(parents=True, exist_ok=True)
    temp = tempfile.TemporaryDirectory(prefix="cdm-timeout-", dir=artifact_root)
    path = Path(temp.name)
    marker = path / "started"
    child_code = ("from pathlib import Path; import sys\n"
                  "Path(sys.argv[1]).write_text('started', encoding='utf-8')\n"
                  "while True: pass\n")
    started = time.monotonic()
    timed_out = False
    marker_created = False
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen([sys.executable, "-c", child_code, str(marker)],
                                   cwd=path, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = started + max(2.0, timeout_seconds * 10)
        while not marker.exists() and time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("worker exited before entering bounded workload")
            time.sleep(0.005)
        if not marker.exists():
            raise RuntimeError("worker startup exceeded teardown fixture deadline")
        marker_created = True
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2.0)
            exit_code = process.returncode
            worker_terminated = process.poll() is not None
        else:
            exit_code = None
            worker_terminated = True
        temp.cleanup()
    return {"schema": "cdm-timeout-teardown-v1", "timeout_seconds": timeout_seconds,
        "timed_out": timed_out, "worker_marker_created": marker_created,
        "worker_returncode": exit_code, "worker_terminated": worker_terminated,
        "temporary_directory_removed": not path.exists(),
        "temporary_path_was_isolated": path.is_relative_to(artifact_root),
        "network_calls": 0, "model_calls": 0,
        "limitations": ["verifies parent-enforced wall timeout teardown",
            "does not impose or verify an OS-level CPU quota"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=0.1)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    report = run(args.timeout)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if (report["timed_out"] and report["worker_terminated"]
                 and report["temporary_directory_removed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
