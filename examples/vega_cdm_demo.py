"""Operator demo: semantic hypothesis -> verified replay -> decision repair. Not a benchmark.

    python examples/vega_cdm_demo.py                       # scripted advisor (no model)
    python examples/vega_cdm_demo.py --vega-url http://127.0.0.1:8011

Every line says what kind of statement it is: a MODEL PROPOSAL, a VERIFIED
replay result, or a GRADED terminal outcome.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks import vega_cdm_matched_arms as arms  # noqa: E402
from benchmarks import vega_cdm_worlds as worlds  # noqa: E402
from memory_fabric.causal_replay.bayes import BinaryNode  # noqa: E402
from memory_fabric.causal_replay.intervention import ReplacementFixture, create  # noqa: E402
from memory_fabric.causal_replay.policy import ThresholdPolicy  # noqa: E402
from memory_fabric.causal_replay.replay import DeterministicSimulator  # noqa: E402
from memory_fabric.causal_replay.semantic import effects, packets, support  # noqa: E402
from memory_fabric.causal_replay.semantic.scripted import ScriptedAdvisor  # noqa: E402
from memory_fabric.causal_replay.state import Observation  # noqa: E402
from memory_fabric.causal_replay.types import BeliefReference  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vega-url")
    args = parser.parse_args(argv)
    print("DEMO ONLY: seeded synthetic world; the scripted advisor is not a model; no external action is performed.")
    if args.vega_url:
        from memory_fabric.adapters.vega_u import VegaClient
        advisor = VegaClient(args.vega_url)
    else:
        advisor = ScriptedAdvisor()

    world = worlds.build("delayed_correction", 0)
    fabric = worlds.materialize(world)
    try:
        bundle = packets.from_retrieval(fabric, "planner", world.query, tenant_id=worlds.TENANT)
        print(f"\nEVIDENCE ({bundle.status}, {bundle.independent_root_count()} independent roots):")
        for p in bundle.packets:
            print(f"  {p.ref}  v{p.version} {p.status:<9} {p.visible_text}")
        claim = "pack P-7 is overheating"
        for proposal in support.assess(bundle, claim, advisor):
            print(f"MODEL PROPOSAL  {proposal.evidence_ref}: {proposal.label} (route {proposal.route}, "
                  f"guard {proposal.guard}, tier {proposal.tier})")
    finally:
        fabric.close()

    nodes = (BinaryNode("hot", (), {(): 0.2}),
             BinaryNode("tb2_high", ("hot",), {(False,): 0.1, (True,): 0.9}))
    sim, policy = DeterministicSimulator(nodes), ThresholdPolicy("hot", investigate_above=0.35, diagnose_above=0.6)
    stale = (Observation("tb2", "tb2_high", True, "sensor-TB2", 1),)
    corrected = ReplacementFixture("tb2-corrected", Observation("tb2", "tb2_high", False, "sensor-TB2", 1))
    target = BeliefReference("tb2", 1, worlds.TENANT, "0" * 64)
    result = effects.evaluate(stale, create(target, "replace", replacement=corrected), simulator=sim, policy=policy)
    print(f"\nVERIFIED replay of the correction: {result.status}; proposal {result.factual_proposal} -> "
          f"{result.counterfactual_proposal}; tier {result.tier}; terminal effect {result.terminal_improvement}")

    for arm in ("A5", "A5-V"):
        row = arms.run_arm(arm, worlds.build("delayed_correction", 0), advisor)
        print(f"GRADED  {arm}: action {row['action']} -> {row['terminal']} (independent grader)")
    print("\nA model proposal is never a verified cause; only the replay line is verified, and only in the simulator.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
