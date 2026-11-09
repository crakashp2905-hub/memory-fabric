# N4-02 — Hierarchical summaries and edge certificates

`compact_hierarchy` partitions active session memories in stable creation/id/version
order, builds deterministic leaf summaries, then a root summary. Each leaf carries
a SHA-256 edge certificate binding its content, exact source versions, and
fact-level dependency map. The root certificate binds its own content and
sources to the ordered leaf certificates. The root also retains direct provenance
edges to all original versions, making the affected path explicit and auditable.

In the ten-source oracle, `leaf_size=4` produces stable groups of 4/4/2 and
repeated compaction produces identical root content. A source revision from v1
to v2 contests only the leaf using that source and the dependent root; other
leaf summaries remain active. Revision propagation now recomputes derived
support nearest-first, so an active summary cannot keep citing a superseded
parent version. Stale certificate verification is refused.

| Verification | Result |
|---|---:|
| Hierarchy, dependency, existing compaction, and action-race suite | 27 passed |
| Revision, authority, correction, branching compatibility suite | 77 passed, 53 subtests passed |
| Ruff | Passed |

This qualifies a deterministic two-level local hierarchy. Deeper trees,
distributed propagation, and external model summaries remain untested. The
SHA-256 certificates provide integrity checking, not signatures against an
authorized writer that can rewrite both the data and digest.
