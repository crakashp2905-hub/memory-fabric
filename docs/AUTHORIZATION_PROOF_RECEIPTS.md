# Authorization proof receipts

`issue_authorization_receipt` runs the normal `ActionGate.authorize` check and
returns its decision with an `AuthorizationProofReceipt`. The content-free
receipt binds:

- the requirement-graph schema version and digest, including typed predicates;
- the tool-policy digest and policy ID;
- exact evidence memory IDs and versions and the serialized certificates;
- the action-binding digest (tool, principal, tenant, request and certificate
  set), plus the authorization digest and original allow/refusal;
- the verification watermark and the gate's reason codes.

The receipt does not store evidence text or raw request parameters. To replay,
the verifier needs the matching `ActionGate` and the original `ActionRequest`
(and any approval or grant supplied at issuance). `verify_authorization_receipt`
reruns verification against current state without appending audit events or
executing a tool. It returns `VERIFIED_ALLOW` or `VERIFIED_REFUSAL` when the
original decision still matches. If policy, request, evidence, or requirements
have changed, it returns `INVALIDATED` with specific reason codes such as
`requirement_digest_changed`, `authorization_context_changed`,
`evidence_version_moved`, or `evidence_withdrawn`. A malformed or altered
receipt returns `TAMPERED`.

This is a replayable integrity receipt, not a bearer capability or a digital
signature. Its SHA-256 digest detects accidental or uncoordinated mutation
only when the expected digest is trusted. Sign it or anchor it in a trusted
append-only log when origin authentication is required. Verification never
re-authorizes or executes the action on the caller's behalf.
