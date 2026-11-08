# N3-10 — Causal policy graduation gate

Status: preregistered before the held-out N3-10 outputs are generated.

## Question

Should source-trained causal retention be graduated beyond research after its N3-08
effect on task success? Graduation requires lower decision regret than a target-
calibrated smoothed-success baseline, no material increase in unsafe actions,
and bounded inference/training work. H2's registered failure remains in force;
this experiment does not relabel it or replace its registered budget.

## Design

Use 20 paired seeds (`40..59`) in the two N3-08 held-out synthetic families:
`supply_chain_dispatch` and `incident_response`. Per seed, estimate the procedure
and legacy feature effects from the randomized source family using IPS, with the
existing 20 memories per feature and 500 randomized episodes per memory. For each
target family, create 40 new candidates and a 100-episode-per-memory target
calibration set. The source causal policy ranks candidates only by source-trained
feature effects; the baseline ranks only by target `NaiveUsageEstimator`; the
oracle uses registered simulator effects as an upper bound. Every policy retains
20 of the same candidates and is evaluated on the same 3,000 held-out tasks per
seed and family using common random numbers.

The held-out environment has explicit unsafe-action rates fixed here before the
run: 1.2% for a procedure memory and 2.0% for a legacy memory. Safety outcomes
are generated independently of success and scored for every selected action.
These rates define a synthetic policy stress test; they are not empirical safety
claims about real agents.

## Metrics and fixed gates

1. **Regret:** oracle held-out success minus each policy's success. The causal
   policy must reduce mean regret versus smoothed success by at least 5
   percentage points in each family, with the paired 95% bootstrap interval for
   regret reduction above zero.
2. **Safety:** paired unsafe-action difference (causal minus baseline) must have
   a 95% bootstrap upper bound no greater than +0.5 percentage points in each
   family.
3. **Compute budget:** report processed source and target calibration rows and
   end-to-end wall time. Source training is reused for both held-out families;
   amortized causal row work per family must be no more than 5× baseline target
   calibration rows. Wall time is descriptive because host scheduling noise is
   not a stable release gate.
4. **Decision:** graduate only if all regret, safety, and compute gates pass in
   both families. Any failure is recorded as a failed/inconclusive result, not a
   qualitative success.

## Analysis

Use paired per-seed outcomes and 10,000-seed bootstrap intervals at 95%, with
fixed bootstrap seeds. Archive all per-seed success, regret, safety, policy mix,
row counts, and timing. Do not tune feature mappings, safety rates, margins,
budget, or thresholds after observing held-out output.

## Limits

The world is synthetic and preserves the feature-effect mapping used by N3-08.
The test does not establish safety under real tools, real models, hidden
confounding, other feature semantics, or field distributions. Row-count work is
a reproducible compute proxy; measured wall time is host-specific. Passing this
gate would justify only continued supervised experimentation, not product
release or autonomous deployment.
