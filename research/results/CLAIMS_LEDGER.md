# Claims-to-evidence ledger

Generated from `research/claims.json`. Every row names its scope and limitation; a missing file, commit field, or required field fails generation.

| ID | claim class | verdict | evidence / commit | limitation |
|---|---|---|---|---|
| `teamworld-current-baseline` | deterministic-agent-simulation | **REPRODUCED_EXACTLY** | [research/results/grand-50-agent-baseline-reproduction-v2.json](../../research/results/grand-50-agent-baseline-reproduction-v2.json) @ `d4fd174ac905` | Measures evidence delivery in a simulator, not behavior of a language-model agent or a physical multi-host deployment. |
| `http-50-client` | single-host-network | **FAIL** | [research/results/master-checklist-http-50.json](../../research/results/master-checklist-http-50.json) @ `f46aea6` | One Windows host and one run; this is not a three-host capacity result. |
| `longmemeval-s100` | retrieval-benchmark | **FAIL** | [research/results/longmemeval-s100-reproduction-v2.json](../../research/results/longmemeval-s100-reproduction-v2.json) @ `beadf2c21263` | Retrieval-only, 100-instance deterministic sample; dataset license is not declared upstream. |
| `windows-adversarial-gate` | single-host-security-test | **PASS** | [research/results/adversarial-gate-windows-v2.json](../../research/results/adversarial-gate-windows-v2.json) @ `6b77d7d` | AI-led repository testing is not an independent external human security review. |
