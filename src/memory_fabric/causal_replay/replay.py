"""Deterministic replay over immutable evidence with a pure simulator registry."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass, replace
from dataclasses import asdict
from typing import Mapping

from .bayes import BinaryNode
from .intervention import (Intervention, InterventionBatch, ReplacementFixture,
                           SensitivityFixture, compose)
from .state import BeliefState, Observation, update
from .types import (BeliefReference, CaptureResult, InvalidIntervention, ReplayContext,
                    ReplayStatus, SimulatorForbidden, digest_json)

@dataclass(frozen=True)
class DeterministicSimulator:
    """Data-only simulator configuration; replay never calls a caller function."""
    nodes: tuple
    updater_id: str = "exact-enumeration-v1"
    policy_id: str = "investigate-threshold-v1"

    def run(self, items: tuple[Observation, ...]) -> BeliefState:
        return update(self.nodes, items, updater_id=self.updater_id, policy_id=self.policy_id)


@dataclass(frozen=True)
class ReplayResult:
    status: ReplayStatus
    state: BeliefState
    intervention_digest: str
    consumed: int
    complete: bool
    real_actions_executed: bool = False
    intervention_kind: str = "evidence_change"


def replay(observations: tuple[Observation, ...], *,
           intervention: Intervention | InterventionBatch,
           simulator_id: str, simulators: Mapping[str, DeterministicSimulator],
           max_steps: int = 1_000,
           authorized_evidence: tuple[BeliefReference, ...] = ()) -> ReplayResult:
    if type(max_steps) is not int or not 1 <= max_steps <= 100_000:
        raise ValueError("max_steps must be between 1 and 100000")
    handler = simulators.get(simulator_id)
    if type(handler) is not DeterministicSimulator:
        raise SimulatorForbidden("simulator is not registered as a pure local function")
    if (type(handler.nodes) is not tuple
            or any(type(node) is not BinaryNode or type(node.probability_true) is not dict
                   for node in handler.nodes)):
        raise SimulatorForbidden("simulator contains unsupported executable configuration")
    if (type(observations) is not tuple
            or any(type(item) is not Observation for item in observations)):
        raise SimulatorForbidden("replay accepts only an immutable observation tuple")
    if len(observations) > max_steps:
        raise ValueError("replay budget exceeded; no partial result returned")
    if type(intervention) is InterventionBatch:
        validated = compose(intervention.interventions)
        if validated.intervention_id != intervention.intervention_id:
            raise ValueError("intervention batch digest does not match its operations")
        changed, policy_id = _apply_batch(observations, validated, handler.policy_id,
                                          authorized_evidence)
        state = update(handler.nodes, changed, updater_id=handler.updater_id,
                       policy_id=policy_id)
        kind = ("composite" if len(validated.interventions) > 1 else
                _intervention_kind(validated.interventions[0]))
        return ReplayResult(ReplayStatus.EXACT, state, validated.intervention_id,
                            len(changed), True, False, kind)
    if type(intervention) is not Intervention:
        raise SimulatorForbidden("replay accepts only a typed intervention or validated batch")
    compose((intervention,))
    if intervention.operation == "sensitivity":
        fixture = intervention.sensitivity
        if type(fixture) is not SensitivityFixture:
            raise InvalidIntervention("model sensitivity fixture is missing")
        changed_nodes = []
        found = False
        for node in handler.nodes:
            if node.name != fixture.node_name:
                changed_nodes.append(node)
                continue
            if fixture.parent_assignment not in node.probability_true:
                raise InvalidIntervention("sensitivity parent assignment is not in the model")
            table = dict(node.probability_true)
            table[fixture.parent_assignment] = fixture.probability_true
            changed_nodes.append(BinaryNode(node.name, node.parents, table))
            found = True
        if not found:
            raise InvalidIntervention("sensitivity node is not in the model")
        state = update(tuple(changed_nodes), observations,
                       updater_id=handler.updater_id, policy_id=handler.policy_id)
        return ReplayResult(ReplayStatus.EXACT, state, intervention.intervention_id,
                            len(observations), True, False, "model_assumption_change")
    operation = intervention.operation
    if operation == "noop":
        changed = observations
        policy_id = handler.policy_id
    elif operation in {"suppress", "replace", "delay", "withhold"}:
        target = intervention.target
        if target is None:
            raise ValueError("evidence intervention requires a target")
        matches = [i for i, o in enumerate(observations)
                   if o.observation_id == target.belief_id]
        if len(matches) != 1:
            raise ValueError("intervention target is missing or ambiguous")
        index = matches[0]
        items = list(observations)
        policy_id = handler.policy_id
        if operation == "suppress":
            items.pop(index)
        elif operation == "withhold":
            if (type(authorized_evidence) is not tuple
                    or any(type(ref) is not BeliefReference for ref in authorized_evidence)
                    or target not in authorized_evidence):
                raise SimulatorForbidden("withhold target must come from authorized capture")
            if (intervention.window_start is None or intervention.window_end is None
                    or not intervention.window_start <= items[index].sequence
                    <= intervention.window_end):
                pass
            else:
                items.pop(index)
        elif operation == "replace":
            replacement = intervention.replacement
            if (type(replacement) is not ReplacementFixture
                    or replacement.observation.observation_id != target.belief_id
                    or replacement.observation.sequence != items[index].sequence):
                raise ValueError("replacement must be a target-matched frozen fixture")
            items[index] = replacement.observation
        else:
            if intervention.delay_until is None:
                raise ValueError("delay sequence is missing")
            if intervention.delay_until <= items[index].sequence:
                raise ValueError("delay sequence must be later than the observation")
            items[index] = replace(items[index], sequence=intervention.delay_until)
        changed = tuple(sorted(items, key=lambda o: (o.sequence, o.observation_id)))
    elif operation == "swap_policy":
        if intervention.policy_id is None:
            raise ValueError("policy id is missing")
        changed = observations
        policy_id = intervention.policy_id
    else:
        raise ValueError("this replay runner accepts evidence interventions only")
    state = update(handler.nodes, changed, updater_id=handler.updater_id, policy_id=policy_id)
    factual = handler.run(observations)
    if operation == "noop" and state.fingerprint != factual.fingerprint:
        return ReplayResult(ReplayStatus.NON_REPLAYABLE, state, intervention.intervention_id,
                            len(changed), False, False)
    return ReplayResult(ReplayStatus.EXACT, state, intervention.intervention_id,
                        len(changed), True, False, _intervention_kind(intervention))


def _intervention_kind(intervention: Intervention) -> str:
    if intervention.operation == "noop":
        return "null_intervention"
    if intervention.operation == "swap_policy":
        return "policy_change"
    if intervention.operation == "sensitivity":
        return "model_assumption_change"
    return "evidence_change"


def _apply_batch(observations: tuple[Observation, ...], batch: InterventionBatch,
                 default_policy_id: str,
                 authorized_evidence: tuple[BeliefReference, ...]
                 ) -> tuple[tuple[Observation, ...], str]:
    """Apply a prevalidated, non-overlapping batch to disposable trace data."""
    changed = list(observations)
    policy_id: str | None = None
    for action in batch.interventions:
        if action.operation == "noop":
            continue
        if action.operation == "swap_policy":
            policy_id = action.policy_id
            continue
        target = action.target
        if target is None:
            raise ValueError("batch evidence operation requires a target")
        matches = [index for index, item in enumerate(changed)
                   if item.observation_id == target.belief_id]
        if len(matches) != 1:
            raise ValueError("batch target is missing or ambiguous")
        index = matches[0]
        if action.operation == "suppress":
            changed.pop(index)
        elif action.operation == "withhold":
            if (type(authorized_evidence) is not tuple
                    or any(type(ref) is not BeliefReference for ref in authorized_evidence)
                    or target not in authorized_evidence):
                raise SimulatorForbidden("withhold target must come from authorized capture")
            if action.window_start is None or action.window_end is None:
                raise ValueError("withhold interval is missing")
            if action.window_start <= changed[index].sequence <= action.window_end:
                changed.pop(index)
        elif action.operation == "delay":
            if action.delay_until is None or action.delay_until <= changed[index].sequence:
                raise ValueError("batch delay must be later than the original sequence")
            changed[index] = replace(changed[index], sequence=action.delay_until)
        elif action.operation == "replace":
            fixture = action.replacement
            if (type(fixture) is not ReplacementFixture
                    or fixture.observation.observation_id != target.belief_id
                    or fixture.observation.sequence != changed[index].sequence):
                raise ValueError("batch replacement must match target and original sequence")
            changed[index] = fixture.observation
        else:
            raise ValueError("unsupported operation in intervention batch")
    return tuple(sorted(changed, key=lambda item: (item.sequence, item.observation_id))), \
        policy_id or default_policy_id


def replay_captured(fabric, session, capture_result: CaptureResult,
                    observations: tuple[Observation, ...], *,
                    intervention: Intervention | InterventionBatch,
                    simulator_id: str,
                    simulators: Mapping[str, DeterministicSimulator],
                    max_steps: int = 1_000) -> ReplayResult:
    """Revalidate historical capture/current authority before source-scoped replay."""
    from .capture import capture

    if (type(capture_result) is not CaptureResult or not capture_result.complete
            or not capture_result.archival_only
            or not capture_result.historical_snapshot_only
            or not capture_result.source_currently_admissible
            or capture_result.source_head > fabric.log.head_seq):
        raise SimulatorForbidden("withheld sources require a complete authorized capture")
    body = {"schema": capture_result.schema,
        "principal": capture_result.principal_id, "tenant": capture_result.tenant_id,
        "known_at": capture_result.known_at, "valid_at": capture_result.valid_at,
        "source_head": capture_result.source_head,
        "evidence": [{"id": ref.belief_id, "version": ref.version,
            "digest": ref.digest} for ref in capture_result.evidence],
        "decision": asdict(capture_result.decision) if capture_result.decision else None,
        "trace": [asdict(item) for item in capture_result.trace]}
    if digest_json(body) != capture_result.factual_digest:
        raise SimulatorForbidden("historical capture digest is invalid")
    current = capture(fabric, session, [ref.belief_id for ref in capture_result.evidence],
        context=ReplayContext(capture_result.known_at, valid_at=capture_result.valid_at,
                              max_events=100_000), decision=capture_result.decision)
    if (current.evidence != capture_result.evidence
            or current.principal_id != capture_result.principal_id
            or current.tenant_id != capture_result.tenant_id
            or current.trace != capture_result.trace):
        raise SimulatorForbidden("historical capture is no longer authorized")
    ids = {item.observation_id for item in observations}
    evidence_ids = {ref.belief_id for ref in current.evidence}
    if ids != evidence_ids or len(ids) != len(observations):
        raise SimulatorForbidden("observation trace does not map to captured evidence")
    return replay(observations, intervention=intervention, simulator_id=simulator_id,
        simulators=simulators, max_steps=max_steps, authorized_evidence=current.evidence)


def deterministic_simulator(nodes, *, updater_id: str = "exact-enumeration-v1",
                            policy_id: str = "investigate-threshold-v1") -> DeterministicSimulator:
    frozen = tuple(nodes)
    if any(type(node) is not BinaryNode or type(node.probability_true) is not dict
           for node in frozen):
        raise SimulatorForbidden("only built-in BinaryNode data is supported")
    if not updater_id or not policy_id:
        raise ValueError("updater and policy identifiers are required")
    return DeterministicSimulator(frozen, updater_id, policy_id)
