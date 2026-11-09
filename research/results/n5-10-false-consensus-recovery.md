# N5-10 false-consensus recovery experiment

Preregistration: [`research/prereg/n5-10-false-consensus-recovery-v1.md`](../prereg/n5-10-false-consensus-recovery-v1.md).
Verdict: **INCONCLUSIVE_UNDERPOWERED**. Eligible paired false-consensus states: **112** of 1000 attempted seeds (preregistered minimum 200 met: `False`).

| post-checkpoint arm | recovery rate | mean recovery round among recovered | bad-pull fraction |
|---|---:|---:|---:|
| complete_collapse | 0.080 (9/112) | 56.11 | 0.943 |
| complete_preserve | 0.973 (109/112) | 27.92 | 0.219 |
| ring_collapse | 0.107 (12/112) | 106.67 | 0.938 |
| ring_preserve | 0.982 (110/112) | 57.10 | 0.316 |

## Preregistered paired contrasts

- `h1_complete_preserve_minus_complete_collapse`: uplift +0.893; 97.5% paired bootstrap CI [+0.821, +0.955].
- `h2_complete_preserve_minus_ring_collapse`: uplift +0.866; 97.5% paired bootstrap CI [+0.786, +0.938].
- `interaction` (secondary): difference-in-differences +0.018; 95% CI [-0.036, +0.071].

Both primary comparisons start from the same false-consensus posterior state per seed. The topology comparator changes only post-checkpoint sharing structure. See the JSON artifact for all paired outcomes, exact seeds, hashes and limitations.
