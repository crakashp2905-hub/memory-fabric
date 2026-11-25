#!/usr/bin/env python3
"""Stage timings, parser throughput and worker contention for the next study (VEGA next W14).

    python tools/vega_next_perf.py --out research/results/vega-cdm/next/perf/perf.json

Measured on this host only, model-free unless a result file is passed in:

* ``replay_stages``: per-decision time in the replay executor and in the independent
  verifier, p50/p95/p99 over many decisions (W14-07);
* ``parser``: deterministic typed extraction time per evidence text on the dev worlds, the
  identical inputs the calibration study sent to vega-U (W14-03);
* ``workers``: the scripted arms benchmark split across 1, 2, 4 and 8 processes, wall time
  including process start, and the actual speedup (W14-08). More workers are not assumed
  to help.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT, ROOT / "src"):
    sys.path.insert(0, str(extra))


def _pct(xs: list[float], q: float) -> float:
    s = sorted(xs)
    return round(s[min(len(s) - 1, int(q * len(s)))] * 1e3, 4)


def replay_stages(n: int = 400) -> dict[str, Any]:
    from benchmarks import vega_next_cdm_value as cdm
    from memory_fabric.causal_replay.executor import execute
    from memory_fabric.causal_replay.state import Observation
    from memory_fabric.causal_replay.verifier import verify_execution

    ex, ve = [], []
    for i in range(n):
        obs = (Observation(f"p{i}", "reading_high", i % 3 == 0, f"s/{i}", 1),)
        t0 = time.perf_counter()
        execution = execute(obs, simulator=cdm.SIM, policy=cdm.POLICY)
        t1 = time.perf_counter()
        verify_execution(obs, execution=execution, simulator=cdm.SIM, policy=cdm.POLICY)
        t2 = time.perf_counter()
        ex.append(t1 - t0)
        ve.append(t2 - t1)
    return {"decisions": n, "unit": "ms", "execute": {q: _pct(ex, v) for q, v in (("p50", .5), ("p95", .95), ("p99", .99))},
            "verify": {q: _pct(ve, v) for q, v in (("p50", .5), ("p95", .95), ("p99", .99))}}


def parser(seeds: int = 8) -> dict[str, Any]:
    from benchmarks import vega_next_worlds as worlds
    from memory_fabric.causal_replay.semantic.observations import extract

    texts = [i.text for f in worlds.FAMILIES for s in range(seeds) for i in worlds.build(f, s, "dev").items]
    times = []
    for t in texts:
        t0 = time.perf_counter()
        extract(t, default_unit="C")
        times.append(time.perf_counter() - t0)
    return {"texts": len(texts), "unit": "ms", "p50": _pct(times, .5), "p95": _pct(times, .95), "p99": _pct(times, .99),
            "total_s": round(sum(times), 4)}


def _family_job(args: tuple[str, int]) -> int:
    from benchmarks import vega_next_arms as arms
    from benchmarks import vega_next_worlds as worlds
    family, seeds = args
    return sum(1 for s in range(seeds) for arm in ("A5-P", "A3-P", "A7")
               if arms.run_arm(arm, worlds.build(family, s, "dev"), None))


def workers(seeds: int = 4) -> dict[str, Any]:
    from benchmarks import vega_next_worlds as worlds
    jobs = [(f, seeds) for f in worlds.FAMILIES]
    out: dict[str, Any] = {}
    for n in (1, 2, 4, 8):
        t0 = time.perf_counter()
        with ProcessPoolExecutor(max_workers=n) as pool:
            done = sum(pool.map(_family_job, jobs))
        out[str(n)] = {"wall_s": round(time.perf_counter() - t0, 3), "tasks": done}
    base = out["1"]["wall_s"]
    for n in out:
        out[n]["speedup_vs_1"] = round(base / out[n]["wall_s"], 3)
    return {"by_workers": out, "includes": "process start and queueing", "cpus": os.cpu_count()}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out")
    args = p.parse_args(argv)
    report = {"schema_id": "memory-fabric.vega-next-perf.v1",
              "host": {"platform": platform.platform(), "cpus": os.cpu_count(), "python": platform.python_version()},
              "replay_stages": replay_stages(), "parser": parser(), "workers": workers(),
              "scope": "this host only; model-free; a model process running alongside is noted in the report"}
    text = json.dumps(report, indent=1, sort_keys=True)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
