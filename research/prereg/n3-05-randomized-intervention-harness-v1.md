# N3-05 — Seeded randomized intervention harness

Status: preregistered before generating the harness qualification result.

## Harness contract

For each unique unit ID, derive independent pseudorandom draws from a frozen
master seed and domain-separated stream labels (`treatment` and `observation`).
The draw is a deterministic SHA-256 based uniform value, so replay is
independent of row order and does not rely on process-global random state.
Treatment and observation use separately configured probabilities. The
returned record stores the treatment probability, realized assignment
propensity, observation probability, assignment, and observation indicator.
Probabilities are validated; treatment probabilities must be strictly between
zero and one, while observation probability may be zero or one.

## Qualification fixture

Use 10,000 named episodes with difficulty-stratified treatment probabilities
(`0.7` for easy, `0.3` for hard). Observation probabilities are `0.8` for
treated and `0.9` for control episodes. Repeat the same seed and verify the
entire record sequence and SHA-256 manifest are identical. Verify a changed
seed changes the record sequence, every assigned treatment has the correct
realized propensity, every row retains both probability fields, and empirical
assignment/observation rates are within `0.05` of their registered
probabilities in each stratum.

This qualifies reproducible assignment and observation logging. It does not
claim treatment-effect recovery, missing-data identification, cryptographic
randomness, or security against an operator who chooses the seed after seeing
outcomes.
