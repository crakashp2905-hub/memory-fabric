# Agent-outcome security principals and permissions

Five principals touch an agent episode. Each has its own secret, kept
separately, and each is allowed only what its row in the matrix grants
(agent-validation checklist W19-01). `tests/test_agent_principals.py` checks
that every endpoint the code exposes appears in the matrix, and that no actor
endpoint reaches evaluator or operator power.

| Principal | Who | Secret and custody |
|---|---|---|
| **actor** | Observer, planner and executor agents, scripted or model-backed | A per-agent session credential issued by the service registry; it carries no role it was not issued, and cannot mint credentials |
| **evaluator** | The grader that holds hidden world truth | A task-bound evaluator capability (`OracleTask.seal_for_evaluator`); it is never serialized and never given to an actor |
| **operator** | People who review, withdraw or erase memories | An operator credential issued by the registry; it is separate from any agent credential and cannot cross tenants |
| **integration** | The host service that runs tools and issues action grants | The action-gate policy and host grant issuer, configured by the host; agents never supply them |
| **auditor** | Read-only reviewers of logs and reports | Read access to the event log and the read-only dashboard; no write route |

## Permission matrix

`yes` means the principal may call the endpoint. `no` means it may not. `own`
means it may call it only within its own tenant and session.

| Endpoint | actor | evaluator | operator | integration | auditor |
|---|---|---|---|---|---|
| agent-api `recall` | own | no | no | no | no |
| agent-api `fetch` | own | no | no | no | no |
| agent-api `verify` | own | no | no | no | no |
| agent-api `remember` | own | no | no | no | no |
| mcp `recall` | own | no | no | no | no |
| mcp `fetch` | own | no | no | no | no |
| mcp `verify` | own | no | no | no | no |
| mcp `remember` | own | no | no | no | no |
| mcp `browse_topics` | own | no | no | no | no |
| mcp `open_topic` | own | no | no | no | no |
| mcp `build_context` | own | no | no | no | no |
| mcp `explain_context` | own | no | no | no | no |
| mcp `trace_provenance` | own | no | no | no | no |
| mcp `preview_correction` | own | no | no | no | no |
| mcp `branch_create` | own | no | no | no | no |
| mcp `branch_propose` | own | no | no | no | no |
| mcp `wake` | own | no | no | no | no |
| mcp `zoom` | own | no | no | no | no |
| mcp `nap` | own | no | no | no | no |
| mcp `merge_preview` | own | no | no | no | no |
| episode `record_observations` | own | no | no | no | no |
| episode `recall` | own | no | no | no | no |
| episode `set_target` (protected) | own | no | no | yes | no |
| episode `execute_proposal` (protected) | own | no | no | yes | no |
| evaluator `grade_episode` | no | yes | no | no | no |
| evaluator `open_payload` | no | yes | no | no | no |
| operator `review_decide` | no | no | own | no | no |
| operator `quarantine` | no | no | own | no | no |
| operator `erase_content` | no | no | own | no | no |
| action `issue_grant` | no | no | no | yes | no |
| `dashboard` (read-only) | no | no | own | no | yes |

The actor's `own` on the protected episode tools covers proposing the effect
(planner) and asking for it to run (executor). The effect itself runs only on
the grant the integration issues to the executor, after the gate re-verifies
the evidence.
