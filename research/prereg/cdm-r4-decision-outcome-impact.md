# CDM-R4: utility and cost protocol

Status: corrected protocol frozen before fresh held-out seed run. Version 2.
Date: 2026-11-08.

The generated hidden state is used only by the benchmark evaluator after each
arm has emitted a proposal. Utility is fixed as: correct `diagnose` +1,
incorrect `diagnose` -1, `investigate` 0.0, correct negative `monitor` +0.1,
and missed positive `monitor` -0.5. The oracle selects `diagnose` when the
hidden fault is present and `monitor` otherwise. The baseline is the unchanged
factual proposal. All intervention arms use the same three observations and
one-evidence-removal budget.

The earlier v1 score gave `investigate` +0.2, exceeding the purported oracle
on negative cases. Its utility results are invalid and are retained only as
raw history in `research/results/cdm/heldout/`.

Report paired utility deltas, a normal-approximation 95% interval, case count,
refusal count, posterior error, and runtime. This simple interval is
descriptive and not a claim of asymptotic validity. No deployment-benefit or
cost-effectiveness claim is allowed from the toy world.
