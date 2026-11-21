"""Cross-tenant existence probes through refusals and timing (W16-06).

    python -m benchmarks.outcome_tenant_probe --trials 200

An agent in tenant A asks for memory ids that either belong to tenant B or do
not exist at all. If the refusal (its code, fields or text) or its latency
differed, the agent could learn that a foreign memory exists. The benchmark
interleaves the two kinds of probe through the enforced read path and reports:

* whether the visible refusal payloads are identical once the echoed id and the
  monotonic audit counter are set aside;
* the median latency of each kind and their difference, as a residual to
  document; this harness does not claim timing is indistinguishable. The HTTP
  agent API rate-limits each credential, which is the throttle on probing
  (``tests/test_agent_api_rate_limit.py``).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from typing import Any, Sequence

SCHEMA_ID = "memory-fabric.tenant-existence-probe.v1"
IGNORED = ("memory_id", "integrity_revision")


def _visible(read: Any) -> dict[str, Any]:
    decision = read.decision
    body = {key: getattr(decision, key) for key in ("verdict", "reason_code", "detail",
                                                     "lifecycle_state", "version")}
    body["verdict"] = str(body["verdict"])
    body["has_memory"] = read.memory is not None
    body["has_token"] = read.token is not None
    body["warnings"] = list(read.warnings)
    return body


def run(trials: int = 200) -> dict[str, Any]:
    from memory_fabric import MemoryFabric

    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        foreign = [fabric.remember("other", f"tenant B private plan {i}", scope="team",
                                   tenant_id="tn_b") for i in range(trials)]
        missing = [f"01M{str(i).zfill(23)}" for i in range(trials)]
        payloads: dict[str, set[str]] = {"foreign": set(), "missing": set()}
        timings: dict[str, list[float]] = {"foreign": [], "missing": []}
        for index in range(trials):
            for kind, ids in (("foreign", foreign), ("missing", missing)):
                started = time.perf_counter()
                read = fabric.use(ids[index], "bob", tenant_id="tn_a")
                timings[kind].append(time.perf_counter() - started)
                payloads[kind].add(json.dumps(_visible(read), sort_keys=True))
        median = {kind: statistics.median(values) for kind, values in timings.items()}
        return {"schema_id": SCHEMA_ID, "trials": trials, "ignored_fields": list(IGNORED),
                "payload_variants": {kind: sorted(values) for kind, values in payloads.items()},
                "payloads_identical": payloads["foreign"] == payloads["missing"]
                and len(payloads["foreign"]) == 1,
                "median_seconds": {kind: round(value, 7) for kind, value in median.items()},
                "median_difference_seconds": round(median["foreign"] - median["missing"], 7),
                "timing_claim": "RESIDUAL_DOCUMENTED: medians are reported, not claimed equal; "
                                "the HTTP API rate-limits each credential"}
    finally:
        fabric.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trials", type=int, default=200)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    report = run(args.trials)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(f"payloads identical: {report['payloads_identical']}; medians {report['median_seconds']}; "
          f"difference {report['median_difference_seconds']} s")
    return 0 if report["payloads_identical"] else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
