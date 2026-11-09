# CDM checkpoint invalidation classification

Checkpoint invalidation has two distinct outcomes:

| Invalidation | Correctness/security effect | Utility effect |
|---|---|---|
| Invalidate entries that cite the corrected, withdrawn, or erased memory | Required; prevents reuse of a checkpoint whose evidence version is stale | Necessary recomputation for affected work |
| Clear every checkpoint after one memory changes | Conservative for cache reuse; every later lookup still rechecks current authorization and evidence | Harmful when unrelated checkpoints remain current: they become avoidable misses and must be rebuilt |
| Keep an unrelated entry but current access/version has changed | Entry may remain stored, but `get` must refuse it after revalidation | No unsafe hit; storage persists until eviction/invalidation |

The classification is intentionally scoped to the in-memory checkpoint cache.
It does not claim that all dependency types are known or that direct evidence
references capture derived semantic dependencies. If dependency completeness is
unknown, broader invalidation can be a justified conservative choice. The
regression fixture demonstrates the narrow case where the changed memory ID
is known and a second checkpoint's evidence and current authorization are
independent and valid: targeted invalidation removes the first and preserves
the second, while blanket clear needlessly removes both.
