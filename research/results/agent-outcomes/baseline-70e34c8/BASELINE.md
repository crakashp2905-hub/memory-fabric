# Agent-outcome baseline at `70e34c8`

Starting point for the agent-validation checklist
([specification](../../../../docs/checklists/AGENT_VALIDATION_CHECKLIST_2026-11-20.md),
[task ledger](../../../checklist/AGENT_VALIDATION_LEDGER.md)). Machine-readable form:
[`baseline.json`](baseline.json). Everything below is pinned to commit
`70e34c870d387cb5de8ba0bbdda0320cf3574d6c` (main on 2026-11-15), recorded on 2026-11-20.

**Overall: `NOT_RUN`.** No same-commit real-agent, confirmatory or independent
evidence exists. What exists is scripted and contract evidence, plus two historical
local-model smokes at an earlier commit. None of it is a production qualification.

## Environment

[`manifest.json`](manifest.json), from `python tools/baseline_manifest.py`: clean tree at
the commit above, CPython 3.13.18, SQLite 3.53.1, Linux x86_64, package 0.19.0,
no runtime dependencies, and the installed optional distributions with their versions.
It is deterministic (no timestamp; `manifest_sha256` covers every field) and made no
network call. `python tools/baseline_manifest.py --verify` checks a stored copy.

## Local test run

[`local-test-run.json`](local-test-run.json): `python -m pytest tests -q` on the clean
tree passed 3449, skipped 61 and failed 1. The failure is environmental: this container
has the official `mcp` SDK 2.3.0 installed, and SDK 2.x expects a float read timeout where
`tests/test_mcp_official.py` passes a `timedelta`. CI does not install `mcp` in the test
matrix and pins `mcp==1.26.0` in its `mcp-contract` job, so CI at this commit was green.

## Known results

Each is reported at its own evidence type and never pooled with another population.

| result | status | evidence | do not extrapolate |
|---|---|---|---|
| A5 vs A3 and A4, 10 scripted development cases, seed 701: A5–A3 0.00, A5–A4 +0.20 | `SCRIPTED_PASS` | [json](../../agent-outcome-a5-matched-development.json) | One seed, development split, A6 not run; no promotion |
| A5 recovery 12/12 vs A0 immediate abstention 0/12, 12 seeds | `SCRIPTED_PASS` | [json](../../agent-outcome-v1-ao096-scripted-example.json) | A0 is a negative control, not the strongest fair baseline |
| One `qwen2.5:1.5b` decision, 1 model call | `LOCAL_MODEL_PASS` | [manifest](../../../../benchmarks/real_agent_smoke_manifest.json) | Interface smoke at `24b1e9d`, not a task-success population |
| Five sequential `qwen2.5:1.5b` Q4_K_M calls across three roles | `LOCAL_MODEL_PASS` | [manifest](../../../../benchmarks/real_agent_team_smoke_manifest.json) | One integration smoke; not task-success or safety evidence |
| TeamWorld 50 agents: task success 0.584, valid evidence withheld 0.168, 500 tasks, zero observed stale actions | `SCRIPTED_PASS` | [json](../../grand-50-agent-baseline-reproduction-v2.json) | Historical population at `d4fd174`; not an A5 result |
| Withholding re-encoded at 17.2% (86/500) | `SCRIPTED_PASS` | [doc](../../../../docs/FALSE_WITHHOLDING_ABLATION.md), [benchmark](../../../../benchmarks/false_withholding.py) | Separate re-encoding, not a row-level import |
| CDM R5 v3: +0.055 utility, 95% interval [−0.0528, +0.1628] | `INCONCLUSIVE` | [reports](../../cdm/architecture-superiority-r5v3/) | Does not support the superiority hypothesis |

## Known failures

| failure | class | evidence |
|---|---|---|
| Scheduled `model-attacks` run 43848470357 (2026-11-16, this commit) failed in 3 seconds with `runner_id` 0 and no steps. No attack or invariant ran; its logs return HTTP 404. Root cause `CAUSE_UNVERIFIED`. | `NO_RUNNER_ASSIGNED` | [classification](model-attacks-run-43848470357.classification.json), [metadata](model-attacks-run-43848470357.json) |
| Local `test_mcp_official.py` against `mcp` 2.3.0 | `ENVIRONMENT_INCOMPATIBILITY` | [run](local-test-run.json) |
| `docs/AGENT_OUTCOME_EVALUATION.md` said the schema and `SPEC.md` were at 0.14.0 (both 0.19.0); the release checklist named a 0.14.0 wheel. Fixed; `tools/status_at_head.py --check` now fails on such drift. | `DOCUMENTATION_DRIFT` | [check](../../../../tools/status_at_head.py) |
| The 12/12 scripted example was stated without an evidence link. Linked; `tools/claim_scanner.py` now fails on unlinked outcome numbers. | `UNSUPPORTED_CLAIM` | [scanner](../../../../tools/claim_scanner.py) |

## Not run

| gate | status | why | evidence |
|---|---|---|---|
| Real-agent execution | `NOT_RUN` | No local model runtime in this environment: `REAL_AGENT_NOT_RUN` / `LOCAL_RUNTIME_UNAVAILABLE` | [preflight](model-preflight.json) |
| Confirmatory study | `NOT_RUN` | The registration is `DRAFT`, with no confirmatory seeds and sample size 0 | [registration](../../../prereg/agent-outcome-confirmatory-v1.json) |
| A6 (CDM) matched arm | `NOT_RUN` | Not run in the matched development comparison | [json](../../agent-outcome-a5-matched-development.json) |
| Independent review and pilot | `NOT_RUN` | None exists; the release checklist is NO-GO for external publication | [checklist](../../../../docs/MEMORY_FABRIC_RELEASE_CHECKLIST.md) |

## Non-extrapolation rules

- Scripted, contract and green-CI evidence never qualifies a learned-agent efficacy claim.
- Results from different populations, seeds or commits are reported side by side and never pooled; `memory_fabric.outcome_typed.evidence.validate_paired_comparison` refuses unpaired comparisons.
- Zero observed unsafe actions is not proof of zero risk.
- Nothing here is a production qualification.
