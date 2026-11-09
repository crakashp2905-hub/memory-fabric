# Decision feature and policy provenance contract

`DecisionContext` is a host-built snapshot of the query, closed option set, evidence IDs and JSON-like constraints supplied to a decision model. Nested mappings and sequences are copied into immutable containers. Feature keys must be strings; arbitrary mutable objects are rejected. This prevents a model from mutating the context shared with its caller.

A valid `DecisionProposal` may cite only unique, non-empty evidence IDs already present in its context. Its selected option must be one of the host-supplied options. The model cannot add an option, grant, tool rule, approver, or policy. `ActionPolicy` likewise snapshots the host's tool rules and grants into immutable mappings when constructed.

These are provenance and data-flow boundaries, not a sandbox around arbitrary Python model code. The decision model returns a proposal; the host still passes a requested tool through `ActionGate`, which independently checks the host policy, grants, evidence, approvals and any exact-action grant. A high-confidence proposal cannot authorize itself.

Contract evidence is in `tests/test_n6_04_feature_provenance.py` and the neighboring decision and action-gate regression tests.
