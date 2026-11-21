# Agent-outcome end-to-end gate

- commit: `05ced0e3c556360111bc5c6cfa7f7a295eb561a4`
- overall: **PASS**

| stage | status | seconds |
|---|---|---:|
| source | PASS |  |
| contracts | PASS | 14.62 |
| security | PASS | 85.72 |
| demo | PASS | 0.25 |
| arms | PASS | 0.56 |
| provenance | PASS | 7.13 |
| local_model | REAL_AGENT_NOT_RUN | 0.17 |

## Release-evidence matrix

| gate | status | evidence type |
|---|---|---|
| main_ci | NOT_RUN | - |
| synthetic_outcome_gate | SCRIPTED_PASS | scripted |
| model_attacks | NOT_RUN | - |
| real_agent | NOT_RUN | local_model |
| confirmatory | NOT_RUN | - |
| independent_review | NOT_RUN | - |

No row is a production qualification. NOT_RUN means no evidence of that gate's own type exists for this commit.
