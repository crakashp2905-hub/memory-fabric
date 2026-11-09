# Pre-registration — N5-06 Byzantine-agent simulation (v1)

**Registered before implementation and before any pilot or evaluation output.**
This synthetic experiment measures how four aggregation policies respond to
agents that lie, replay, copy, or selectively withdraw reports. It does not
estimate real-world attacker prevalence or establish operational safety.

## Threat model

- Each task has 8 source roots and 16 reporters; the underlying binary truth is
  balanced within each seed. Honest source reports use the frozen quality rates
  and root multiplicities from `n5-04-aggregation-policies-v1.md`.
- In each evaluation task, a fixed fraction of reporter identities are
  Byzantine: 0%, 10%, 25%, or 40% (rounded down from 16 identities). The same
  identities remain faulty for the full task. Identity labels are not hidden
  from the simulator but policies receive only the resulting reports, as in
  N5-04.
- Byzantine reporters coordinate, know the task truth and honest report values,
  and may choose their behavior after inspecting the reports visible to them.
  This is a strong, fully informed adversary.
- **Lie:** emit the binary value opposite the true value once per assigned
  honest report slot, preserving the slot's root, quality, and arrival wave.
- **Replay:** duplicate the first observed report value for each distinct
  `(root, wave)` slot up to three times, with the same root and reporter. This
  tests whether repeated deliveries inflate vote counts.
- **Copy:** repeat the most common value among the attacker's observed source
  reports into its assigned slots, preserving the reported root; copies do not
  become new source roots.
- **Selective withdrawal:** suppress the attacker's assigned reports whenever
  their value equals truth; wrong reports remain visible. The attacker can
  identify correctness in this worst-case synthetic world.
- No cryptographic compromise, forged root identifier, adaptive identity
  churn, or out-of-band communication is modeled. Source-root labels are
  assumed accurate; compromised root identity is outside this experiment.

## Design and outcomes

- Policies: majority, reporter reputation, independent-root, and
  evidence-quality from N5-04, unchanged. All policies see the same attacked
  report table for a condition.
- Conditions: four attack behaviors crossed with faulty identity fractions
  0%, 10%, 25%, and 40%. Zero faults is the matched baseline for each behavior.
- Five fixed evaluation seeds (301–305), 200 balanced tasks per seed and
  condition. Pilot seed 300, 100 tasks, is reported separately and does not
  enter evaluation estimates.
- Primary measure: wrong decisive actions divided by all tasks (abstentions
  count as no wrong action). Also report decisive coverage, wrong-decision rate,
  abstention rate, and utility under +1 correct / -1 wrong / 0 abstain.
- For every condition and policy, report per-seed results and pooled mean with
  task-bootstrap 95% percentile intervals (10,000 paired resamples within each
  seed, then equal-weight average across seeds). Report the paired difference
  from the same behavior's zero-fault baseline.
- No policy is promoted by this benchmark. A decrease in errors with sharply
  lower coverage must be visible; safety and availability are separate.

## Reproducibility and limits

Use deterministic `random.Random` streams derived from seed, behavior, fault
fraction, and task. Persist per-condition report hashes, code commit, script
hash, seed rows, skipped conditions, test output, and threat-model reference.
Tests cover deterministic replay, exact fault fractions, attack semantics,
root preservation, identical policy inputs, bootstrap reproducibility, and
input validation.

Findings are conditional on this binary world, known truth to attackers, fixed
identities, assigned report slots, and supplied provenance labels. They do not
prove Byzantine resilience in live federation or authorize an action.
