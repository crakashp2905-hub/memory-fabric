"""Action-time verification: the gate in front of a protected tool (plan Task 4).

Two questions are kept apart, because the plan's invariant is that *memory
validity is not action authorisation*:

1. **May this agent use this tool at all?** Answered from the gate's own grant
   table, configured by the host. Nothing an agent writes, retrieves or
   certifies can add a tool to its grants.
2. **Is the evidence for this action still good?** Answered by re-verifying an
   `EvidenceCertificate` against the store, immediately before the action.

The tool grant is checked first, so an ungranted call is refused without
touching memory at all and a perfect certificate cannot rescue it. A protected
tool without a certificate is refused. A tool rule can require stronger checks
than the certificate declares; it can never be weakened by one, because the
verifier runs the *union* of the rule's checks and the certificate's.

**Service-unavailable behaviour.** If the store cannot be read, a protected
action is refused with `state_unavailable`. An unprotected tool does not depend
on memory and is not blocked by a memory outage. Unknown tools are refused.

**Audit.** Every decision on a protected tool appends an `ActionGated` event:
the tool, the agent, the verdict, the reason codes, the certificate digest and
the evidence ids and versions. Never content. This is the link Task 9 needs
from evidence to action.

## The fence: closing the window between "verified" and "done" (S6)

`authorize` answers "may this run now?", and the answer is stale the moment it
returns. A retraction committed after `verify` and before the tool's side
effect was not seen. That is threat S14, which was accepted as a residual race.

`execute` closes it for a tool the store can wait on. Verification and the
tool run inside **one store write transaction** (`BEGIN IMMEDIATE`, plus the
in-process lock), so no retraction, quarantine or revocation can commit
between them. A concurrent writer in this process or any other waits for the
action, and then commits after it. The outcome is linearisable: every action
happened either before a withdrawal of its evidence or not at all. Readers are
not blocked, because the log is in WAL mode.

The price and the limits, stated:

- **Writers wait** up to the lease. A writer in another process waits up to
  its SQLite busy timeout (5 s by default), so `lease_s` must stay below it,
  or that writer fails with "database is locked" and must retry. `execute`
  refuses a lease at or above `MAX_LEASE_S`.
- **A tool that overruns its lease** has the fence released, so a hung tool
  cannot stop every write to the store. The call returns `timed_out`, the
  record says `fenced: false`, and `unfenced_changes()` reports any change to
  the evidence after that point. The window is bounded and recorded, not
  closed.
- **The tool must not call this store.** It runs on a worker thread while the
  caller holds the store's lock, so a store call from inside it waits until
  the lease runs out.
- **A crash mid-action** rolls the transaction back, so neither the decision
  nor the outcome is recorded. The tool receives the idempotency key so that
  it, the only party that can know, deduplicates a retry.
- **Retry.** A key whose last attempt `executed` is not run again
  (`already_executed`). One that `timed_out` or `failed` has an unknown
  effect, so it runs again only with `retry=True`, and then it re-verifies
  from scratch. A stale verification is never reused.
"""

from __future__ import annotations

__stability__ = "beta"

import threading
import time
import hashlib
import json
from dataclasses import dataclass, field, fields, replace
from typing import Any, Callable, Mapping

from . import events as ev
from .certificates import (
    ALWAYS,
    CertificateError,
    CertificateVerification,
    CertificateVerifier,
    EvidenceCertificate,
    STATE_UNAVAILABLE,
)
from .requirement_graph import (
    AllOfRequirement, AnyOfRequirement, ClaimRequirement,
    IndependentSourcesRequirement, RequirementGraph, RuleReference,
    TemporalRequirement,
)
from .enforcement import RiskLevel

ACTION_POLICY_VERSION = "action-policy-v1"

# Reason codes.
ALLOWED = "allowed"
UNPROTECTED = "unprotected_tool"
UNKNOWN_TOOL = "unknown_tool"
TOOL_NOT_GRANTED = "tool_not_granted"
CERTIFICATE_REQUIRED = "certificate_required"
HUMAN_APPROVAL_REQUIRED = "human_approval_required"
APPROVAL_INVALID = "approval_invalid"
CREDENTIAL_INVALID = "credential_invalid"
PERMISSION_DENIED = "execute_permission_missing"
RETRY_REQUIRED = "retry_required"
AUTHORITY_INSUFFICIENT = "authority_insufficient"
INSTRUCTION_EVIDENCE = "instruction_is_not_evidence"
EVIDENCE_SUSPICIOUS = "evidence_suspicious"
EVIDENCE_PROVISIONAL = "evidence_provisional"
EVIDENCE_NOT_FRESH = "evidence_not_fresh"
GRANT_REQUIRED = "grant_required"
GRANT_UNKNOWN = "grant_unknown"
GRANT_EXPIRED = "grant_expired"
GRANT_REVOKED = "grant_revoked"
GRANT_MISMATCH = "grant_binding_mismatch"
GRANT_REPLAYED = "grant_replayed"
IDEMPOTENCY_CONFLICT = "idempotency_key_payload_mismatch"
REQUIREMENT_EVIDENCE_MISSING = "requirement_evidence_missing"
MAX_GRANT_TTL_S = 300

# Execution outcomes (`execute`).
EXECUTED = "executed"
FAILED = "failed"
TIMED_OUT = "timed_out"
ALREADY_EXECUTED = "already_executed"
REFUSED = "refused"
UNCERTAIN = "uncertain"
"""An attempt with no recorded outcome: the process died mid-action. Treated
like `timed_out`: the side effect may or may not have happened."""

MAX_LEASE_S = 4.0
"""Below the store's default 5 s busy timeout, so a writer in another process
waiting on the fence gets in before it gives up."""


@dataclass(frozen=True)
class ToolRule:
    """How one tool is governed. `protected` tools need a valid certificate."""

    name: str
    protected: bool = True
    required_checks: tuple[str, ...] = ALWAYS
    min_independent_sources: int = 1
    requires_human_approval: bool = False
    min_authority: str = "unverified"
    """The lowest origin-bound trust (`authority.py`) any piece of evidence
    may have. `unverified` refuses evidence descending from a tool output, an
    import, a hostile source, an instruction or a withdrawn memory, unless an
    approver elevated it. `untrusted` turns the check off."""
    requires_grant: bool = False
    """Require a short-lived grant bound to this exact action (`issue_grant`)."""
    refuse_suspicious: bool = True
    """Refuse evidence whose claim contradicts what the store knows
    (`validation.assess`: a corrected value restated, a value far out of
    range, or a contradiction of an established fact)."""
    require_fresh: bool = False
    """Strict freshness: refuse imported evidence unless the gate's `LeaseBook`
    holds a valid, unexpired lease from its origin at the held version
    (`freshness.py`). Bounds how stale a withdrawal at an offline peer can be
    when an action relies on it: one lease lifetime. Native evidence is fresh."""
    refuse_provisional: bool = False
    """Also refuse evidence `validation.assess` rates provisional: a first
    claim from a new source, untrusted origin, or an author's own change to a
    fact a reviewer had validated (`revises_validated`). Off by default; turn
    it on for tools where a compromised account must not act unreviewed."""
    tool_digest: str | None = None
    """Optional host supplied SHA-256 digest of the registered tool descriptor."""
    requirement_graph: RequirementGraph | None = None
    """Optional host-owned static evidence policy. Every claim leaf must be
    backed by a separately named certificate in `claim_certificates`."""


@dataclass(frozen=True)
class ActionRequest:
    """The exact action: what it acts on and with which parameters."""

    target: str
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Grant:
    grant_id: str
    tool: str
    agent_id: str
    binding: str
    expires_ms: int


def binding_digest(tool: str, agent_id: str, tenant_id: str | None,
                   request: ActionRequest | None,
                   certificate: EvidenceCertificate | None,
                   claim_certificates: Mapping[str, EvidenceCertificate] | None = None) -> str:
    """Digest of everything an approval or grant is for. Any change is a different action."""
    import hashlib
    import json

    body = {"tool": tool, "agent": agent_id, "tenant": tenant_id,
            "target": request.target if request else None,
            "parameters": dict(request.parameters) if request else None,
            "evidence": sorted([e.memory_id, e.version] for e in certificate.evidence)
            if certificate else []}
    if claim_certificates is not None:
        body["claim_certificates"] = {
            claim_id: cert.digest() for claim_id, cert in sorted(claim_certificates.items())
        }
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str,
                                     separators=(",", ":")).encode()).hexdigest()


def certificate_set_digest(certificates: Mapping[str, EvidenceCertificate]) -> str:
    """Stable digest for a claim-to-certificate set used by human approvals."""
    encoded = json.dumps({key: cert.digest() for key, cert in sorted(certificates.items())},
                         sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ActionPolicy:
    """The host's configuration. Agents never supply any of it."""

    tools: Mapping[str, ToolRule]
    grants: Mapping[str, frozenset[str]]
    """agent_id -> tool names that agent may call."""

    approvers: frozenset[str] = frozenset()
    policy_id: str = ACTION_POLICY_VERSION


@dataclass(frozen=True)
class Approval:
    """A human's approval, bound to one certificate or named certificate set.

    For graph policies, set `certificate_digest` with
    `certificate_set_digest(claim_certificates)`.
    """

    approver_id: str
    certificate_digest: str
    binding: str | None = None
    """When set, the approval covers only the action with this
    `binding_digest`: a changed target or parameter voids it."""


@dataclass(frozen=True)
class ActionDecision:
    allowed: bool
    tool: str
    agent_id: str
    reason_codes: tuple[str, ...]
    verification: CertificateVerification | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def reason_code(self) -> str:
        return self.reason_codes[0]


@dataclass(frozen=True)
class ActionExecution:
    """What `ActionGate.execute` did."""

    outcome: str
    decision: ActionDecision | None
    key: str
    result: Any = None
    error: str | None = None
    fenced: bool = True

    @property
    def ran(self) -> bool:
        return self.outcome in (EXECUTED, FAILED, TIMED_OUT)


class ActionGate:
    """Decides, immediately before a tool runs, whether it may run."""

    def __init__(
        self,
        fabric: Any,
        policy: ActionPolicy,
        mode: str = "selective",
        audit: bool = True,
        leases: Any = None,
    ) -> None:
        self.fabric = fabric
        self.policy = policy
        self.leases = leases
        """A `freshness.LeaseBook`, consulted by rules with `require_fresh`."""
        self.verifier = CertificateVerifier(fabric, mode=mode)
        self.audit = audit

    def authorize(
        self,
        tool: str,
        agent_id: str,
        certificate: EvidenceCertificate | Mapping[str, Any] | None = None,
        tenant_id: str | None = None,
        approval: Approval | None = None,
        session: Any = None,
        request: ActionRequest | None = None,
        grant: Grant | str | None = None,
        claim_certificates: Mapping[str, EvidenceCertificate | Mapping[str, Any]] | None = None,
    ) -> ActionDecision:
        """Return whether `agent_id` may call `tool` now.

        Fail-closed order: identity, tool grant, certificate, evidence
        re-verification, origin-bound authority of every piece of evidence,
        human approval, then the exact-action grant. `request` names the
        target and parameters; approvals and grants are bound to them.

        With `session` (a `service.Session`), the caller's identity and tenant
        come from its credential, which is re-verified here: a credential
        revoked since retrieval stops the action (authorisation drift, S13).
        """
        if session is not None:
            try:
                principal = session.principal()
            except Exception:
                return self._decide(tool, agent_id, (CREDENTIAL_INVALID,), None, None, tenant_id=tenant_id)
            agent_id, tenant_id = principal.agent_id, principal.tenant_id
            if hasattr(principal, "can") and not principal.can("execute"):
                return self._decide(tool, agent_id, (PERMISSION_DENIED,), None, None,
                                    tenant_id=tenant_id)

        rule = self.policy.tools.get(tool)
        if rule is None:
            return self._decide(tool, agent_id, (UNKNOWN_TOOL,), None, None, tenant_id=tenant_id)
        if tool not in self.policy.grants.get(agent_id, frozenset()):
            # Before any memory is consulted. A valid certificate is evidence,
            # not permission.
            return self._decide(tool, agent_id, (TOOL_NOT_GRANTED,), None, rule, tenant_id=tenant_id)
        if not rule.protected:
            return self._decide(tool, agent_id, (UNPROTECTED,), None, rule, allowed=True, tenant_id=tenant_id)
        rule_certificates: dict[str, EvidenceCertificate] | None = None
        if claim_certificates is not None:
            try:
                rule_certificates = self._parse_claim_certificates(claim_certificates)
            except CertificateError as exc:
                return self._decide(tool, agent_id, (exc.reason_code,), None, rule, tenant_id=tenant_id)
        if rule.requirement_graph is not None:
            # The policy graph, not caller supplied evidence, determines which
            # claims are mandatory. The legacy certificate argument is accepted
            # only as an additional certificate keyed by its own claim id.
            if certificate is not None:
                try:
                    legacy = certificate if isinstance(certificate, EvidenceCertificate) else EvidenceCertificate.from_json(certificate)
                except CertificateError as exc:
                    return self._decide(tool, agent_id, (exc.reason_code,), None, rule, tenant_id=tenant_id)
                if rule_certificates is None:
                    rule_certificates = {}
                if legacy.claim_id in rule_certificates and rule_certificates[legacy.claim_id].digest() != legacy.digest():
                    return self._decide(tool, agent_id, (REQUIREMENT_EVIDENCE_MISSING,), None, rule, tenant_id=tenant_id)
                rule_certificates[legacy.claim_id] = legacy
            if not rule_certificates:
                return self._decide(tool, agent_id, (REQUIREMENT_EVIDENCE_MISSING,), None, rule, tenant_id=tenant_id)
            satisfied, verification, used = self._evaluate_requirement_graph(
                rule.requirement_graph, rule_certificates, rule, agent_id, tenant_id)
            if not satisfied:
                return self._decide(tool, agent_id, (REQUIREMENT_EVIDENCE_MISSING,), verification,
                                    rule, tenant_id=tenant_id, claim_certificates=rule_certificates)
            selected = {claim_id: rule_certificates[claim_id] for claim_id in used}
            primary = next(iter(selected.values())) if selected else None
            # Bind every submitted alternative consistently for approvals,
            # grants and idempotency. Only the satisfied branch is recorded
            # as the policy decision's selected claim set.
            binding = binding_digest(tool, agent_id, tenant_id, request, None, rule_certificates)
            approval_digest = certificate_set_digest(rule_certificates)
            if rule.requires_human_approval:
                if approval is None:
                    return self._decide(tool, agent_id, (HUMAN_APPROVAL_REQUIRED,), verification,
                                        rule, certificate=primary, tenant_id=tenant_id,
                                        claim_certificates=selected)
                if (approval.approver_id not in self.policy.approvers or approval.approver_id == agent_id
                        or approval.certificate_digest != approval_digest
                        or (approval.binding is not None and approval.binding != binding)):
                    return self._decide(tool, agent_id, (APPROVAL_INVALID,), verification, rule,
                                        certificate=primary, tenant_id=tenant_id,
                                        claim_certificates=selected)
            grant_id = grant.grant_id if isinstance(grant, Grant) else grant
            if rule.requires_grant or grant_id is not None:
                if grant_id is None:
                    return self._decide(tool, agent_id, (GRANT_REQUIRED,), verification, rule,
                                        certificate=primary, tenant_id=tenant_id,
                                        claim_certificates=selected, binding=binding)
                problem = self._check_grant(grant_id, tool, agent_id, binding)
                if problem:
                    return self._decide(tool, agent_id, (problem,), verification, rule,
                                        certificate=primary, tenant_id=tenant_id,
                                        claim_certificates=selected, grant_id=grant_id, binding=binding)
            return self._decide(tool, agent_id, (ALLOWED,), verification, rule, allowed=True,
                                certificate=primary, tenant_id=tenant_id,
                                claim_certificates=selected, grant_id=grant_id, binding=binding)
        if certificate is None:
            return self._decide(tool, agent_id, (CERTIFICATE_REQUIRED,), None, rule, tenant_id=tenant_id)

        if not isinstance(certificate, EvidenceCertificate):
            try:
                certificate = EvidenceCertificate.from_json(certificate)
            except CertificateError as exc:
                return self._decide(tool, agent_id, (exc.reason_code,), None, rule, tenant_id=tenant_id)
        # The rule can strengthen the certificate's checks, never the reverse.
        strengthened = replace(
            certificate,
            required_checks=tuple(dict.fromkeys(
                [*certificate.required_checks, *rule.required_checks])),
            min_independent_sources=max(certificate.min_independent_sources,
                                        rule.min_independent_sources),
        )
        verification = self.verifier.verify(
            strengthened, agent_id=agent_id, tenant_id=tenant_id, risk=RiskLevel.HIGH)
        if not verification.ok:
            return self._decide(tool, agent_id, verification.reason_codes,
                                verification, rule, certificate=certificate, tenant_id=tenant_id)
        authority_reason = self._authority(certificate, rule)
        if authority_reason:
            return self._decide(tool, agent_id, (authority_reason,), verification, rule,
                                certificate=certificate, tenant_id=tenant_id)
        binding = binding_digest(tool, agent_id, tenant_id, request, certificate)

        if rule.requires_human_approval:
            if approval is None:
                return self._decide(tool, agent_id, (HUMAN_APPROVAL_REQUIRED,),
                                    verification, rule, certificate=certificate, tenant_id=tenant_id)
            if (approval.approver_id not in self.policy.approvers
                    or approval.approver_id == agent_id
                    or approval.certificate_digest != certificate.digest()
                    or (approval.binding is not None and approval.binding != binding)):
                return self._decide(tool, agent_id, (APPROVAL_INVALID,),
                                    verification, rule, certificate=certificate, tenant_id=tenant_id)

        grant_id = grant.grant_id if isinstance(grant, Grant) else grant
        if rule.requires_grant or grant_id is not None:
            if grant_id is None:
                return self._decide(tool, agent_id, (GRANT_REQUIRED,), verification, rule,
                                    certificate=certificate, tenant_id=tenant_id, binding=binding)
            problem = self._check_grant(grant_id, tool, agent_id, binding)
            if problem:
                return self._decide(tool, agent_id, (problem,), verification, rule,
                                    certificate=certificate, tenant_id=tenant_id,
                                    grant_id=grant_id, binding=binding)
        return self._decide(tool, agent_id, (ALLOWED,), verification, rule,
                            allowed=True, certificate=certificate, tenant_id=tenant_id,
                            grant_id=grant_id, binding=binding)

    @staticmethod
    def _parse_claim_certificates(
        certificates: Mapping[str, EvidenceCertificate | Mapping[str, Any]],
    ) -> dict[str, EvidenceCertificate]:
        parsed: dict[str, EvidenceCertificate] = {}
        for claim_id, value in certificates.items():
            if not isinstance(claim_id, str) or not claim_id:
                raise CertificateError("invalid_claim_id", "claim certificate keys must be non-empty strings")
            cert = value if isinstance(value, EvidenceCertificate) else EvidenceCertificate.from_json(value)
            if cert.claim_id != claim_id:
                raise CertificateError("claim_id_mismatch", "certificate claim_id does not match its policy key")
            parsed[claim_id] = cert
        return parsed

    def _evaluate_requirement_graph(
        self, graph: RequirementGraph, certificates: Mapping[str, EvidenceCertificate],
        rule: ToolRule, agent_id: str, tenant_id: str | None,
    ) -> tuple[bool, CertificateVerification | None, set[str]]:
        cache: dict[tuple[str, int], tuple[bool, CertificateVerification | None]] = {}

        def verify_claim(claim_id: str, min_sources: int = 1):
            cert = certificates.get(claim_id)
            if cert is None:
                return False, None
            key = (claim_id, min_sources)
            if key not in cache:
                strengthened = replace(
                    cert,
                    required_checks=tuple(dict.fromkeys([*cert.required_checks, *rule.required_checks])),
                    min_independent_sources=max(cert.min_independent_sources,
                                                rule.min_independent_sources, min_sources),
                )
                result = self.verifier.verify(strengthened, agent_id=agent_id,
                                              tenant_id=tenant_id, risk=RiskLevel.HIGH)
                if result.ok:
                    reason = self._authority(cert, rule)
                    if reason:
                        result = replace(result, ok=False, reason_codes=(reason,))
                cache[key] = (result.ok, result)
            return cache[key]

        def visit(node, active: frozenset[str] = frozenset()):
            if isinstance(node, ClaimRequirement):
                ok, result = verify_claim(node.claim_id)
                return ok, result, {node.claim_id} if ok else set()
            if isinstance(node, IndependentSourcesRequirement):
                ok, result = verify_claim(node.claim_id, node.min_sources)
                return ok, result, {node.claim_id} if ok else set()
            if isinstance(node, RuleReference):
                if node.rule_id in active:
                    return False, None, set()
                return visit(graph.rules[node.rule_id], active | {node.rule_id})
            if isinstance(node, TemporalRequirement):
                # decision_time requires a separately authenticated timestamp,
                # which this API does not yet accept. Fail closed. action_time
                # is measured from the certificate's signed issuance time.
                if node.anchor == "decision_time":
                    return False, None, set()
                ok, result, used = visit(node.requirement, active)
                now = self.fabric.now()
                if not ok or any(now < certificates[c].issued_at_ms
                                 or now - certificates[c].issued_at_ms > node.max_age_ms
                                 for c in used):
                    return False, result, set()
                return True, result, used
            if isinstance(node, AllOfRequirement):
                results = [visit(child, active) for child in node.requirements]
                ok = all(result[0] for result in results)
                used = set().union(*(result[2] for result in results)) if ok else set()
                verification = next((result[1] for result in results if result[1] is not None), None)
                return ok, verification, used
            if isinstance(node, AnyOfRequirement):
                for child in node.requirements:
                    result = visit(child, active)
                    if result[0]:
                        return result
                return False, next((result[1] for child in node.requirements
                                    if (result := visit(child, active))[1] is not None), None), set()
            return False, None, set()

        ok, verification, used = visit(graph.root)
        return ok, verification, used

    # --- origin-bound authority and exact-action grants --------------------

    def _authority(self, certificate: EvidenceCertificate, rule: ToolRule) -> str | None:
        from . import authority

        for item in certificate.evidence if rule.min_authority != authority.UNTRUSTED else ():
            try:
                found = authority.of(self.fabric, item.memory_id)
            except Exception:
                return STATE_UNAVAILABLE
            if found.kind == "instruction":
                return INSTRUCTION_EVIDENCE
            if not found.at_least(rule.min_authority):
                return AUTHORITY_INSUFFICIENT
        if rule.require_fresh:
            from .freshness import FRESH, LOCAL, LeaseBook, freshness_of

            book = self.leases if self.leases is not None else LeaseBook()
            for item in certificate.evidence:
                try:
                    if freshness_of(self.fabric, item.memory_id, book) not in (FRESH, LOCAL):
                        return EVIDENCE_NOT_FRESH
                except KeyError:
                    return STATE_UNAVAILABLE
        if rule.refuse_suspicious or rule.refuse_provisional:
            from .validation import assess

            for item in certificate.evidence:
                try:
                    level = assess(self.fabric, item.memory_id).level
                except KeyError:
                    return STATE_UNAVAILABLE
                # Refusing the provisional means refusing the worse, too.
                if level == "suspicious" and (rule.refuse_suspicious or rule.refuse_provisional):
                    return EVIDENCE_SUSPICIOUS
                if level == "provisional" and rule.refuse_provisional:
                    return EVIDENCE_PROVISIONAL
        return None

    def issue_grant(self, tool: str, agent_id: str, issuer: str, *,
                    certificate: EvidenceCertificate | None = None,
                    claim_certificates: Mapping[str, EvidenceCertificate] | None = None,
                    request: ActionRequest | None = None,
                    tenant_id: str | None = None, ttl_s: float = 60.0) -> Grant:
        """A grant for one exact action, valid for `ttl_s` and consumed by its first use.

        The issuer is the host or a human; it must not be the agent.
        """
        from .ids import new_ulid

        if issuer == agent_id:
            raise ValueError("an agent cannot grant itself an action")
        if not 0 < ttl_s <= MAX_GRANT_TTL_S:
            raise ValueError(f"ttl_s must be in (0, {MAX_GRANT_TTL_S}]")
        if tool not in self.policy.grants.get(agent_id, frozenset()):
            raise ValueError(f"{agent_id} is not granted {tool}")
        binding = binding_digest(tool, agent_id, tenant_id, request, certificate,
                                 claim_certificates)
        grant = Grant("gr_" + new_ulid(), tool, agent_id, binding,
                      self.fabric.now() + int(ttl_s * 1000))
        self.fabric._emit(ev.grant_issued(ts=self.fabric.now(), grant_id=grant.grant_id,
                                          tool=tool, agent_id=agent_id, binding=binding,
                                          expires_ms=grant.expires_ms, issuer=issuer))
        return grant

    def revoke_grant(self, grant_id: str, issuer: str) -> None:
        self.fabric._emit(ev.grant_issued(ts=self.fabric.now(), grant_id=grant_id, tool="",
                                          agent_id="", binding="", expires_ms=0,
                                          issuer=issuer, revoked=True))

    def _check_grant(self, grant_id: str, tool: str, agent_id: str, binding: str) -> str | None:
        issued = None
        revoked = False
        for event in self.fabric.log.read_types([ev.EventType.GRANT_ISSUED]):
            if event.payload.get("grant_id") != grant_id:
                continue
            if event.payload.get("revoked"):
                revoked = True
            elif issued is None:
                issued = event.payload
        if issued is None:
            return GRANT_UNKNOWN
        if revoked:
            return GRANT_REVOKED
        if self.fabric.now() >= int(issued["expires_ms"]):
            return GRANT_EXPIRED
        if (issued["tool"], issued["agent"], issued["binding"]) != (tool, agent_id, binding):
            return GRANT_MISMATCH
        for event in self.fabric.log.read_types([ev.EventType.ACTION_GATED]):
            if event.payload.get("grant_id") == grant_id and event.payload.get("allowed"):
                return GRANT_REPLAYED
        return None

    def execute(
        self,
        tool: str,
        agent_id: str,
        run: Callable[[str], Any],
        certificate: EvidenceCertificate | Mapping[str, Any] | None = None,
        *,
        key: str,
        lease_s: float = 2.0,
        tenant_id: str | None = None,
        approval: Approval | None = None,
        session: Any = None,
        retry: bool = False,
        request: ActionRequest | None = None,
        grant: Grant | str | None = None,
        claim_certificates: Mapping[str, EvidenceCertificate | Mapping[str, Any]] | None = None,
    ) -> ActionExecution:
        """Authorize and run `run(key)` with no window between them (module docstring).

        `run` is the tool's side effect. It receives `key` so it can
        deduplicate. It must not call this store.
        """
        if not 0 < lease_s < MAX_LEASE_S:
            raise ValueError(f"lease_s must be in (0, {MAX_LEASE_S}); writers in other "
                             "processes give up after the store's busy timeout")
        if isinstance(certificate, Mapping):
            try:
                certificate = EvidenceCertificate.from_json(certificate)
            except CertificateError:
                pass  # authorize reports malformed certificates as a refusal
        # Bind the durable attempt and idempotency key to authenticated identity
        # before writing anything. Never let a caller-supplied agent label stand
        # in for the principal presented by a session credential.
        if session is not None:
            try:
                principal = session.principal()
            except Exception:
                pass  # authorize records the credential-invalid refusal
            else:
                agent_id, tenant_id = principal.agent_id, principal.tenant_id
        parsed_claim_certificates = None
        if claim_certificates is not None:
            try:
                parsed_claim_certificates = self._parse_claim_certificates(claim_certificates)
            except CertificateError:
                pass
        action_certificates = dict(parsed_claim_certificates or {})
        if (self.policy.tools.get(tool) is not None
                and self.policy.tools[tool].requirement_graph is not None
                and isinstance(certificate, EvidenceCertificate)):
            action_certificates.setdefault(certificate.claim_id, certificate)
        action_binding = binding_digest(
            tool, agent_id, tenant_id, request,
            None if self.policy.tools.get(tool) is not None
            and self.policy.tools[tool].requirement_graph is not None
            else certificate if isinstance(certificate, EvidenceCertificate) else None,
            action_certificates if self.policy.tools.get(tool) is not None
            and self.policy.tools[tool].requirement_graph is not None else parsed_claim_certificates,
        )
        if isinstance(certificate, Mapping):
            action_binding = hashlib.sha256(json.dumps({
                "base": action_binding, "invalid_certificate": certificate,
            }, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()
        fabric = self.fabric
        tool_digest = self._tool_digest(tool)
        # Recorded and committed before the fence, so it survives a crash
        # that rolls the fence's transaction back. Without it, a process that
        # died mid-tool left no trace and the next call ran the tool again as
        # though nothing had happened (tests/test_action_crash.py).
        with fabric.lock, fabric._transaction():
            prior = self._last_execution(key)
            if prior is not None:
                if prior.get("binding") != action_binding:
                    return ActionExecution(REFUSED, None, key, error=IDEMPOTENCY_CONFLICT)
                if prior["outcome"] == EXECUTED:
                    return ActionExecution(ALREADY_EXECUTED, None, key)
                if prior["outcome"] != REFUSED and not retry:
                    return ActionExecution(REFUSED, None, key, error=(
                        f"{RETRY_REQUIRED}: the last attempt {prior['outcome']} with an unknown "
                        "effect; pass retry=True to re-verify and run again"))
            fabric._emit(ev.action_attempted(ts=fabric.now(), agent_id=agent_id, key=key,
                                             tool=tool, tenant_id=tenant_id,
                                             binding=action_binding,
                                             policy_version=self.policy.policy_id,
                                             tool_digest=tool_digest))
        with fabric.lock, fabric._transaction():
            decision = self.authorize(tool, agent_id, certificate, tenant_id=tenant_id,
                                      approval=approval, session=session,
                                      request=request, grant=grant,
                                      claim_certificates=claim_certificates)
            if not decision.allowed:
                # Settles the attempt recorded above: nothing ran.
                fabric._emit(ev.action_executed(
                    ts=fabric.now(), agent_id=decision.agent_id, key=key, tool=tool,
                    outcome=REFUSED, fenced=True, watermark=None,
                    lease_ms=int(lease_s * 1000), elapsed_ms=0, evidence=[],
                    tenant_id=tenant_id, binding=action_binding,
                    policy_version=self.policy.policy_id, tool_digest=tool_digest))
                return ActionExecution(REFUSED, decision, key)
            box: dict[str, Any] = {}

            def work() -> None:
                try:
                    box["result"] = run(key)
                except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
                    box["error"] = f"{type(exc).__name__}: {exc}"

            started = time.monotonic()
            worker = threading.Thread(target=work, name=f"action-{key}", daemon=True)
            worker.start()
            worker.join(lease_s)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            if worker.is_alive():
                outcome, fenced = TIMED_OUT, False
            elif "error" in box:
                outcome, fenced = FAILED, True
            else:
                outcome, fenced = EXECUTED, True
            verification = decision.verification
            all_certificates = dict(parsed_claim_certificates or {})
            if isinstance(certificate, EvidenceCertificate):
                all_certificates.setdefault(certificate.claim_id, certificate)
            evidence = [list(item) for item in sorted({(e.memory_id, e.version)
                                                       for cert in all_certificates.values()
                                                       for e in cert.evidence})]
            fabric._emit(ev.action_executed(
                ts=fabric.now(), agent_id=decision.agent_id, key=key, tool=tool,
                outcome=outcome, fenced=fenced,
                watermark=verification.verified_at_watermark if verification else None,
                lease_ms=int(lease_s * 1000), elapsed_ms=elapsed_ms, evidence=evidence,
                tenant_id=tenant_id, binding=action_binding,
                policy_version=self.policy.policy_id, tool_digest=tool_digest))
        return ActionExecution(outcome, decision, key, result=box.get("result"),
                               error=box.get("error"), fenced=fenced)

    def _tool_digest(self, tool: str) -> str:
        """Resolve an explicit descriptor digest or hash this gate's tool rule."""
        rule = self.policy.tools.get(tool)
        if rule is not None and rule.tool_digest is not None:
            digest = rule.tool_digest
            if len(digest) == 64 and all(char in "0123456789abcdef" for char in digest):
                return digest
            raise ValueError("ToolRule.tool_digest must be a lowercase SHA-256 hex digest")
        rule_body = None
        if rule is not None:
            rule_body = {item.name: getattr(rule, item.name) for item in fields(rule)
                         if item.name != "requirement_graph"}
            if rule.requirement_graph is not None:
                rule_body["requirement_graph"] = rule.requirement_graph.to_dict()
        body = {"tool": tool, "rule": rule_body}
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _last_execution(self, key: str) -> Mapping[str, Any] | None:
        """The last settled outcome for this key; `uncertain` if an attempt has none.

        A refusal under the fence records outcome `refused`: nothing ran, so
        it is no reason to require a retry, and it is skipped here.
        """
        last: Mapping[str, Any] | None = None
        for event in self.fabric.log.read_types([ev.EventType.ACTION_ATTEMPTED,
                                                 ev.EventType.ACTION_EXECUTED]):
            if event.payload.get("key") != key:
                continue
            if event.type == ev.EventType.ACTION_ATTEMPTED:
                last = {"outcome": UNCERTAIN, "binding": event.payload.get("binding")}
            else:
                last = event.payload
        return last

    # --- audit -----------------------------------------------------------

    def _decide(
        self,
        tool: str,
        agent_id: str,
        reasons: tuple[str, ...],
        verification: CertificateVerification | None,
        rule: ToolRule | None,
        allowed: bool = False,
        certificate: EvidenceCertificate | None = None,
        tenant_id: str | None = None,
        grant_id: str | None = None,
        binding: str | None = None,
        claim_certificates: Mapping[str, EvidenceCertificate] | None = None,
    ) -> ActionDecision:
        decision = ActionDecision(
            allowed=allowed, tool=tool, agent_id=agent_id,
            reason_codes=reasons, verification=verification,
        )
        if self.audit and (rule is None or rule.protected):
            try:
                self.fabric._emit(ev.action_gated(
                    ts=self.fabric.now(),
                    agent_id=agent_id,
                    tool=tool,
                    allowed=allowed,
                    reason_codes=list(reasons),
                    policy_id=self.policy.policy_id,
                    claim_id=certificate.claim_id if certificate else None,
                    certificate_digest=certificate.digest() if certificate else None,
                    evidence=[list(item) for item in sorted({(e.memory_id, e.version)
                                                             for cert in ({**(claim_certificates or {}),
                                                                           **({certificate.claim_id: certificate}
                                                                              if certificate else {})}).values()
                                                             for e in cert.evidence})],
                    claim_certificates={**(claim_certificates or {}),
                                       **({certificate.claim_id: certificate}
                                          if certificate else {})},
                    watermark=verification.verified_at_watermark if verification else None,
                    tenant_id=tenant_id,
                    required_checks=list(dict.fromkeys(
                        [*(certificate.required_checks if certificate else ()),
                         *(rule.required_checks if rule else ())])),
                    min_independent_sources=max(
                        certificate.min_independent_sources if certificate else 0,
                        rule.min_independent_sources if rule else 0),
                    grant_id=grant_id, binding=binding,
                ))
            except Exception:
                # An audit write that fails must not turn a refusal into an
                # allow, and must not let an allow proceed unrecorded.
                if allowed:
                    return ActionDecision(
                        allowed=False, tool=tool, agent_id=agent_id,
                        reason_codes=(STATE_UNAVAILABLE,), verification=verification,
                        notes=("audit write failed",),
                    )
        return decision


def unfenced_changes(fabric: Any) -> list[dict[str, Any]]:
    """Changes to an action's evidence that landed after its fence was released.

    For every `timed_out` execution: lifecycle changes to any memory it rested
    on, recorded after the execution. Each is a withdrawal the tool may have
    acted against. That is the bounded remainder of S14, made visible rather
    than closed. A fenced execution cannot appear here, because nothing could
    commit inside its window.
    """
    out: list[dict[str, Any]] = []
    pending: list[tuple[int, Mapping[str, Any]]] = []
    for event in fabric.log.read_types([ev.EventType.ACTION_EXECUTED,
                                        ev.EventType.LIFECYCLE_CHANGED]):
        if event.type == ev.EventType.ACTION_EXECUTED:
            if not event.payload.get("fenced", True):
                pending.append((event.seq or 0, event.payload))
            continue
        memory_id = event.payload.get("memory_id")
        for seq, execution in pending:
            if any(e[0] == memory_id for e in execution.get("evidence", [])):
                out.append({"key": execution["key"], "tool": execution["tool"],
                            "memory_id": memory_id, "change_seq": event.seq,
                            "execution_seq": seq})
    return out


def reconciliation_ledger(fabric: Any) -> list[dict[str, Any]]:
    """Classify each action key from its durable attempt and outcome events.

    This is a local evidence ledger, not a claim about an external system's
    state. A missing outcome, callback error, or released fence remains
    `unknown`; only a successful fenced receipt is `completed`, and only a
    gate refusal is `definitely_unexecuted`.
    """
    latest: dict[str, dict[str, Any]] = {}
    for event in fabric.log.read_types([ev.EventType.ACTION_ATTEMPTED,
                                        ev.EventType.ACTION_EXECUTED]):
        payload = event.payload
        key = str(payload.get("key", ""))
        if not key:
            continue
        row = latest.setdefault(key, {
            "key": key, "attempt_count": 0, "status": "unknown",
            "tool": payload.get("tool"), "tenant_id": payload.get("tenant_id"),
            "agent_id": event.agent_id, "binding": payload.get("binding"),
            "policy_version": payload.get("policy_version"),
            "tool_digest": payload.get("tool_digest"),
            "last_event_seq": event.seq,
        })
        row["tool"] = payload.get("tool", row.get("tool"))
        row["tenant_id"] = payload.get("tenant_id", row.get("tenant_id"))
        row["agent_id"] = event.agent_id or row.get("agent_id")
        row["binding"] = payload.get("binding", row.get("binding"))
        row["policy_version"] = payload.get("policy_version", row.get("policy_version"))
        row["tool_digest"] = payload.get("tool_digest", row.get("tool_digest"))
        row["last_event_seq"] = event.seq
        if event.type == ev.EventType.ACTION_ATTEMPTED:
            row["attempt_count"] += 1
            row["status"] = "unknown"
            row["last_outcome"] = "attempted_without_receipt"
        else:
            outcome = payload.get("outcome")
            row["last_outcome"] = outcome
            if outcome == REFUSED:
                row["status"] = "definitely_unexecuted"
            elif outcome == EXECUTED and payload.get("fenced", True):
                row["status"] = "completed"
            else:
                row["status"] = "unknown"
    for row in latest.values():
        row["reconciliation_required"] = row["status"] == "unknown"
    return [latest[key] for key in sorted(latest)]
