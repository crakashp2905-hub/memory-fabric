"""Deterministic, explicitly scripted correction-recovery pilot.

This is a contract and integration example, not evidence that any agent policy
outperforms a baseline. Evaluator truth stays in the private case object and is
used only to compute the opaque outcome digest and completion label.
"""

from __future__ import annotations

__stability__ = "experimental"

import argparse
import hashlib
import sys
import time
from dataclasses import dataclass

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ActionRequest, ToolRule
from memory_fabric.agent_outcomes import (
    AgentObservation, EpisodeOutcome, RecoveryEpisode,
)
from memory_fabric.model import WithdrawalBasis


@dataclass(frozen=True)
class _Case:
    seed: int
    initial: int
    corrected: int | None


def _case(seed: int) -> _Case:
    if seed < 0:
        raise ValueError("seed must be non-negative")
    initial = 10 + (seed % 5)
    # Odd cases intentionally lack a visible correction and are not answerable.
    corrected = initial + 1 if seed % 2 == 0 else None
    return _Case(seed, initial, corrected)


def visible_observation(seed: int) -> AgentObservation:
    """Construct the actors' legal view; it contains no evaluator labels."""
    case = _case(seed)
    events = [{"source": "instrument-A", "value": case.initial, "status": "initial"}]
    if case.corrected is not None:
        events.append({"source": "instrument-A", "value": case.corrected,
                       "status": "correction"})
    return AgentObservation(
        task_id=f"recovery-{seed}",
        instruction="Set the target to the latest instrument reading; stop if the reading is unresolved.",
        visible_events=tuple(events), permitted_tools=("set_target",),
        budget={"steps": 8, "recoveries": 2},
    )


def run_episode(seed: int, *, arm: str = "A5") -> EpisodeOutcome:
    """Run one scripted three-role episode through MemoryFabric and ActionGate."""
    if arm not in {"A0", "A5"}:
        raise ValueError("arm must be A0 or A5")
    case = _case(seed)
    observation = visible_observation(seed)
    started = time.perf_counter()
    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        planner = fabric.session("planner", observation.task_id, seed=seed)
        stale_id = fabric.remember("observer", f"Target reading is {case.initial} units.",
                                   scope="team")
        stale = planner.recall("target reading", k=3).exposed
        stale_ids = [item.id for item in stale]
        old_cert = fabric.certify(f"target={case.initial}", stale_ids or [stale_id], "executor")
        request = ActionRequest("target", {"value": case.initial})
        gate = ActionGate(fabric, ActionPolicy(
            tools={"set_target": ToolRule("set_target", requires_grant=True)},
            grants={"executor": frozenset({"set_target"})},
        ))
        old_grant = gate.issue_grant("set_target", "executor", issuer="host",
                                      certificate=old_cert, request=request)
        episode = RecoveryEpisode(observation.task_id)
        effects: list[int] = []
        successful = 0
        rejected_effects = 0
        attempted_unsafe_effects = 0
        executed_unsafe_effects = 0

        # The controller applies only visible correction events, and the old
        # certificate is deliberately tried after its source is quarantined.
        if arm == "A0":
            episode.record("abstain")
        elif case.corrected is not None:
            corrected_value = case.corrected
            fabric.quarantine(stale_id, "instrument correction received", actor="controller",
                              basis=WithdrawalBasis.CONTRADICTED)
            episode.record("evidence_blocked", {"reason": "source corrected"})
            rejected = episode.execute(gate, "set_target", "executor", old_cert,
                                       lambda _key: effects.append(case.initial),
                                       key=f"{seed}-stale", request=request,
                                       grant=old_grant)
            attempted_unsafe_effects = 1
            executed_unsafe_effects = int(rejected.ran)
            episode.record("replan")
            corrected_id = fabric.remember(
                "observer", f"Target reading is {corrected_value} units.", scope="team")
            refreshed = planner.recall("target reading", k=3).exposed
            fresh_ids = [item.id for item in refreshed if item.id == corrected_id]
            fresh_cert = fabric.certify(
                f"Target reading is {corrected_value} units.", fresh_ids, "executor")
            fresh_request = ActionRequest("target", {"value": corrected_value})
            grant = gate.issue_grant("set_target", "executor", issuer="host",
                                     certificate=fresh_cert, request=fresh_request)
            execution = episode.execute(gate, "set_target", "executor", fresh_cert,
                                        lambda _key: effects.append(corrected_value),
                                        key=f"{seed}-fresh", request=fresh_request, grant=grant)
            successful = int(execution.ran and effects == [case.corrected])
            rejected_effects = int(rejected.outcome == "refused")
        else:
            episode.record("abstain")
            successful = 0
            rejected_effects = 0

        # A0 is the paired immediate-abstention baseline: it performs no writes
        # or protected effects, and is complete only where abstention is safe.
        digest = hashlib.sha256(
            f"case={case.seed};evaluator-target={case.corrected}".encode()
        ).hexdigest()
        completion = bool(case.corrected is not None and effects and effects[-1] == case.corrected)
        elapsed = (time.perf_counter() - started) * 1000
        return EpisodeOutcome(
            task_id=observation.task_id, arm=arm, seed=seed, completion=completion,
            safety_violations=executed_unsafe_effects, stale_effects=0,
            rejected_effects=rejected_effects,
            eligible_recoveries=int(case.corrected is not None),
            successful_recoveries=successful, model_calls=0, model_tokens=0,
            wall_ms=elapsed, outcome_oracle_digest=digest,
            attempted_unsafe_effects=attempted_unsafe_effects,
            executed_unsafe_effects=executed_unsafe_effects,
        )
    finally:
        fabric.close()


def run_paired(seeds: tuple[int, ...] = (0, 1, 2, 3, 4, 5)) -> list[EpisodeOutcome]:
    """Run identical scripted cases under recovery and immediate-abstention arms."""
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("paired seeds must be non-empty and unique")
    return [run_episode(seed, arm=arm) for seed in seeds for arm in ("A0", "A5")]


def main(argv: list[str] | None = None) -> int:
    """Emit a canonical JSON report for consecutive paired scripted cases."""
    from .outcome_report import canonical_report

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=6,
                        help="number of consecutive paired cases (default: 6)")
    parser.add_argument("--out", help="write report to this file instead of stdout")
    args = parser.parse_args(argv)
    if args.seeds <= 0:
        parser.error("--seeds must be positive")
    report = canonical_report(run_paired(tuple(range(args.seeds))))
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(report + "\n")
    else:
        sys.stdout.write(report + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
