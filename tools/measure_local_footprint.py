"""Measure one installed Memory Fabric wheel on the current local host.

This is an engineering smoke measurement, not a cross-host benchmark.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import psutil


THRESHOLDS = {
    "installed_package_bytes_max": 5_000_000,
    "wheel_bytes_max": 2_000_000,
    "cli_version_median_ms_max": 1_500,
    "cli_version_p95_ms_max": 2_000,
    "sqlite_bytes_per_record_max": 100_000,
    "idle_cpu_percent_max": 5.0,
}


def _size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def measure(wheel: Path, *, output: Path, starts: int = 15,
            records: int = 200, idle_seconds: float = 30.0) -> dict[str, Any]:
    """Install a wheel to an isolated target and measure basic local costs."""
    wheel = wheel.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    site = output / "site"
    site.mkdir(exist_ok=True)
    python = Path(sys.executable)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(site)
    env["TEMP"] = str(output)
    env["TMP"] = str(output)
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-index", "--no-deps",
         "--upgrade", "--target", str(site), str(wheel)],
        check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    cli = site / "bin" / "memory-fabric.exe" if os.name == "nt" else site / "bin" / "memory-fabric"
    if not cli.is_file():
        raise RuntimeError(f"wheel did not install the CLI at {cli}")

    startup_ms: list[float] = []
    for _ in range(starts):
        before = time.perf_counter()
        subprocess.run([str(cli), "--version"], check=True, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        startup_ms.append((time.perf_counter() - before) * 1000)

    db = output / "growth.sqlite3"
    db.unlink(missing_ok=True)
    writer = (
        "from memory_fabric import MemoryFabric\n"
        "import sys\n"
        "with MemoryFabric(sys.argv[1], seed=0) as fabric:\n"
        "    for i in range(int(sys.argv[2])):\n"
        "        fabric.remember('footprint', f'Maintenance reading sensor-{i}: value {i} units.', scope='team')\n"
    )
    subprocess.run([str(python), "-c", writer, str(db), str(records)], check=True, env=env)
    database_bytes = db.stat().st_size

    idle = psutil.Popen([str(python), "-c", "import time; time.sleep(60)"], env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    process = psutil.Process(idle.pid)
    process.cpu_percent(None)
    time.sleep(idle_seconds)
    idle_cpu = process.cpu_percent(None)
    idle.terminate()
    idle.wait(timeout=5)

    site_bytes = _size(site)
    ordered = sorted(startup_ms)
    p95_index = max(0, min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1))
    observed = {
        "installed_package_bytes": site_bytes,
        "wheel_bytes": wheel.stat().st_size,
        "cli_version_median_ms": statistics.median(startup_ms),
        "cli_version_p95_ms": ordered[p95_index],
        "sqlite_bytes_per_record": database_bytes / records,
        "idle_cpu_percent": idle_cpu,
    }
    passed = all(observed[key] <= limit for key, limit in (
        ("installed_package_bytes", THRESHOLDS["installed_package_bytes_max"]),
        ("wheel_bytes", THRESHOLDS["wheel_bytes_max"]),
        ("cli_version_median_ms", THRESHOLDS["cli_version_median_ms_max"]),
        ("cli_version_p95_ms", THRESHOLDS["cli_version_p95_ms_max"]),
        ("sqlite_bytes_per_record", THRESHOLDS["sqlite_bytes_per_record_max"]),
        ("idle_cpu_percent", THRESHOLDS["idle_cpu_percent_max"]),
    ))
    return {
        "schema": "memory-fabric-local-footprint/1",
        "package": "memory-fabric",
        "version": "0.14.0",
        "wheel": str(wheel),
        "host": {"python": platform.python_version(), "platform": platform.platform(),
                 "processor": platform.processor(), "logical_cpus": psutil.cpu_count()},
        "method": {"install": "pip --no-index --no-deps --target from local wheel",
                   "startup": "cold process memory-fabric --version wall time",
                   "startup_samples": starts,
                   "storage": "SQLite file size after sequential unique memory inserts",
                   "storage_records": records,
                   "idle_cpu_sample_seconds": idle_seconds,
                   "installed_bytes_include": ["package source", "dist-info", "generated CLI", "Python bytecode"]},
        "observed": observed,
        "thresholds": THRESHOLDS,
        "checks_passed": passed,
        "limitations": [
            "One local Windows host and Python minor version only; no cross-host portability claim.",
            "Cold CLI version invocation is not a service startup or request latency SLO.",
            "One small SQLite fixture; no WAL peak, backup, encryption key, concurrency or federation costs.",
            "Idle CPU is a single short sample, not a long-duration soak.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--output", type=Path, default=Path(tempfile.gettempdir()) / "memory-fabric-footprint")
    parser.add_argument("--starts", type=int, default=15)
    parser.add_argument("--records", type=int, default=200)
    parser.add_argument("--idle-seconds", type=float, default=30.0)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if args.starts < 1 or args.records < 1 or args.idle_seconds <= 0:
        parser.error("starts, records and idle-seconds must be positive")
    result = measure(args.wheel, output=args.output, starts=args.starts,
                     records=args.records, idle_seconds=args.idle_seconds)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.json:
        args.json.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
