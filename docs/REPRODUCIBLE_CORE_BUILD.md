# Local core build provenance

The project core declares no runtime dependencies. The local core wheel was
built from the source commit recorded in
`research/results/h5-01-core-build-repeatability.json` with Python 3.13.5,
`build` 1.6.1, and `setuptools` 80.9.0.

On Windows PowerShell, reproduce the wheel with the same toolchain and fixed
archive epoch:

```powershell
$env:SOURCE_DATE_EPOCH = "0"
python -m build --no-isolation --wheel --sdist --outdir dist
python tools/normalize_sdist.py dist/memory_fabric-0.19.0.tar.gz
Remove-Item Env:SOURCE_DATE_EPOCH
```

The pinned wheel and normalized sdist hashes are in the build-repeatability
result. Two independent builds produced byte-identical copies of both. The
normalizer sorts tar entries and resets member timestamps, ownership metadata,
and gzip timestamps without changing file contents. The wheel installed in a
fresh virtual environment with `pip install --no-index --no-deps` and imported
as version 0.19.0.

This qualifies only the zero-dependency core wheel under the recorded local
toolchain. It is not a release or a published artifact. A complete project
lock is still missing: offline `uv lock` failed because the local registry cache
does not contain the pinned `pytest==9.0.3` package metadata, and optional
extras were not fully resolved. Do not infer transitive extra dependency pins
from the current machine's installed package list.

The deterministic sdist regression test is recorded at `research/results/h5-01-normalize-sdist-tests.xml`. H5-01 remains partial because complete optional dependency lock metadata could not be generated offline.
