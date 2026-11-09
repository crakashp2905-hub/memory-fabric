# Retrieval index invalidation

Memory Fabric does not cache retrieval result packages. Its derived query
indexes now contain only active or explicitly requested contested evidence.
Candidate, quarantined, deprecated, deleted, and content-erased memories are
removed before they can be query candidates. Validation adds a candidate;
correction replaces old terms; withdrawal and erasure evict immediately.

Replay and process refresh apply the same rule, so reopening a store cannot
repopulate an index from an ineligible log row. Tenant and scope checks still
run before every search through `restrict_to`; the shared index is a candidate
index, never an authorization cache.

The copy detector is deliberately separate. It retains fingerprints of
quarantined content so re-ingesting a withdrawn poison is contested rather
than treated as new trusted evidence. Those fingerprints are never searched
to answer a query, and erasure removes them.
