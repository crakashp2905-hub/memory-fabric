"""Immutable evidence state and deterministic transition semantics."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .bayes import BinaryNode, enumerate_posterior, marginal
from .types import (SCHEMA, BeliefReference, CDMError,
                    canonical_json, digest_json, parse_record)


@dataclass(frozen=True)
class Observation:
    observation_id: str
    variable: str
    value: bool
    origin: str
    sequence: int
    kind: str = "exogenous"

    def __post_init__(self) -> None:
        if not self.observation_id or not self.origin or type(self.value) is not bool:
            raise CDMError("observation identity and boolean value are required")
        if type(self.sequence) is not int or self.sequence < 0:
            raise CDMError("observation sequence must be non-negative")
        if self.kind not in {"exogenous", "simulated_endogenous"}:
            raise CDMError("unsupported observation kind")


@dataclass(frozen=True)
class BeliefState:
    schema: str
    updater_id: str
    policy_id: str
    observations: tuple[Observation, ...]
    posterior: Mapping[str, float]
    conflict_variables: tuple[str, ...]
    fingerprint: str
    evidence_refs: tuple[BeliefReference, ...] = ()
    update_policy_digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a versioned JSON-compatible belief-state record."""
        return {
            "schema": self.schema,
            "updater_id": self.updater_id,
            "update_policy_digest": self.update_policy_digest,
            "policy_id": self.policy_id,
            "variables": sorted(self.posterior),
            "posterior": dict(self.posterior),
            "uncertainty": {name: min(value, 1.0 - value)
                            for name, value in self.posterior.items()},
            "observations": [item.__dict__ for item in self.observations],
            "evidence_refs": [{"belief_id": ref.belief_id,
                "version": ref.version, "tenant_id": ref.tenant_id,
                "digest": ref.digest} for ref in self.evidence_refs],
            "conflict_variables": list(self.conflict_variables),
            "fingerprint": self.fingerprint,
        }


def generated_belief_state_schema() -> dict[str, Any]:
    """Generate the local strict field/type contract for the v1 belief state."""
    return {
        "schema": f"{SCHEMA}.belief-state",
        "record_schema": SCHEMA,
        "type": "object",
        "additionalProperties": False,
        "required": ["schema", "updater_id", "update_policy_digest", "policy_id",
                     "variables", "posterior", "uncertainty", "observations",
                     "evidence_refs", "conflict_variables", "fingerprint"],
        "fields": {
            "schema": {"type": "string", "const": SCHEMA},
            "updater_id": {"type": "string", "nonempty": True},
            "update_policy_digest": {"type": "string", "format": "sha256"},
            "policy_id": {"type": "string", "nonempty": True},
            "variables": {"type": "array", "items": "string", "unique": True},
            "posterior": {"type": "object", "values": "finite-number-in-[0,1]"},
            "uncertainty": {"type": "object", "values": "finite-number-in-[0,0.5]"},
            "observations": {"type": "array", "items": "Observation"},
            "evidence_refs": {"type": "array", "items": "BeliefReference"},
            "conflict_variables": {"type": "array", "items": "string"},
            "fingerprint": {"type": "string", "format": "sha256"},
        },
    }


def validate_belief_state_record(value: str | dict[str, Any]) -> dict[str, Any]:
    """Validate generated schema fields and normalized values with stdlib types."""
    import json
    import math

    try:
        record = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError) as exc:
        raise CDMError("belief-state JSON is invalid") from exc
    if type(record) is not dict:
        raise CDMError("belief-state record must be an object")
    schema = generated_belief_state_schema()
    required = set(schema["required"])
    if set(record) != required or record.get("schema") != SCHEMA:
        raise CDMError("belief-state fields or schema are invalid")
    if (not isinstance(record["updater_id"], str) or not record["updater_id"]
            or not isinstance(record["policy_id"], str) or not record["policy_id"]
            or not isinstance(record["update_policy_digest"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", record["update_policy_digest"])
            or not isinstance(record["fingerprint"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", record["fingerprint"])):
        raise CDMError("belief-state identity or digest is invalid")
    posterior = record["posterior"]
    uncertainty = record["uncertainty"]
    variables = record["variables"]
    if (type(posterior) is not dict or type(uncertainty) is not dict
            or type(variables) is not list or variables != sorted(posterior)
            or len(set(variables)) != len(variables) or set(uncertainty) != set(posterior)):
        raise CDMError("belief-state variables are not normalized")
    for name, probability in posterior.items():
        if (not isinstance(name, str) or not name or type(probability) not in (int, float)
                or not math.isfinite(probability) or not 0 <= probability <= 1
                or type(uncertainty[name]) not in (int, float)
                or not math.isfinite(uncertainty[name])
                or uncertainty[name] != min(probability, 1 - probability)):
            raise CDMError("belief-state probability or uncertainty is invalid")
    if (type(record["observations"]) is not list
            or type(record["evidence_refs"]) is not list
            or type(record["conflict_variables"]) is not list):
        raise CDMError("belief-state traces must be arrays")
    observation_ids: set[str] = set()
    for item in record["observations"]:
        if (type(item) is not dict
                or set(item) != {"observation_id", "variable", "value", "origin", "sequence", "kind"}
                or not isinstance(item["observation_id"], str) or not item["observation_id"]
                or not isinstance(item["variable"], str) or item["variable"] not in variables
                or type(item["value"]) is not bool
                or not isinstance(item["origin"], str) or not item["origin"]
                or type(item["sequence"]) is not int or item["sequence"] < 0
                or item["kind"] not in {"exogenous", "simulated_endogenous"}
                or item["observation_id"] in observation_ids):
            raise CDMError("belief-state observation is invalid")
        observation_ids.add(item["observation_id"])
    for ref in record["evidence_refs"]:
        parse_record(BeliefReference, ref)
    if set(record["conflict_variables"]) - set(variables):
        raise CDMError("belief-state conflict variable is undeclared")
    canonical_json(record)
    return record


def update(nodes: tuple[BinaryNode, ...], observations: tuple[Observation, ...], *,
           updater_id: str = "exact-enumeration-v1", policy_id: str = "investigate-threshold-v1"
           ) -> BeliefState:
    if len({o.observation_id for o in observations}) != len(observations):
        raise CDMError("duplicate observation ids are forbidden")
    # Same-origin repeats are one observation; conflicting distinct sources
    # remain in the trace and are excluded from conditioning until a registered
    # sensor model can score their dependence. This preserves uncertainty.
    unique: dict[tuple[str, str], Observation] = {}
    for item in sorted(observations, key=lambda x: (x.sequence, x.observation_id)):
        unique.setdefault((item.origin, item.variable), item)
    admitted = tuple(sorted(unique.values(), key=lambda x: (x.sequence, x.observation_id)))
    evidence: dict[str, bool] = {}
    conflicts: set[str] = set()
    for item in admitted:
        if item.variable in evidence and evidence[item.variable] != item.value:
            conflicts.add(item.variable)
        else:
            evidence.setdefault(item.variable, item.value)
    for variable in conflicts:
        evidence.pop(variable, None)
    distribution = enumerate_posterior(nodes, evidence)
    posterior = {node.name: marginal(distribution, node.name) for node in nodes}
    update_policy_digest = digest_json({"updater_id": updater_id,
        "policy_id": policy_id, "implementation": "exact-enumeration-v1"})
    payload: dict[str, Any] = {"schema": "memory-fabric-cdm-v1", "updater": updater_id,
        "policy": policy_id, "observations": [o.__dict__ for o in admitted],
        "posterior": posterior, "conflicts": sorted(conflicts),
        "update_policy_digest": update_policy_digest}
    return BeliefState("memory-fabric-cdm-v1", updater_id, policy_id, admitted, posterior,
                       tuple(sorted(conflicts)), digest_json(payload), (),
                       update_policy_digest)
