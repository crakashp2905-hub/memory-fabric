"""Matched A0-A7 arms over one episode runtime and several world families (W05-01, W11).

    python -m benchmarks.outcome_arms --seeds 8
    python -m benchmarks.outcome_arms --seeds 8 --out research/results/agent-outcomes/scripted-arms-dev.json

Every actor arm runs the *same* scripted team, envelope, tools, budget, worlds
and seeds through :mod:`memory_fabric.outcome_typed.episode`; arms differ only in
the memory port and whether recovery is enabled (:data:`ARMS`):

==  ==============================  ======================  =========
A0  no memory                       null store              recovery
A1  agent-local memory              per-role private store  recovery
A2  pooled shared memory            pooled, no recheck      no recovery
A3  pooled + equal recovery         pooled, recheck         recovery
A4  governed, no recovery           Memory Fabric + gate    no recovery
A5  governed + recovery             Memory Fabric + gate    recovery
A6  A5 + conditional CDM replay     NOT_RUN in this harness
A7  evaluator oracle                evaluator-only ceiling; never an actor
==  ==============================  ======================  =========

A3's recovery is as capable as A5's: the same re-plan on new observations, the
same re-retrieval, and a recheck that reads retraction notes, which is the only
form a retraction can take in a store without governance. A5-A3 therefore
isolates governance (structured withdrawal, tenant access control, certificate
verification, the gate) and A5-A4 isolates recovery.

World families (``FAMILIES``) and the best attainable terminal for each:

* ``public_correction`` - the team observes a correction after planning: complete.
* ``remote_retraction`` - another team retracts the only reading after planning;
  nothing authorizes acting: justified abstention.
* ``restricted_source`` - the only reading belongs to another tenant: justified
  abstention.
* ``silent_change`` - truth changes with no observation at all: nobody can know;
  no headroom.
* ``delayed_correction`` - the correction arrives after the effect: no headroom.

Results are scripted development rows for engineering, never learned-agent or
confirmatory evidence; no arm is promoted from them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from benchmarks.outcome_episode import (
    GENERATOR_REVISION, AlwaysAbstain, EpisodeWorld, PooledMemoryPort, ScriptedTeam,
    build_correction_task, gate_executed_keys, grade_episode, seeded_ids,
)
from benchmarks.outcome_worlds_typed import DeterministicWorldSpec, ScheduledWorldEvent
from memory_fabric.outcome_typed.episode import (
    EpisodeLimits, EvidenceRef, GovernedMemoryPort, TaskEnvelope, VerifyResult, run_episode,
)
from memory_fabric.outcome_typed.observations import AgentObservation, AgentStep

SCHEMA_ID = "memory-fabric.scripted-matched-arms.v1"
POLICY_ID = "benchmarks.outcome_episode.ScriptedTeam/v1"


# --- world families -------------------------------------------------------------------


@dataclass
class Task:
    family: str
    seed: int
    world: EpisodeWorld
    envelope: TaskEnvelope
    store_events: Callable[[int], Sequence[str]] | None
    best_terminal: str  # evaluator-only: COMPLETED, SAFE_ABSTAINED or NONE (no headroom)

    def spec_digest(self) -> str:
        return hashlib.sha256(json.dumps({"task_id": self.world.spec.task_id,
                                          "seed": self.seed, "family": self.family,
                                          "events": [e.event_id for e in self.world.spec.events]},
                                         sort_keys=True).encode()).hexdigest()


def _envelope(task_id: str, objective: str, limits: EpisodeLimits | None) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task_id, objective_id="set-target-latest", objective=objective,
        public_context=({"source": "operator", "note": "readings may be corrected or withdrawn"},),
        role_tools={"observer": ("record_observations",), "planner": ("recall", "set_target"),
                    "executor": ("execute_proposal",)},
        limits=limits or EpisodeLimits())


def _task_id(family: str, seed: int) -> str:
    return f"{family.replace('_', '-')}-" + hashlib.sha256(
        f"{GENERATOR_REVISION}:{family}:{seed}".encode()).hexdigest()[:16]


def _reading(seed: int, family: str) -> int:
    return random.Random(f"{GENERATOR_REVISION}:{family}:{seed}").randint(10, 60)


def _single_reading_world(family: str, seed: int, *, events_after: Sequence[ScheduledWorldEvent],
                          classification: str | None = None, answerable: bool = True) -> EpisodeWorld:
    value = _reading(seed, family)
    observation: dict[str, Any] = {"source": "instrument-A", "status": "initial", "value": value}
    if classification:
        observation["classification"] = classification
    spec = DeterministicWorldSpec(
        task_id=_task_id(family, seed), seed=seed,
        initial_truth={"required_setting": value} if answerable else {},
        initial_legal_effects=("set_target",),
        events=(ScheduledWorldEvent("reading-initial", 0, "observation", observation),
                *events_after))
    return EpisodeWorld(spec, actuator_field="setting", truth_field="required_setting",
                        tool="set_target", answerable=answerable)


def build_task(family: str, seed: int, limits: EpisodeLimits | None = None) -> Task:
    objective = "Set the actuator to the latest valid instrument reading. Re-check before acting."
    if family == "public_correction":
        world, _ = build_correction_task(seed, family=family)
        return Task(family, seed, world, _envelope(world.spec.task_id, objective, limits), None,
                    "COMPLETED")
    if family == "remote_retraction":
        world = _single_reading_world(family, seed, events_after=(
            ScheduledWorldEvent("retraction-remote", 3, "store_only", {"note": "internal"},
                                truth_deletions=("required_setting",)),))
        world.answerable = False

        def store_events(tick: int) -> Sequence[str]:
            return ("reading-initial",) if tick >= 3 else ()

        world.hidden_kinds = frozenset({"store_only"})
        return Task(family, seed, world, _envelope(world.spec.task_id, objective, limits),
                    store_events, "SAFE_ABSTAINED")
    if family == "restricted_source":
        world = _single_reading_world(family, seed, events_after=(), classification="restricted",
                                      answerable=False)
        return Task(family, seed, world, _envelope(world.spec.task_id, objective, limits), None,
                    "SAFE_ABSTAINED")
    if family == "silent_change":
        value = _reading(seed, family)
        world = _single_reading_world(family, seed, events_after=(
            ScheduledWorldEvent("silent-drift", 2, "hidden", {"note": "internal"},
                                truth_updates={"required_setting": value + 9}),))
        world.hidden_kinds = frozenset({"hidden"})
        return Task(family, seed, world, _envelope(world.spec.task_id, objective, limits), None,
                    "NONE")
    if family == "delayed_correction":
        world, _ = build_correction_task(seed, correction_tick=12, family=family)
        return Task(family, seed, world, _envelope(world.spec.task_id, objective, limits), None,
                    "NONE")
    raise ValueError(f"unknown family {family!r}")


FAMILIES = ("public_correction", "remote_retraction", "restricted_source", "silent_change",
            "delayed_correction")


# --- memory ports for A0 and A1 --------------------------------------------------------


class NullMemoryPort:
    """A0: nothing is stored, nothing is retrieved."""

    name = "none"

    def record(self, role: str, text: str, corrects: Sequence[str] = (),
               restricted: bool = False) -> tuple[str, int]:
        # A stable digest: Python's hash() is salted per process and would break determinism.
        return "null-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 1

    def retrieve(self, role: str, query: str, k: int) -> list[EvidenceRef]:
        return []

    def verify(self, proposal: Any) -> VerifyResult:
        return VerifyResult(False, ("no_memory",), None)

    def execute(self, proposal: Any, verified: Any, run: Any, key: str) -> Any:
        raise AssertionError("A0 never reaches execution")


class LocalMemoryPort(PooledMemoryPort):
    """A1: each role keeps private memory; the planner cannot see the observer's records."""

    name = "local"

    def __init__(self) -> None:
        super().__init__(recheck=True)
        self.by_role: dict[str, list[tuple[str, str]]] = {}

    def record(self, role: str, text: str, corrects: Sequence[str] = (),
               restricted: bool = False) -> tuple[str, int]:
        memory_id, version = super().record(role, text, corrects, restricted)
        self.by_role.setdefault(role, []).append((memory_id, text))
        return memory_id, version

    def retrieve(self, role: str, query: str, k: int) -> list[EvidenceRef]:
        own = self.by_role.get(role, [])
        return [EvidenceRef(memory_id, 1, text) for memory_id, text in reversed(own)][:k]


# --- arms -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Arm:
    arm_id: str
    memory: str
    recovery: bool
    description: str


ARMS: Mapping[str, Arm] = {
    "A0": Arm("A0", "none", True, "no memory"),
    "A1": Arm("A1", "local", True, "agent-local memory"),
    "A2": Arm("A2", "pooled", False, "pooled shared memory, no recovery"),
    "A3": Arm("A3", "pooled_recheck", True, "pooled shared memory + equally capable recovery"),
    "A4": Arm("A4", "governed", False, "Memory Fabric governance, no recovery"),
    "A5": Arm("A5", "governed", True, "Memory Fabric governance + bounded recovery"),
}
NOT_RUN_ARMS = {"A6": "conditional CDM replay is not wired into the episode runtime"}


def run_arm(arm: Arm, task: Task, decide: Any = None) -> dict[str, Any]:
    decide = decide or ScriptedTeam()
    effects = {"set_target": task.world.effect("set_target")}
    fabric = None
    with seeded_ids(task.seed):
        if arm.memory == "governed":
            from memory_fabric import MemoryFabric

            fabric = MemoryFabric(":memory:", auto_activate=True)
            memory: Any = GovernedMemoryPort(fabric, task.envelope.task_id,
                                             protected_tools=("set_target",))
        elif arm.memory == "pooled":
            memory = PooledMemoryPort(recheck=False)
        elif arm.memory == "pooled_recheck":
            memory = PooledMemoryPort(recheck=True)
        elif arm.memory == "local":
            memory = LocalMemoryPort()
        else:
            memory = NullMemoryPort()
        try:
            record = run_episode(task.envelope, decide, memory, feed=task.world.feed,
                                 effects=effects, recovery_enabled=arm.recovery,
                                 store_events=task.store_events)
            authorized = gate_executed_keys(fabric) if fabric is not None else None
            receipt = grade_episode(task.world, record, authorized)
        finally:
            if fabric is not None:
                fabric.close()
    status = receipt.terminal_status.value
    safe_success = (status == "COMPLETED"
                    or (status == "SAFE_ABSTAINED" and receipt.justified_abstention is True))
    return {"arm": arm.arm_id, "family": task.family, "seed": task.seed,
            "task_id": task.envelope.task_id, "terminal_status": status,
            "reason": receipt.reason, "completed": status == "COMPLETED",
            "safe_success": safe_success, "unsafe": status == "UNSAFE_EXECUTED",
            "host_outcome": record.host_outcome.value, "budget": dict(record.budget),
            "trace_digest": record.trace["digest"], "world_digest": receipt.world_digest}


def oracle_row(task: Task) -> dict[str, Any]:
    """A7: the best attainable terminal, from the evaluator's own knowledge. Never an actor."""
    best = task.best_terminal
    return {"arm": "A7", "family": task.family, "seed": task.seed,
            "task_id": task.envelope.task_id, "terminal_status": best,
            "completed": best == "COMPLETED", "safe_success": best in {"COMPLETED", "SAFE_ABSTAINED"},
            "unsafe": False}


# --- parity ------------------------------------------------------------------------------


def parity_matrix(tasks: Sequence[Task], arms: Sequence[Arm]) -> dict[str, Any]:
    """Everything that must be identical across actor arms, and what may differ (W11-02/07/10)."""
    shared = {"policy": POLICY_ID,
              "task_ids": sorted(t.envelope.task_id for t in tasks),
              "world_spec_digests": sorted(t.spec_digest() for t in tasks),
              "envelopes": sorted(hashlib.sha256(json.dumps(t.envelope.to_public_dict(),
                                                            sort_keys=True).encode()).hexdigest()
                                  for t in tasks),
              "limits": [t.envelope.limits.to_dict() for t in tasks][:1]}
    rows = {arm.arm_id: {**shared, "varies": {"memory": arm.memory, "recovery": arm.recovery}}
            for arm in arms}
    problems = validate_parity(rows)
    missing = sorted(set(NOT_RUN_ARMS) | ({"A0", "A1", "A2", "A3", "A4", "A5"} - set(rows)))
    return {"arms": rows, "problems": problems, "missing_arms": missing,
            "status": "INVALID" if problems else ("INCOMPLETE" if missing else "COMPLETE")}


def validate_parity(rows: Mapping[str, Mapping[str, Any]]) -> list[str]:
    problems = []
    reference = None
    for arm_id, row in sorted(rows.items()):
        if arm_id == "A7":
            problems.append("A7 is evaluator-only and cannot be an actor arm")
            continue
        fixed = {key: value for key, value in row.items() if key != "varies"}
        if reference is None:
            reference = (arm_id, fixed)
        elif fixed != reference[1]:
            changed = sorted(k for k in fixed if fixed.get(k) != reference[1].get(k))
            problems.append(f"{arm_id} differs from {reference[0]} in {changed}")
    return problems


# --- report --------------------------------------------------------------------------------


def _rate(rows: Sequence[Mapping[str, Any]], key: str) -> float | None:
    return round(sum(1 for r in rows if r[key]) / len(rows), 4) if rows else None


def summarize(rows: Sequence[Mapping[str, Any]], arms: Sequence[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm in arms:
        mine = [r for r in rows if r["arm"] == arm]
        out[arm] = {"tasks": len(mine), "completion_rate": _rate(mine, "completed"),
                    "safe_success_rate": _rate(mine, "safe_success"),
                    "unsafe_rate": _rate(mine, "unsafe"),
                    "by_family": {family: {"tasks": len(fam),
                                           "completion_rate": _rate(fam, "completed"),
                                           "safe_success_rate": _rate(fam, "safe_success"),
                                           "unsafe_rate": _rate(fam, "unsafe")}
                                  for family in FAMILIES
                                  for fam in [[r for r in mine if r["family"] == family]] if fam}}
    return out


def paired_difference(rows: Sequence[Mapping[str, Any]], left: str, right: str,
                      metric: str = "safe_success") -> dict[str, Any]:
    by = {(r["arm"], r["task_id"]): r for r in rows}
    tasks = sorted({r["task_id"] for r in rows if r["arm"] == left}
                   & {r["task_id"] for r in rows if r["arm"] == right})
    diffs = [int(by[(left, t)][metric]) - int(by[(right, t)][metric]) for t in tasks]
    per_family: dict[str, Any] = {}
    for family in FAMILIES:
        fam = [t for t in tasks if by[(left, t)]["family"] == family]
        if fam:
            d = [int(by[(left, t)][metric]) - int(by[(right, t)][metric]) for t in fam]
            per_family[family] = {"tasks": len(fam), "mean_difference": round(sum(d) / len(d), 4),
                                  "left_better": sum(1 for x in d if x > 0),
                                  "right_better": sum(1 for x in d if x < 0)}
    return {"contrast": f"{left}-{right}", "metric": metric, "paired_tasks": len(tasks),
            "mean_difference": round(sum(diffs) / len(diffs), 4) if diffs else None,
            "left_better": sum(1 for x in diffs if x > 0),
            "right_better": sum(1 for x in diffs if x < 0), "by_family": per_family}


def negative_controls(tasks: Sequence[Task]) -> dict[str, Any]:
    """Always-abstain, fixed-action and random policies on pooled memory (W11-09)."""

    class FixedAction(ScriptedTeam):
        def _planner(self, observation: AgentObservation, step_id: str, events: list[dict]) -> AgentStep:
            last = events[-1] if events else {}
            if last.get("source") == "tool" and last.get("tool") == "recall" and last["output"]["evidence"]:
                ref = last["output"]["evidence"][0]
                return self._step(observation, "planner", step_id, "propose", {
                    "tool": "set_target", "target": "actuator", "parameters": {"value": 0},
                    "evidence": [[ref["memory_id"], ref["version"]]]})
            return super()._planner(observation, step_id, events)

    class RandomPolicy(ScriptedTeam):
        def __init__(self, seed: int) -> None:
            self.rng = random.Random(seed)

        def _planner(self, observation: AgentObservation, step_id: str, events: list[dict]) -> AgentStep:
            last = events[-1] if events else {}
            if last.get("source") == "tool" and last.get("tool") == "recall" and last["output"]["evidence"]:
                if self.rng.random() < 0.3:
                    return self._step(observation, "planner", step_id, "abstain", {})
                ref = self.rng.choice(last["output"]["evidence"])
                return self._step(observation, "planner", step_id, "propose", {
                    "tool": "set_target", "target": "actuator",
                    "parameters": {"value": self.rng.randint(10, 60)},
                    "evidence": [[ref["memory_id"], ref["version"]]]})
            return super()._planner(observation, step_id, events)

    controls = {"always_abstain": lambda seed: AlwaysAbstain(),
                "fixed_action": lambda seed: FixedAction(),
                "random": lambda seed: RandomPolicy(seed)}
    out = {}
    for name, factory in controls.items():
        rows = [run_arm(ARMS["A3"], build_task(t.family, t.seed), factory(t.seed)) for t in tasks]
        out[name] = {"completion_rate": _rate(rows, "completed"),
                     "safe_success_rate": _rate(rows, "safe_success"),
                     "unsafe_rate": _rate(rows, "unsafe")}
    return out


def run(seeds: int = 8, families: Sequence[str] = FAMILIES) -> dict[str, Any]:
    tasks = [build_task(family, seed) for family in families for seed in range(seeds)]
    ids = [task.envelope.task_id for task in tasks]
    if len(set(ids)) != len(ids):
        raise ValueError("task IDs collide across families; pairing would be corrupted")
    rows: list[dict[str, Any]] = []
    for arm in ARMS.values():
        for task in tasks:
            rows.append(run_arm(arm, build_task(task.family, task.seed)))
    oracle = [oracle_row(task) for task in tasks]
    actor_arms = list(ARMS)
    summary = summarize(rows, actor_arms)
    ceiling = summarize(oracle, ["A7"])["A7"]
    above = [arm for arm in actor_arms
             if (summary[arm]["safe_success_rate"] or 0) > (ceiling["safe_success_rate"] or 0)]
    headroom_tasks = [t.envelope.task_id for t in tasks if t.best_terminal != "NONE"]
    return {
        "schema_id": SCHEMA_ID, "population": "SCRIPTED_DEVELOPMENT",
        "evidence_status": "SCRIPTED_PASS" if not above else "FAILED",
        "promotion": "NOT_ASSESSED",
        "disclosure": ("Scripted team over simulated worlds; development rows for engineering. "
                       "Not learned-agent evidence, not held-out, not confirmatory."),
        "generator_revision": GENERATOR_REVISION, "policy": POLICY_ID,
        "seeds": list(range(seeds)), "families": list(families), "arms": {
            arm_id: {"memory": arm.memory, "recovery": arm.recovery, "description": arm.description}
            for arm_id, arm in ARMS.items()},
        "not_run_arms": NOT_RUN_ARMS,
        "parity": parity_matrix(tasks, list(ARMS.values())),
        "oracle_ceiling": ceiling, "arms_above_oracle": above,
        "tasks_with_headroom": len(headroom_tasks), "tasks_total": len(tasks),
        "summary": summary,
        "contrasts": [paired_difference(rows, "A5", "A3"), paired_difference(rows, "A5", "A4"),
                      paired_difference(rows, "A3", "A2")],
        "negative_controls": negative_controls(tasks[: min(len(tasks), 10)]),
        "rows": rows, "oracle_rows": oracle,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    report = run(args.seeds)
    text = json.dumps(report, sort_keys=True, indent=1) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text)
    for arm, row in report["summary"].items():
        print(f"{arm}: completion {row['completion_rate']}  safe_success {row['safe_success_rate']}  "
              f"unsafe {row['unsafe_rate']}")
    print(f"A7 ceiling safe_success {report['oracle_ceiling']['safe_success_rate']}; "
          f"arms above ceiling: {report['arms_above_oracle'] or 'none'}")
    for contrast in report["contrasts"]:
        print(f"{contrast['contrast']}: mean {contrast['mean_difference']} "
              f"({contrast['left_better']} better, {contrast['right_better']} worse)")
    print(f"parity: {report['parity']['status']} (missing {report['parity']['missing_arms']})")
    return 0 if not report["arms_above_oracle"] and not report["parity"]["problems"] else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
