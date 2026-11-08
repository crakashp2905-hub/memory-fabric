"""Bounded deterministic replay from a complete local observation trace."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass, replace
import hashlib
import inspect
import json
from typing import Any, Mapping

from .bayes import BinaryNode, enumerate_posterior, marginal
from .policy import ThresholdPolicy
from .replay import DeterministicSimulator
from .scheduler import dependency_frontier
from .state import BeliefState, Observation, update
from .types import (BudgetExceeded, DecisionRecord, NonReplayable, ReplayStatus,
                    SimulatorForbidden, canonical_json, digest_json)

OBSERVATION_ADAPTER_ID = "memory-fabric-boolean-observation-json-v1"


@dataclass(frozen=True)
class ReplayStep:
    sequence: int
    observation_id: str | None
    belief_fingerprint: str
    proposal: str
    proposal_digest: str


@dataclass(frozen=True)
class ReplayExecution:
    status: ReplayStatus
    steps: tuple[ReplayStep, ...]
    final_state: BeliefState
    consumed: int
    complete: bool
    first_divergence: int | None = None
    rng_applicability: str = "not_applicable_deterministic_engine"
    real_actions_executed: bool = False
    source_observations: tuple[Observation, ...] = ()
    execution_kind: str = "policy_reexecution"
    source_adapter_id: str = ""
    source_adapter_digest: str = ""


@dataclass(frozen=True)
class ExecutionCheckpoint:
    """Verified local continuation point; contains no authorization to use evidence."""
    schema: str
    prefix: tuple[Observation, ...]
    steps: tuple[ReplayStep, ...]
    state_fingerprint: str
    simulator_digest: str
    policy_digest: str
    checkpoint_digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "prefix": [item.__dict__ for item in self.prefix],
            "steps": [item.__dict__ for item in self.steps],
            "state_fingerprint": self.state_fingerprint,
            "simulator_digest": self.simulator_digest,
            "policy_digest": self.policy_digest,
        }


@dataclass(frozen=True)
class StepInterventionComparison:
    """Local CAR-inspired step contrast; not an official CAR reproduction."""
    target_observation_id: str
    factual: ReplayExecution
    counterfactual: ReplayExecution
    method: str = "local_step_suppression_full_suffix_replay"
    limitations: tuple[str, ...] = (
        "agent_internal_only", "deterministic_registered_policy_only",
        "physical_world_effect_not_established", "not_official_car_reproduction")


def execute_step_intervention(observations: tuple[Observation, ...], *,
                              target_observation_id: str,
                              simulator: DeterministicSimulator,
                              policy: ThresholdPolicy,
                              max_events: int = 1_000) -> StepInterventionComparison:
    """Suppress one evidence step and replay the full dependent suffix locally."""
    if (type(observations) is not tuple
            or any(type(item) is not Observation for item in observations)
            or not isinstance(target_observation_id, str) or not target_observation_id):
        raise NonReplayable("step intervention requires a typed trace and target ID")
    positions = [index for index, item in enumerate(observations)
                 if item.observation_id == target_observation_id]
    if len(positions) != 1:
        raise NonReplayable("step intervention target must occur exactly once")
    factual = execute(observations, simulator=simulator, policy=policy,
                      max_events=max_events)
    counterfactual_observations = tuple(item for item in observations
                                        if item.observation_id != target_observation_id)
    affected_index = min(positions[0], len(counterfactual_observations))
    counterfactual = execute_full_suffix(counterfactual_observations,
        affected_index=affected_index, simulator=simulator, policy=policy,
        max_events=max_events)
    if (not factual.complete or factual.status is not ReplayStatus.EXACT
            or not counterfactual.complete or counterfactual.status is not ReplayStatus.EXACT):
        raise NonReplayable("step intervention did not produce two exact complete traces")
    return StepInterventionComparison(target_observation_id, factual, counterfactual)


def create_execution_checkpoint(execution: ReplayExecution, *,
                                simulator: DeterministicSimulator,
                                policy: ThresholdPolicy) -> ExecutionCheckpoint:
    """Create an integrity-bound continuation point from an exact replay prefix."""
    if type(execution) is not ReplayExecution or not execution.complete or execution.status.value != "EXACT":
        raise NonReplayable("only complete exact replay can be checkpointed")
    prefix = execution.source_observations
    simulator_digest = digest_json({"nodes": [
        {"name": node.name, "parents": node.parents,
         "probability_true": sorted((repr(key), value)
                                    for key, value in node.probability_true.items())}
        for node in simulator.nodes], "updater_id": simulator.updater_id})
    policy_digest = policy.implementation_digest
    payload = {"schema": "memory-fabric-cdm-v1", "prefix": [item.__dict__ for item in prefix],
        "steps": [item.__dict__ for item in execution.steps],
        "state_fingerprint": execution.final_state.fingerprint,
        "simulator_digest": simulator_digest, "policy_digest": policy_digest}
    return ExecutionCheckpoint("memory-fabric-cdm-v1", prefix, execution.steps,
        execution.final_state.fingerprint, simulator_digest, policy_digest, digest_json(payload))


def execute_from_checkpoint(checkpoint: ExecutionCheckpoint,
                            suffix: tuple[Observation, ...], *,
                            simulator: DeterministicSimulator,
                            policy: ThresholdPolicy, max_events: int = 1_000,
                            verify_prefix: bool = True) -> ReplayExecution:
    """Continue from a digest-checked prefix and fail closed on any mismatch."""
    if type(checkpoint) is not ExecutionCheckpoint or type(suffix) is not tuple:
        raise NonReplayable("unsupported checkpoint or suffix")
    if checkpoint.schema != "memory-fabric-cdm-v1":
        raise NonReplayable("checkpoint schema cannot be resolved")
    simulator_digest = digest_json({"nodes": [
        {"name": node.name, "parents": node.parents,
         "probability_true": sorted((repr(key), value)
                                    for key, value in node.probability_true.items())}
        for node in simulator.nodes], "updater_id": simulator.updater_id})
    payload = checkpoint.payload()
    if (checkpoint.checkpoint_digest != digest_json(payload)
            or checkpoint.simulator_digest != simulator_digest
            or checkpoint.policy_digest != policy.implementation_digest):
        raise NonReplayable("checkpoint integrity or implementation binding failed")
    if verify_prefix:
        prefix_result = execute(checkpoint.prefix, simulator=simulator, policy=policy,
                                max_events=max_events)
        if (not prefix_result.complete
                or prefix_result.final_state.fingerprint != checkpoint.state_fingerprint
                or prefix_result.steps != checkpoint.steps):
            raise NonReplayable("checkpoint prefix does not reproduce exactly")
    all_observations = (*checkpoint.prefix, *suffix)
    if len(all_observations) > max_events:
        raise BudgetExceeded("trace exceeds event budget; partial replay refused")
    suffix_ids = {item.observation_id for item in suffix if type(item) is Observation}
    result = execute(all_observations, simulator=simulator, policy=policy, max_events=max_events)
    if not result.complete:
        return result
    suffix_steps = tuple(step for step in result.steps if step.observation_id in suffix_ids)
    return ReplayExecution(result.status, checkpoint.steps + suffix_steps, result.final_state,
                           result.consumed,
                           result.complete, result.first_divergence, result.rng_applicability,
                           result.real_actions_executed, result.source_observations)


def execute_full_suffix(observations: tuple[Observation, ...], *, affected_index: int,
                        simulator: DeterministicSimulator, policy: ThresholdPolicy,
                        max_events: int = 1_000) -> ReplayExecution:
    """Correctness baseline that replays every event from the affected index onward.

    The unchanged prefix is independently replayed into a checkpoint and then
    revalidated by ``execute_from_checkpoint``. This deliberately favors
    correctness and reproducibility over avoiding prefix work; selective replay
    implementations can compare their result against this full-suffix oracle.
    """
    if (type(observations) is not tuple
            or any(type(item) is not Observation for item in observations)
            or type(affected_index) is not int
            or not 0 <= affected_index <= len(observations)):
        raise NonReplayable("full-suffix baseline requires a typed trace and valid affected index")
    if len(observations) > max_events:
        raise BudgetExceeded("trace exceeds event budget; partial replay refused")
    prefix = execute(observations[:affected_index], simulator=simulator,
                     policy=policy, max_events=max_events)
    if not prefix.complete or prefix.status is not ReplayStatus.EXACT:
        raise NonReplayable("unchanged prefix is not an exact replay")
    checkpoint = create_execution_checkpoint(prefix, simulator=simulator, policy=policy)
    result = execute_from_checkpoint(checkpoint, observations[affected_index:],
        simulator=simulator, policy=policy, max_events=max_events, verify_prefix=True)
    return ReplayExecution(result.status, result.steps, result.final_state, result.consumed,
        result.complete, result.first_divergence, result.rng_applicability,
        result.real_actions_executed, result.source_observations, "full_suffix_oracle")


def execute_dependency_frontier(observations: tuple[Observation, ...], *,
                                baseline: ReplayExecution,
                                target_observation_id: str,
                                dependencies: Mapping[str, tuple[str, ...]],
                                dependencies_complete: bool,
                                simulator: DeterministicSimulator,
                                policy: ThresholdPolicy,
                                max_events: int = 1_000) -> ReplayExecution:
    """Recompute only certified affected proposals; keep full-trace state exact.

    The caller supplies the complete counterfactual observation trace and an
    exact factual execution. Only the target may differ or be suppressed. A
    complete dependency graph defines which proposals need recomputation;
    fingerprints are rebuilt for every retained event because they bind the
    entire trace prefix. Unknown graph completeness falls back to exhaustive
    replay. A complete-but-semantically-inaccurate graph violates the caller's
    precondition and can reuse a stale proposal; verify this routine against
    ``execute`` when registering any dependency adapter.
    """
    if (type(observations) is not tuple or type(baseline) is not ReplayExecution
            or not isinstance(target_observation_id, str) or not target_observation_id
            or type(dependencies_complete) is not bool
            or type(max_events) is not int or not 1 <= max_events <= 100_000
            or not isinstance(simulator, DeterministicSimulator)
            or not isinstance(policy, ThresholdPolicy)):
        raise NonReplayable("dependency replay arguments are invalid")
    if any(type(item) is not Observation for item in observations):
        raise SimulatorForbidden("dependency replay requires immutable typed observations")
    if len(observations) > max_events:
        raise BudgetExceeded("trace exceeds event budget; partial replay refused")
    factual = baseline.source_observations
    if (not baseline.complete or baseline.status is not ReplayStatus.EXACT
            or baseline.final_state.updater_id != simulator.updater_id
            or baseline.final_state.policy_id != policy.policy_id
            or len({item.observation_id for item in factual}) != len(factual)):
        raise NonReplayable("dependency replay requires a compatible exact baseline")
    if baseline.final_state.fingerprint != update(simulator.nodes, factual,
            updater_id=simulator.updater_id, policy_id=policy.policy_id).fingerprint:
        raise NonReplayable("baseline final state does not match its source observations")
    original_ids = tuple(item.observation_id for item in factual)
    if (not original_ids or tuple(sorted(factual, key=lambda item: (item.sequence,
            item.observation_id))) != factual
            or len(baseline.steps) != len(factual)
            or tuple(step.observation_id for step in baseline.steps) != original_ids):
        raise NonReplayable("baseline steps do not bind the full ordered source trace")
    positions = [index for index, item in enumerate(factual)
                 if item.observation_id == target_observation_id]
    if len(positions) != 1:
        raise NonReplayable("dependency replay target must occur exactly once in baseline")
    changed_by_id = {item.observation_id: item for item in observations}
    if len(changed_by_id) != len(observations) or not set(changed_by_id) <= set(original_ids):
        raise NonReplayable("counterfactual trace has duplicate or unknown event IDs")
    original_by_id = {item.observation_id: item for item in factual}
    for event_id, original in original_by_id.items():
        if event_id != target_observation_id and changed_by_id.get(event_id) != original:
            raise NonReplayable("only the declared target may change in dependency replay")
    target = original_by_id[target_observation_id]
    changed_target = changed_by_id.get(target_observation_id)
    if (changed_target is not None and changed_target.sequence != target.sequence):
        raise NonReplayable("dependency frontier does not support sequence reordering")
    ordered = tuple(sorted(observations, key=lambda item: (item.sequence, item.observation_id)))
    if not dependencies_complete:
        exhaustive = execute(ordered, simulator=simulator, policy=policy,
                             max_events=max_events)
        return ReplayExecution(exhaustive.status, exhaustive.steps, exhaustive.final_state,
            exhaustive.consumed, exhaustive.complete, exhaustive.first_divergence,
            exhaustive.rng_applicability, exhaustive.real_actions_executed,
            exhaustive.source_observations, "dependency_frontier_incomplete_fallback")

    frontier = set(dependency_frontier(original_ids, target_observation_id,
        dependencies=dependencies, dependencies_complete=True))
    affected_retained = frontier & set(changed_by_id)
    baseline_steps = {step.observation_id: step for step in baseline.steps}
    steps: list[ReplayStep] = []
    prefix: list[Observation] = []
    for item in ordered:
        prefix.append(item)
        state = update(simulator.nodes, tuple(prefix), updater_id=simulator.updater_id,
                       policy_id=policy.policy_id)
        old_step = baseline_steps[item.observation_id]
        if item.observation_id in affected_retained:
            proposal = policy.propose(state)
            if proposal.selected is None:
                raise NonReplayable("deterministic policy abstained during frontier replay")
            selected = proposal.selected
            proposal_digest = digest_json({"selected": selected,
                "probabilities": proposal.probabilities, "policy": policy.policy_id})
        else:
            selected = old_step.proposal
            proposal_digest = old_step.proposal_digest
        steps.append(ReplayStep(item.sequence, item.observation_id, state.fingerprint,
                                selected, proposal_digest))
    final_state = update(simulator.nodes, ordered, updater_id=simulator.updater_id,
                         policy_id=policy.policy_id)
    return ReplayExecution(ReplayStatus.EXACT, tuple(steps), final_state,
        len(affected_retained), True, source_observations=ordered,
        execution_kind="dependency_frontier_replay")


def execute(observations: tuple[Observation, ...], *, simulator: DeterministicSimulator,
            policy: ThresholdPolicy, max_events: int = 1_000,
            expected_fingerprint: str | None = None) -> ReplayExecution:
    """Run generic deterministic replay without claiming recorded-decision provenance."""
    return _execute(observations, simulator=simulator, policy=policy,
        max_events=max_events, expected_fingerprint=expected_fingerprint,
        decision_record=None)


def _execute(observations: tuple[Observation, ...], *, simulator: DeterministicSimulator,
             policy: ThresholdPolicy, max_events: int,
             expected_fingerprint: str | None,
             decision_record: DecisionRecord | None) -> ReplayExecution:
    if type(max_events) is not int or not 1 <= max_events <= 100_000:
        raise ValueError("max_events must be between 1 and 100000")
    if (type(observations) is not tuple
            or any(type(item) is not Observation for item in observations)):
        raise SimulatorForbidden("replay requires an explicit immutable observation trace")
    if len(observations) > max_events:
        raise BudgetExceeded("trace exceeds event budget; partial replay refused")
    if type(observations) is tuple and len({item.observation_id for item in observations
                                            if type(item) is Observation}) != len(observations):
        raise NonReplayable("duplicate observation IDs make trace order ambiguous")
    if type(simulator) is not DeterministicSimulator:
        raise NonReplayable("unsupported simulator configuration")
    if type(policy) is not ThresholdPolicy:
        raise SimulatorForbidden("only the built-in data-only decision policy is supported")
    if decision_record is not None and (
            type(decision_record) is not DecisionRecord
            or policy.policy_id != decision_record.policy_id
            or policy.implementation_digest != decision_record.policy_digest):
        raise NonReplayable("recorded policy implementation cannot be resolved exactly")
    if (type(simulator.nodes) is not tuple
            or any(type(node) is not BinaryNode or type(node.probability_true) is not dict
                   for node in simulator.nodes)):
        raise SimulatorForbidden("simulator contains unsupported executable configuration")
    ordered = tuple(sorted(observations, key=lambda item: (item.sequence, item.observation_id)))
    steps: list[ReplayStep] = []
    unique: dict[tuple[str, str], Observation] = {}
    evidence: dict[str, bool] = {}
    conflicts: set[str] = set()
    admitted: list[Observation] = []
    hash_state = _trace_hash_prefix(conflicts, admitted)
    current_fingerprint = ""
    update_policy_digest = digest_json({"updater_id": simulator.updater_id,
        "policy_id": policy.policy_id, "implementation": "exact-enumeration-v1"})
    for observation in ordered:
        key = (observation.origin, observation.variable)
        if key not in unique:
            unique[key] = observation
            admitted.append(observation)
            previous_conflicts = frozenset(conflicts)
            if observation.variable in evidence and evidence[observation.variable] != observation.value:
                conflicts.add(observation.variable)
            else:
                evidence.setdefault(observation.variable, observation.value)
            if previous_conflicts != frozenset(conflicts):
                hash_state = _trace_hash_prefix(conflicts, admitted)
            else:
                _append_trace_observation(hash_state, observation, len(admitted) - 1)
        conditioned = {name: value for name, value in evidence.items()
                       if name not in conflicts}
        distribution = enumerate_posterior(simulator.nodes, conditioned)
        posterior = {node.name: marginal(distribution, node.name)
                     for node in simulator.nodes}
        current_fingerprint = _finish_trace_fingerprint(hash_state, posterior,
            conflicts, simulator.updater_id, policy.policy_id, update_policy_digest)
        # ThresholdPolicy depends only on the posterior; omitting the growing
        # observation tuple here avoids quadratic context allocation.
        state = BeliefState("memory-fabric-cdm-v1", simulator.updater_id,
            policy.policy_id, (), posterior, tuple(sorted(conflicts)),
            current_fingerprint, (), update_policy_digest)
        proposal = policy.propose(state)
        if decision_record is not None and proposal.selected not in decision_record.options:
            raise NonReplayable("replay proposal is outside the original decision options")
        if proposal.selected is None:
            raise NonReplayable("deterministic policy abstained without a recorded proposal")
        steps.append(ReplayStep(observation.sequence, observation.observation_id,
                                state.fingerprint, proposal.selected,
                                digest_json({"selected": proposal.selected,
                                             "probabilities": proposal.probabilities,
                                             "policy": policy.policy_id})))
    final_state = update(simulator.nodes, ordered, updater_id=simulator.updater_id,
                         policy_id=policy.policy_id)
    if ordered and current_fingerprint != final_state.fingerprint:
        raise NonReplayable("incremental trace commitment disagrees with canonical state")
    if expected_fingerprint is not None and final_state.fingerprint != expected_fingerprint:
        return ReplayExecution(ReplayStatus.NON_REPLAYABLE, tuple(steps), final_state,
                               len(ordered), False, rng_applicability="not_applicable",
                               source_observations=ordered)
    return ReplayExecution(ReplayStatus.EXACT, tuple(steps), final_state, len(ordered), True,
                           source_observations=ordered)


def _trace_hash_prefix(conflicts: set[str], admitted: list[Observation]):
    """Build a streaming SHA-256 prefix for the canonical state payload."""
    prefix = canonical_json({"conflicts": sorted(conflicts)})[:-1]
    hasher = hashlib.sha256((prefix + ',"observations":[').encode("utf-8"))
    for index, observation in enumerate(admitted):
        if index:
            hasher.update(b",")
        hasher.update(canonical_json(observation.__dict__).encode("utf-8"))
    return hasher


def _append_trace_observation(hasher: Any, observation: Observation, index: int) -> None:
    """Append one newly admitted, already sequence-ordered observation."""
    if index:
        hasher.update(b",")
    hasher.update(canonical_json(observation.__dict__).encode("utf-8"))


def _finish_trace_fingerprint(hasher: Any, posterior: dict[str, float],
        conflicts: set[str], updater_id: str, policy_id: str,
        update_policy_digest: str) -> str:
    suffix = canonical_json({"policy": policy_id, "posterior": posterior,
        "schema": "memory-fabric-cdm-v1", "update_policy_digest": update_policy_digest,
        "updater": updater_id})
    final = hasher.copy()
    final.update(b"],")
    final.update(suffix[1:].encode("utf-8"))
    return final.hexdigest()


def execute_recorded(fabric: Any, observations: tuple[Observation, ...], *,
                     simulator: DeterministicSimulator, policy: ThresholdPolicy,
                     decision_record: DecisionRecord, max_events: int = 1_000,
                     expected_fingerprint: str | None = None) -> ReplayExecution:
    """Re-execute the local policy only when its original receipt resolves."""
    from .capture import verify_decision_record

    if not verify_decision_record(fabric, decision_record):
        raise NonReplayable("decision record has no valid immutable event receipt")
    if decision_record.rng_applicability == "missing_state_non_replayable":
        raise NonReplayable("the original decision's RNG continuation state is unavailable")
    if decision_record.tool_observations:
        raise NonReplayable("tool/environment observations lack a registered pure replay handler")
    return _execute(observations, simulator=simulator, policy=policy,
        max_events=max_events, expected_fingerprint=expected_fingerprint,
        decision_record=decision_record)


def _adapt_boolean_observation_json(memory_id: str, version: int,
                                    content: str, sequence: int) -> Observation:
    """Parse the closed v1 content format into one immutable boolean observation."""
    try:
        value = json.loads(content)
    except (TypeError, ValueError) as exc:
        raise NonReplayable("authorized content does not match a registered observation format") from exc
    if (type(value) is not dict or canonical_json(value) != content
            or set(value) != {"schema", "variable", "value"}
            or value.get("schema") != "memory-fabric-observation-v1"
            or not isinstance(value.get("variable"), str) or not value["variable"]
            or type(value.get("value")) is not bool):
        raise NonReplayable("authorized content does not match a registered observation format")
    return Observation(memory_id, value["variable"], value["value"],
                       f"{memory_id}@v{version}", sequence)


def _observation_adapter_digest() -> str:
    """Commit to the exact local adapter implementation and input contract."""
    material = {"adapter_id": OBSERVATION_ADAPTER_ID,
        "implementation_sha256": hashlib.sha256(
            inspect.getsource(_adapt_boolean_observation_json).encode("utf-8")).hexdigest(),
        "schema": "memory-fabric-observation-v1",
        "fields": ["schema", "variable", "value"]}
    return digest_json(material)


def execute_captured(fabric: Any, session: Any, capture_result: Any,
                     observations: tuple[Observation, ...] | None = None, *,
                     adapter_id: str,
                     simulator: DeterministicSimulator, policy: ThresholdPolicy,
                     decision_record: DecisionRecord,
                     max_events: int = 1_000) -> ReplayExecution:
    """Replay observations deterministically materialized from authorized history."""
    from .capture import _materialize_capture, verify_decision_record
    from .types import CaptureResult

    if (type(capture_result) is not CaptureResult or not capture_result.complete
            or not capture_result.archival_only
            or not capture_result.historical_snapshot_only
            or not capture_result.source_currently_admissible
            or capture_result.decision != decision_record
            or capture_result.source_head > fabric.log.head_seq):
        raise NonReplayable("authorized historical capture is unavailable")
    if (type(decision_record) is not DecisionRecord
            or not verify_decision_record(fabric, decision_record)):
        raise NonReplayable("recorded decision receipt cannot be verified")
    if adapter_id != OBSERVATION_ADAPTER_ID:
        raise NonReplayable("observation adapter is not registered")
    if (type(decision_record) is not DecisionRecord
            or not verify_decision_record(fabric, decision_record)):
        raise NonReplayable("recorded decision receipt cannot be verified")
    try:
        materialized = _materialize_capture(fabric, session, capture_result)
    except Exception as exc:
        raise NonReplayable("historical capture is no longer currently authorized") from exc
    expected_refs = decision_record.evidence
    if (not expected_refs or any((ref.belief_id, ref.version) not in materialized
                                for ref in expected_refs)):
        raise NonReplayable("decision evidence is outside the authorized historical capture")
    derived = tuple(_adapt_boolean_observation_json(ref.belief_id, ref.version,
        *materialized[(ref.belief_id, ref.version)]) for ref in expected_refs)
    if observations is not None:
        if (type(observations) is not tuple
                or any(type(item) is not Observation for item in observations)
                or observations != derived):
            raise NonReplayable("caller observations differ from registered historical materialization")
    execution = execute_recorded(fabric, derived, simulator=simulator, policy=policy,
        decision_record=decision_record, max_events=max_events)
    return replace(execution, source_adapter_id=adapter_id,
                   source_adapter_digest=_observation_adapter_digest())


def first_divergence(factual: ReplayExecution, counterfactual: ReplayExecution) -> int | None:
    """Return the first sequence whose state or proposal differs."""
    for left, right in zip(factual.steps, counterfactual.steps):
        if (left.belief_fingerprint, left.proposal) != (right.belief_fingerprint, right.proposal):
            return min(left.sequence, right.sequence)
    if len(factual.steps) != len(counterfactual.steps):
        longer = factual.steps if len(factual.steps) > len(counterfactual.steps) else counterfactual.steps
        return longer[min(len(factual.steps), len(counterfactual.steps))].sequence
    return None
