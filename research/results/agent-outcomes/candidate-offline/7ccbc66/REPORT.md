# Agent-outcome end-to-end gate

- commit: `7ccbc6686051ecac477d940576177793b74a7991`
- overall: **PASS**

| stage | status | seconds |
|---|---|---:|
| source | PASS |  |
| contracts | PASS | 14.26 |
| security | PASS | 70.88 |
| demo | PASS | 0.21 |
| arms | PASS | 0.47 |
| provenance | PASS | 6.68 |
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
