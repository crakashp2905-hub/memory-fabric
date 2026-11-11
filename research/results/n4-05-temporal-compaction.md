# N4-05 temporal compaction evidence

The fixture revises a future-valid preference after recording an older, already-expired preference. The summary keeps the revised text and the older alternative, while per-source metadata retains exact ID/version, version author, recorded time, and the half-open valid-time interval. Applicability is checked at a declared world time; transaction order is not used as a truth rule. Hierarchical certificates also verify the source metadata. See the JSON for checks and limits.
