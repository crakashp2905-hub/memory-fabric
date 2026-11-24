"""SQLite and (optional) PostgreSQL on identical transaction scenarios (W17-07).

    python -m benchmarks.outcome_storage_bench --threads 4 --per-thread 50
    MEMORY_FABRIC_TEST_PG=postgresql://... python -m benchmarks.outcome_storage_bench

Every backend gets the same scenario: T threads, each with its own handle on the
same event log, append N events. The report gives throughput, the retries the
writers needed, and consistency (unique, gapless sequence numbers and an
integrity chain that verifies). PostgreSQL runs only when a DSN is provided and
``psycopg`` is installed; otherwise its row says ``NOT_RUN``. No new backend is
required, and numbers are for this host only.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence

SCHEMA_ID = "memory-fabric.storage-transaction-bench.v1"


def _event(thread: int, index: int) -> Any:
    from memory_fabric.events import Event

    return Event(type="memory_created", ts=int(time.time() * 1000),
                 payload={"thread": thread, "n": index}, agent_id=f"w{thread}", episode_id=None,
                 event_id=uuid.uuid4().hex, schema_version="0.9.0")


def scenario(opener: Callable[[], Any], threads: int, per_thread: int) -> dict[str, Any]:
    retries = [0] * threads
    errors: list[str] = []

    def writer(index: int) -> None:
        log = opener()
        try:
            for n in range(per_thread):
                for attempt in range(20):
                    try:
                        log.append(_event(index, n))
                        break
                    except Exception as exc:  # noqa: BLE001 - counted as a retry
                        retries[index] += 1
                        if attempt == 19:
                            errors.append(f"{type(exc).__name__}: {exc}"[:200])
                        time.sleep(0.005 * (attempt + 1))
        finally:
            close = getattr(log, "close", None)
            if callable(close):
                close()

    started = time.perf_counter()
    workers = [threading.Thread(target=writer, args=(i,)) for i in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    seconds = time.perf_counter() - started
    log = opener()
    try:
        events = list(log.read())
        seqs = [e.seq for e in events if getattr(e, "seq", None) is not None]
        chain = getattr(log, "chain", None)
        verified = bool(chain.verify(log.read()).ok) if chain is not None else None
    finally:
        close = getattr(log, "close", None)
        if callable(close):
            close()
    expected = threads * per_thread
    return {"status": "RUN", "events": len(events), "expected": expected,
            "throughput_per_s": round(len(events) / seconds, 1) if seconds else None,
            "seconds": round(seconds, 4), "retries": sum(retries), "errors": errors[:5],
            "sequences_unique": len(seqs) == len(set(seqs)),
            "sequences_gapless": bool(seqs) and sorted(seqs) == list(range(min(seqs), min(seqs) + len(seqs))),
            "chain_verifies": verified, "consistent": len(events) == expected and not errors}


def run(threads: int = 4, per_thread: int = 50) -> dict[str, Any]:
    from memory_fabric.eventlog import EventLog

    rows: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as directory:
        path = str(Path(directory) / "bench.db")
        first = EventLog(path)  # create the schema once before the writers race
        getattr(first, "close", lambda: None)()
        rows["sqlite"] = scenario(lambda: EventLog(path), threads, per_thread)
    dsn = os.environ.get("MEMORY_FABRIC_TEST_PG")
    try:
        import psycopg  # noqa: F401
        have_driver = True
    except ImportError:
        have_driver = False
    if dsn and have_driver:
        rows["postgres"] = scenario(lambda: EventLog(dsn), threads, per_thread)
    else:
        rows["postgres"] = {"status": "NOT_RUN",
                            "reason": "set MEMORY_FABRIC_TEST_PG and install psycopg"}
    return {"schema_id": SCHEMA_ID, "threads": threads, "per_thread": per_thread,
            "host": {"python": platform.python_version(), "platform": platform.platform(),
                     "cpus": os.cpu_count()},
            "backends": rows,
            "scope": "this host only; no cross-machine or production-throughput claim"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--per-thread", type=int, default=50)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    report = run(args.threads, args.per_thread)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    for name, row in report["backends"].items():
        print(name, {k: row.get(k) for k in ("status", "events", "throughput_per_s", "retries",
                                              "sequences_gapless", "chain_verifies", "consistent")})
    sqlite_ok = report["backends"]["sqlite"].get("consistent")
    return 0 if sqlite_ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
