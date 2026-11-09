# Offline reproducibility package and reviewer checklist

This package is the repository at the exact commit plus pinned result artifacts,
not a claim of third-party reproduction. It requires the checked-out source,
Python 3.13, and the repository's declared test/tool dependencies. The focused
commands below need no API key or external dataset. Optional live-model,
PostgreSQL and POSIX-only tests remain disclosed separately.

## Reviewer checklist

- [ ] Record `git rev-parse HEAD`, branch, `git status --short`, Python version,
  OS and CPU before interpreting any local measurement.
- [ ] Confirm the pinned claims and denominators: `python tools/claims_ledger.py`
  and `python -m pytest tests/test_claims_ledger.py tests/test_claim_checker_contract.py -q`.
- [ ] Recheck exact checklist evidence: `python tools/offline_qualification.py`.
  Exit code 2 is expected while external gates or P0 work remain open; review
  the printed counts and task evidence issues.
- [ ] Rerun the deterministic correction, provenance and comparison examples:
  `python examples/correction_spares_unrelated_action.py`,
  `python examples/multi_agent_provenance_dispute.py`, and
  `python examples/correction_strategy_comparison.py`.
- [ ] Re-run the contract tests for this research package:
  `python -m unittest tests.test_contribution_map tests.test_failure_taxonomy tests.test_research_limitations tests.test_claim_checker_contract`.
- [ ] Verify generated output and code quality:
  `python tools/check_product_claims.py --check`,
  `python tools/gen_capabilities.py --check`, `python -m ruff check`.
- [ ] Preserve every nonzero exit, negative result, skip reason, denominator,
  input hash and artifact SHA. Do not update a pinned result in place; create a
  new run record and review any changed claim.

## What this package can reproduce

The deterministic examples and contract checks above use repository code and
fixtures. Their tables describe those fixtures only. The 50-agent TeamWorld
result is deterministic and model-free, but requires the repository's
experiment dependencies; see `research/results/grand-50-agent-baseline-reproduction-v2.json`
for its seeds, denominator and input hashes. The local footprint result is
host-specific and its cold startup threshold currently fails; see
`research/results/p4-08-local-footprint.json`.

## Gates that remain external or unresolved

| Gate | Status | Needed evidence |
|---|---|---|
| Independent human security review | OPEN | Commissioned written report covering tenancy, federation, MCP and action gates |
| Representative-user pilot | OPEN | Consented real workflows, task outcomes and operator feedback |
| Independent scientific reproduction and global prior-art review | OPEN | Third-party rerun and source-aware literature/patent review |
| Physical multi-host validation | OPEN | Distinct hosts, network faults, monitored durable services and recovery measurements |
| Live-model studies | OPEN unless a pinned local model is explicitly available | Model/version, prompt, cost and full run artifacts; scripted agents do not qualify |
| P0 release and correctness blockers | OPEN | Resolve and retest every remaining P0 item on the exact release SHA |

This checklist does not convert a local pass into external validation or a
production-readiness certification.
