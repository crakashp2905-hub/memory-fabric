# Decision feature and policy provenance contract

`DecisionContext` is a host-built snapshot of the query, closed option set, evidence IDs and JSON-like constraints supplied to a decision model. Nested mappings and sequences are copied into immutable containers. Feature keys must be strings; arbitrary mutable objects are rejected. This prevents a model from mutating the context shared with its caller.

A valid `DecisionProposal` may cite only unique, non-empty evidence IDs already present in its context. Its selected option must be one of the host-supplied options. The model cannot add an option, grant, tool rule, approver, or policy. `ActionPolicy` likewise snapshots the host's tool rules and grants into immutable mappings when constructed.

These are provenance and data-flow boundaries, not a sandbox around arbitrary Python model code. The decision model returns a proposal; the host still passes a requested tool through `ActionGate`, which independently checks the host policy, grants, evidence, approvals and any exact-action grant. A high-confidence proposal cannot authorize itself.

Constrained Code Mode adds the digest of the exact parsed source to the
`ActionRequest` provenance. The action binding covers this field when the host
requires human approval or an exact-action grant. This detects source changes
that preserve a tool's arguments; it does not change authorization when the
host has no source-bound approval requirement. The code-mode parser still
accepts only literal tool calls, and handlers remain outside its sandbox.

Contract evidence is in `tests/test_n6_04_feature_provenance.py` and the neighboring decision and action-gate regression tests.
