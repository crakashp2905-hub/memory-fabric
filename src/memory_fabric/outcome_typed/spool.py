"""A bounded local job spool with leases, heartbeats, a retry budget and dead letters (W17-04).

Model and replay work is queued here so a worker crash cannot lose a job or run
it twice at once. Storage is SQLite, the store's own engine, with the same
busy-timeout convention as the event log.

* ``lease`` claims one ready job atomically; a job has at most one live lease.
* ``heartbeat`` extends a lease only for the worker that holds it.
* ``complete`` and ``fail`` are accepted only from the current, unexpired lease;
  a stale worker cannot settle a job another worker now owns.
* A failed job is retried until its attempt budget is spent, then dead-lettered
  and kept visible.
* ``depth`` and the ``max_depth`` cap give backpressure: a full spool refuses
  new work instead of growing without bound (W18-08).

A lease is a scheduling claim, not authority: nothing here can authorize an
effect. Protected effects still go through the action gate.
"""

from __future__ import annotations

__stability__ = "experimental"

import json
import sqlite3
import threading
from dataclasses import dataclass
from typing import Any, Mapping

READY, LEASED, DONE, DEAD = "ready", "leased", "done", "dead"


class SpoolFull(RuntimeError):
    """The spool is at its depth cap; the caller should abstain or retry later."""


@dataclass(frozen=True)
class Lease:
    job_id: str
    worker: str
    expires_ms: int
    attempt: int
    payload: Mapping[str, Any]
    authorizes_effects: bool = False


class JobSpool:
    def __init__(self, path: str = ":memory:", *, max_attempts: int = 3, max_depth: int = 1000,
                 busy_timeout_ms: int = 5000) -> None:
        if max_attempts < 1 or max_depth < 1:
            raise ValueError("attempt budget and depth cap must be positive")
        self.max_attempts, self.max_depth = max_attempts, max_depth
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, timeout=busy_timeout_ms / 1000, check_same_thread=False,
                                   isolation_level=None)
        self._db.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
        self._db.execute("""CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL,
            worker TEXT, expires_ms INTEGER, attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT)""")

    def close(self) -> None:
        self._db.close()

    def depth(self) -> int:
        row = self._db.execute("SELECT COUNT(*) FROM jobs WHERE state IN (?, ?)",
                               (READY, LEASED)).fetchone()
        return int(row[0])

    def enqueue(self, job_id: str, payload: Mapping[str, Any]) -> None:
        with self._lock:
            if self.depth() >= self.max_depth:
                raise SpoolFull(f"spool depth cap {self.max_depth} reached")
            self._db.execute("INSERT INTO jobs (job_id, payload, state) VALUES (?, ?, ?)",
                             (job_id, json.dumps(dict(payload), sort_keys=True), READY))

    def _expire(self, now_ms: int) -> None:
        self._db.execute("UPDATE jobs SET state = ?, worker = NULL, expires_ms = NULL "
                         "WHERE state = ? AND expires_ms <= ?", (READY, LEASED, now_ms))

    def lease(self, worker: str, now_ms: int, ttl_ms: int) -> Lease | None:
        if ttl_ms <= 0:
            raise ValueError("lease ttl must be positive")
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._expire(now_ms)
                row = self._db.execute("SELECT job_id, payload, attempts FROM jobs WHERE state = ? "
                                       "ORDER BY rowid LIMIT 1", (READY,)).fetchone()
                if row is None:
                    self._db.execute("COMMIT")
                    return None
                job_id, payload, attempts = row
                self._db.execute("UPDATE jobs SET state = ?, worker = ?, expires_ms = ?, "
                                 "attempts = attempts + 1 WHERE job_id = ?",
                                 (LEASED, worker, now_ms + ttl_ms, job_id))
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
        return Lease(job_id, worker, now_ms + ttl_ms, attempts + 1, json.loads(payload))

    def _owned(self, lease: Lease, now_ms: int) -> bool:
        row = self._db.execute("SELECT state, worker, expires_ms FROM jobs WHERE job_id = ?",
                               (lease.job_id,)).fetchone()
        return (row is not None and row[0] == LEASED and row[1] == lease.worker
                and row[2] is not None and row[2] > now_ms)

    def heartbeat(self, lease: Lease, now_ms: int, ttl_ms: int) -> Lease | None:
        with self._lock:
            if not self._owned(lease, now_ms):
                return None
            self._db.execute("UPDATE jobs SET expires_ms = ? WHERE job_id = ?",
                             (now_ms + ttl_ms, lease.job_id))
        return Lease(lease.job_id, lease.worker, now_ms + ttl_ms, lease.attempt, lease.payload)

    def complete(self, lease: Lease, now_ms: int) -> bool:
        with self._lock:
            if not self._owned(lease, now_ms):
                return False
            self._db.execute("UPDATE jobs SET state = ?, worker = NULL, expires_ms = NULL "
                             "WHERE job_id = ?", (DONE, lease.job_id))
            return True

    def fail(self, lease: Lease, now_ms: int, error: str) -> str | None:
        """Return the job's new state (``ready`` to retry, ``dead`` when spent), or None."""
        with self._lock:
            if not self._owned(lease, now_ms):
                return None
            attempts = self._db.execute("SELECT attempts FROM jobs WHERE job_id = ?",
                                        (lease.job_id,)).fetchone()[0]
            state = DEAD if attempts >= self.max_attempts else READY
            self._db.execute("UPDATE jobs SET state = ?, worker = NULL, expires_ms = NULL, "
                             "last_error = ? WHERE job_id = ?", (state, error[:200], lease.job_id))
            return state

    def state(self, job_id: str) -> dict[str, Any]:
        row = self._db.execute("SELECT state, worker, attempts, last_error FROM jobs "
                               "WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return {"state": row[0], "worker": row[1], "attempts": row[2], "last_error": row[3]}

    def dead_letters(self) -> list[str]:
        return [r[0] for r in self._db.execute("SELECT job_id FROM jobs WHERE state = ? "
                                               "ORDER BY rowid", (DEAD,))]
