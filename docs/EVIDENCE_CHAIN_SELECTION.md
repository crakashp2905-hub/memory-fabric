# Evidence-chain bridge selection

Chain reconstruction is bounded graph search, not greedy query-term coverage.
A necessary intermediate may contain none of the query terms; it is selected
when shared, discriminating non-query terms connect otherwise separate proof
components. Returned bridge steps use reason `DEPENDENCY_REQUIRED`, have empty
`covers`, and name their linking terms in `bridges`.

`EvidenceChain.insufficient_reason` is stable and machine-readable:

- `NO_QUERY_ANCHOR`
- `MISSING_QUERY_TERMS:<sorted terms>`
- `DISCONNECTED_EVIDENCE`
- `SEARCH_BUDGET_EXHAUSTED`
- `INSUFFICIENT_CHAIN` (defensive fallback)

The acceptance fixture runs five seeded four-hop examples. Each has two middle
records with zero query-term overlap and distractors with similar surface
terms. All four required records must be recovered. Removing the first bridge
must return `DISCONNECTED_EVIDENCE`, never a confident partial answer.

Search remains subject to authorization and lifecycle eligibility before graph
construction; a withdrawn or out-of-tenant bridge is not recoverable and makes
the result incomplete.

