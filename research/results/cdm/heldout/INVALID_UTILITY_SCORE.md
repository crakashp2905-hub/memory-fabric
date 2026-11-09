# Invalid utility score notice

The v1 held-out utility comparison in this directory is invalid. Its
preregistered reward assigned `investigate` +0.2, while the oracle action on a
negative case (`monitor`) received +0.1. The supposed oracle therefore was not
an upper bound. Preserve the raw files for audit, but do not use their utility
summaries as evidence. Posterior parity remains a separate valid code-path
check. The corrected v2 protocol and fresh held-out seeds are in
`research/prereg/cdm-r4-decision-outcome-impact.md`,
`research/prereg/cdm-r5-evaluator-executor-ablations.md`, and
`research/results/cdm/heldout-v2/`.
