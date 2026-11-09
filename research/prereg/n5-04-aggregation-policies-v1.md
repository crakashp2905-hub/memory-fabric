# Pre-registration — N5-04 aggregation policy benchmark (v1)

**Registered before implementation and before generating pilot or evaluation
outputs.** This is a synthetic policy benchmark, not a claim about real agents,
real source credibility, or field action safety. The protocol compares majority,
historical-reputation, independent-source-root, and evidence-quality aggregation
under the same cases, reports, arrival order, and one-action output budget.

## Question

When one source's claim is repeated through a population, do policies that use
reporter history, source-root deduplication, or evidence-quality metadata reduce
wrong actions while preserving recovery of a correct claim that is a minority
of the raw reports?

## World and units

- One task is a binary decision with a generated ground-truth value, `left` or
  `right`; truths are balanced within each seed.
- Each task has eight independent source roots. Two roots carry high-quality
  instrument readings, three carry medium-quality firsthand reports, and three
  carry low-quality hearsay. Their registered per-report correctness rates are
  0.85, 0.65, and 0.55 respectively. The generator samples correctness once
  per source root; all copies inherit that root's value and provenance.
- Root multiplicities are `[1, 1, 2, 2, 4, 4, 8, 8]`, assigned before labels
  are generated. Repeated reports therefore change raw vote counts without
  creating new independent observations.
- Each root's copies are distributed over eight arrival waves using the same
  fixed, seed-derived report schedule for every policy. Root identity, source
  quality tier, reporter identity, arrival wave, and truth label are explicit
  fields in the generated data. Policies receive all fields except truth.
- Reporter reputation is estimated only from a separate 40-case calibration
  split, using Laplace-smoothed accuracy and a 0.5 floor/0.95 cap. Evaluation
  labels never update reputations.
- The 16 reporter base accuracies repeat `[0.55, 0.65, 0.75, 0.85]` four times.
  Each reporter receives 40 independent Bernoulli calibration outcomes from
  `random.Random(seed + 10_000)`; the 100/500 balanced evaluation labels,
  source outcomes and copies use a separate `random.Random(seed)`. Reports are
  assigned to reporter `(root_id * 7 + copy_index) mod 16` and wave
  `(root_id + copy_index) mod 8`.
- Evaluation truth labels start as an exactly balanced list of alternating
  `left`/`right` values, then are shuffled by the evaluation RNG. Source quality
  roots are ordered high, high, medium, medium, medium, low, low, low; the same
  evaluation RNG samples each root's correctness once before any copies are
  created.
- Pilot: seed 200, 100 tasks. Held-out evaluation: seeds 201–205, 500 tasks per
  seed. Pilot outputs cannot be pooled with held-out results.

## Frozen policies

1. **Majority:** one equal vote per arriving report.
2. **Reputation:** one report vote weighted by that reporter's calibration
   accuracy log-odds; repeated copies remain repeated votes.
3. **Independent root:** one equal vote per source root, regardless of how many
   reporters repeat it.
4. **Evidence quality:** one vote per source root, weighted by the registered
   tier log-odds derived from 0.85/0.65/0.55. The mapping is fixed before the
   pilot and is not fitted to evaluation labels.
5. **Oracle ceiling:** chooses the true value for the same case and wave, using
   one binary action like each other arm. It receives no extra output budget.

A tie yields `ABSTAIN`; for the primary metric it receives utility 0. An
incorrect decisive action receives utility -1 and a correct decisive action +1.
Every method is scored at all eight waves; the registered primary endpoint is
mean utility at wave 8. All arms see identical reports at each wave.

## Metrics

- **Primary:** mean decision utility at wave 8, with the above fixed loss.
- **Action errors:** wrong decisive actions per task and wrong-decision rate
  among decisive actions, reported separately from abstention.
- **Minority recovery:** accuracy on cases where the true value is held by no
  more than 3 of the 8 independent roots, at wave 8. Also report its count and
  abstention rate; do not silently drop these cases.
- **Convergence:** first wave after which the policy's output never changes
  through wave 8. Non-converged cases are reported as such; abstention is a
  distinct output, not a missing observation.
- Report each seed, pooled task counts, and paired 95% bootstrap intervals for
  primary mean utility and the confirmatory evidence-quality contrast,
  resampling tasks within seed (10,000 replicates). No significance-only pass
  claim; report effect sizes and all seed values.

## Baseline, ceiling, and stopping checks

- Run the seed-200 pilot and score all four policies and the oracle on the
  registered primary metric, at the same wave and budget, before running any
  held-out evaluation seed.
- If any non-oracle policy reaches the oracle on mean utility **and** has zero
  action errors on the pilot, the primary metric is degenerate for this world;
  stop, publish the diagnostic, and register a new version before evaluation.
- The confirmatory candidate contrast is evidence-quality versus the best of
  majority and reputation. Its target is at least 25% of per-seed headroom from
  that baseline to the oracle, averaged over held-out seeds. The registered
  independent-root policy remains a named comparator, not a post-hoc substitute.
- On every seed and wave, assert no policy utility exceeds the oracle. Any
  exceedance invalidates that run and triggers oracle/harness repair before a
  fresh held-out run; do not clip or explain away an exceedance.
- Every arm is computed from the same report table and wave cutoff. No baseline
  number is imported from another experiment, metric, split, or wave.

## Reproducibility and limitations

Use injected `random.Random(seed)` only. Emit the full task/report manifest,
configuration, code commit, script and data hashes, seed-level results, skipped
cases, and test output. Tests must cover copy-count invariance of root counts,
policy label isolation, calibration/evaluation separation, tie abstention,
pilot stopping, oracle dominance checks, and deterministic replay.

The generator's reliability rates are assumptions chosen to create a known
synthetic world; they are not empirical estimates. Source-root deduplication is
only as reliable as the supplied provenance graph. No result grants action
authority outside this benchmark.
