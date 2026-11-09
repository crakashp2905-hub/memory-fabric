# N4-10 provenance-preserving compression hypothesis

**Registration status:** frozen before any N4-10 comparison run.
**Evidence status:** `NOT_RUN`. This registration is not evidence of an
improvement, scientific novelty, real-agent benefit, or cost reduction.

## Hypothesis

At equal policy and tokenizer-measured context budget, a provenance-preserving
summary yields more correct consequential decisions per input token than
no-compaction, naive-recency, and extractive-summary baselines, while producing
no increase in false stale actions and preserving every required evidence edge.

## Estimand and metrics

- Primary: correct consequential decisions divided by input tokens actually
  exposed to the agent, with abstentions counted as unsuccessful decisions.
- Safety co-primary: false stale actions per task and false authorization rate.
  Any unsafe action is reported individually; it cannot be averaged away.
- Fidelity: exact source ID/version coverage, required-edge verification, and
  reconstruction of all consequential facts.
- Cost: tokenizer input-token count and separately observed provider cost, when
  a real provider is explicitly authorized. UTF-8 bytes are reported separately
  and never substituted for token count or cost.
- Report per-family and pooled estimates, paired differences, confidence
  intervals, seed-level outcomes, abstentions and worst-case slices.

## Arms and controls

All arms receive the same task, policy, source history, decision interface,
authorization gate, token budget and held-out cases:

1. no compaction (full-history comparator);
2. naive recency;
3. extractive summary;
4. provenance-preserving summary.

The full-history arm is the decision ceiling. It must have the same retrieval
budget and authorization mechanisms, differing only in access to the full
eligible history. No candidate arm may exceed the ceiling; if it does, the run
is invalid and the ceiling is repaired before interpreting the result. Every
registered baseline is evaluated on the primary metric and the same token
budget before any learned or model-assisted arm is run. If a baseline trivially
maximizes the metric, the estimand is rejected and redesigned.

## Data, split and seeds

- Use only newly generated, in-repository synthetic histories unless separately
  licensed public data becomes available; no external data is assumed here.
- Development family: temporal preference histories from N4-07.
- Held-out, previously unseen families: corrected procedures; source revocation
  and expiry; minority/contested evidence; and multi-step action dependencies.
- Keep family generators and held-out seed lists separate from development.
  Freeze task templates, generator version, split digests, tokenizer revision,
  policy versions and analysis code before evaluating the held-out split.
- Minimum five fixed seeds per family; report the exact seed allocations and
  paired per-task rows. A result with missing, duplicated or extra seeds is
  rejected.

## Decision gates

A positive result requires all of the following:

1. all four baselines, followed by candidate arms, run on the same held-out
   tasks and a matched context-token budget;
2. the lower bound of the paired 95% confidence interval for primary-metric
   improvement is above zero in the pooled held-out data;
3. no held-out family has a negative point estimate hidden by pooling;
4. false stale actions and false authorizations do not increase relative to
   full-history and are zero in the preregistered strict consequential-action
   cases;
5. exact dependency verification passes for every exposed provenance summary;
6. no candidate beats the full-history ceiling.

Failure of any gate is a negative or inconclusive result, never a reason to
weaken the threshold after seeing outcomes. If a local tokenizer is unavailable,
the token-normalized hypothesis remains `NOT_TESTED`; byte counts may be shown
descriptively but cannot satisfy the primary metric. If no real provider run is
authorized, provider cost and real-agent claims remain `NOT_RUN`.

## Analysis and reporting

Use paired task-level differences, seed-clustered bootstrap confidence intervals,
per-family scorecards, worst-seed outcomes, explicit missingness and complete
artifact hashes. Release the result table only with exact source commit, clean
state, task-data digest, tokenizer/model/prompt identifiers, policy versions,
seed manifest, test report and analysis code digest.

The current N4-07 synthetic comparison is a development fixture, not held-out
evidence. Until the held-out study passes every decision gate, do not claim
proven improvement, cost efficiency, superiority, or novelty. This preregistration
does not establish absolute novelty; that requires a separate prior-art review.
