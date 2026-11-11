# N5-06 Byzantine-agent simulation

Protocol: `research/prereg/n5-06-byzantine-agents-v1.md`. Synthetic conditional evidence only. Faulty reporters know task truth; realized identity fractions are 0%, 6.25%, 25%, and 37.5% for the requested 0%, 10%, 25%, and 40% levels (16 reporter identities, rounded down). Reputation uses a separate fixed 40-case calibration split per seed.

## Held-out results

Equal-weight means across five seeds; each cell is wrong actions / all tasks (coverage). Paired bootstrap intervals compare against the same behavior's zero-fault condition.

| behavior | requested faults | policy | wrong action rate | coverage | paired change (95% CI) |
|---|---:|---|---:|---:|---:|
| lie | 0% | majority | 0.259 | 0.977 | +0.000 to +0.000 |
| lie | 0% | reputation | 0.263 | 1.000 | +0.000 to +0.000 |
| lie | 0% | independent_root | 0.065 | 0.835 | +0.000 to +0.000 |
| lie | 0% | evidence_quality | 0.093 | 1.000 | +0.000 to +0.000 |
| lie | 10% | majority | 0.296 | 0.949 | +0.026 to +0.049 |
| lie | 10% | reputation | 0.275 | 1.000 | +0.006 to +0.019 |
| lie | 10% | independent_root | 0.088 | 0.792 | +0.014 to +0.033 |
| lie | 10% | evidence_quality | 0.118 | 1.000 | +0.016 to +0.035 |
| lie | 25% | majority | 0.563 | 0.927 | +0.276 to +0.332 |
| lie | 25% | reputation | 0.559 | 1.000 | +0.271 to +0.322 |
| lie | 25% | independent_root | 0.236 | 0.698 | +0.148 to +0.194 |
| lie | 25% | evidence_quality | 0.220 | 1.000 | +0.108 to +0.146 |
| lie | 40% | majority | 0.757 | 0.924 | +0.467 to +0.529 |
| lie | 40% | reputation | 0.663 | 1.000 | +0.372 to +0.428 |
| lie | 40% | independent_root | 0.407 | 0.673 | +0.313 to +0.371 |
| lie | 40% | evidence_quality | 0.487 | 1.000 | +0.371 to +0.417 |
| replay | 0% | majority | 0.259 | 0.977 | +0.000 to +0.000 |
| replay | 0% | reputation | 0.263 | 1.000 | +0.000 to +0.000 |
| replay | 0% | independent_root | 0.065 | 0.835 | +0.000 to +0.000 |
| replay | 0% | evidence_quality | 0.093 | 1.000 | +0.000 to +0.000 |
| replay | 10% | majority | 0.271 | 0.974 | +0.001 to +0.023 |
| replay | 10% | reputation | 0.269 | 1.000 | -0.001 to +0.013 |
| replay | 10% | independent_root | 0.065 | 0.835 | +0.000 to +0.000 |
| replay | 10% | evidence_quality | 0.093 | 1.000 | +0.000 to +0.000 |
| replay | 25% | majority | 0.245 | 0.946 | -0.028 to -0.000 |
| replay | 25% | reputation | 0.266 | 1.000 | -0.014 to +0.020 |
| replay | 25% | independent_root | 0.065 | 0.835 | +0.000 to +0.000 |
| replay | 25% | evidence_quality | 0.093 | 1.000 | +0.000 to +0.000 |
| replay | 40% | majority | 0.272 | 0.986 | +0.004 to +0.023 |
| replay | 40% | reputation | 0.271 | 1.000 | -0.004 to +0.021 |
| replay | 40% | independent_root | 0.065 | 0.835 | +0.000 to +0.000 |
| replay | 40% | evidence_quality | 0.093 | 1.000 | +0.000 to +0.000 |
| copy | 0% | majority | 0.259 | 0.977 | +0.000 to +0.000 |
| copy | 0% | reputation | 0.263 | 1.000 | +0.000 to +0.000 |
| copy | 0% | independent_root | 0.065 | 0.835 | +0.000 to +0.000 |
| copy | 0% | evidence_quality | 0.093 | 1.000 | +0.000 to +0.000 |
| copy | 10% | majority | 0.269 | 0.994 | +0.004 to +0.017 |
| copy | 10% | reputation | 0.265 | 1.000 | -0.005 to +0.009 |
| copy | 10% | independent_root | 0.080 | 0.848 | +0.007 to +0.024 |
| copy | 10% | evidence_quality | 0.091 | 1.000 | -0.009 to +0.005 |
| copy | 25% | majority | 0.272 | 1.000 | +0.006 to +0.020 |
| copy | 25% | reputation | 0.272 | 1.000 | -0.005 to +0.024 |
| copy | 25% | independent_root | 0.143 | 0.879 | +0.061 to +0.096 |
| copy | 25% | evidence_quality | 0.117 | 1.000 | +0.010 to +0.039 |
| copy | 40% | majority | 0.272 | 1.000 | +0.006 to +0.021 |
| copy | 40% | reputation | 0.272 | 1.000 | -0.005 to +0.024 |
| copy | 40% | independent_root | 0.211 | 0.938 | +0.124 to +0.169 |
| copy | 40% | evidence_quality | 0.183 | 1.000 | +0.067 to +0.113 |
| selective_withdrawal | 0% | majority | 0.259 | 0.977 | +0.000 to +0.000 |
| selective_withdrawal | 0% | reputation | 0.263 | 1.000 | +0.000 to +0.000 |
| selective_withdrawal | 0% | independent_root | 0.065 | 0.835 | +0.000 to +0.000 |
| selective_withdrawal | 0% | evidence_quality | 0.093 | 1.000 | +0.000 to +0.000 |
| selective_withdrawal | 10% | majority | 0.276 | 0.974 | +0.010 to +0.025 |
| selective_withdrawal | 10% | reputation | 0.267 | 1.000 | +0.001 to +0.008 |
| selective_withdrawal | 10% | independent_root | 0.065 | 0.835 | +0.000 to +0.000 |
| selective_withdrawal | 10% | evidence_quality | 0.093 | 1.000 | +0.000 to +0.000 |
| selective_withdrawal | 25% | majority | 0.376 | 0.954 | +0.098 to +0.138 |
| selective_withdrawal | 25% | reputation | 0.389 | 1.000 | +0.106 to +0.146 |
| selective_withdrawal | 25% | independent_root | 0.095 | 0.865 | +0.021 to +0.040 |
| selective_withdrawal | 25% | evidence_quality | 0.108 | 1.000 | +0.008 to +0.023 |
| selective_withdrawal | 40% | majority | 0.457 | 0.958 | +0.174 to +0.223 |
| selective_withdrawal | 40% | reputation | 0.438 | 1.000 | +0.152 to +0.198 |
| selective_withdrawal | 40% | independent_root | 0.159 | 0.929 | +0.077 to +0.112 |
| selective_withdrawal | 40% | evidence_quality | 0.144 | 1.000 | +0.038 to +0.065 |

## Interpretation limits

See the preregistration for the full threat model. These results do not establish live Byzantine resilience, root authenticity, or action safety.
