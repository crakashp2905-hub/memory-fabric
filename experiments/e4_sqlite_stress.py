"""Measure SQLite WAL and busy-timeout behavior with 50 local writer processes.

Each process owns an independent EventLog connection and appends transaction
batches of 1, 5 and 10 events. The result checks exact event identity, sequence
continuity and the integrity chain, then records SQLite's WAL checkpoint state.
It also holds a write lock deliberately to verify that a configured busy timeout
is a bounded wait rather than an unbounded retry.

    python -m experiments.e4_sqlite_stress --out research/results/e4-05-sqlite-stress
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import platform
import sqlite3
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from memory_fabric.eventlog import EventLog
from memory_fabric.events import Event


BATCH_SIZES = (1, 5, 10)


def _worker(path: str, worker_id: int, timeout_ms: int, cycles: int,
            start_stagger_ms: int, barrier: Any, output: Any) -> None:
    log: EventLog | None = None
    phase = "open"
    try:
        if start_stagger_ms:
            time.sleep(worker_id * start_stagger_ms / 1000)
        log = EventLog(path, busy_timeout_ms=timeout_ms)
        settings = {
            "journal_mode": str(log._conn.execute("PRAGMA journal_mode").fetchone()[0]),
            "busy_timeout_ms": int(log._conn.execute("PRAGMA busy_timeout").fetchone()[0]),
            "wal_autocheckpoint_pages": int(
                log._conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0]
            ),
        }
        phase = "wait_for_start_barrier"
        barrier.wait(timeout=120)
        phase = "append"
        durations_ms: list[float] = []
        attempted_keys: list[str] = []
        committed_keys: list[str] = []
        failed_batches = 0
        counter = 0
        for cycle in range(cycles):
            for batch_size in BATCH_SIZES:
                events = []
                for _ in range(batch_size):
                    key = f"{worker_id}:{cycle}:{counter}"
                    attempted_keys.append(key)
                    events.append(Event(
                        type="QualificationWrite",
                        ts=1_800_000_000_000 + worker_id * 100_000 + counter,
                        agent_id=f"writer-{worker_id:02d}",
                        payload={"writer": worker_id, "key": key},
                    ))
                    counter += 1
                started = time.perf_counter()
                try:
                    log.append_many(events)
                    committed_keys.extend(str(event.payload["key"]) for event in events)
                except Exception:
                    failed_batches += 1
                    raise
                finally:
                    durations_ms.append((time.perf_counter() - started) * 1000)
        output.put({"worker": worker_id, "phase": phase, "settings": settings,
                    "attempted_keys": attempted_keys, "committed_keys": committed_keys,
                    "failed_batches": failed_batches, "durations_ms": durations_ms,
                    "error": None})
    except BaseException as exc:  # report worker failures instead of losing them
        try:
            barrier.abort()
        except Exception:
            pass
        output.put({"worker": worker_id, "phase": phase,
                    "attempted_keys": locals().get("attempted_keys", []),
                    "committed_keys": locals().get("committed_keys", []),
                    "failed_batches": locals().get("failed_batches", 0),
                    "durations_ms": locals().get("durations_ms", []),
                    "error": f"{type(exc).__name__}: {exc}"})
    finally:
        if log is not None:
            log.close()


def _checkpoint_probe(path: Path, timeout_ms: int = 250) -> dict[str, Any]:
    log = EventLog(path, busy_timeout_ms=timeout_ms)
    blocker = sqlite3.connect(path, timeout=1, isolation_level=None)
    try:
        blocker.execute("BEGIN IMMEDIATE")
        started = time.perf_counter()
        error = None
        try:
            log.append(Event(type="TimeoutProbe", ts=1, payload={"probe": True}))
        except sqlite3.OperationalError as exc:
            error = type(exc).__name__
        elapsed_ms = (time.perf_counter() - started) * 1000
        blocker.execute("ROLLBACK")
        appended = log.append(Event(type="AfterTimeoutProbe", ts=2,
                                    payload={"probe": "released"}))
        return {
            "configured_busy_timeout_ms": timeout_ms,
            "blocked_append_error": error,
            "blocked_append_elapsed_ms": elapsed_ms,
            "blocked_event_was_not_committed": log.head_seq == appended.seq == 1,
            "write_succeeds_after_release": appended.seq == 1,
        }
    finally:
        try:
            if blocker.in_transaction:
                blocker.execute("ROLLBACK")
        finally:
            blocker.close()
            log.close()


def run_trial(processes: int, cycles: int, timeout_ms: int, start_stagger_ms: int,
              start_method: str = "spawn") -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "stress.db"
        seed = EventLog(path, busy_timeout_ms=timeout_ms)
        initial_settings = {
            "journal_mode": str(seed._conn.execute("PRAGMA journal_mode").fetchone()[0]),
            "busy_timeout_ms": int(seed._conn.execute("PRAGMA busy_timeout").fetchone()[0]),
            "wal_autocheckpoint_pages": int(
                seed._conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0]
            ),
        }
        seed.close()

        context = mp.get_context(start_method)
        barrier = context.Barrier(processes + 1, timeout=120)
        output = context.Queue()
        children = [context.Process(target=_worker, args=(str(path), i, timeout_ms,
                                                           cycles, start_stagger_ms,
                                                           barrier, output))
                    for i in range(processes)]
        for child in children:
            child.start()
        start_wait = time.perf_counter()
        try:
            barrier.wait(timeout=120)
            start_error = None
        except Exception as exc:
            start_error = f"{type(exc).__name__}: {exc}"
        results = []
        for _ in children:
            try:
                results.append(output.get(timeout=300))
            except Exception as exc:
                results.append({"error": f"worker result unavailable: {type(exc).__name__}"})
        for child in children:
            child.join(timeout=30)
            if child.is_alive():
                child.terminate()
                child.join(timeout=5)
        wall_s = time.perf_counter() - start_wait

        reopened = EventLog(path, busy_timeout_ms=timeout_ms)
        try:
            rows = list(reopened.read())
            sequences = [int(row.seq or 0) for row in rows]
            observed = [str(row.payload.get("key")) for row in rows]
            attempted = [key for result in results for key in result.get("attempted_keys", [])]
            committed = [key for result in results for key in result.get("committed_keys", [])]
            duplicate_keys = len(observed) != len(set(observed))
            missing_keys = sorted(set(committed) - set(observed))
            unexpected_keys = sorted(set(observed) - set(committed))
            verification = reopened.chain.verify(iter(rows))
            wal_before = reopened._conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            wal_checkpoint = {
                "busy": int(wal_before[0]), "log_frames": int(wal_before[1]),
                "checkpointed_frames": int(wal_before[2]),
            }
            truncate = reopened._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            wal_truncate = {
                "busy": int(truncate[0]), "log_frames": int(truncate[1]),
                "checkpointed_frames": int(truncate[2]),
            }
            max_batch_ms = max(
                (duration for result in results
                 for duration in result.get("durations_ms", [])), default=0.0
            )
            all_durations = [duration for result in results
                             for duration in result.get("durations_ms", [])]
            expected_events = processes * cycles * sum(BATCH_SIZES)
            failed_keys = sorted(set(attempted) - set(committed))
            errors = [result["error"] for result in results if result.get("error")]
            exit_codes = [child.exitcode for child in children]
        finally:
            reopened.close()

        probe = _checkpoint_probe(Path(directory) / "timeout-probe.db")
        return {
            "processes": processes, "cycles_per_process": cycles,
            "batch_sizes_events_per_transaction": list(BATCH_SIZES),
            "busy_timeout_ms": timeout_ms, "wall_s": wall_s,
            "initial_sqlite_settings": initial_settings,
            "successful_transactions": len(all_durations),
            "events_expected": expected_events, "events_observed": len(rows),
            "events_attempted": len(attempted), "events_committed_by_workers": len(committed),
            "explicitly_failed_event_keys": len(failed_keys),
            "transaction_latency_ms": {
                "mean": statistics.fmean(all_durations) if all_durations else 0.0,
                "p95": sorted(all_durations)[min(len(all_durations)-1,
                                                  int(.95 * len(all_durations)))]
                      if all_durations else 0.0,
                "max": max_batch_ms,
            },
            "errors": errors, "start_error": start_error,
            "worker_errors": [result for result in results if result.get("error")],
            "process_exit_codes": exit_codes,
            "duplicate_events": duplicate_keys, "missing_event_keys": missing_keys,
            "unexpected_event_keys": unexpected_keys,
            "sequence_contiguous": sequences == list(range(1, len(sequences) + 1)),
            "integrity_chain_ok": bool(verification.ok),
            "integrity_events_verified": verification.checked,
            "wal_checkpoint_passive": wal_checkpoint,
            "wal_checkpoint_truncate": wal_truncate,
            "busy_timeout_control": probe,
            "passed": (not errors and start_error is None
                       and all(code == 0 for code in exit_codes)
                       and len(attempted) == expected_events
                       and len(committed) == expected_events
                       and len(rows) == expected_events and not duplicate_keys
                       and not missing_keys and not unexpected_keys
                       and sequences == list(range(1, expected_events + 1))
                       and verification.ok and initial_settings["journal_mode"] == "wal"
                       and initial_settings["busy_timeout_ms"] == timeout_ms
                       and probe["blocked_append_error"] == "OperationalError"
                       and probe["blocked_append_elapsed_ms"] >= (
                           probe["configured_busy_timeout_ms"] * 0.8
                       )
                       and probe["blocked_append_elapsed_ms"] < 3_000
                       and probe["blocked_event_was_not_committed"]
                       and probe["write_succeeds_after_release"]
                       and wal_checkpoint["busy"] == 0
                       and wal_truncate["busy"] == 0),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--processes", type=int, default=50)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--busy-timeout-ms", type=int, default=5_000)
    parser.add_argument("--start-stagger-ms", type=int, default=25,
                        help="space out connection/schema open; writes still start together")
    parser.add_argument("--out", default="e4-05-sqlite-stress")
    args = parser.parse_args(argv)
    if min(args.processes, args.cycles, args.repeats, args.busy_timeout_ms) < 1 \
            or args.start_stagger_ms < 0:
        parser.error("counts and timeout must be positive; start-stagger-ms must be non-negative")

    results = []
    for trial in range(args.repeats):
        result = run_trial(args.processes, args.cycles, args.busy_timeout_ms,
                           args.start_stagger_ms)
        result["trial"] = trial
        results.append(result)
        print(f"trial {trial + 1}/{args.repeats}: {result['events_observed']}/"
              f"{result['events_expected']} events, {result['successful_transactions']} "
              f"transactions, {result['wall_s']:.2f}s, passed={result['passed']}",
              flush=True)

    import subprocess
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                            text=True, check=True).stdout.strip()
    machine = (f"{platform.system()} {platform.machine()}, {os.cpu_count()} CPUs, "
               f"Python {platform.python_version()}, SQLite {sqlite3.sqlite_version}")
    data = {
        "schema": "memory-fabric-e4-05-sqlite-stress/1", "commit": commit,
        "machine": machine,
        "configuration": {"processes": args.processes, "cycles": args.cycles,
                          "repeats": args.repeats, "busy_timeout_ms": args.busy_timeout_ms,
                          "start_stagger_ms": args.start_stagger_ms,
                          "transaction_event_sizes": list(BATCH_SIZES),
                          "start_method": "spawn", "sqlite_synchronous": "FULL default"},
        "results": results, "passed": all(row["passed"] for row in results),
        "limitations": ["One local Windows host and local SQLite file; not a multi-host test.",
                        "SQLite WAL auto-checkpoint behavior is recorded at the tested workload size."]
    }
    output = Path("research/results") / args.out
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".json").write_text(json.dumps(data, indent=2) + "\n",
                                            encoding="utf-8")
    lines = [f"# E4-05 SQLite stress — {machine}", "",
             f"Commit `{commit}`; {args.processes} concurrent processes, "
             f"{args.repeats} trials, transaction event sizes {BATCH_SIZES}; "
             f"SQLite busy timeout {args.busy_timeout_ms} ms; FULL synchronous mode; "
             f"connections staggered {args.start_stagger_ms} ms each before synchronized writes.", "",
             "| trial | writes expected/observed | transactions | wall seconds | WAL mode | busy timeout | auto-checkpoint pages | chain verified | result |",
             "|---:|---:|---:|---:|---|---:|---:|---|---|"]
    for row in results:
        settings = row["initial_sqlite_settings"]
        lines.append(f"| {row['trial']} | {row['events_expected']}/{row['events_observed']} "
                     f"| {row['successful_transactions']} | {row['wall_s']:.2f} "
                     f"| {settings['journal_mode']} | {settings['busy_timeout_ms']} "
                     f"| {settings['wal_autocheckpoint_pages']} "
                     f"| {row['integrity_chain_ok']} | {'PASS' if row['passed'] else 'FAIL'} |")
    lines += ["", "The experiment requires complete event identity, contiguous authoritative "
              "sequence numbers, a valid integrity chain, zero worker errors, successful "
              "checkpoint calls, and a bounded lock-timeout control followed by a successful "
              "write after lock release. Full transaction latency, checkpoint results and "
              "worker exit codes are in the JSON artifact."]
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if data["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
