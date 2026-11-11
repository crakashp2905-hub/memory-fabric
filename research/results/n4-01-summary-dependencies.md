# N4-01 — Summary fact dependency map

Compaction now reconstructs a fact-level map from every consequential summary
fact to the exact active source memory versions. The map is stored in summary
context alongside ordinary provenance parents. Before a summary can remain
exposable, all extracted source facts must appear in the summary and every
summary fact must resolve to an active source fact. Unsupported summaries fail
closed; quarantined outputs can still be retained for audit with the failed
mapping recorded.

The exact oracle suite passes for a generated extractive summary containing
four unique facts, including both sides of a dispute, duplicate source versions, and a corrected version 2, and for the optional lossless
phrase-dictionary summary. Negative controls verify refusal when a fact is
invented, omitted, or tied to a retracted original. The targeted compaction
suite passed **20 tests**, and Ruff passed.

The extractor defines a consequential fact as one with a recognized identifier
or numeric value. Unstructured qualitative claims without either signal are
not certified by this implementation. This is contract evidence, not an
independent security or model-quality review.
