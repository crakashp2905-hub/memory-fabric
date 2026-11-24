#!/usr/bin/env python3
"""Measure a local vega-U server: cold start, warm latency, batching, memory (VEGA S13, S15).

    python tools/vega_cdm_profile.py --url http://127.0.0.1:8011 --calls 30 \\
        --out research/results/vega-cdm/model-profile-0.8b.json
    python tools/vega_cdm_profile.py --cold-start "/path/to/venv/bin/vegaml-serve --port 8012 --threads 1 --preload" \\
        --url http://127.0.0.1:8012 ...

Everything reported is measured on this host. GPU utilisation and energy are
``NOT_INSTRUMENTED``; a missing server is ``MODEL_NOT_RUN``. With
``--cold-start`` the command is started, timed until ``/health`` reports the
model loaded, profiled, and stopped. Only loopback URLs are accepted.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric.adapters.vega_u import VegaClient, VegaLimits, check_endpoint  # noqa: E402
from memory_fabric.causal_replay.semantic.advice import Question  # noqa: E402

STATE = ("[ev-1@1] (observation, recorded 1000): pack P-7 sensor TA1 reads 61 C.\n"
         "[ev-2@1] (observation, recorded 1015): pack P-7 sensor TB2 reads 41 C.")
QUESTIONS = {
    "support": Question("support", "choice", "How does this evidence relate to the claim: pack P-7 is overheating",
                        {"supported": "supports", "contradicted": "conflicts", "unknown": "cannot tell"}),
    "drift": Question("drift", "boolean", "Is a drifted TA1 sensor consistent with the evidence?",
                      {"true": "consistent, not proven", "false": "not supported"}),
    "urgency": Question("urgency", "score", "How urgent is intervention?", ("none", "low", "medium", "high")),
}


def _pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(q * len(ordered)))], 4)


def _rss_kib(pid: int | None) -> int | None:
    if pid is None:
        return None
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1])
    except OSError:
        return None
    return None


def _listener_pid(port: int) -> int | None:
    try:
        out = subprocess.run(["ss", "-ltnpH", f"sport = :{port}"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    marker = "pid="
    if marker in out:
        return int(out.split(marker, 1)[1].split(",", 1)[0])
    return None


def profile(url: str, calls: int, pid: int | None) -> dict[str, Any]:
    client = VegaClient(url, limits=VegaLimits(deadline_s=120, retries=0))
    try:
        model = client.handshake()
    except ConnectionError as exc:
        return {"status": "MODEL_NOT_RUN", "reason": str(exc)}
    batched, single = [], []
    for _ in range(calls):
        t0 = time.perf_counter()
        advice = client.decide(STATE, QUESTIONS)
        batched.append(time.perf_counter() - t0)
        if not advice.available:
            return {"status": "MODEL_NOT_RUN", "reason": "a decision failed during profiling"}
    for _ in range(max(3, calls // 5)):
        t0 = time.perf_counter()
        for name, q in QUESTIONS.items():
            client.decide(STATE, {name: q})
        single.append(time.perf_counter() - t0)
    payload = len(json.dumps({"state": STATE, "questions": {n: q.to_wire() for n, q in QUESTIONS.items()}}))
    return {"status": "MEASURED", "model": model, "calls": calls,
            "batched_three_questions_s": {"p50": _pct(batched, 0.5), "p95": _pct(batched, 0.95),
                                          "p99": _pct(batched, 0.99), "mean": round(statistics.mean(batched), 4)},
            "three_single_question_calls_s": {"p50": _pct(single, 0.5), "trials": len(single)},
            "batch_amortization_ratio": round(_pct(single, 0.5) / _pct(batched, 0.5), 3),
            "request_payload_bytes": payload,
            "server_peak_rss_kib": _rss_kib(pid), "server_pid_found": pid is not None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8011")
    parser.add_argument("--calls", type=int, default=30)
    parser.add_argument("--cold-start")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    url = check_endpoint(args.url)
    port = int(url.rsplit(":", 1)[1])
    cold: dict[str, Any] = {"status": "NOT_RUN: pass --cold-start to measure"}
    proc = None
    if args.cold_start:
        t0 = time.perf_counter()
        env = {**os.environ, "HF_HUB_OFFLINE": "1"}
        proc = subprocess.Popen(shlex.split(args.cold_start), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env=env)
        client = VegaClient(url)
        deadline = time.time() + 900
        while time.time() < deadline:
            try:
                client.handshake()
                break
            except ConnectionError:
                time.sleep(1)
        cold = {"status": "MEASURED", "load_until_healthy_s": round(time.perf_counter() - t0, 2),
                "weights": "local cache only (HF_HUB_OFFLINE=1)"}
    try:
        warm = profile(url, args.calls, proc.pid if proc else _listener_pid(port))
    finally:
        if proc:
            proc.terminate()
            proc.wait(timeout=30)
    report = {"schema_id": "memory-fabric.vega-cdm-profile.v1", "evidence_level": "VEGA_MODEL_SMOKE"
              if warm.get("status") == "MEASURED" else "MODEL_NOT_RUN",
              "host": {"platform": platform.platform(), "machine": platform.machine(), "cpus": os.cpu_count(),
                       "python": platform.python_version()},
              "cold_start": cold, "warm": warm,
              "gpu_utilisation": "NOT_INSTRUMENTED", "energy": "NOT_INSTRUMENTED",
              "scope": "this host only; CPU; one server process; no claim about other hardware"}
    text = json.dumps(report, indent=1, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if warm.get("status") == "MEASURED" else 1


if __name__ == "__main__":
    sys.exit(main())
