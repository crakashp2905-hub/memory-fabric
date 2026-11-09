# N4-06 budgeted compaction evidence

A token budget is checked against the complete summary using an explicit counter and provenance. Every usable source is compulsory. If the summary does not fit, the API returns a structured `CompactionBudgetExceeded` containing the required token count, UTF-8 byte counts, tokenizer identity, and all source IDs; the event store is unchanged. The compacted summary records its limit and observed count when it fits. See JSON for exact checks.
