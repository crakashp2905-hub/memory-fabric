# Bitemporal historical-read contract

Memory Fabric keeps two independent notions of time for historical reads:

- **Transaction time** (`known_at`) is an inclusive event-log sequence. It
  answers: “What version had this store recorded by this sequence?” Events
  appended after that sequence cannot change the reconstructed belief at that
  sequence.
- **Valid time** (`valid_at`) is an optional domain/event-time point. It
  answers: “Did the version reconstructed at `known_at` apply at this point?”
  It filters the reconstructed version by its half-open validity window; it
  does not select a version that was unknown at `known_at`.

Therefore a late correction is appended as a new transaction. Reading before
that transaction continues to return the old belief. Reading after it returns
the corrected version when its validity window matches. The stable `revise`
API preserves the memory's validity window; it does not accept a replacement
window that could silently reinterpret the original record.

Historical visibility is not historical authorization. Before returning
content, `history_query.query` intersects eligibility at `known_at` with the
current tenant, scope, collection grants, lifecycle state, erasure state, and
hostile-source policy. A current withdrawal, erased key, or revoked grant wins
over an older readable snapshot. Results are marked `archival_only` and carry
no exposure token or action certificate, so they cannot authorize a current
effect.

The executable acceptance fixtures are in `tests/test_history_query.py`.

