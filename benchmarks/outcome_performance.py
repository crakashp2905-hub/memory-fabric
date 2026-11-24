"""Measured performance of the agent-outcome stack on this host (W18-01..03, 05..07, 09, 10).

    python -m benchmarks.outcome_performance --quick --out perf.json

Every figure here is a measurement on the host named in the report. Nothing is
extrapolated to other machines, and every row is scripted; no model ran, so no
figure says anything about model inference capacity.

* ``latency_breakdown``: one governed episode, timed per stage (observe,
  retrieve, plan, verify, execute, effect acknowledgment, counterfactual
  review), wall and CPU time separately; ``unattributed`` is the runner's own
  overhead, so stages never sum past the total.
* ``worker_contention``: the same episodes on 1, 2, 4 and 8 processes after a
  warm-up, repeated; process start, queue wait and service time apart.
* ``cdm_cost``: actual replay time for dependence-first vs always-on review.
* ``replay_profile``: projection rebuild time and peak Python memory at
  10k and 100k events (1M only with ``--full``).
* ``agent_stress``: 1-50 simultaneous agents with skewed traffic on one store;
  per-agent tail latency, starvation and Jain fairness.
* ``batched_verification``: verifying certificates grouped by principal, never
  coalescing two principals.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import platform
import random
import statistics
import sys
import threading
import time
import tracemalloc
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable, Mapping, Sequence

SCHEMA_ID = "memory-fabric.agent-outcome-performance.v1"


def host() -> dict[str, Any]:
    return {"python": platform.python_version(), "platform": platform.platform(),
            "machine": platform.machine(), "cpus": os.cpu_count(),
            "scope": "this host only; scripted agents; no model inference measured"}


def _pct(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(q * (len(ordered) - 1) + 0.5))], 6)


class _Timer:
    def __init__(self) -> None:
        self.wall: dict[str, float] = {}
        self.cpu: dict[str, float] = {}

    def wrap(self, stage: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        def timed(*args: Any, **kwargs: Any) -> Any:
            w, c = time.perf_counter(), time.process_time()
            try:
                return fn(*args, **kwargs)
            finally:
                self.wall[stage] = self.wall.get(stage, 0.0) + time.perf_counter() - w
                self.cpu[stage] = self.cpu.get(stage, 0.0) + time.process_time() - c
        return timed


def latency_breakdown(seed: int = 0) -> dict[str, Any]:
    from memory_fabric import MemoryFabric
    from memory_fabric.outcome_typed.episode import GovernedMemoryPort, run_episode

    from .outcome_arms import ARMS, build_task, cdm_advice
    from .outcome_episode import ScriptedTeam

    task = build_task("public_correction", seed)
    timer = _Timer()
    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        port = GovernedMemoryPort(fabric, task.envelope.task_id, protected_tools=("set_target",))
        port.record = timer.wrap("observe_record", port.record)  # type: ignore[method-assign]
        port.retrieve = timer.wrap("retrieve", port.retrieve)  # type: ignore[method-assign]
        port.verify = timer.wrap("verify", port.verify)  # type: ignore[method-assign]
        port.execute = timer.wrap("execute_commit", port.execute)  # type: ignore[method-assign]
        team = ScriptedTeam()
        effect = timer.wrap("effect_ack", task.world.effect("set_target"))
        decide = timer.wrap("decision_scripted", team)
        w0, c0 = time.perf_counter(), time.process_time()
        record = run_episode(task.envelope, decide, port, feed=task.world.feed,
                             effects={"set_target": effect}, recovery_enabled=ARMS["A5"].recovery,
                             store_events=task.store_events)
        total_wall, total_cpu = time.perf_counter() - w0, time.process_time() - c0
        cw = time.perf_counter()
        cdm_advice(task, record, port, fabric)
        cdm_wall = time.perf_counter() - cw
    finally:
        fabric.close()
    # execute_commit includes the effect callback; report the commit part net of it.
    wall = dict(timer.wall)
    wall["execute_commit"] = wall.get("execute_commit", 0.0) - wall.get("effect_ack", 0.0)
    attributed = sum(wall.values())
    return {"stages_wall_s": {k: round(v, 6) for k, v in sorted(wall.items())},
            "stages_cpu_s": {k: round(v, 6) for k, v in sorted(timer.cpu.items())},
            "total_wall_s": round(total_wall, 6), "total_cpu_s": round(total_cpu, 6),
            "unattributed_wall_s": round(total_wall - attributed, 6),
            "cdm_review_wall_s": round(cdm_wall, 6),
            "model_inference_s": "NOT_MEASURED: scripted decisions, no model",
            "host_outcome": record.host_outcome.value}


def _episode_job(args: tuple[int, float]) -> tuple[float, float, float, float]:
    seed, submitted = args
    started = time.time()
    c0 = time.process_time()
    from .outcome_arms import ARMS, build_task, run_arm

    run_arm(ARMS["A5"], build_task("public_correction", seed))
    return started - submitted, time.time() - started, time.process_time() - c0, time.time()


def worker_contention(workers: Sequence[int] = (1, 2, 4, 8), episodes: int = 16,
                      trials: int = 3) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    rows: dict[str, Any] = {}
    for count in workers:
        trial_wall: list[float] = []
        queue: list[float] = []
        service: list[float] = []
        cpu: list[float] = []
        start_costs: list[float] = []
        for trial in range(trials + 1):  # trial 0 is the warm-up and is discarded
            p0 = time.time()
            with ProcessPoolExecutor(max_workers=count, mp_context=context) as pool:
                pool.submit(int, 0).result()  # force worker start before timing the work
                start_cost = time.time() - p0
                t0 = time.time()
                results = list(pool.map(_episode_job, [(s, time.time()) for s in range(episodes)]))
                wall = time.time() - t0
            if trial == 0:
                continue
            trial_wall.append(wall)
            start_costs.append(start_cost)
            queue.extend(r[0] for r in results)
            service.extend(r[1] for r in results)
            cpu.extend(r[2] for r in results)
        rows[str(count)] = {"episodes_per_trial": episodes, "trials": trials,
                            "wall_s_median": round(statistics.median(trial_wall), 4),
                            "wall_s_min": round(min(trial_wall), 4),
                            "wall_s_max": round(max(trial_wall), 4),
                            "process_start_s_median": round(statistics.median(start_costs), 4),
                            "queue_wait_s_p50": _pct(queue, 0.5), "queue_wait_s_p95": _pct(queue, 0.95),
                            "service_s_p50": _pct(service, 0.5), "service_s_p95": _pct(service, 0.95),
                            "cpu_s_p50": _pct(cpu, 0.5)}
        rows[str(count)]["bottleneck_top_two"] = bottleneck(rows[str(count)])
    base = rows[str(workers[0])]["wall_s_median"]
    for count in workers:
        rows[str(count)]["speedup_vs_first"] = round(base / rows[str(count)]["wall_s_median"], 3)
    return {"by_workers": rows,
            "not_separated": {"database_lock_s": "inside blocked_s", "network_model_s": "NOT_MEASURED: no model or network"},
            "claim": "descriptive; more workers are not claimed to help (see speedup_vs_first)"}


def bottleneck(row: Mapping[str, Any]) -> list[str]:
    """The two largest per-episode components (W18-03). Lock and model time are not separable here.

    ``blocked_s`` is service time not spent on this process's CPU: lock waits, I/O and
    being descheduled together; it is never relabelled as database lock time.
    """
    service, cpu = row["service_s_p50"] or 0.0, row["cpu_s_p50"] or 0.0
    parts = {"process_start_s": row["process_start_s_median"] / max(1, row["episodes_per_trial"]),
             "queue_wait_s": row["queue_wait_s_p50"] or 0.0, "cpu_s": cpu,
             "blocked_s": max(0.0, service - cpu)}
    return sorted(parts, key=lambda k: (-parts[k], k))[:2]


def cdm_cost(seeds: int = 2) -> dict[str, Any]:
    from memory_fabric.outcome_typed.cdm_dispatch import DecisionRecord, always_on, dispatch

    from .outcome_arms import ARMS, FAMILIES, build_task, run_arm

    lazy_s = eager_s = 0.0
    lazy_n = eager_n = flips = 0
    for family in FAMILIES:
        for seed in range(seeds):
            row = run_arm(ARMS["A6"], build_task(family, seed))
            for item in row["cdm"]["rows"]:
                decision = DecisionRecord(item["decision_id"], item["original"],
                                          frozenset({("m", 1)}), ("a", "b"))

                def replay(d: DecisionRecord, answer: str | None = item["replayed"]) -> str:
                    sum(range(2000))  # stand-in for the planner pass the arm ran
                    return answer or d.chosen

                changed = {"m"} if item["reason"] == "replayed" else set()
                first = dispatch([decision], changed, replay, budget=1)
                every = always_on([decision], replay)
                lazy_s += first.replay_seconds
                eager_s += every.replay_seconds
                lazy_n += first.replays
                eager_n += every.replays
                flips += first.flips
    return {"dependence_first": {"replays": lazy_n, "seconds": round(lazy_s, 6)},
            "always_on": {"replays": eager_n, "seconds": round(eager_s, 6)},
            "flips_either_way": flips, "wasted_replays_always_on": eager_n - lazy_n,
            "net_terminal_utility": "0.0 completion and safety difference for A6 vs A5; "
                                    "see scripted-arms-dev.json cdm block"}


def replay_profile(sizes: Sequence[int] = (10_000, 100_000)) -> dict[str, Any]:
    import tempfile
    import uuid

    from memory_fabric.eventlog import EventLog
    from memory_fabric.events import Event
    from memory_fabric.projections import Projection

    rows: dict[str, Any] = {}
    for size in sizes:
        with tempfile.TemporaryDirectory() as directory:
            log = EventLog(os.path.join(directory, "replay.db"))
            batch = []
            for index in range(size):
                batch.append(Event(type="access_logged", ts=index, payload={"n": index},
                                   agent_id="a", episode_id=None, event_id=uuid.uuid4().hex,
                                   schema_version="0.9.0"))
                if len(batch) == 5000:
                    log.append_many(batch)
                    batch = []
            if batch:
                log.append_many(batch)
            tracemalloc.start()
            t0 = time.perf_counter()
            Projection.rebuild(log)
            seconds = time.perf_counter() - t0
            peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            log.close()
        rows[str(size)] = {"events": size, "rebuild_s": round(seconds, 4),
                           "peak_python_bytes": peak, "events_per_s": round(size / seconds, 1)}
    return {"by_size": rows, "event_type": "access_logged (no projection state change)",
            "limit": "measured on this host only; sizes not listed were not run"}


def agent_stress(agent_counts: Sequence[int] = (1, 5, 10, 25, 50), ops: int = 400,
                 seed: int = 0) -> dict[str, Any]:
    from memory_fabric import MemoryFabric

    rows: dict[str, Any] = {}
    for count in agent_counts:
        fabric = MemoryFabric(":memory:", auto_activate=True)
        try:
            for index in range(20):
                fabric.remember("seed", f"valve {index} limit {index + 3} bar", scope="team")
            rng = random.Random(seed)
            weights = [1.0 / (rank + 1) for rank in range(count)]  # Zipf-skewed traffic
            schedule = rng.choices(range(count), weights=weights, k=ops)
            latencies: dict[int, list[float]] = {agent: [] for agent in range(count)}
            lock = threading.Lock()

            def agent_loop(agent: int) -> None:
                for turn, owner in enumerate(schedule):
                    if owner != agent:
                        continue
                    t0 = time.perf_counter()
                    if turn % 5 == 0:
                        fabric.remember(f"agent-{agent}", f"note {turn} from agent {agent}", scope="team")
                    else:
                        fabric.retrieve(f"agent-{agent}", f"valve {turn % 20} limit", k=3)
                    with lock:
                        latencies[agent].append(time.perf_counter() - t0)

            threads = [threading.Thread(target=agent_loop, args=(a,)) for a in range(count)]
            t0 = time.perf_counter()
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            wall = time.perf_counter() - t0
        finally:
            fabric.close()
        served = [len(v) for v in latencies.values()]
        scheduled = [schedule.count(agent) for agent in range(count)]
        everything = [x for v in latencies.values() for x in v]
        share = [s / max(1, sc) for s, sc in zip(served, scheduled)]
        jain = (sum(share) ** 2) / (len(share) * sum(x * x for x in share)) if any(share) else None
        rows[str(count)] = {"ops": len(everything), "wall_s": round(wall, 4),
                            "p50_s": _pct(everything, 0.5), "p95_s": _pct(everything, 0.95),
                            "p99_s": _pct(everything, 0.99),
                            "worst_agent_p95_s": max((_pct(v, 0.95) or 0.0) for v in latencies.values()),
                            "starved_agents": sum(1 for s, sc in zip(served, scheduled) if sc and not s),
                            "jain_fairness_served_share": round(jain, 4) if jain is not None else None,
                            "completed_all_scheduled": served == scheduled}
    return {"by_agents": rows, "traffic": "Zipf-skewed; one write per five operations"}


def batched_verification(principals: int = 4, per_principal: int = 10) -> dict[str, Any]:
    from memory_fabric import MemoryFabric

    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        requests = []
        for p in range(principals):
            tenant = f"tn_{p}"
            memory = fabric.remember(f"agent-{p}", f"pump {p} limit {p + 2} bar", scope="team",
                                     tenant_id=tenant)
            for _ in range(per_principal):
                requests.append((f"agent-{p}", tenant,
                                 fabric.certify(f"c{p}", [memory], f"agent-{p}", tenant_id=tenant)))
        t0 = time.perf_counter()
        single = [fabric.verify_certificate(c, a, tenant_id=t).reason_codes for a, t, c in requests]
        single_s = time.perf_counter() - t0
        groups: dict[tuple[str, str], list[Any]] = {}
        for agent, tenant, certificate in requests:
            groups.setdefault((agent, tenant), []).append(certificate)
        t0 = time.perf_counter()
        batched = {key: [fabric.verify_certificate(c, key[0], tenant_id=key[1]).reason_codes
                         for c in certs] for key, certs in groups.items()}
        batched_s = time.perf_counter() - t0
        mixed = [fabric.verify_certificate(requests[0][2], requests[-1][0],
                                           tenant_id=requests[-1][1]).reason_codes]
    finally:
        fabric.close()
    return {"requests": len(requests), "groups": len(groups),
            "single_s": round(single_s, 6), "batched_s": round(batched_s, 6),
            "same_results": sorted(map(tuple, single)) == sorted(tuple(r) for rs in batched.values() for r in rs),
            "coalescing_two_principals_refused": list(mixed[0]) != ["ok"],
            "note": "groups never span principals; batching here saves no verification work"}


def run(quick: bool = True, full: bool = False) -> dict[str, Any]:
    sizes = (10_000, 100_000, 1_000_000) if full else ((10_000,) if quick else (10_000, 100_000))
    return {"schema_id": SCHEMA_ID, "host": host(),
            "latency_breakdown": latency_breakdown(),
            "worker_contention": worker_contention(episodes=8 if quick else 16, trials=2 if quick else 3),
            "cdm_cost": cdm_cost(),
            "replay_profile": replay_profile(sizes),
            "agent_stress": agent_stress(ops=200 if quick else 400),
            "batched_verification": batched_verification(),
            "not_run": [] if full else ["replay_profile at 1,000,000 events (use --full)"]}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    report = run(quick=args.quick, full=args.full)
    text = json.dumps(report, indent=1, sort_keys=True) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(json.dumps({k: report[k] for k in ("latency_breakdown", "cdm_cost")}, indent=1)[:1500])
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
