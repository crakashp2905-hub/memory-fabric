# Agent-outcome end-to-end gate

- commit: `26a578946ef93862df237a0fbfb8dfe7c27b2b65`
- overall: **PASS**

| stage | status | seconds |
|---|---|---:|
| source | PASS |  |
| contracts | PASS | 13.72 |
| security | PASS | 71.23 |
| demo | PASS | 0.18 |
| arms | PASS | 0.49 |
| provenance | PASS | 7.47 |
| local_model | REAL_AGENT_NOT_RUN | 0.14 |

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
