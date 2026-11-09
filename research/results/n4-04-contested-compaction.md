# N4-04 contested-compaction evidence

A 10:1 fixture verifies that flat and hierarchical compaction retain both values and render the conflict as unresolved. In the hierarchy, all ten majority reports occupy one leaf and the lone alternative occupies its own leaf; the certified root still renders and maps both alternatives.

The default-hold control keeps the minority assertion in CANDIDATE state and in the review queue, while excluding it from the active summary. This prevents compaction from turning an unreviewed candidate into an actionable fact. See the JSON for exact checks, source binding, and limits.
