# Vega next: decision (2026-11-25)

**Decision: HOLD.** The confirmatory study `vega-cdm-v2` was not run; the holdout split has never been
read. vega-U stays OFF by default, advisory only, and never touches permissions, evidence, grants or the
ActionGate. `QUALIFIED` remains refused.

Completion and safety are reported separately below, as the checklist requires. Every number cites a
record under [research/results/vega-cdm/next/](../research/results/vega-cdm/next/BASELINE.md); the
reader is vega-U 0.19.0 with Qwen3.5-0.8B (engine sha256 `78f96be7c6a0...`), the planner is
Qwen2.5-1.5B-Instruct behind the loopback server in `tools/local_chat_server.py`.

## Why HOLD and not GO

The registration validator (`python -m benchmarks.vega_next_confirmatory validate
research/prereg/vega-cdm-v2.json`) refuses the draft for one reason:

> not specific: on the pilot the candidate beats the A5-PV-shuffled placebo by 0.01, below the minimum
> effect 0.05, so a gain could not be credited to what vega-U reads

On the pilot split (10 families x 10 seeds, phrasing the deterministic rules were not written for):

| Arm | Safe success | Unsafe omissions | Model calls |
|---|---|---|---|
| A5-P (typed reader + guard, no model) | 0.50 | 0 | 0 |
| A5-PV (A5-P, vega-U reads open doubt notes) | 0.56 | 0 | 32 |
| A5-PV-shuffled (same calls on a note from another world) | 0.55 | 0 | 32 |
| A5-PV-wrongconf (inverted answers) | 0.50 | 0 | 32 |
| A5-VG (PR #41 semantic pipeline + guard) | 0.18 | 0 | 238 |
| A7 oracle | 1.00 | 0 | 0 |

A5-PV beats A5-P on 6 of 100 paired tasks and loses none; the shuffled placebo comes within one task of
it. The gain comes almost entirely from vega-U answering "TA1 was verified accurate" on `local_heat`
worlds, and it gives that answer to unrelated notes nearly as often as to the right one. There is no
specific effect to confirm, so a holdout run would spend the split on a result the pilot already
predicts. Per the checklist the negative result is kept, not tuned away: the dev split is saturated
(every typed arm 1.0, equal to the oracle), and the threshold was not lowered.

The specificity rule was tightened from "beats the placebo" to "beats it by at least the minimum effect"
after this pilot was seen. That change can only refuse more registrations; it was made before any
holdout data existed.

## Safety findings (these are fixes, not efficacy)

1. **The two PR #41 unsafe omissions** are reproduced exactly and both become escalations under the
   typed reader and the omission guard.
2. **A model answer settled contested readings without cooling.** The first worlds-v2 pilot recorded
   6 (shuffled) and 10 (inverted) unsafe omissions: a "TA1 may be inaccurate" answer turned a real
   local overheat into `recalibrate_probe`, and the guard allowed it because the readings were
   CONTESTED, not VERIFIED_HAZARD. `guard(..., settled_by_model=True)` now requires a registered
   response (cooling) in that case. Archived: `development/worlds-v2-pre-contest-fix/`.
3. **A planner model is a model too.** The first planner pilot recorded 6 unsafe omissions in M-A5
   (evidence texts only): Qwen2.5-1.5B chose `recalibrate_probe` on `local_heat` with no verified doubt.
   Only a doubt read by the deterministic rule may now justify a non-cooling action on contested
   readings. Archived: `agents/pre-planner-contest-fix/`.
4. **vega-U must not read numbers.** On the calibration study it answered "not hot", without
   abstaining, for 42% (dev) and 58% (pilot) of truly hot readings (AUROC 0.80). Numeric facts come
   from `observations.extract`; the model is asked only about notes.

Zero unsafe events in the corrected runs is a bound, not zero risk: with 0 in 100 pilot tasks per arm
the one-sided 95% upper bound is 2.95% (`omission.coverage_bound`).

## Calibration (W06-05 to W06-07)

[calibration/vega-0.8b.json](../research/results/vega-cdm/next/calibration/vega-0.8b.json), fitted on
dev rows, applied once to pilot rows:

| Question | AUROC dev | AUROC pilot | Brier pilot | Threshold transfer |
|---|---|---|---|---|
| hot (numeric) | 0.80 | 0.80 | 0.56 | 2 of 230 accepted |
| doubt | 0.98 | 1.00 | 0.10 | ADVISORY, risk 0.0 |
| cleared | 0.98 | 0.78 | 0.30 | REVIEW_ONLY, risk 0.12 |

vega-U reads calibration-doubt notes well on unseen phrasing. It does not transfer on "was verified
accurate" notes, which is where the arms needed it.

## Real planner (W09-09, W12-07)

See [agents/model-agents-pilot.json](../research/results/vega-cdm/next/agents/model-agents-pilot.json)
and the section appended to [VEGA_CDM_LIMITATIONS.md](VEGA_CDM_LIMITATIONS.md). Failed or missing
calls stay in the denominator.

## What would change the decision

- A note reader whose "cleared" answers are specific (beats the shuffled placebo by the minimum effect
  on a fresh pilot), then a new registration (v3) frozen before any holdout read.
- A planner large enough to follow the catalog rules; the 1.5B planner proposes `no_action` on most
  hot packs and is saved only by the guard.
- Measurements on a 16 GB laptop (W06-10, W14-02), which this project has not had.
