# False-withholding promotion gate

R2-10 uses the frozen local five-seed TeamWorld corpus to gate promotion. The contract requires valid-evidence withholding at or below 5% and zero additional stale authorizations on the stale-control set. Both conditions are required; a better task-recovery score cannot compensate for a stale-action regression.

Run `python -m benchmarks.withholding_promotion_gate`. The report includes exact denominators, Wilson intervals, a Pareto frontier over withholding, stale authorizations, and recovered valid tasks, and whether the live policy remains in place. `acceptance_status: PASS` means the gate was correctly applied; `promotion_status: HOLD_EXISTING_POLICY` means no candidate qualified.

On the frozen local report, the live withholding rate is 86/500 (17.2%), above the 5% threshold. No diagnostic ablation recovers a valid task, and all produce zero additional stale authorizations in 125 stale controls. The gate therefore retains the existing policy. The historical PR #30 reference is 84/500 (16.8%); it also misses the target. The Pareto report is descriptive and does not convert these synthetic results into real-agent evidence.
