# R4-05 adversarial near-miss and distractor fixture v1

## Scope

Generate 256 deterministic synthetic cases. Each case contains one current
answer, one superseded same-entity/same-attribute value, and two irrelevant
sibling-entity values. All records share one repeated surface template so a
template-frequency heuristic has no discriminating information. Task values,
distractor values, and opaque identifiers use separate seeded RNG streams
(45051, 45052, 45053).

## Shortcut controls

Measure first-option selection and lexicographically smallest identifier
selection. The fixture passes when each has accuracy at most 0.35; this is a
descriptive shortcut-control ceiling, not a model promotion threshold. Report
answer-position counts, option count, number of near misses and distractors,
and the exact case denominator. Do not claim model performance from these
controls. A future language-model evaluation must use separately authored
paraphrases and a frozen held-out split.

## Result interpretation

The currently generated result is an internal synthetic fixture check. The
source freezes the seeds and the 0.35 shortcut ceiling before generating its
machine-readable result. The hierarchy and result do not constitute a real
agent or model evaluation.
