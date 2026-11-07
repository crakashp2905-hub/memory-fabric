# Fixed-budget evidence packages

`chains.pack_evidence` converts a complete `EvidenceChain` into a bounded
package. Its unit is the documented local estimate of one token per four
characters, rounded up per citation. The returned object records the estimate
and configured budget; it does not claim model-provider token counts.

The packer inserts every `necessary=True` step before considering supporting
steps. If the mandatory set does not fit, it returns no partial package,
`complete=False`, every required memory ID in `missing_required`, and the
stable reason `MANDATORY_EVIDENCE_EXCEEDS_BUDGET`. An already incomplete chain
instead preserves its precise chain-search failure reason.

This fail-closed result lets callers request a larger context or abstain. It
prevents a superficially valid answer package whose citation list silently
lost the bridge that made the answer supported.
