# Preregistered follow-up — N5-10 false-consensus recovery

- **Written:** 2026-11-09, after the original preregistered batch returned only 112 eligible seeds and was labeled underpowered. The original result remains unchanged at [`n5-10-false-consensus-recovery.json`](../results/n5-10-false-consensus-recovery.json).
- **Purpose:** A fixed-seed follow-up to satisfy the original sample-size floor and estimate whether H4b's post-event intervention adds recovery beyond collapse and topology change. This is a follow-up prompted by the original batch's low eligibility, not an independent blinded replication; the original effect estimates have been observed.
- **Protocol basis:** The original [N5-10 preregistration](n5-10-false-consensus-recovery-v1.md) and [H4b preregistration](h4-topology-and-diversity.md). All outcomes, arms, thresholds and analysis below retain the original definitions.

## Fixed design

- Attempt exactly seeds `20000..24999` (5,000 seeds); do not replace, extend or stop early based on results.
- Use the exact original checkpoint generation and four paired continuations: `complete + collapse`, `complete + preserve`, `ring + collapse`, `ring + preserve`.
- Determine eligibility only from the pre-intervention complete-collapse state at the end of round index 20, where every agent believes BAD. Fork identical posterior states to every arm.
- The follow-up is adequately powered only if at least 400 seeds are eligible. Otherwise report `INCONCLUSIVE_UNDERPOWERED` and do not add seeds.
- Use the original primary contrasts, paired percentile bootstrap with 10,000 resamples, bootstrap seed `10510`, and two-sided 97.5% intervals. The success rule remains at least +0.10 recovery probability with each interval lower bound above zero for both complete-preserve versus complete-collapse and complete-preserve versus ring-collapse.
- Report the original and follow-up results separately, including all seed outcomes. Do not merge them into one confirmatory estimate or present this follow-up as blinded validation.

## Interpretation

Passing the fixed follow-up threshold supports incremental contribution of the existing H4b retest mechanism in this simulator, beyond collapse and the selected topology-only comparator, conditional on the registered false-consensus states. It does not establish language-model-agent or production behavior. Failing the threshold is reported as inconclusive or not supported exactly as defined in the original preregistration.
