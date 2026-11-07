# Source and wheel installation parity

Run `python tools/package_parity.py --report research/results/package-parity.json`
from a clean checkout. The tool builds both sdist and wheel from that checkout,
installs them independently, and runs identical import, CLI help, quickstart,
reference-agent, initialization and `doctor` checks from outside the checkout.

The JSON report binds the run to the source commit, includes artifact SHA-256
hashes and records every command's exit code and output tail. The script checks
that both imports resolve under their respective virtual environments and that
the two artifacts report the same version and smoke-check outcomes. It uses
locally available build tooling and installs the project's declared no-runtime-
dependency package without reaching out to package indexes.
