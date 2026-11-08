# Claims-to-evidence ledger

Generated from `research/claims.json`. Every quantitative statement is bound to exact evidence bytes, the recorded run commit, and registered value/denominator assertions; a missing or changed field prevents SUPPORTED status.

| ID | claim status | verdict | evidence / commit | limitation |
|---|---|---|---|---|
| `teamworld-current-baseline` | **SUPPORTED** | **REPRODUCED_EXACTLY** | [research/results/grand-50-agent-baseline-reproduction-v2.json](../../research/results/grand-50-agent-baseline-reproduction-v2.json) @ `d4fd174ac905` | Measures evidence delivery in a simulator, not behavior of a language-model agent or a physical multi-host deployment. |
| `http-50-client` | **SUPPORTED** | **FAIL** | [research/results/master-checklist-http-50.json](../../research/results/master-checklist-http-50.json) @ `f46aea6` | One Windows host and one run; this is not a three-host capacity result. |
| `http-capacity-curve` | **SUPPORTED** | **FAIL** | [research/results/master-checklist-http-capacity-v1.json](../../research/results/master-checklist-http-capacity-v1.json) @ `a626fdccd698` | Single Windows/SQLite host; confidence intervals cover three machine-local trials and do not generalize to PostgreSQL or multi-host deployments. |
| `longmemeval-s100` | **SUPPORTED** | **FAIL** | [research/results/longmemeval-s100-reproduction-v2.json](../../research/results/longmemeval-s100-reproduction-v2.json) @ `beadf2c21263` | Retrieval-only, 100-instance deterministic sample; dataset license is not declared upstream. |
| `windows-adversarial-gate` | **SUPPORTED** | **PASS** | [research/results/adversarial-gate-windows-v2.json](../../research/results/adversarial-gate-windows-v2.json) @ `6b77d7d` | AI-led repository testing is not an independent external human security review. |
