"""P12b: many agents through one `agent-api` process.

P12 measured agents as separate processes, each opening the store, and found
throughput collapses (214 → 4 ops/s from 1 to 100 agents). Its recommendation
was to serve many agents from one process, but that was not measured. This
measures it. One `memory_fabric agent-api` server runs in its own process. N
agents, each with its own credential, are client threads in another process.
They wait at a barrier, then each runs the same mix over HTTP:

- 30% `remember`;
- 50% `recall`;
- 20% `fetch` then `verify` of a recalled memory (the action-time check).

Rate limiting is turned off (`--rate-limit 0`), because the question is what
the store can do, not what the limiter allows. Latency is per request, as the
client sees it.

The profiler records server CPU, process I/O counters, sampled RSS, wait time
for the fabric's in-process lock, and SQLite append duration. Python allocation
peaks are captured in a separate traced pass for each scenario so `tracemalloc`
does not distort the latency and throughput measurements. Lock wait is
application mutex wait, not kernel scheduler wait; OS I/O counters can omit
cached writes.

    python -m experiments.p12b_api_load            # writes the result
    python -m experiments.p12b_api_load --quick    # 10 agents, prints only

Not pre-registered: an operational measurement on this machine, like P12.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import statistics
from pathlib import Path
from typing import Any

from experiments.p12_load import SEED_MEMORIES, _pct

ROOT = Path(__file__).resolve().parent.parent
CLI = [sys.executable, "-m", "memory_fabric"]
AGENT_COUNTS = (1, 10, 50, 100)
OPS_PER_AGENT = 20
TOPICS = ("pump", "valve", "hoist", "compressor", "conveyor", "generator")


def subprocess_env() -> dict[str, str]:
    """Make the source checkout importable without requiring an editable install."""

    env = os.environ.copy()
    source = str(ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = source if not existing else source + os.pathsep + existing
    return env


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def post(port: int, op: str, body: dict, bearer: str) -> tuple[int, dict]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/{op}", data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {bearer}"})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")
    except OSError as exc:              # a dropped connection is an error, not a crash
        return 0, {"error": type(exc).__name__}


def get_json(port: int, path: str, profile_token: str) -> tuple[int, dict]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        headers={"X-Memory-Fabric-Profile-Token": profile_token})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def agent_loop(port: int, bearer: str, seed: int, barrier: threading.Barrier,
               out: list[tuple[str, float, int]], ops_per_agent: int = OPS_PER_AGENT) -> None:
    rng = random.Random(seed)
    barrier.wait()
    seen: list[str] = []
    for i in range(ops_per_agent):
        roll = rng.random()
        topic = rng.choice(TOPICS)
        started = time.perf_counter()
        if roll < 0.3:
            op = "remember"
            status, _ = post(port, "remember", {
                "content": f"{topic} unit {rng.randrange(100)} at site {seed}: "
                           f"observation {i} on the {topic} seal"}, bearer)
        elif roll < 0.8 or not seen:
            op = "recall"
            status, body = post(port, "recall", {"query": f"{topic} seal site", "k": 5}, bearer)
            seen += [m["memory_id"] for m in body.get("memories", [])]
        else:
            op = "fetch+verify"
            memory_id = rng.choice(seen)
            status, _ = post(port, "fetch", {"memory_id": memory_id}, bearer)
            if status == 200:
                status, _ = post(port, "verify", {"memory_id": memory_id}, bearer)
        out.append((op, (time.perf_counter() - started) * 1000.0, status))


def create_seed_database(path: str) -> None:
    from memory_fabric import MemoryFabric

    seed = MemoryFabric(path, auto_activate=True)
    rng = random.Random(0)
    for i in range(SEED_MEMORIES):
        topic = rng.choice(TOPICS)
        seed.remember("ag_seed", f"{topic} unit {i} at site {i % 17}: the {topic} seal "
                                  f"was replaced on visit {i}", scope="team")
    seed.close()


def run_one(agents: int, ops_per_agent: int = OPS_PER_AGENT,
            warmup_ops: int = 5, trial: int = 0,
            seed_template: str | None = None,
            trace_allocations: bool = False) -> dict[str, Any]:

    try:
        import psutil
    except ImportError:  # report absence; the benchmark remains useful for latency
        psutil = None
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "load.db")
        if seed_template:
            shutil.copy2(seed_template, db)
        else:
            create_seed_database(db)
        agents_file = os.path.join(tmp, "agents")
        with open(agents_file, "w") as fh:
            for n in range(agents):
                fh.write(f"ag_{n}:tn_default:{os.urandom(32).hex()}\n")
        port = free_port()
        run_env = subprocess_env()
        run_env["MEMORY_FABRIC_PROFILE"] = "1"
        profile_token = secrets.token_hex(32)
        run_env["MEMORY_FABRIC_PROFILE_TOKEN"] = profile_token
        if trace_allocations:
            run_env["MEMORY_FABRIC_PROFILE_ALLOCATIONS"] = "1"
        else:
            run_env.pop("MEMORY_FABRIC_PROFILE_ALLOCATIONS", None)
        server = subprocess.Popen(CLI + ["--db", db, "agent-api", "--agents-file", agents_file,
                                         "--port", str(port), "--rate-limit", "0"],
                                  cwd=ROOT, env=run_env,
                                  stdout=subprocess.DEVNULL,
                                  stderr=open(os.environ.get("P12B_LOG", os.devnull), "w"))
        try:
            process = psutil.Process(server.pid) if psutil is not None else None
            deadline = time.time() + 30
            while time.time() < deadline:
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/health", timeout=1)
                    break
                except Exception:  # noqa: BLE001 - polling a server that is starting
                    time.sleep(0.2)
            bearers = []
            for n in range(agents):
                issued = subprocess.run(
                    CLI + ["--db", db, "agent-api-issue", "--agents-file", agents_file,
                           "--agent", f"ag_{n}", "--ttl", "3600"],
                    capture_output=True, text=True, cwd=ROOT, env=subprocess_env())
                lines = issued.stdout.strip().splitlines()
                if issued.returncode != 0 or not lines:
                    detail = issued.stderr.strip() or "credential command produced no output"
                    raise RuntimeError(
                        f"credential issuance failed for ag_{n} "
                        f"(exit {issued.returncode}): {detail}"
                    )
                bearers.append(lines[-1])
            # Prime imports, authentication, routing and SQLite page caches.
            # These requests are deliberately excluded from measured records.
            for i in range(warmup_ops):
                post(port, "recall", {"query": f"{TOPICS[i % len(TOPICS)]} seal site", "k": 5},
                     bearers[i % len(bearers)])
            reset_status, _ = get_json(port, "/__profile/reset", profile_token)
            if reset_status != 200:
                raise RuntimeError("could not reset server profile after warmup")
            process_cpu_start = process.cpu_times() if process is not None else None
            process_io_start = process.io_counters() if process is not None else None
            process_memory_start = process.memory_info().rss if process is not None else None
            monitor_stop = threading.Event()
            rss_samples = [process_memory_start] if process_memory_start is not None else []

            def sample_rss() -> None:
                while not monitor_stop.wait(0.01):
                    try:
                        rss_samples.append(process.memory_info().rss)
                    except (psutil.Error, AttributeError):
                        return

            monitor = threading.Thread(target=sample_rss, daemon=True)
            if process is not None:
                monitor.start()
            barrier = threading.Barrier(agents + 1)
            records: list[tuple[str, float, int]] = []
            threads = [threading.Thread(target=agent_loop,
                                        args=(port, bearers[n], n + trial * 100_000, barrier,
                                              records, ops_per_agent))
                       for n in range(agents)]
            for t in threads:
                t.start()
            barrier.wait()
            started = time.perf_counter()
            for t in threads:
                t.join()
            wall = time.perf_counter() - started
            monitor_stop.set()
            if process is not None:
                monitor.join()
            try:
                rss_end = process.memory_info().rss if process is not None else None
                if rss_end is not None:
                    rss_samples.append(rss_end)
            except (psutil.Error, AttributeError):
                rss_end = None
            process_cpu_end = process.cpu_times() if process is not None else None
            process_io_end = process.io_counters() if process is not None else None
            profile_status, internal_profile = get_json(port, "/__profile", profile_token)
            if profile_status != 200:
                internal_profile = {}
        finally:
            server.terminate()
            server.wait(timeout=30)

    def lat(op: str | None) -> list[float]:
        return [r[1] for r in records if op is None or r[0] == op]

    errors: dict[str, int] = {}
    for op, _, status in records:
        if status != 200:
            errors[f"{op}:{status}"] = errors.get(f"{op}:{status}", 0) + 1
    ok = sum(1 for r in records if r[2] == 200)
    operation_counts = {
        name: sum(1 for op, _, _ in records if op == name)
        for name in ("remember", "recall", "fetch+verify")
    }
    if agents > 1 and any(count == 0 for count in operation_counts.values()):
        raise RuntimeError(f"load mix was not exercised: {operation_counts}")
    return {
        "agents": agents, "trial": trial, "ops_per_agent": ops_per_agent,
        "warmup_ops": warmup_ops, "ops": len(records), "ok": ok, "wall_s": wall,
        "ops_per_s": ok / wall if wall else 0.0, "errors": errors,
        "operation_counts": operation_counts,
        "profile": {
            "process_cpu_seconds": ((process_cpu_end.user + process_cpu_end.system)
                                     - (process_cpu_start.user + process_cpu_start.system))
                                   if process is not None else None,
            "process_cpu_percent_of_one_core": (
                100 * ((process_cpu_end.user + process_cpu_end.system)
                       - (process_cpu_start.user + process_cpu_start.system)) / wall
                if process is not None and wall else None),
            "server_read_bytes": (process_io_end.read_bytes - process_io_start.read_bytes)
                                 if process is not None else None,
            "server_write_bytes": (process_io_end.write_bytes - process_io_start.write_bytes)
                                  if process is not None else None,
            "server_rss_start_bytes": process_memory_start,
            "server_rss_end_bytes": rss_end,
            "server_rss_peak_bytes": max(rss_samples) if rss_samples else None,
            "psutil_available": process is not None,
            "fabric_profile": internal_profile,
        },
        "latency_ms": {name: {"p50": _pct(lat(op), 0.5), "p95": _pct(lat(op), 0.95),
                              "p99": _pct(lat(op), 0.99)}
                       for name, op in (("all", None), ("remember", "remember"),
                                        ("recall", "recall"), ("fetch+verify", "fetch+verify"))},
    }


def summarise_trials(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Capacity points with normal-approximation 95% CIs across repeated trials."""
    groups: dict[int, list[dict[str, Any]]] = {}
    for row in results:
        groups.setdefault(int(row["agents"]), []).append(row)
    summary: list[dict[str, Any]] = []
    for agents, rows in sorted(groups.items()):
        throughputs = [float(row["ops_per_s"]) for row in rows]
        p99s = [float(row["latency_ms"]["all"]["p99"]) for row in rows]

        def estimate(values: list[float]) -> dict[str, float]:
            mean = statistics.fmean(values)
            half = (1.96 * statistics.stdev(values) / len(values) ** 0.5
                    if len(values) > 1 else 0.0)
            return {"mean": mean, "ci95_low": mean - half, "ci95_high": mean + half}

        summary.append({
            "agents": agents,
            "trials": len(rows),
            "successful_operations": sum(int(row["ok"]) for row in rows),
            "attempted_operations": sum(int(row["ops"]) for row in rows),
            "throughput_ops_s": estimate(throughputs),
            "p99_ms": estimate(p99s),
        })
    return summary


def to_markdown(results: list[dict[str, Any]], commit: str, machine: str,
                result_name: str = "p12b-api-load",
                capacity: list[dict[str, Any]] | None = None) -> str:
    def cell(d: dict[str, float]) -> str:
        return f"{d['p50']:.1f} / {d['p95']:.1f} / {d['p99']:.1f}"

    rows = "\n".join(
        f"| {r['agents']} | {r['ops_per_agent']} | {r['ok']}/{r['ops']} "
        f"| {r['ops_per_s']:.0f} | {cell(r['latency_ms']['all'])} "
        f"| {cell(r['latency_ms']['remember'])} | {cell(r['latency_ms']['recall'])} "
        f"| {cell(r['latency_ms']['fetch+verify'])} | {r['errors'] or 'none'} |" for r in results)
    capacity = capacity or summarise_trials(results)
    curves = "\n".join(
        f"| {r['agents']} | {r['trials']} | {r['successful_operations']}/{r['attempted_operations']} "
        f"| {r['throughput_ops_s']['mean']:.1f} [{r['throughput_ops_s']['ci95_low']:.1f}, {r['throughput_ops_s']['ci95_high']:.1f}] "
        f"| {r['p99_ms']['mean']:.1f} [{r['p99_ms']['ci95_low']:.1f}, {r['p99_ms']['ci95_high']:.1f}] |"
        for r in capacity)
    profile_rows = []
    for r in results:
        profile = r.get("profile", {})
        fabric = profile.get("fabric_profile", {})
        lock = fabric.get("fabric_lock_wait", {})
        sqlite = fabric.get("sqlite_append_ns", {})
        allocation = profile.get("python_allocation_pass", {})
        lock_mean_us = lock.get("total", 0) / lock["count"] / 1000 if lock.get("count") else 0
        sqlite_mean_ms = (sqlite.get("total", 0) / sqlite["count"] / 1_000_000
                          if sqlite.get("count") else 0)
        profile_rows.append(
            f"| {r['agents']} | {profile.get('process_cpu_seconds')} "
            f"| {profile.get('process_cpu_percent_of_one_core')} "
            f"| {lock_mean_us:.2f} | {sqlite_mean_ms:.3f} "
            f"| {profile.get('server_read_bytes')} / {profile.get('server_write_bytes')} "
            f"| {profile.get('server_rss_peak_bytes')} "
            f"| {allocation.get('server_python_allocation_peak_bytes')} |"
        )
    profile_table = "\n".join(profile_rows)
    return f"""# P12b — many agents through one agent-api process

Produced by `python -m experiments.p12b_api_load` at commit `{commit}`; raw numbers
in [{result_name}.json]({result_name}.json). Machine: {machine}. One `agent-api`
server process on a SQLite store seeded with {SEED_MEMORIES} memories, rate limiting
off. N agents with their own credentials are client threads; the operation count per
agent is shown for each scenario (30% remember, 50% recall, 20% fetch then verify).
An operational measurement, not pre-registered.

Latencies in ms as the client sees them, p50 / p95 / p99. Throughput is successful
operations per second of wall time (a fetch+verify counts once).

| agents | ops / agent | ok / ops | ops/s | all ops | remember | recall | fetch+verify | errors |
|---:|---:|---:|---:|---|---|---|---|---|
{rows}

## Resource profile

| agents | server CPU seconds | CPU % of one core | mean fabric lock wait µs | mean SQLite append ms | OS read / write bytes | sampled RSS peak bytes | traced Python allocation peak bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|
{profile_table}

Latency, CPU, I/O and RSS come from the untraced pass. Allocation peaks come
from a separate `tracemalloc` pass with the same clients and workload size.
Lock wait measures the process-local Memory Fabric lock. OS I/O counters can
omit writes served from the OS cache; RSS is sampled every 10 ms and may miss
shorter peaks.

## Capacity curve across trials

Intervals are 95% normal-approximation confidence intervals across independent
trials; a one-trial point has a zero-width interval and is descriptive only.

| agents | trials | successful / attempted | ops/s mean [CI] | p99 ms mean [CI] |
|---|---:|---:|---:|---:|
{curves}

Compare [P12](p12-load.md), where each agent was its own process opening the
store: 214 → 31 → 9 → 4 ops/s at 1, 10, 50 and 100 agents on SQLite.
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--quick", action="store_true")
    p.add_argument("--agents", type=int, nargs="+", help="agent counts to run instead")
    p.add_argument("--ops-per-agent", type=int, default=OPS_PER_AGENT)
    p.add_argument("--warmup-ops", type=int, default=5)
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--out", default="p12b-api-load")
    args = p.parse_args(argv)
    counts = (10,) if args.quick else tuple(args.agents or AGENT_COUNTS)
    results = []
    if args.repeats < 1 or args.ops_per_agent < 1 or args.warmup_ops < 0:
        p.error("repeats and ops-per-agent must be positive; warmup-ops must be non-negative")
    with tempfile.TemporaryDirectory() as setup:
        seed_template = os.path.join(setup, "seed-template.db")
        create_seed_database(seed_template)
        for n in counts:
            for trial in range(args.repeats):
                r = run_one(n, args.ops_per_agent, args.warmup_ops, trial, seed_template)
                allocation = run_one(n, args.ops_per_agent, args.warmup_ops, trial,
                                     seed_template, trace_allocations=True)
                allocation_profile = allocation["profile"]["fabric_profile"]
                r["profile"]["python_allocation_pass"] = {
                    "ops": allocation["ops"],
                    "server_python_allocation_current_bytes": allocation_profile.get(
                        "server_python_allocation_current_bytes"),
                    "server_python_allocation_peak_bytes": allocation_profile.get(
                        "server_python_allocation_peak_bytes"),
                    "note": "separate traced pass; excluded from reported latency and throughput",
                }
                results.append(r)
                print(f"{n:>4} agents trial {trial + 1}/{args.repeats}: "
                      f"{r['ok']}/{r['ops']} ok, {r['ops_per_s']:.0f} ops/s, "
                      f"p50 {r['latency_ms']['all']['p50']:.1f} ms, "
                      f"p99 {r['latency_ms']['all']['p99']:.1f} ms, "
                      f"errors {r['errors'] or 'none'}", flush=True)
    if args.quick:
        return 0
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                            text=True, cwd=ROOT).stdout.strip()
    machine = f"{platform.system()} {platform.machine()}, {os.cpu_count()} CPUs, Python {platform.python_version()}"
    out = ROOT / "research" / "results"
    capacity = summarise_trials(results)
    (out / f"{args.out}.json").write_text(json.dumps(
        {"schema": "memory-fabric-http-capacity/1", "commit": commit,
         "machine": machine, "configuration": {"agents": list(counts),
         "ops_per_agent": args.ops_per_agent, "warmup_ops": args.warmup_ops,
         "repeats": args.repeats}, "results": results, "capacity_curve": capacity},
        indent=2) + "\n",
        encoding="utf-8")
    (out / f"{args.out}.md").write_text(
        to_markdown(results, commit, machine, args.out, capacity), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
