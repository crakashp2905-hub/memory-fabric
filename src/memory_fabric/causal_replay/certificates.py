"""Content-addressed replay certificates; verification grants no authority."""

from __future__ import annotations

__stability__ = "experimental"

import re
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from typing import Any

from .policy import ThresholdPolicy
from .types import CDMError, NonReplayable, ReplayStatus, SCHEMA, canonical_json, digest_json


class ExplanationStatus(StrEnum):
    EXACT = "EXACT"
    APPROXIMATE = "APPROXIMATE"
    UNDEFINED_CONTINUATION = "UNDEFINED_CONTINUATION"
    ERASED = "ERASED"
    UNAUTHORIZED = "UNAUTHORIZED"
    NON_REPLAYABLE = "NON_REPLAYABLE"


class WorldSemantics(StrEnum):
    AGENT_INTERNAL = "agent_internal"
    SIMULATOR = "simulator_world"
    PHYSICAL_UNSUPPORTED = "physical_counterfactual_unsupported"


class Estimand(StrEnum):
    NONE = "none"
    DECISION_FLIP = "policy_decision_flip"
    TOTAL_VARIATION = "option_distribution_total_variation"
    UTILITY_DIFFERENCE = "simulator_utility_difference"


class MinimalityClaim(StrEnum):
    NONE = "none"
    SUFFICIENT = "verified_sufficient_subset"
    INCLUSION_MINIMAL = "inclusion_minimal"
    CARDINALITY_MINIMUM = "cardinality_minimum"


@dataclass(frozen=True)
class ReplayCertificate:
    schema: str
    capture_digest: str
    intervention_digest: str
    factual_fingerprint: str
    counterfactual_fingerprint: str
    updater_id: str
    policy_id: str
    status: str
    proposal_changed: bool
    claims: tuple[str, ...]
    certificate_digest: str
    action_entitlement: bool = False
    estimand: str = Estimand.DECISION_FLIP.value
    world_semantics: str = WorldSemantics.SIMULATOR.value
    minimality_claim: str = MinimalityClaim.NONE.value
    minimality_proof_digest: str | None = None
    limitations: tuple[str, ...] = (
        "no_action_entitlement", "physical_world_not_verified",
        "local_synthetic_or_simulator_evidence")

    def payload(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_digest")
        return data

    def to_json(self) -> str:
        return canonical_json({**self.payload(), "certificate_digest": self.certificate_digest})


def issue(*, capture_digest: str, intervention_digest: str, factual_fingerprint: str,
          counterfactual_fingerprint: str, updater_id: str, policy_id: str,
          status: str, factual_proposal: str | None,
          counterfactual_proposal: str | None, complete: bool,
          estimand: str = Estimand.DECISION_FLIP.value,
          world_semantics: str = WorldSemantics.SIMULATOR.value,
          minimality_claim: str = MinimalityClaim.NONE.value,
          minimality_proof_digest: str | None = None,
          limitations: tuple[str, ...] = (
              "no_action_entitlement", "physical_world_not_verified",
              "local_synthetic_or_simulator_evidence"),
          minimality_verification: Any = None) -> ReplayCertificate:
    try:
        explanation_status = ExplanationStatus(status)
        estimand = Estimand(estimand).value
        world_semantics = WorldSemantics(world_semantics).value
        minimality_claim = MinimalityClaim(minimality_claim).value
    except ValueError as exc:
        raise CDMError("unknown certificate status or claim class") from exc
    if explanation_status is ExplanationStatus.EXACT and not complete:
        raise CDMError("incomplete replay cannot receive EXACT status")
    for value in (capture_digest, intervention_digest, factual_fingerprint,
                  counterfactual_fingerprint):
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise CDMError("certificate digests must be SHA-256")
    if minimality_claim != MinimalityClaim.NONE.value:
        from .verifier import MinimalityVerification
        if (type(minimality_verification) is not MinimalityVerification
                or not minimality_verification.verified
                or minimality_verification.code != "VERIFIED"
                or minimality_verification.claim != minimality_claim
                or minimality_verification.proof_digest != minimality_proof_digest):
            raise CDMError("minimality claim requires a matching independently verified proof")
    elif minimality_proof_digest is not None:
        raise CDMError("proof digest supplied without a minimality claim")
    required_limitations = {"no_action_entitlement", "physical_world_not_verified"}
    if (type(limitations) is not tuple or not limitations
            or any(type(item) is not str or not item for item in limitations)
            or len(set(limitations)) != len(limitations)
            or not required_limitations.issubset(limitations)):
        raise CDMError("certificate limitations must be explicit and include authority and world bounds")
    changed = factual_proposal != counterfactual_proposal
    if explanation_status is not ExplanationStatus.EXACT:
        changed = False
    payload = {"schema": SCHEMA, "capture_digest": capture_digest,
        "intervention_digest": intervention_digest, "factual_fingerprint": factual_fingerprint,
        "counterfactual_fingerprint": counterfactual_fingerprint, "updater_id": updater_id,
        "policy_id": policy_id, "status": explanation_status.value, "proposal_changed": changed,
        "claims": ("caused_internal_decision_change",) if changed else (),
        "action_entitlement": False, "estimand": estimand,
        "world_semantics": world_semantics, "minimality_claim": minimality_claim,
        "minimality_proof_digest": minimality_proof_digest,
        "limitations": limitations}
    return ReplayCertificate(SCHEMA, capture_digest, intervention_digest, factual_fingerprint,
        counterfactual_fingerprint, updater_id, policy_id, explanation_status.value, changed,
        ("caused_internal_decision_change",) if changed else (), digest_json(payload), False,
        estimand, world_semantics, minimality_claim, minimality_proof_digest,
        limitations)


def issue_verified_recorded_replay(*, fabric: Any, decision_record: Any,
        factual_observations: tuple[Any, ...], intervention: Any,
        simulator: Any, policy: Any, session: Any, capture_result: Any,
        capture_digest: str, intervention_digest: str,
        updater_id: str, policy_id: str,
        estimand: str = Estimand.DECISION_FLIP.value,
        world_semantics: str = WorldSemantics.SIMULATOR.value) -> ReplayCertificate:
    """Issue EXACT only after receipt validation and independent local replay checks.

    Stochastic decisions remain non-replayable until a registered executor and
    independent verifier consume and validate their complete RNG continuation.
    """
    from .capture import capture, verify_decision_record
    from .executor import execute_recorded
    from .intervention import Intervention
    from .state import Observation
    from .types import CaptureResult, DecisionRecord, ReplayContext
    from .verifier import verify_execution

    if (type(decision_record) is not DecisionRecord
            or not verify_decision_record(fabric, decision_record)):
        raise NonReplayable("recorded decision receipt cannot be verified")
    if (type(capture_result) is not CaptureResult or not capture_result.complete
            or not capture_result.archival_only or not capture_result.historical_snapshot_only
            or not capture_result.source_currently_admissible
            or capture_result.decision != decision_record
            or capture_digest != capture_result.factual_digest
            or capture_result.source_head > fabric.log.head_seq):
        raise NonReplayable("authorized historical capture does not match the decision receipt")
    capture_body = {"schema": capture_result.schema,
        "principal": capture_result.principal_id, "tenant": capture_result.tenant_id,
        "known_at": capture_result.known_at, "valid_at": capture_result.valid_at,
        "source_head": capture_result.source_head,
        "evidence": [{"id": ref.belief_id, "version": ref.version,
            "digest": ref.digest} for ref in capture_result.evidence],
        "decision": asdict(decision_record)}
    if digest_json(capture_body) != capture_digest:
        raise NonReplayable("historical capture digest is invalid")
    current_capture = capture(fabric, session,
        [ref.belief_id for ref in capture_result.evidence],
        context=ReplayContext(capture_result.known_at, valid_at=capture_result.valid_at,
                              max_events=100_000), decision=decision_record)
    if (current_capture.evidence != capture_result.evidence
            or current_capture.principal_id != capture_result.principal_id
            or current_capture.tenant_id != capture_result.tenant_id):
        raise NonReplayable("historical capture is no longer currently authorized")
    if (decision_record.rng_applicability != "not_applicable_deterministic"
            or decision_record.tool_observations):
        raise NonReplayable("RNG or tool continuation lacks an independently verified handler")
    if (decision_record.policy_id != policy_id or type(policy) is not ThresholdPolicy
            or policy.policy_id != policy_id
            or decision_record.policy_digest != policy.implementation_digest):
        raise NonReplayable("recorded policy implementation does not match the requested replay")
    if (type(factual_observations) is not tuple or not factual_observations
            or any(type(item) is not Observation for item in factual_observations)
            or type(intervention) is not Intervention):
        raise NonReplayable("a complete factual trace and typed intervention are required")
    evidence_ids = {ref.belief_id for ref in decision_record.evidence}
    observation_ids = {item.observation_id for item in factual_observations}
    if len(observation_ids) != len(factual_observations) or observation_ids != evidence_ids:
        raise NonReplayable("factual observations must map one-to-one to recorded evidence")
    expected_intervention_digest = digest_json({
        "op": intervention.operation,
        "target": intervention.target.belief_id if intervention.target else None,
        "replacement": (intervention.replacement.to_dict()
                        if intervention.replacement is not None else None),
        "delay": intervention.delay_until,
        "policy": intervention.policy_id,
        "window_start": intervention.window_start,
        "window_end": intervention.window_end,
        "sensitivity": (intervention.sensitivity.to_dict()
                        if intervention.sensitivity is not None else None)})
    if (intervention.intervention_id != expected_intervention_digest
            or intervention_digest != expected_intervention_digest
            or intervention.operation not in {"noop", "suppress", "delay"}):
        raise NonReplayable("intervention is unsupported or its digest does not match")
    if intervention.operation == "noop":
        counterfactual_observations = factual_observations
    elif intervention.operation == "suppress":
        if (intervention.target is None
                or intervention.target not in decision_record.evidence):
            raise NonReplayable("suppression target is outside the recorded evidence")
        counterfactual_observations = tuple(item for item in factual_observations
            if item.observation_id != intervention.target.belief_id)
    else:
        if (intervention.target is None or intervention.target not in decision_record.evidence
                or intervention.delay_until is None):
            raise NonReplayable("delay target or sequence is missing from the receipt")
        target_items = [item for item in factual_observations
                        if item.observation_id == intervention.target.belief_id]
        if len(target_items) != 1 or intervention.delay_until <= target_items[0].sequence:
            raise NonReplayable("delay target is absent or delay is not later")
        counterfactual_observations = tuple(replace(item, sequence=intervention.delay_until)
            if item.observation_id == intervention.target.belief_id else item
            for item in factual_observations)

    factual = execute_recorded(fabric, factual_observations, simulator=simulator,
        policy=policy, decision_record=decision_record)
    counterfactual = execute_recorded(fabric, counterfactual_observations,
        simulator=simulator, policy=policy, decision_record=decision_record)
    factual_check = verify_execution(factual_observations, execution=factual,
        simulator=simulator, policy=policy)
    counterfactual_check = verify_execution(counterfactual_observations,
        execution=counterfactual, simulator=simulator, policy=policy)
    if (factual.status is not ReplayStatus.EXACT or not factual.complete
            or counterfactual.status is not ReplayStatus.EXACT or not counterfactual.complete
            or not factual_check.verified or not counterfactual_check.verified
            or factual.final_state.updater_id != updater_id
            or counterfactual.final_state.updater_id != updater_id):
        raise NonReplayable("independent replay verification did not establish exactness "
            f"(factual={factual_check.code}, counterfactual={counterfactual_check.code})")
    factual_proposal = factual.steps[-1].proposal if factual.steps else None
    counterfactual_proposal = (counterfactual.steps[-1].proposal
                               if counterfactual.steps else None)
    return issue(capture_digest=capture_digest, intervention_digest=intervention_digest,
        factual_fingerprint=factual.final_state.fingerprint,
        counterfactual_fingerprint=counterfactual.final_state.fingerprint,
        updater_id=updater_id, policy_id=policy_id, status=ExplanationStatus.EXACT.value,
        factual_proposal=factual_proposal, counterfactual_proposal=counterfactual_proposal,
        complete=True, estimand=estimand, world_semantics=world_semantics)


def verify(value: ReplayCertificate | str | dict[str, Any]) -> bool:
    """Validate structure and digest independently; reject unknown/missing fields."""
    if isinstance(value, ReplayCertificate):
        payload = value.payload()
        digest = value.certificate_digest
    elif isinstance(value, str):
        import json
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return False
        return verify(value)
    elif isinstance(value, dict):
        expected = {"schema", "capture_digest", "intervention_digest", "factual_fingerprint",
            "counterfactual_fingerprint", "updater_id", "policy_id", "status", "proposal_changed",
            "claims", "action_entitlement", "estimand", "world_semantics", "minimality_claim",
            "minimality_proof_digest", "limitations", "certificate_digest"}
        if set(value) != expected:
            return False
        raw_digest = value.get("certificate_digest")
        digest = raw_digest if isinstance(raw_digest, str) else ""
        payload = {k: v for k, v in value.items() if k != "certificate_digest"}
    else:
        return False
    if payload.get("schema") != SCHEMA or payload.get("status") != ExplanationStatus.EXACT.value:
        return False
    if payload.get("action_entitlement") is not False:
        return False
    limitations = payload.get("limitations")
    if (not isinstance(limitations, (tuple, list))
            or "no_action_entitlement" not in limitations
            or "physical_world_not_verified" not in limitations
            or any(not isinstance(item, str) or not item for item in limitations)
            or len(set(limitations)) != len(limitations)):
        return False
    if (payload.get("estimand") not in {item.value for item in Estimand}
            or payload.get("world_semantics") not in {item.value for item in WorldSemantics}
            or payload.get("minimality_claim") not in {item.value for item in MinimalityClaim}):
        return False
    if payload["world_semantics"] == WorldSemantics.PHYSICAL_UNSUPPORTED.value:
        return False
    proof = payload.get("minimality_proof_digest")
    if payload["minimality_claim"] == MinimalityClaim.NONE.value:
        if proof is not None:
            return False
    elif not isinstance(proof, str) or not re.fullmatch(r"[0-9a-f]{64}", proof):
        return False
    digest_fields = ("capture_digest", "intervention_digest", "factual_fingerprint",
                     "counterfactual_fingerprint")
    if any(not isinstance(payload.get(k), str)
           or not re.fullmatch(r"[0-9a-f]{64}", payload[k]) for k in digest_fields):
        return False
    if not isinstance(payload.get("updater_id"), str) or not payload["updater_id"]:
        return False
    if not isinstance(payload.get("policy_id"), str) or not payload["policy_id"]:
        return False
    if not isinstance(payload.get("proposal_changed"), bool):
        return False
    expected_claims = ("caused_internal_decision_change",) if payload["proposal_changed"] else ()
    if payload.get("claims") not in (expected_claims, list(expected_claims)):
        return False
    return isinstance(digest, str) and digest == digest_json(payload)


def verify_with_minimality_proof(value: ReplayCertificate | str | dict[str, Any], *,
                                 players: tuple[str, ...],
                                 coalition_proposals: dict[tuple[str, ...], str | None],
                                 sufficient_subset: tuple[str, ...],
                                 target_proposal: str) -> bool:
    """Verify a certificate and recompute its bound minimality proof table."""
    if not verify(value):
        return False
    claim: Any
    digest: Any
    if isinstance(value, ReplayCertificate):
        claim, digest = value.minimality_claim, value.minimality_proof_digest
    else:
        import json
        try:
            data = json.loads(value) if isinstance(value, str) else value
        except (ValueError, TypeError):
            return False
        claim, digest = data.get("minimality_claim"), data.get("minimality_proof_digest")
    if claim == MinimalityClaim.NONE.value:
        return digest is None
    from .verifier import verify_minimality_proof
    proof = verify_minimality_proof(players, coalition_proposals=coalition_proposals,
        sufficient_subset=sufficient_subset, target_proposal=target_proposal, claim=claim)
    return proof.verified and proof.proof_digest == digest


def masked_export(value: ReplayCertificate) -> dict[str, Any]:
    """Return a minimal shareable summary without IDs, hashes, counts or content."""
    if type(value) is not ReplayCertificate or not verify(value):
        raise CDMError("only a verified exact certificate can be exported")
    return {"schema": value.schema, "status": value.status,
            "estimand": value.estimand, "world_semantics": value.world_semantics,
            "proposal_changed": value.proposal_changed,
            "claims": list(value.claims), "action_entitlement": False,
            "limitations": list(value.limitations), "masked": True}
