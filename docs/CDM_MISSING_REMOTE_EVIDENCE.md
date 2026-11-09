# CDM handling of unavailable remote evidence

Attribution requires a source-root mapping for every evidence ID before it can
report an independent-root count. A missing mapping, including an unavailable
remote reference, produces `AMBIGUOUS_LINEAGE` and a null count. Known local
roots may remain visible in the diagnostic groups, but missing remote evidence
is never assigned its own root and cannot raise the count. Callers must not
interpret a missing remote as absent, disproven, independent, or current.

The CDM attribution assessment is a pure local operation. It performs no
network request or remote retry. A caller may retry retrieval through a
separately governed federation flow and then rerun attribution with complete
current provenance. Until then, exact independence and attribution claims are
unavailable.
