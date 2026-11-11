# Formal lifecycle transition contract

The normative, machine-checked table is `STATE_TRANSITIONS.json`. It describes
the six state-changing operations requested by the offline qualification plan:
append, correct, withdraw, erase, branch, and merge. Preconditions are refusal
boundaries, postconditions are committed observable effects, and invariants
must have tests that fail when the guarantee breaks.

Corrections and withdrawals never overwrite history. Erasure destroys content
keys while retaining non-content audit lineage. Branch changes are ordinary
screened memories held outside main retrieval until an authorized, fresh
preview is merged. Merge deliberately delegates to ordinary append, correction
and withdrawal operations so it cannot create a second lifecycle semantics.

The contract does not claim that arbitrary storage corruption is recoverable,
that old backups lose keys automatically, or that physical multi-host ordering
is proven. Those remain explicit limitations.
