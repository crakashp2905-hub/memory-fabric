# R4-06 order and identity randomization v1

## Conditions

Run all five registered matched scripted-agent arms at 50 agents on seeds
701, 709, and 719. For each seed/arm pair, compare a seeded randomized
condition with a deterministic ordinal control. The randomized condition
uses opaque agent IDs and permutes insertion order of `publish`, `archive`,
and `notify`; only `publish` is granted. Task order remains the registered
seed-shuffled manifest. Answer-position coverage is evaluated separately by
R4-05.

## Acceptance

All arms within a condition must receive identical task order, evidence
context, and runtime grants. Randomized and ordinal conditions must produce
exactly identical aggregate decisions, unsafe-action counts, and stale-action
counts (absolute tolerance 0 attempts). A mismatch fails the qualification.

## Limits

This measures deterministic scripted policy behavior, not model robustness.
Only registry insertion order is randomized; no external tools execute. The
answer-position control is the separate R4-05 synthetic fixture.
