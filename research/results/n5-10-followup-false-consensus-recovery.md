# N5-10 false-consensus recovery experiment

Preregistration: [`research/prereg/n5-10-followup-false-consensus-recovery-v1.md`](../prereg/n5-10-followup-false-consensus-recovery-v1.md).
Verdict: **SUPPORTED**. Eligible paired false-consensus states: **533** of 5000 attempted seeds (preregistered minimum 400 met: `True`).

| post-checkpoint arm | recovery rate | mean recovery round among recovered | bad-pull fraction |
|---|---:|---:|---:|
| complete_collapse | 0.120 (64/533) | 49.41 | 0.912 |
| complete_preserve | 0.972 (518/533) | 27.48 | 0.216 |
| ring_collapse | 0.092 (49/533) | 91.14 | 0.940 |
| ring_preserve | 0.977 (521/533) | 56.68 | 0.310 |

## Preregistered paired contrasts

- `h1_complete_preserve_minus_complete_collapse`: uplift +0.852; 97.5% paired bootstrap CI [+0.816, +0.886].
- `h2_complete_preserve_minus_ring_collapse`: uplift +0.880; 97.5% paired bootstrap CI [+0.846, +0.912].
- `interaction` (secondary): difference-in-differences -0.034; 95% CI [-0.062, -0.006].

Both primary comparisons start from the same false-consensus posterior state per seed. The topology comparator changes only post-checkpoint sharing structure. See the JSON artifact for all paired outcomes, exact seeds, hashes and limitations.
