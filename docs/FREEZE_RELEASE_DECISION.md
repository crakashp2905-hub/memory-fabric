# Feature-freeze release: decision

Per-component verdicts for the feature-frozen release, from the records under
[qualification/](../qualification/) and [research/results/vega-cdm/freeze/](../research/results/vega-cdm/freeze/).
Plan: [FEATURE_FREEZE_RELEASE_CLOSURE_2026-11-25.md](checklists/FEATURE_FREEZE_RELEASE_CLOSURE_2026-11-25.md);
supported scope: [SUPPORTED_SCOPE.md](SUPPORTED_SCOPE.md).

**Status: in progress.** The ladder stages below that say `running` are being measured; the final
verdicts are written from the completed records.

## Thresholds: strict first, gentler only on fresh data

The plan asked for thresholds that start strict and relax over time. They are pre-registered in
[freeze-threshold-ladder.json](../research/prereg/freeze-threshold-ladder.json) (digest
`0c4bdf2b6857`), sealed before any stage's data existed, and enforced by
`benchmarks.freeze_ladder`: a gentler stage is reachable only after the stricter one passed, only on
rows no earlier stage used, and safety bounds never relax. One sealed amendment moves the CDM S1
population to fresh seeds because the original seeds could not reach its own minimum size; no
threshold changed.
