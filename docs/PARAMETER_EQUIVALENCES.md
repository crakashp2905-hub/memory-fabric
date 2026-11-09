# Bounded parameter equivalences

`ParameterEquivalences` lets an application register reviewed local phrases
that denote the same parameter, such as `trip current` and `overcurrent
setting`. The table is data, not a model call: matching is deterministic,
limited to 64 groups and 16 aliases per group, and never learns new entries.

Pass a table to `RetrievalResult.answerability(..., equivalences=table)`. A
registered paraphrase can satisfy the parameter portion of the structural
coverage check, but identifiers and a stated value are still mandatory. When
a table is supplied and the question's parameter is not registered, the
result is `undetermined` and `should_abstain` is true. The API never guesses
that novel wording is equivalent.

This mechanism is intentionally local. Different domains may use the same
wording differently, so applications should version and review their tables
alongside their own schemas.
