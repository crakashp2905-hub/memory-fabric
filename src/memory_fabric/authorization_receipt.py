"""Replayable proof receipts for action authorization decisions.

Receipts bind the requirement graph, policy/tool digest, action binding, exact
evidence versions, and the original allow/refusal. Verification re-runs the
gate without emitting audit events or executing a tool. Digests provide
integrity checks, not signer identity; sign or anchor receipts externally when
their origin must be authenticated.
"""

from __future__ import annotations

__stability__ = "beta"

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping

from .actions import (
    ActionDecision,
    ActionGate,
    ActionRequest,
    Approval,
    Grant,
    binding_digest,
    certificate_set_digest,
)
from .certificates import CertificateError, EvidenceCertificate
from .enforcement import RiskLevel

RECEIPT_SCHEMA = "memory-fabric-authorization-receipt/1"
LEGACY_CERTIFICATE_KEY = "$legacy"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _approval_digest(approval: Approval | None) -> str | None:
    if approval is None:
        return None
    return _digest(asdict(approval))


def _grant_digest(grant: Grant | str | None) -> str | None:
    if grant is None:
        return None
    grant_id = grant.grant_id if isinstance(grant, Grant) else grant
    return _digest({"grant_id": grant_id})


def _requirement_digest(gate: ActionGate, tool: str) -> tuple[str | None, str | None]:
    rule = gate.policy.tools.get(tool)
    if rule is None or rule.requirement_graph is None:
        return None, None
    body = {
        "schema": rule.requirement_graph.schema,
        "graph": rule.requirement_graph.to_dict(),
        "claim_predicates": {
            key: asdict(value) for key, value in sorted(rule.claim_predicates.items())
        },
        "min_independent_sources": rule.min_independent_sources,
        "required_checks": list(rule.required_checks),
    }
    return rule.requirement_graph.schema, _digest(body)


def _normalize_certificates(
    gate: ActionGate,
    tool: str,
    certificate: EvidenceCertificate | Mapping[str, Any] | None,
    claim_certificates: Mapping[str, EvidenceCertificate | Mapping[str, Any]] | None,
) -> tuple[EvidenceCertificate | None, dict[str, EvidenceCertificate]]:
    parsed_primary: EvidenceCertificate | None
    if certificate is None:
        parsed_primary = None
    elif isinstance(certificate, EvidenceCertificate):
        parsed_primary = certificate
    else:
        parsed_primary = EvidenceCertificate.from_json(certificate)
    parsed_claims = (gate._parse_claim_certificates(claim_certificates)
                     if claim_certificates is not None else {})
    rule = gate.policy.tools.get(tool)
    if rule is not None and rule.requirement_graph is not None:
        if parsed_primary is not None:
            existing = parsed_claims.get(parsed_primary.claim_id)
            if existing is not None and existing.digest() != parsed_primary.digest():
                raise CertificateError("claim_certificate_conflict",
                                       "primary and claim certificates differ")
            parsed_claims[parsed_primary.claim_id] = parsed_primary
        return parsed_primary, parsed_claims
    return parsed_primary, ({LEGACY_CERTIFICATE_KEY: parsed_primary}
                           if parsed_primary is not None else {})


def _action_binding(
    tool: str,
    agent_id: str,
    tenant_id: str | None,
    request: ActionRequest | None,
    primary: EvidenceCertificate | None,
    claim_certificates: Mapping[str, EvidenceCertificate],
    requirement_digest: str | None,
) -> str:
    if requirement_digest is not None:
        return binding_digest(tool, agent_id, tenant_id, request, None,
                              claim_certificates)
    return binding_digest(tool, agent_id, tenant_id, request, primary)


def _authorization_digest(
    *, action_binding: str, policy_id: str, policy_digest: str,
    requirement_digest: str | None,
    certificate_digest: str, allowed: bool, reason_codes: tuple[str, ...],
    approval_digest: str | None, grant_digest: str | None,
) -> str:
    return _digest({
        "action_binding": action_binding,
        "policy_id": policy_id,
        "policy_digest": policy_digest,
        "requirement_digest": requirement_digest,
        "certificate_digest": certificate_digest,
        "allowed": allowed,
        "reason_codes": list(reason_codes),
        "approval_digest": approval_digest,
        "grant_digest": grant_digest,
    })


@dataclass(frozen=True)
class AuthorizationProofReceipt:
    """Immutable, content-free receipt for one authorization decision."""

    schema: str
    tool: str
    agent_id: str
    tenant_id: str | None
    policy_id: str
    policy_digest: str
    requirement_version: str | None
    requirement_digest: str | None
    action_binding_digest: str
    authorization_digest: str
    certificate_digest: str
    certificates_json: str
    evidence: tuple[tuple[str, int], ...]
    approval_digest: str | None
    grant_digest: str | None
    allowed: bool
    reason_codes: tuple[str, ...]
    verified_at_watermark: int | None
    receipt_digest: str

    def _body(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "tool": self.tool,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "policy_id": self.policy_id,
            "policy_digest": self.policy_digest,
            "requirement_version": self.requirement_version,
            "requirement_digest": self.requirement_digest,
            "action_binding_digest": self.action_binding_digest,
            "authorization_digest": self.authorization_digest,
            "certificate_digest": self.certificate_digest,
            "certificates_json": self.certificates_json,
            "evidence": [[memory_id, version] for memory_id, version in self.evidence],
            "approval_digest": self.approval_digest,
            "grant_digest": self.grant_digest,
            "allowed": self.allowed,
            "reason_codes": list(self.reason_codes),
            "verified_at_watermark": self.verified_at_watermark,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self._body(), "receipt_digest": self.receipt_digest}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def digest_is_valid(self) -> bool:
        return _digest(self._body()) == self.receipt_digest

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AuthorizationProofReceipt":
        expected = {
            "schema", "tool", "agent_id", "tenant_id", "policy_id", "policy_digest",
            "requirement_version", "requirement_digest", "action_binding_digest",
            "authorization_digest", "certificate_digest", "certificates_json", "evidence",
            "approval_digest", "grant_digest", "allowed", "reason_codes",
            "verified_at_watermark", "receipt_digest",
        }
        if set(value) != expected:
            raise ValueError("authorization receipt has missing or unknown fields")
        if value["schema"] != RECEIPT_SCHEMA:
            raise ValueError("unsupported authorization receipt schema")
        if type(value["allowed"]) is not bool:
            raise ValueError("authorization receipt allowed must be bool")
        for key in ("tool", "agent_id", "policy_id", "policy_digest",
                    "action_binding_digest", "authorization_digest",
                    "certificate_digest", "certificates_json", "receipt_digest"):
            if not isinstance(value[key], str) or not value[key]:
                raise ValueError(f"authorization receipt {key} must be a non-empty string")
        digest_fields = ("policy_digest", "action_binding_digest", "authorization_digest",
                         "certificate_digest", "receipt_digest")
        if any(len(value[key]) != 64 or any(ch not in "0123456789abcdef"
                                             for ch in value[key])
               for key in digest_fields):
            raise ValueError("authorization receipt contains a malformed SHA-256 digest")
        for key in ("requirement_digest", "approval_digest", "grant_digest"):
            item = value[key]
            if item is not None and (not isinstance(item, str) or len(item) != 64
                                     or any(ch not in "0123456789abcdef" for ch in item)):
                raise ValueError(f"authorization receipt {key} is malformed")
        if value["tenant_id"] is not None and not isinstance(value["tenant_id"], str):
            raise ValueError("authorization receipt tenant_id must be string or null")
        if (value["requirement_version"] is not None
                and not isinstance(value["requirement_version"], str)):
            raise ValueError("authorization receipt requirement_version must be string or null")
        if (value["verified_at_watermark"] is not None
                and (type(value["verified_at_watermark"]) is not int
                     or value["verified_at_watermark"] < 0)):
            raise ValueError("authorization receipt watermark must be non-negative integer or null")
        try:
            certificate_data = json.loads(value["certificates_json"])
        except json.JSONDecodeError as exc:
            raise ValueError("authorization receipt certificates_json is invalid") from exc
        if not isinstance(certificate_data, dict):
            raise ValueError("authorization receipt certificates_json must be an object")
        reason_codes = value["reason_codes"]
        if (not isinstance(reason_codes, list) or not reason_codes
                or any(not isinstance(item, str) or not item for item in reason_codes)):
            raise ValueError("authorization receipt reason_codes must be non-empty strings")
        evidence = value["evidence"]
        if not isinstance(evidence, list) or any(
            not isinstance(item, list) or len(item) != 2
            or not isinstance(item[0], str) or type(item[1]) is not int or item[1] < 1
            for item in evidence
        ):
            raise ValueError("authorization receipt evidence references are malformed")
        evidence_pairs = [(item[0], item[1]) for item in evidence]
        if evidence_pairs != sorted(set(evidence_pairs)):
            raise ValueError("authorization receipt evidence references are not canonical")
        receipt = cls(
            schema=value["schema"], tool=value["tool"], agent_id=value["agent_id"],
            tenant_id=value["tenant_id"], policy_id=value["policy_id"],
            policy_digest=value["policy_digest"],
            requirement_version=value["requirement_version"],
            requirement_digest=value["requirement_digest"],
            action_binding_digest=value["action_binding_digest"],
            authorization_digest=value["authorization_digest"],
            certificate_digest=value["certificate_digest"],
            certificates_json=value["certificates_json"],
            evidence=tuple((item[0], item[1]) for item in evidence),
            approval_digest=value["approval_digest"], grant_digest=value["grant_digest"],
            allowed=value["allowed"], reason_codes=tuple(reason_codes),
            verified_at_watermark=value["verified_at_watermark"],
            receipt_digest=value["receipt_digest"],
        )
        if not receipt.digest_is_valid():
            raise ValueError("authorization receipt digest does not verify")
        return receipt


@dataclass(frozen=True)
class AuthorizationReceiptVerification:
    status: str
    valid: bool
    reason_codes: tuple[str, ...] = ()
    current_allowed: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "valid": self.valid,
                "reason_codes": list(self.reason_codes),
                "current_allowed": self.current_allowed}


def issue_authorization_receipt(
    gate: ActionGate,
    tool: str,
    agent_id: str,
    certificate: EvidenceCertificate | Mapping[str, Any] | None = None,
    *,
    tenant_id: str | None = None,
    request: ActionRequest | None = None,
    approval: Approval | None = None,
    grant: Grant | str | None = None,
    claim_certificates: Mapping[str, EvidenceCertificate | Mapping[str, Any]] | None = None,
) -> tuple[AuthorizationProofReceipt, ActionDecision]:
    """Authorize once and capture a content-free replay receipt."""
    primary, certificates = _normalize_certificates(
        gate, tool, certificate, claim_certificates)
    rule = gate.policy.tools.get(tool)
    requirement_version, requirement_digest = _requirement_digest(gate, tool)
    policy_digest = gate._tool_digest(tool)
    action_binding = _action_binding(tool, agent_id, tenant_id, request, primary,
                                     certificates, requirement_digest)
    decision = gate.authorize(
        tool, agent_id, primary, tenant_id=tenant_id, approval=approval,
        request=request, grant=grant,
        claim_certificates=(certificates if rule is not None
                            and rule.requirement_graph is not None else None),
    )
    certificate_digest = certificate_set_digest(certificates)
    approval_digest = _approval_digest(approval)
    grant_digest = _grant_digest(grant)
    authorization_digest = _authorization_digest(
        action_binding=action_binding, policy_id=gate.policy.policy_id,
        policy_digest=policy_digest,
        requirement_digest=requirement_digest, certificate_digest=certificate_digest,
        allowed=decision.allowed, reason_codes=decision.reason_codes,
        approval_digest=approval_digest, grant_digest=grant_digest,
    )
    evidence = tuple(sorted({(ref.memory_id, ref.version)
                             for cert in certificates.values() for ref in cert.evidence}))
    certificates_json = json.dumps(
        {key: cert.to_json() for key, cert in sorted(certificates.items())},
        sort_keys=True, separators=(",", ":"),
    )
    watermark = (decision.verification.verified_at_watermark
                 if decision.verification is not None else None)
    body = {
        "schema": RECEIPT_SCHEMA, "tool": tool, "agent_id": agent_id,
        "tenant_id": tenant_id, "policy_id": gate.policy.policy_id,
        "policy_digest": policy_digest, "requirement_version": requirement_version,
        "requirement_digest": requirement_digest,
        "action_binding_digest": action_binding,
        "authorization_digest": authorization_digest,
        "certificate_digest": certificate_digest, "certificates_json": certificates_json,
        "evidence": [[memory_id, version] for memory_id, version in evidence],
        "approval_digest": approval_digest, "grant_digest": grant_digest,
        "allowed": decision.allowed, "reason_codes": list(decision.reason_codes),
        "verified_at_watermark": watermark,
    }
    receipt = AuthorizationProofReceipt(
        schema=RECEIPT_SCHEMA, tool=tool, agent_id=agent_id, tenant_id=tenant_id,
        policy_id=gate.policy.policy_id, policy_digest=policy_digest,
        requirement_version=requirement_version, requirement_digest=requirement_digest,
        action_binding_digest=action_binding, authorization_digest=authorization_digest,
        certificate_digest=certificate_digest, certificates_json=certificates_json,
        evidence=evidence, approval_digest=approval_digest, grant_digest=grant_digest,
        allowed=decision.allowed, reason_codes=decision.reason_codes,
        verified_at_watermark=watermark, receipt_digest=_digest(body),
    )
    return receipt, decision


def verify_authorization_receipt(
    receipt: AuthorizationProofReceipt | Mapping[str, Any],
    gate: ActionGate,
    *,
    request: ActionRequest | None = None,
    approval: Approval | None = None,
    grant: Grant | str | None = None,
) -> AuthorizationReceiptVerification:
    """Replay a receipt without writing audit events or running the tool."""
    try:
        parsed = (AuthorizationProofReceipt.from_dict(receipt.to_dict())
                  if isinstance(receipt, AuthorizationProofReceipt)
                  else AuthorizationProofReceipt.from_dict(receipt))
    except (TypeError, ValueError):
        return AuthorizationReceiptVerification("TAMPERED", False,
                                                 ("receipt_integrity_invalid",))
    if not parsed.digest_is_valid():
        return AuthorizationReceiptVerification("TAMPERED", False,
                                                 ("receipt_integrity_invalid",))
    if _approval_digest(approval) != parsed.approval_digest:
        return AuthorizationReceiptVerification("INVALIDATED", False,
                                                 ("approval_context_changed",))
    if _grant_digest(grant) != parsed.grant_digest:
        return AuthorizationReceiptVerification("INVALIDATED", False,
                                                 ("grant_context_changed",))
    if gate.policy.policy_id != parsed.policy_id:
        return AuthorizationReceiptVerification("INVALIDATED", False,
                                                 ("policy_version_changed",))
    current_rule = gate.policy.tools.get(parsed.tool)
    if current_rule is None:
        return AuthorizationReceiptVerification("INVALIDATED", False,
                                                 ("tool_policy_missing",))
    current_policy_digest = gate._tool_digest(parsed.tool)
    if current_policy_digest != parsed.policy_digest:
        current_version, current_requirement = _requirement_digest(gate, parsed.tool)
        reason = ("requirement_digest_changed"
                  if (current_version, current_requirement)
                  != (parsed.requirement_version, parsed.requirement_digest)
                  else "tool_policy_changed")
        return AuthorizationReceiptVerification("INVALIDATED", False, (reason,))

    try:
        certificates_data = json.loads(parsed.certificates_json)
        if parsed.requirement_digest is None:
            legacy_data = certificates_data.get(LEGACY_CERTIFICATE_KEY)
            legacy_certificate = (EvidenceCertificate.from_json(legacy_data)
                                 if legacy_data is not None else None)
            certificates = ({LEGACY_CERTIFICATE_KEY: legacy_certificate}
                            if legacy_certificate is not None else {})
        else:
            certificates = gate._parse_claim_certificates(certificates_data)
        requirement_version, requirement_digest = _requirement_digest(gate, parsed.tool)
        primary = certificates.get(LEGACY_CERTIFICATE_KEY)
        graph_certificates = ({key: cert for key, cert in certificates.items()
                               if key != LEGACY_CERTIFICATE_KEY}
                              if requirement_digest is not None else None)
        if requirement_digest is not None:
            primary = None
        if certificate_set_digest(certificates) != parsed.certificate_digest:
            raise ValueError("certificate digest mismatch")
        current_evidence = tuple(sorted({(ref.memory_id, ref.version)
                                         for cert in certificates.values()
                                         for ref in cert.evidence}))
        if current_evidence != parsed.evidence:
            raise ValueError("evidence reference mismatch")
        action_binding = _action_binding(
            parsed.tool, parsed.agent_id, parsed.tenant_id, request, primary,
            certificates, requirement_digest,
        )
        if action_binding != parsed.action_binding_digest:
            return AuthorizationReceiptVerification("INVALIDATED", False,
                                                     ("authorization_context_changed",))
    except (CertificateError, TypeError, ValueError, json.JSONDecodeError):
        return AuthorizationReceiptVerification("TAMPERED", False,
                                                 ("receipt_certificate_invalid",))
    if (requirement_version, requirement_digest) != (
        parsed.requirement_version, parsed.requirement_digest
    ):
        return AuthorizationReceiptVerification("INVALIDATED", False,
                                                 ("requirement_digest_changed",))

    replay_gate = ActionGate(gate.fabric, gate.policy, mode=gate.verifier.mode,
                             audit=False, leases=gate.leases)
    current = replay_gate.authorize(
        parsed.tool, parsed.agent_id, primary, tenant_id=parsed.tenant_id,
        request=request, approval=approval, grant=grant,
        claim_certificates=graph_certificates,
    )
    precise_reasons: list[str] = []
    for cert in certificates.values():
        strengthened = cert
        if current_rule is not None:
            strengthened = replace(
                cert,
                required_checks=tuple(dict.fromkeys(
                    [*cert.required_checks, *current_rule.required_checks])),
                min_independent_sources=max(
                    cert.min_independent_sources, current_rule.min_independent_sources),
            )
        verification = replay_gate.verifier.verify(
            strengthened, agent_id=parsed.agent_id, tenant_id=parsed.tenant_id,
            risk=RiskLevel.HIGH,
        )
        precise_reasons.extend(code for code in verification.reason_codes if code != "ok")
    current_reasons = tuple(dict.fromkeys((*current.reason_codes, *precise_reasons)))
    current_auth = _authorization_digest(
        action_binding=action_binding, policy_id=gate.policy.policy_id,
        policy_digest=current_policy_digest,
        requirement_digest=requirement_digest,
        certificate_digest=parsed.certificate_digest, allowed=current.allowed,
        reason_codes=current_reasons, approval_digest=parsed.approval_digest,
        grant_digest=parsed.grant_digest,
    )
    if current.allowed != parsed.allowed or current_reasons != parsed.reason_codes:
        reasons = current_reasons or ("authorization_outcome_changed",)
        return AuthorizationReceiptVerification("INVALIDATED", False, reasons,
                                                 current.allowed)
    if current_auth != parsed.authorization_digest:
        return AuthorizationReceiptVerification("INVALIDATED", False,
                                                 ("authorization_digest_changed",),
                                                 current.allowed)
    status = "VERIFIED_ALLOW" if current.allowed else "VERIFIED_REFUSAL"
    return AuthorizationReceiptVerification(status, True, current.reason_codes,
                                             current.allowed)
