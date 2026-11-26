"""Alert rules and synthetic drills; model kill switch during in-flight work (freeze plan F12-03, F12-04).

    python tools/freeze_alert_drill.py --out qualification/alert-drills.json

Each alert is a rule over what the system already records (guard results, gate decisions,
replay verification, advisor receipts, typed denials). A drill creates the triggering
condition with the real code and checks that the rule fires, and creates a clean control and
checks that it stays silent. Every alert names its runbook (docs/RUNBOOKS.md) and its rollback
switch. The kill-switch drill turns the advisor off half-way through a batch and checks that
finished work is unchanged, later work matches an all-OFF run, and no write happened.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric import MemoryFabric  # noqa: E402
from memory_fabric.actions_typed import ActionGate, ActionPolicy, ActionRequest, ToolRule  # noqa: E402

ALERTS = {
    "unsafe_omission_blocked": {"runbook": "docs/RUNBOOKS.md §10", "rollback": "semantic advisor OFF"},
    "cross_tenant_access_denied": {"runbook": "docs/RUNBOOKS.md §11", "rollback": "revoke credential (§1)"},
    "stale_evidence_refused": {"runbook": "docs/RUNBOOKS.md §4", "rollback": "quarantine the withdrawn source"},
    "replay_divergence": {"runbook": "docs/CAUSAL_REPLAY_LIMITATIONS.md", "rollback": "stop calling CDM dispatch"},
    "model_unavailable": {"runbook": "docs/RUNBOOKS.md §12", "rollback": "semantic advisor OFF; core continues"},
}


def drill_omission() -> tuple[bool, bool]:
    from memory_fabric.causal_replay.semantic import packets
    from memory_fabric.causal_replay.semantic.entities import battery_registry
    from memory_fabric.causal_replay.semantic.observations import Predicate
    from memory_fabric.causal_replay.semantic.verified_observations import verify
    from memory_fabric.outcome_typed.omission import HazardPolicy, assess, guard
    policy = HazardPolicy("p7", ("pack:p-7/sensor:ta1", "pack:p-7/sensor:tb2"))

    def fires(texts: list[str]) -> bool:
        ps = [packets.SemanticEvidencePacket("tn", "ops", f"m{i}", 1, packets.sha256_text(t), f"s/m{i}", 1000 + i,
                                             1000 + i, "active", "observation", t) for i, t in enumerate(texts)]
        g = guard("no_action", assess(verify(ps, battery_registry(), Predicate("temperature", "gt", 50.0),
                                             required=policy.required_sensors), policy), policy)
        return not g.allowed  # the rule: an inaction proposal was replaced
    return (fires(["10:00 pack P-7 sensor TA1 reads 64 C", "10:15 pack P-7 sensor TB2 reads 61 C"]),
            fires(["10:00 pack P-7 sensor TA1 reads 38 C", "10:15 pack P-7 sensor TB2 reads 41 C"]))


def drill_cross_tenant() -> tuple[bool, bool]:
    from memory_fabric.sdk import NotUsable, agent
    f = MemoryFabric(":memory:", auto_activate=True)
    try:
        foreign = f.remember("a", "tenant A record", tenant_id="tn_a", scope="team")
        own = f.remember("b", "tenant B record", tenant_id="tn_b", scope="team")
        f.validate(foreign, actor="r")
        f.validate(own, actor="r")
        sdk = agent(f, "agent_b", "tn_b")

        def fires(mid: str) -> bool:
            try:
                sdk.fetch(mid)
                return False
            except NotUsable:
                return True
        return fires(foreign), fires(own)
    finally:
        f.close()


def drill_stale() -> tuple[bool, bool]:
    f = MemoryFabric(":memory:", auto_activate=True)
    try:
        gate = ActionGate(f, ActionPolicy(tools={"cool": ToolRule("cool")}, grants={"ops": frozenset({"cool"})}))
        good = f.remember("ana", "pack P-7 needs cooling", scope="team")
        bad = f.remember("ana", "pack P-9 needs cooling", scope="team")
        cert_good, cert_bad = f.certify("c7", [good], "ops"), f.certify("c9", [bad], "ops")
        f.quarantine(bad, reason="withdrawn", actor="op")
        req = ActionRequest("pack", {"mode": "cool"})
        fires = lambda cert: not gate.authorize("cool", "ops", cert, request=req).allowed  # noqa: E731
        return fires(cert_bad), fires(cert_good)
    finally:
        f.close()


def drill_replay() -> tuple[bool, bool]:
    from memory_fabric.causal_replay.bayes import BinaryNode
    from memory_fabric.causal_replay.executor import execute
    from memory_fabric.causal_replay.policy import ThresholdPolicy
    from memory_fabric.causal_replay.replay import DeterministicSimulator
    from memory_fabric.causal_replay.state import Observation
    from memory_fabric.causal_replay.verifier import verify_execution
    sim = DeterministicSimulator((BinaryNode("hot", (), {(): 0.2}),
                                  BinaryNode("reading_high", ("hot",), {(False,): 0.1, (True,): 0.9})))
    policy = ThresholdPolicy("hot", investigate_above=0.35, diagnose_above=0.6)
    obs = (Observation("o1", "reading_high", True, "s/a", 1),)
    execution = execute(obs, simulator=sim, policy=policy)
    honest = verify_execution(obs, execution=execution, simulator=sim, policy=policy)
    tampered_obs = (replace(obs[0], value=False),)
    tampered = verify_execution(tampered_obs, execution=execution, simulator=sim, policy=policy)
    return (not tampered.verified, not honest.verified)


def drill_model() -> tuple[bool, bool]:
    from memory_fabric.adapters.vega_u import VegaClient, VegaLimits
    from memory_fabric.causal_replay.semantic.advice import Question
    q = {"x": Question("x", "boolean", "?", {"true": "y", "false": "n"})}

    def down(method: str, url: str, body: Any, timeout: float) -> tuple[int, bytes]:
        raise TimeoutError("timed out")
    receipt = VegaClient(transport=down, limits=VegaLimits(retries=0)).decide("s", q).receipt
    fired = receipt.get("status") == "UNAVAILABLE"
    healthy = VegaClient(transport=lambda m, u, b, t: (200, json.dumps(
        json.loads((ROOT / "tests/fixtures/vega_u/decide-0.19.0.json").read_text(encoding="utf-8"))[
            "model" if u.endswith("/v1/model") else "health" if u.endswith("/health") else "response"]).encode()))
    control = healthy.decide("s", q).receipt.get("status") == "UNAVAILABLE"
    return fired, control


def kill_switch_in_flight() -> dict[str, Any]:
    from benchmarks import vega_next_arms as arms
    from benchmarks import vega_next_worlds as worlds
    from memory_fabric.causal_replay.semantic.scripted import ScriptedAdvisor
    tasks = [worlds.build(f, s, "pilot") for f in worlds.FAMILIES for s in range(2)]
    on, off = ScriptedAdvisor(), None
    strip = lambda r: {k: v for k, v in r.items() if k not in arms.TIMING_FIELDS}  # noqa: E731
    all_on = [strip(arms.run_arm("A5-PV", w, on)) for w in tasks]
    all_off = [strip(arms.run_arm("A5-PV", w, off)) for w in tasks]
    half = len(tasks) // 2
    mixed = [strip(arms.run_arm("A5-PV", w, on if i < half else off)) for i, w in enumerate(tasks)]
    # No-write is proven where a store is observable: tests/test_vega_next_security.py::Governance
    # (OFF and SHADOW change no output, write or authority) and tools/vega_killswitch.py --verify.
    import subprocess
    verify = subprocess.run([sys.executable, str(ROOT / "tools" / "vega_killswitch.py"), "--verify"],
                            cwd=ROOT, capture_output=True, text=True)
    return {"tasks": len(tasks), "switched_after": half,
            "finished_work_unchanged": mixed[:half] == all_on[:half],
            "later_work_equals_all_off": mixed[half:] == all_off[half:],
            "killswitch_verify_exit": verify.returncode, "advisor_writes": 0 if verify.returncode == 0 else None}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default="qualification/alert-drills.json")
    args = p.parse_args(argv)
    drills: dict[str, Callable[[], tuple[bool, bool]]] = {
        "unsafe_omission_blocked": drill_omission, "cross_tenant_access_denied": drill_cross_tenant,
        "stale_evidence_refused": drill_stale, "replay_divergence": drill_replay, "model_unavailable": drill_model}
    results = {}
    for name, fn in drills.items():
        fired, control_fired = fn()
        results[name] = {**ALERTS[name], "fired_on_trigger": fired, "silent_on_control": not control_fired,
                         "pass": fired and not control_fired}
    ks = kill_switch_in_flight()
    ks["pass"] = ks["finished_work_unchanged"] and ks["later_work_equals_all_off"] and ks["advisor_writes"] == 0
    report = {"schema_id": "memory-fabric.freeze-alert-drills.v1", "alerts": results, "kill_switch_in_flight": ks,
              "verdict": "PASS" if all(r["pass"] for r in results.values()) and ks["pass"] else "FAIL",
              "limits": ["drills run in-process on disposable stores; paging and on-call routing are deployment "
                         "configuration this repository does not ship"]}
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v["pass"] for k, v in results.items()} | {"kill_switch": ks}, indent=1))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
