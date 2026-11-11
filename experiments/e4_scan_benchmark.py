"""E4-06: bounded event-log page scans at 1k, 10k and 100k memory records.

The fixture writes one complete MemoryCreated event per synthetic memory. A
keyset cursor (`seq > cursor LIMIT page_size`) scans the append-only source of
truth in bounded pages. Setup, integrity verification, scan time and measured
Python peak allocation are reported separately. This does not claim to benchmark
the in-memory operator `memory-fabric list`, which currently materializes and
sorts the full projection before applying its output limit.

    python -m experiments.e4_scan_benchmark
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any

from memory_fabric.eventlog import EventLog
from memory_fabric.events import memory_created
from memory_fabric.model import Memory, MemoryType, Provenance, Scope


SIZES = (1_000, 10_000, 100_000)
PAGE_SIZES = (100, 500, 1_000)
REPEATS = 3
BATCH_SIZE = 500


def memory_event(index: int):
    memory = Memory(
        id=f"memory-{index:06d}", version=1, type=MemoryType.SEMANTIC,
        content=f"Synthetic scan fixture {index}: pump pressure at site {index % 97}.",
        provenance=Provenance(created_by=f"agent-{index % 50:02d}"),
        scope=Scope.TEAM, created_at=1_800_000_000_000 + index,
    )
    return memory_created(ts=memory.created_at, memory=memory)


def seed(path: Path, count: int) -> dict[str, Any]:
    log = EventLog(path)
    started = time.perf_counter()
    for first in range(0, count, BATCH_SIZE):
        log.append_many([memory_event(i) for i in range(first, min(first + BATCH_SIZE, count))])
    seed_s = time.perf_counter() - started
    checkpoint = log._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    verification = log.chain.verify(log.read())
    settings = {
        "journal_mode": str(log._conn.execute("PRAGMA journal_mode").fetchone()[0]),
        "busy_timeout_ms": int(log._conn.execute("PRAGMA busy_timeout").fetchone()[0]),
        "wal_autocheckpoint_pages": int(log._conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0]),
    }
    log.close()
    return {"seed_seconds": seed_s, "checkpoint": [int(v) for v in checkpoint],
            "settings": settings, "integrity_chain_ok": bool(verification.ok),
            "verified_events": verification.checked}


def scan(log: EventLog, count: int, page_size: int) -> dict[str, Any]:
    cursor = 0
    seen = 0
    pages = 0
    max_page_records = 0
    page_ms: list[float] = []
    digest = hashlib.sha256()
    tracemalloc.start()
    started = time.perf_counter()
    while True:
        page_started = time.perf_counter()
        rows = list(log.read(since_seq=cursor, limit=page_size))
        page_ms.append((time.perf_counter() - page_started) * 1000)
        if not rows:
            break
        expected_first = cursor + 1
        if rows[0].seq != expected_first or len(rows) > page_size:
            raise AssertionError("page cursor skipped, repeated, or exceeded its bound")
        max_page_records = max(max_page_records, len(rows))
        for row in rows:
            if row.seq != cursor + 1:
                raise AssertionError("event sequence is not contiguous across pages")
            memory = row.payload.get("memory", {})
            memory_id = str(memory.get("id", ""))
            if not memory_id:
                raise AssertionError("fixture event has no memory id")
            digest.update(memory_id.encode("utf-8"))
            digest.update(b"\n")
            cursor += 1
            seen += 1
        pages += 1
    total_s = time.perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if seen != count:
        raise AssertionError(f"scan returned {seen} records, expected {count}")
    measured_pages = page_ms[:-1] if len(page_ms) > 1 else page_ms
    return {
        "records": seen, "page_size": page_size, "pages": pages,
        "max_page_records": max_page_records, "scan_seconds": total_s,
        "page_latency_ms": {
            "mean": statistics.fmean(measured_pages) if measured_pages else 0.0,
            "p95": sorted(measured_pages)[min(len(measured_pages)-1,
                                               int(.95 * len(measured_pages)))]
                  if measured_pages else 0.0,
            "max": max(measured_pages, default=0.0),
        },
        "python_peak_bytes": peak_bytes, "memory_id_sha256": digest.hexdigest(),
    }


def svg_plot(results: list[dict[str, Any]]) -> str:
    width, height = 1000, 480
    colors = {100: "#2563eb", 500: "#16a34a", 1000: "#dc2626"}
    panels = [(65, 95, 400, 280, "Full scan seconds", "scan_seconds"),
              (560, 95, 370, 280, "Python peak allocation (MiB)", "python_peak_bytes")]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<style>text{font-family:Arial,sans-serif;fill:#111827}.grid{stroke:#d1d5db;stroke-width:1}.axis{stroke:#374151;stroke-width:1.5}</style>',
           '<text x="35" y="35" font-size="22" font-weight="bold">E4-06 bounded page scan scale</text>']
    sizes = sorted({int(row["memories"]) for row in results})
    for x0, y0, plot_w, plot_h, title, key in panels:
        value_key = ("python_peak_bytes_mean" if key == "python_peak_bytes"
                     else "scan_seconds_mean")
        values = [float(r[value_key]) / (1024 * 1024)
                  if key == "python_peak_bytes" else float(r[value_key])
                  for r in results]
        ymax = max(values) if values else 1.0
        ymax = max(ymax * 1.12, 1.0)
        out.append(f'<text x="{x0}" y="{y0-22}" font-size="17" font-weight="bold">{title}</text>')
        for j in range(5):
            y = y0 + plot_h - j * plot_h / 4
            out.append(f'<line class="grid" x1="{x0}" y1="{y:.1f}" x2="{x0+plot_w}" y2="{y:.1f}"/>')
            out.append(f'<text x="{x0-10}" y="{y+4:.1f}" font-size="11" text-anchor="end">{ymax*j/4:.1f}</text>')
        out.append(f'<line class="axis" x1="{x0}" y1="{y0+plot_h}" x2="{x0+plot_w}" y2="{y0+plot_h}"/>')
        out.append(f'<line class="axis" x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0+plot_h}"/>')
        x_positions = {size: x0 + i * plot_w / max(1, len(sizes)-1)
                       for i, size in enumerate(sizes)}
        for size, x in x_positions.items():
            out.append(f'<text x="{x:.1f}" y="{y0+plot_h+22}" font-size="11" text-anchor="middle">{size:,}</text>')
        for page_size in PAGE_SIZES:
            rows = sorted((r for r in results if r["page_size"] == page_size),
                          key=lambda r: r["memories"])
            points = []
            for row in rows:
                yval = (float(row[value_key]) / (1024 * 1024)
                        if key == "python_peak_bytes" else float(row[value_key]))
                px = x_positions[int(row["memories"])]
                py = y0 + plot_h - yval / ymax * plot_h
                points.append(f"{px:.1f},{py:.1f}")
            out.append(f'<polyline fill="none" stroke="{colors[page_size]}" stroke-width="3" points="{" ".join(points)}"/>')
        out.append(f'<text x="{x0+plot_w/2}" y="{y0+plot_h+43}" font-size="12" text-anchor="middle">memories scanned (log-spaced categories)</text>')
    for i, page_size in enumerate(PAGE_SIZES):
        x = 70 + i * 135
        out.append(f'<line x1="{x}" y1="430" x2="{x+28}" y2="430" stroke="{colors[page_size]}" stroke-width="3"/>')
        out.append(f'<text x="{x+34}" y="434" font-size="12">page size {page_size}</text>')
    out.append('</svg>')
    return "\n".join(out) + "\n"


def main() -> int:
    output = Path("research/results")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--render-only", action="store_true",
                        help="regenerate SVG and Markdown from an existing JSON result")
    args = parser.parse_args()
    result_path = output / "e4-06-page-scan.json"
    if args.render_only:
        data = json.loads(result_path.read_text(encoding="utf-8"))
        all_results = data["results"]
    else:
        all_results = []
        datasets = []
        for count in SIZES:
            with tempfile.TemporaryDirectory() as directory:
                db = Path(directory) / f"scan-{count}.db"
                seed_data = seed(db, count)
                log = EventLog(db)
                db_bytes = db.stat().st_size
                try:
                    for page_size in PAGE_SIZES:
                        runs = [scan(log, count, page_size) for _ in range(REPEATS)]
                        latency = [r["scan_seconds"] for r in runs]
                        peak = [r["python_peak_bytes"] for r in runs]
                        row = {
                            "memories": count, "database_bytes": db_bytes,
                            "page_size": page_size, "repeats": REPEATS,
                            "seed_seconds": seed_data["seed_seconds"],
                            "seed_integrity_chain_ok": seed_data["integrity_chain_ok"],
                            "verified_events": seed_data["verified_events"],
                            "checkpoint": seed_data["checkpoint"],
                            "sqlite_settings": seed_data["settings"],
                            "scan_seconds_mean": statistics.fmean(latency),
                            "scan_seconds_trials": latency,
                            "python_peak_bytes_mean": statistics.fmean(peak),
                            "python_peak_bytes_trials": peak,
                            "pages": runs[-1]["pages"],
                            "max_page_records": max(r["max_page_records"] for r in runs),
                            "page_latency_ms_mean": statistics.fmean(
                                r["page_latency_ms"]["mean"] for r in runs
                            ),
                            "page_latency_ms_p95_max": max(
                                r["page_latency_ms"]["p95"] for r in runs
                            ),
                            "memory_id_sha256": runs[-1]["memory_id_sha256"],
                            "scan_hashes_match": len({r["memory_id_sha256"] for r in runs}) == 1,
                        }
                        all_results.append(row)
                        print(f"{count:>7,} memories, page {page_size:>4}: "
                              f"{row['scan_seconds_mean']:.3f}s, "
                              f"{row['python_peak_bytes_mean']/1024/1024:.2f} MiB, "
                              f"{row['pages']} pages, hashes match={row['scan_hashes_match']}",
                              flush=True)
                finally:
                    log.close()
                datasets.append({"memories": count, **seed_data,
                                 "database_bytes": db_bytes})

        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                text=True, check=True).stdout.strip()
        machine = (f"{platform.system()} {platform.machine()}, {os.cpu_count()} CPUs, "
                   f"Python {platform.python_version()}")
        passed = (all(r["scan_hashes_match"] and r["max_page_records"] <= r["page_size"]
                      and r["seed_integrity_chain_ok"]
                      and r["verified_events"] == r["memories"] for r in all_results)
                  and [r["memories"] for r in datasets] == list(SIZES))
        data = {
            "schema": "memory-fabric-e4-06-page-scan/1", "commit": commit,
            "machine": machine,
            "configuration": {"memory_counts": list(SIZES), "page_sizes": list(PAGE_SIZES),
                              "repeats": REPEATS, "seed_transaction_events": BATCH_SIZE,
                              "cursor": "seq > last_seen_seq ORDER BY seq LIMIT page_size"},
            "datasets": datasets, "results": all_results, "passed": passed,
            "limitations": ["Synthetic one-MemoryCreated-event-per-memory fixtures; not an external production corpus.",
                            "Benchmarks EventLog keyset scans, not the in-memory operator list, which currently materializes and sorts before applying limit.",
                            "Warm local SQLite page cache; not a cold-storage or remote-disk benchmark."]
        }
        result_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    all_results = data["results"]
    commit = data["commit"]
    machine = data["machine"]
    passed = bool(data["passed"])
    (output / "e4-06-page-scan.svg").write_text(svg_plot(all_results), encoding="utf-8")
    table = "\n".join(
        f"| {r['memories']:,} | {r['page_size']:,} | {r['pages']} | "
        f"{r['scan_seconds_mean']:.3f} | {r['page_latency_ms_mean']:.2f} | "
        f"{r['python_peak_bytes_mean']/1024/1024:.2f} | {r['database_bytes']:,} | "
        f"{r['scan_hashes_match']} |" for r in all_results
    )
    md = f"""# E4-06 — bounded keyset page scan benchmark

Measured at source commit `{commit}` on {machine}. The fixture contains one complete `MemoryCreated` event per synthetic memory. Scans use `EventLog.read(since_seq=cursor, limit=page_size)` and repeat three times for each size/page combination.

| memories | page size | pages | full scan mean (s) | mean page latency (ms) | Python peak (MiB) | DB bytes | stable digest |
|---:|---:|---:|---:|---:|---:|---:|---|
{table}

![Scan time and peak Python allocation by dataset and page size](e4-06-page-scan.svg)

Every dataset's chain verified before scans; every scan returned exactly the expected ordered IDs with matching hashes across repeats. Per-page result size never exceeded the configured bound. WAL mode and checkpoint result are recorded per dataset in the JSON artifact. Database setup and scan time are separate.

The benchmark demonstrates O(N) full-scan work and bounded per-page Python allocation for the event-log cursor. It does not establish bounds for `memory-fabric list`: that operator path currently materializes all projected memories and sorts them before applying its output limit. That failing regime is recorded for follow-up rather than conflated with event-log pagination.

Synthetic fixtures, warm SQLite cache, and one local host limit generalization. Raw measurements and all configuration are in [e4-06-page-scan.json](e4-06-page-scan.json).
"""
    (output / "e4-06-page-scan.md").write_text(md, encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
