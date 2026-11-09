# R2-10: false-withholding promotion gate v1

**Registered before candidate comparison.** Population: deterministic scripted TeamWorld only. No model or external effect is run.

## Decision rule

A candidate is eligible for promotion only when both conditions hold on the frozen held-out worlds:

1. Valid-evidence withholding is at most 5% of the registered task attempts.
2. The candidate authorizes zero additional stale actions on the frozen stale-control cases, compared with the live policy.

The gate must retain the existing policy if no candidate satisfies both conditions. It must publish a Pareto frontier over valid-evidence withholding, additional stale authorizations, and recovery of valid withheld tasks. Diagnostic ablations cannot be promoted merely because they improve one axis. All comparisons are dry runs; they cannot mutate policy or call an executor.

## Frozen evidence and interpretation

The acceptance input is the R2-02–04 frozen five-seed report (500 task attempts; 125 stale controls), plus the historical PR #30 reference report for context. No thresholds or cases are tuned after observing outcomes. The candidate gate's observed withholding rate is tested against 5%; confidence intervals and exact denominators are reported alongside it. Zero observed stale actions are reported with an upper 95% bound and do not imply universal safety.

The acceptance criterion is that the gate itself enforces the rule, detects a known failing result, emits a frontier, and retains the live policy when no arm qualifies. Passing this contract does **not** mean a candidate passes the performance threshold. Local synthetic outcomes cannot establish real-agent performance.
