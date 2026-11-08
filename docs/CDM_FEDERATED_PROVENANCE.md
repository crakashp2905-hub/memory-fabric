# CDM source roots across imports and copies

`assess_fabric_source_roots(fabric, session, evidence_ids)` resolves source
roots from the current local lineage and recognized copy graph, then follows
the portable root commitment recorded on an actual federation import. It
rechecks the supplied session's current read permission and each evidence
item's current usability before returning a root count. A missing or malformed
root on an imported record yields `AMBIGUOUS_LINEAGE` and no count.

Only records whose provenance method is `imported` may supply remote root
metadata. A locally authored record cannot claim a remote source merely by
placing a `federation` object in user context; it resolves to its local store
and source root. The assessment returns opaque `store-id/memory-id` group
labels and performs no network request. It does not prove that a remote store
is currently available or that the original evidence remains active there.
