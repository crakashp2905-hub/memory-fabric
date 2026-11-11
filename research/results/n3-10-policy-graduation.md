# N3-10 — Causal policy graduation gate

**Decision: GRADUATE FOR SUPERVISED RESEARCH ONLY.** The preregistered regret,
safety, and compute gates passed in both held-out synthetic families. This does
not approve product release or autonomous deployment.

| Held-out family | Regret reduction vs smoothed-success baseline (95% paired CI) | Unsafe-action difference, causal − baseline (95% paired CI) | Regret gate | Safety gate |
|---|---:|---:|---|---|
| Supply-chain dispatch | +8.78 pp [+8.50, +9.03] | −0.73 pp [−0.81, −0.66] | Pass | Pass |
| Incident response | +8.63 pp [+8.22, +9.04] | −0.64 pp [−0.69, −0.59] | Pass | Pass |

Across 20 paired seeds per family, causal mean regret was zero in this simulator
because the source policy selected the same procedure-only budget as the oracle.
The baseline mean regret was 8.78 pp and 8.63 pp respectively. These strong
results depend on the fixed registered procedure-versus-legacy effect mapping.

Compute used 20,000 randomized source rows per seed, reused across both target
families, versus 4,000 target calibration rows per family. Amortized work was
10,000/4,000 = **2.5×**, below the preregistered 5× cap. Mean measured source
training time was 2.268 s per seed; mean baseline calibration and ranking time
was 0.448 s per seed-family. Amortizing source training over both families gives
about **2.54×** wall time per family on this host; causal candidate scoring alone
averaged 0.000057 s. Wall-clock values are descriptive and host-specific.

The result does not alter H2's registered negative result at its original budget.
N3-10 supports only continued supervised experimentation in the two synthetic
families. The unsafe rates are simulator parameters, not real-agent safety
measurements; the study has no real models, tools, hidden confounding, alternate
feature semantics, or field data.
