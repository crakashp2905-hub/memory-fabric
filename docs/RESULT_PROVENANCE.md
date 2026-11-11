# Result source provenance

New result writers should call `benchmarks.provenance.stamp` before writing
their JSON artifact. It records the exact 40-character Git commit and explicit
dirty-tree state. `validate` rejects abbreviated or unknown commits and
rejects dirty results unless they carry `EXPLORATORY` classification and a
reason. `benchmarks.manifest.write` applies this gate automatically.

Do not reconstruct provenance for older results. The generated results
catalogue reports missing or abbreviated historical source identifiers as
gaps; it does not infer a clean tree from a commit field.
