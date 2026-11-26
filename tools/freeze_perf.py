"""Action-time verification latency with and without model load (freeze plan F11-01, F11-04, F11-05).

    python tools/freeze_perf.py --label saturated --out qualification/perf-verification.json

Measures, in this process, the deterministic path that must stay fast whatever the advisors
do: certify + ActionGate.authorize on fresh evidence, the typed reader on a reading, and the
omission guard. ``--label`` names the condition (for example ``saturated`` while the vega-U
and planner servers are busy, ``idle`` otherwise); the record keeps both runs side by side
with p50/p95/p99, the host and whether model servers were busy. No SLO is invented: the
envelope reports what was measured.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric import MemoryFabric  # noqa: E402
from memory_fabric.actions_typed import ActionGate, ActionPolicy, ActionRequest, ToolRule  # noqa: E402
from memory_fabric.causal_replay.semantic import packets  # noqa: E402
from memory_fabric.causal_replay.semantic.entities import battery_registry  # noqa: E402
from memory_fabric.causal_replay.semantic.observations import Predicate, extract  # noqa: E402
from memory_fabric.causal_replay.semantic.verified_observations import verify  # noqa: E402
from memory_fabric.outcome_typed.omission import HazardPolicy, assess, guard  # noqa: E402


def timed(fn: Callable[[], Any], n: int) -> dict[str, float]:
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    q = lambda p: round(samples[min(len(samples) - 1, int(p * len(samples)))], 3)  # noqa: E731
    return {"n": n, "p50_ms": q(0.50), "p95_ms": q(0.95), "p99_ms": q(0.99), "mean_ms": round(statistics.mean(samples), 3)}


def busy_servers() -> list[str]:
    out = subprocess.run(["ps", "-eo", "pcpu,args"], capture_output=True, text=True).stdout.splitlines()
    return [ln.strip()[:80] for ln in out if ("vegaml-serve" in ln or "local_chat_server" in ln)
            and float(ln.split()[0] or 0) > 20.0]


def measure(n: int) -> dict[str, Any]:
    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        gate = ActionGate(fabric, ActionPolicy(tools={"cool": ToolRule("cool")}, grants={"ops": frozenset({"cool"})}))
        mid = fabric.remember("ana", "pack P-7 sensor TA1 reads 61 C", scope="team")
        cert = fabric.certify("cool P-7", [mid], "ops")
        req = ActionRequest("pack-7", {"mode": "cool"})
        text = "10:00 pack P-7 sensor TA1 reads sixty-one degrees Celsius"
        reg, hot = battery_registry(), Predicate("temperature", "gt", 50.0)
        policy = HazardPolicy("p7", ("pack:p-7/sensor:ta1", "pack:p-7/sensor:tb2"),
                              response=frozenset({"cool_pack", "cool_and_recalibrate"}))
        ps = [packets.SemanticEvidencePacket("tn", "ops", f"m{i}", 1, packets.sha256_text(t), f"s/m{i}", 1000 + i,
                                             1000 + i, "active", "observation", t)
              for i, t in enumerate([text, "10:15 pack P-7 sensor TB2 reads 41 C"])]
        return {"authorize": timed(lambda: gate.authorize("cool", "ops", cert, request=req), n),
                "typed_reader": timed(lambda: extract(text, default_unit="C"), n),
                "verify_assess_guard": timed(lambda: guard("no_action", assess(
                    verify(ps, reg, hot, required=policy.required_sensors), policy), policy), n)}
    finally:
        fabric.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--label", required=True)
    p.add_argument("--n", type=int, default=2000)
    p.add_argument("--out", default="qualification/perf-verification.json")
    args = p.parse_args(argv)
    out = ROOT / args.out
    record = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {
        "schema_id": "memory-fabric.freeze-perf-verification.v1", "runs": {}}
    busy = busy_servers()
    record["runs"][args.label] = {"host": {"platform": platform.platform(), "cpus": os.cpu_count(),
                                           "python": platform.python_version()},
                                  "model_servers_busy": busy, "results": measure(args.n),
                                  "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record["runs"][args.label], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
