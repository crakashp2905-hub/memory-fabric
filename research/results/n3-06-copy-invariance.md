# N3-06 — Copy invariance of causal credit

All permitted subsets were enumerated at copy counts `0, 1, 2, 4, 8`. Each
copy is linked to the irrelevant root by a normal `COPY_RECOGNISED` event. The
oracle outcome depends only on the useful memory.

Across all five worlds, the useful memory's exact average inclusion effect,
exact Shapley value, and IPS estimate remain `1.0`. The sum of exact Shapley
credit and IPS credit for the irrelevant root plus all its copies remains
`0.0`, including at eight copies and 1,024 subsets. Thus recognized irrelevant
duplication does not inflate contrastive causal credit in these enumerated
worlds.

Limitations: this does not cover unrecognized paraphrases or observational
data without overlap. Noncontrastive usage scores are not causal credit and
must not be added across copies.
