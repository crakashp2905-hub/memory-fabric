# Local core build and dependency provenance

The Memory Fabric core has no runtime dependencies. The repository commits
`uv.lock`, which resolves the test and every declared optional extra. The lock
contains exact versions and artifact hashes; `research/results/h5-01-dependency-provenance.json`
records the resolved package inventory and lock digest.

The wheel and normalized source distribution are built twice from the source
commit and toolchain recorded in
`research/results/h5-01-core-build-repeatability.json`. On Windows PowerShell,
reproduce them with the recorded Python, `build`, and `setuptools` versions:

```powershell
$env:SOURCE_DATE_EPOCH = "0"
python -m build --no-isolation --wheel --sdist --outdir dist
python tools/normalize_sdist.py dist/memory_fabric-0.19.0.tar.gz
Remove-Item Env:SOURCE_DATE_EPOCH
```

The normalizer sorts tar entries and resets member timestamps, ownership
metadata, and gzip timestamps without changing file contents. The repeatability
result records both artifact hashes and the package manifests. The wheel also
installed and imported as version 0.19.0 in a fresh virtual environment using
`pip install --no-index --no-deps`.

This evidence qualifies local core artifacts and dependency resolution. It does
not indicate that a package was published or that optional integrations were
installed and exercised. The sdist normalizer regression test is recorded at
`research/results/h5-01-normalize-sdist-tests.xml`.
