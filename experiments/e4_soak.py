"""E4-10 deterministic restart, bounded-resource, backup and replay soak.

Run with ``python -m experiments.e4_soak --cycles 40``. Each cycle commits one
retraction in a child process and terminates it with ``os._exit``. At each
checkpoint the harness backs up and restores the origin, replays all missed
retractions to a persistent recipient, and settles the restored outbox by
idempotent redelivery. This is a local SQLite soak, not a production-duration
or physical multi-host qualification.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CRASH_EXIT = 71
MAX_DATABASE_BYTES = 128 * 1024 * 1024
MAX_TEMP_BYTES = 384 * 1024 * 1024
MAX_CHILD_RSS_BYTES = 512 * 1024 * 1024
MAX_PARENT_TRACED_BYTES = 256 * 1024 * 1024
MAX_RESTART_P99_DRIFT = 3.0
CHECKPOINT = 10


def _firewall():
    from memory_fabric.governance.firewall import (
        Firewall, rule_capabilities_must_be_granted, rule_must_be_active,
        rule_restricted_stays_private,
    )
    return Firewall(rules=(rule_restricted_stays_private, rule_must_be_active,
                           rule_capabilities_must_be_granted))


def _crash_commit(db_path: str, memory_id: str, recipient: str, cycle: int) -> int:
    from memory_fabric import MemoryFabric
    fabric = MemoryFabric(db_path, firewall=_firewall(), auto_activate=True)
    fabric.request_retraction(
        memory_id, reason=f"deterministic soak correction {cycle}",
        recipients=[recipient], actor="soak-operator", basis="contradicted",
    )
    sys.stdout.write("COMMITTED\n")
    sys.stdout.flush()
    os._exit(CRASH_EXIT)


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _disk_bytes(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def _nearest(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int((percentile * len(ordered) + 0.999999) - 1)))]


def _run_child(db: Path, memory_id: str, recipient: str, cycle: int, psutil: Any
               ) -> tuple[float, int, str]:
    command = [sys.executable, "-m", "experiments.e4_soak", "--worker",
               str(db), memory_id, recipient, str(cycle)]
    started = time.perf_counter()
    proc = subprocess.Popen(command, cwd=ROOT, env=_env(), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    child = psutil.Process(proc.pid)
    try:
        peak_rss = child.memory_info().rss
    except psutil.Error:
        peak_rss = 0
    while proc.poll() is None:
        try:
            peak_rss = max(peak_rss, child.memory_info().rss)
        except psutil.Error:
            pass
        time.sleep(0.01)
    output, _ = proc.communicate(timeout=5)
    elapsed = time.perf_counter() - started
    if proc.returncode != CRASH_EXIT or "COMMITTED" not in output:
        raise RuntimeError(f"cycle {cycle} did not hard-crash after commit: {proc.returncode}: {output}")
    return elapsed, peak_rss, output.strip()


def run(cycles: int = 40) -> dict[str, Any]:
    if cycles < CHECKPOINT or cycles % CHECKPOINT:
        raise ValueError(f"cycles must be a positive multiple of {CHECKPOINT}")
    try:
        import psutil
    except ImportError as exc:
        raise RuntimeError("E4-10 requires psutil to measure child process RSS") from exc

    from memory_fabric import LifecycleState, MemoryFabric
    from memory_fabric.dispatcher import Dispatcher, reconcile
    from memory_fabric.federation import offer
    from memory_fabric.protocol import PropagationState
    from memory_fabric.transport import InProcessTransport
    from memory_fabric.cli import main as cli_main

    tracemalloc.start()
    restart_seconds: list[float] = []
    child_peak_rss = 0
    max_db_bytes = 0
    max_temp_bytes = 0
    max_pending = 0
    restored_checkpoints = 0
    reconciliation_deliveries = 0
    with tempfile.TemporaryDirectory(prefix="mf-e4-10-") as tmp:
        root = Path(tmp)
        active_dir = root / "active-0"
        active_dir.mkdir()
        active_db = active_dir / "store.db"
        recipient_db = root / "recipient.db"
        origin = MemoryFabric(active_db, firewall=_firewall(), auto_activate=True,
                              recognise_copies=False)
        recipient = MemoryFabric(recipient_db, firewall=_firewall(), auto_activate=True,
                                 recognise_copies=False)
        memories: list[str] = []
        imported: list[str] = []
        for index in range(cycles):
            memory_id = origin.remember(
                "soak-writer", f"E4-10 seeded evidence item {index:04d}",
                scope="federated", auto_activate=True,
            )
            result = offer(origin, memory_id, recipient, recipient_agent="soak-reviewer")
            if not result.accepted or not result.imported_memory_id:
                raise RuntimeError(f"could not seed imported memory {index}: {result}")
            recipient.validate(result.imported_memory_id, actor="soak-reviewer")
            memories.append(memory_id)
            imported.append(result.imported_memory_id)

        checkpoints: list[dict[str, Any]] = []
        for batch_start in range(0, cycles, CHECKPOINT):
            batch_end = batch_start + CHECKPOINT
            for cycle in range(batch_start, batch_end):
                elapsed, rss, _ = _run_child(
                    active_db, memories[cycle], recipient.store_id, cycle, psutil
                )
                restart_seconds.append(elapsed)
                child_peak_rss = max(child_peak_rss, rss)

            origin.close()
            origin = MemoryFabric(active_db, firewall=_firewall(), auto_activate=True,
                                  recognise_copies=False)
            if not origin.log.chain.verify(origin.log.read()).ok:
                raise RuntimeError(f"integrity chain failed at cycle {batch_end}")
            pending = origin.outbox.pending()
            expected = memories[batch_start:batch_end]
            if len(pending) != len(expected):
                raise RuntimeError(f"pending queue mismatch: {len(pending)} != {len(expected)}")
            if any(row.state not in (PropagationState.QUEUED, PropagationState.RETRYING)
                   for row in pending):
                raise RuntimeError("unexpected outbox state before checkpoint recovery")
            max_pending = max(max_pending, len(pending))

            backup = root / f"checkpoint-{batch_end}.db"
            if cli_main(["--db", str(active_db), "backup", str(backup)]) != 0:
                raise RuntimeError(f"backup failed at cycle {batch_end}")
            restore_dir = root / f"restore-{batch_end}"
            if cli_main(["restore", str(backup), str(restore_dir)]) != 0:
                raise RuntimeError(f"restore failed at cycle {batch_end}")
            restored_db = restore_dir / "store.db"
            origin.close()
            origin = MemoryFabric(restored_db, firewall=_firewall(), auto_activate=True,
                                  recognise_copies=False)
            restored_checkpoints += 1
            if origin.store_id != json.loads(backup.with_name(backup.name + ".manifest.json").read_text())["store_id"]:
                raise RuntimeError("store identity changed on restore")
            restored_pending = origin.outbox.pending()
            if len(restored_pending) != len(expected):
                raise RuntimeError("restore lost durable outbox rows")
            missed = origin.retractions_since(recipient.outbox.missed_since(origin.store_id))
            if {row.retraction.origin_memory_id for row in restored_pending} != {
                r.origin_memory_id for r in missed
            }:
                raise RuntimeError("restored outbox and recipient reconciliation cursor have a gap")
            acks = reconcile(recipient, missed, origin.store_id)
            if len(acks) != len(expected) or any(a.state is not PropagationState.ENFORCED for a in acks):
                raise RuntimeError("recipient replay did not enforce the restored correction batch")
            reconciliation_deliveries += len(acks)
            report = Dispatcher(origin, InProcessTransport({recipient.store_id: recipient})).run_once()
            if report.enforced != len(expected) or origin.outbox.pending():
                raise RuntimeError("replayed deliveries did not settle the restored outbox")
            applied_ids = {event.payload.get("local_memory_id") for event in recipient.log.read()
                           if event.type == "RetractionApplied"}
            if not set(imported[:batch_end]) <= applied_ids:
                raise RuntimeError("recipient lacks one or more applied correction events")
            if any(recipient.get(mid).lifecycle_state is not LifecycleState.QUARANTINED
                   for mid in imported[:batch_end]):
                raise RuntimeError("a corrected imported memory remained exposed after replay")

            db_bytes = max(active_db.stat().st_size, restored_db.stat().st_size,
                           recipient_db.stat().st_size)
            max_db_bytes = max(max_db_bytes, db_bytes)
            temp_bytes = _disk_bytes(root)
            max_temp_bytes = max(max_temp_bytes, temp_bytes)
            if db_bytes > MAX_DATABASE_BYTES:
                raise RuntimeError(f"database ceiling exceeded: {db_bytes}")
            if temp_bytes > MAX_TEMP_BYTES:
                raise RuntimeError(f"temporary-soak disk ceiling exceeded: {temp_bytes}")
            checkpoints.append({"through_cycle": batch_end, "pending_before_restore": len(pending),
                                "pending_after_restore": len(restored_pending),
                                "replayed": len(acks), "dispatch_enforced": report.enforced,
                                "restored_chain_valid": True, "database_bytes": db_bytes})
            # Continue on the just-restored store; discard previous snapshots and
            # the old active copy so measured disk use is bounded.
            if active_db != restored_db:
                old_dir = active_db.parent
                if old_dir != root and old_dir.exists() and old_dir != restore_dir:
                    shutil.rmtree(old_dir)
            active_db = restored_db
            for stale in root.glob("checkpoint-*.db*"):
                stale.unlink(missing_ok=True)
            for old_restore in root.glob("restore-*"):
                if old_restore != restore_dir:
                    shutil.rmtree(old_restore, ignore_errors=True)

        origin.close()
        recipient.close()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        quarter = max(2, len(restart_seconds) // 4)
        first_p99 = _nearest(restart_seconds[:quarter], 0.99)
        last_p99 = _nearest(restart_seconds[-quarter:], 0.99)
        p99 = _nearest(restart_seconds, 0.99)
        drift = last_p99 / first_p99 if first_p99 else 1.0
        result = {
            "schema": "memory-fabric-e4-10-deterministic-soak/1",
            "machine": {"platform": platform.platform(), "python": platform.python_version(),
                        "logical_cpus": os.cpu_count(), "psutil": psutil.__version__},
            "configuration": {"cycles": cycles, "hard_crash_after_commit_each_cycle": True,
                              "checkpoint_interval": CHECKPOINT,
                              "database_ceiling_bytes": MAX_DATABASE_BYTES,
                              "temporary_disk_ceiling_bytes": MAX_TEMP_BYTES,
                              "child_rss_ceiling_bytes": MAX_CHILD_RSS_BYTES,
                              "parent_traced_memory_ceiling_bytes": MAX_PARENT_TRACED_BYTES,
                              "pending_outbox_rows_ceiling": CHECKPOINT,
                              "p99_drift_ratio_ceiling": MAX_RESTART_P99_DRIFT},
            "measurements": {"restart_latency_seconds": restart_seconds,
                             "restart_latency_p50_seconds": statistics.median(restart_seconds),
                             "restart_latency_p99_seconds": p99,
                             "first_quartile_p99_seconds": first_p99,
                             "last_quartile_p99_seconds": last_p99,
                             "p99_drift_ratio": drift,
                             "peak_child_rss_bytes": child_peak_rss,
                             "python_peak_traced_bytes": peak,
                             "max_database_file_bytes": max_db_bytes,
                             "max_temporary_disk_bytes": max_temp_bytes,
                             "max_pending_rows": max_pending,
                             "restored_checkpoints": restored_checkpoints,
                             "reconciliation_deliveries": reconciliation_deliveries,
                             "checkpoints": checkpoints},
            "passed": child_peak_rss <= MAX_CHILD_RSS_BYTES and peak <= MAX_PARENT_TRACED_BYTES
                      and max_db_bytes <= MAX_DATABASE_BYTES and max_temp_bytes <= MAX_TEMP_BYTES
                      and max_pending <= CHECKPOINT
                      and drift <= MAX_RESTART_P99_DRIFT
                      and restored_checkpoints == cycles // CHECKPOINT
                      and reconciliation_deliveries == cycles,
            "limitations": ["Local SQLite and localhost process restarts only; not a continuous 24-hour production soak, physical host failure, or PostgreSQL validation."],
        }
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=40)
    parser.add_argument("--worker", nargs=4, metavar=("DB", "MEMORY", "RECIPIENT", "CYCLE"))
    args = parser.parse_args()
    if args.worker:
        return _crash_commit(args.worker[0], args.worker[1], args.worker[2],
                             int(args.worker[3]))
    result = run(args.cycles)
    result["commit"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                      check=True, capture_output=True, text=True).stdout.strip()
    output = ROOT / "research" / "results" / "e4-10-deterministic-soak.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
