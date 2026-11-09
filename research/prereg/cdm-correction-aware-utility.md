# CDM-199 correction-aware utility preregistration

## Frozen unit and labels

One unit is an authorized recorded action considered after a correction. The
positive label is `depended` from the existing recorded-policy dependence
verifier: without the corrected source and its reach, the evidence no longer
satisfies the action's recorded policy. This is not a label for hidden agent
reasoning. Any other eligible action is negative (`would_stand` or unrelated).
`reviewed` means a human review request was actually routed, not merely emitted
as an informational row.

## Frozen utility

For a scenario with `N` eligible actions:

`U = (10*TP - 10*FN - 1*FP - 0.1*R) / N`

where TP is a dependent action routed for review, FN is a dependent action
missed, FP is an unnecessary review, and R is the number of review requests.
The weights and scorer are fixed in `benchmarks/cdm_correction_utility.py`.

## Frozen GO rule

On at least 20 paired confirmatory scenarios, a candidate strategy is GO only
if its mean paired utility gain over the strongest preregistered baseline is
at least `+0.10` utility per eligible action, the paired 95% bootstrap lower
confidence bound is strictly above zero, it misses zero `depended` actions,
and it has zero unauthorized/stale/erased-evidence accepts or authority
mutations. Otherwise the result is NO-GO or inconclusive; no threshold tuning
is allowed on confirmatory cases.

Development seeds: 20261901–20261910. Confirmatory seeds: 20261911–20261930.
The CDM-198 three-action fixture is a protocol sanity check only, not a
confirmatory result. It yields utilities 2.567 (blanket), 3.300 (dependence),
and 2.933 (CDM review rows), so the current fixture does not justify replacing
the existing dependence route with CDM review routing.
