"""Operator demo: verified readings, a model hypothesis, and the omission guard. Not a benchmark.

    python examples/vega_next_demo.py                       # scripted advisor (no model)
    python examples/vega_next_demo.py --vega-url http://127.0.0.1:8011

It replays the PR #41 failure: a hot pack whose readings are written in words. The typed
reader verifies them, a model proposal that disagrees is rejected, and an inaction proposal
is blocked by the guard. Every line says what kind of statement it is.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memory_fabric.causal_replay.semantic import packets  # noqa: E402
from memory_fabric.causal_replay.semantic.advice import Answer  # noqa: E402
from memory_fabric.causal_replay.semantic.entities import battery_registry  # noqa: E402
from memory_fabric.causal_replay.semantic.observations import Predicate  # noqa: E402
from memory_fabric.causal_replay.semantic.verified_observations import cross_check, verify  # noqa: E402
from memory_fabric.outcome_typed.omission import HazardPolicy, assess, explain, guard  # noqa: E402

TEXTS = ("At 10:00 the A-side thermistor TA1 on pack P-7 was showing sixty-one degrees",
         "The second sensor on P-7, TB2, logged sixty-four degrees at 10:15")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vega-url")
    args = parser.parse_args(argv)
    print("DEMO ONLY: synthetic readings; the scripted proposal is not a model; no external action is performed.")
    ps = [packets.SemanticEvidencePacket("tn_demo", "planner", f"m{i}", 1, packets.sha256_text(t), f"s/m{i}",
                                         1000 + i, 1000 + i, "active", "observation", t) for i, t in enumerate(TEXTS)]
    policy = HazardPolicy("pack-p7-overheat", ("pack:p-7/sensor:ta1", "pack:p-7/sensor:tb2"))
    v = verify(ps, battery_registry(), Predicate("temperature", "gt", 50.0), required=policy.required_sensors)
    for sensor, f in v.findings.items():
        print(f"VERIFIED READING  {sensor}: {f.status} above-50={f.value} from {', '.join(f.evidence_refs)}")
    if args.vega_url:
        from memory_fabric.adapters.vega_u import VegaClient
        from memory_fabric.causal_replay.semantic.advice import Question
        q = {"hot": Question("hot", "boolean", "Does this report a temperature above 50 C?",
                             {"true": "above 50 C", "false": "at or below 50 C"})}
        answer = VegaClient(args.vega_url).decide(TEXTS[1], q).answers["hot"]
    else:  # the PR #41 model answer, replayed: p(hot)=0.234, decisive
        answer = Answer("hot", "boolean", "OK", 0.234, {"true": 0.234, "false": 0.766}, ("false",), False, False)
    check = cross_check(v, "pack:p-7/sensor:tb2", answer)
    print(f"MODEL PROPOSAL    TB2 hot={check.proposal} -> {check.outcome} (the verified reading is unchanged)")
    a = assess(v, policy)
    g = guard("no_action", a, policy)
    e = explain(g, a)
    print(f"GUARD             proposal no_action: {e['decision']} ({e['reason']}); next step "
          f"{e['next_permitted_step']}; terminal action {e['terminal_action']}")
    print("\nA model proposal never lowers a verified hazard; inaction needs verified negative readings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
