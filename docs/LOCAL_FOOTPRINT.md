# Local installation and footprint qualification

This check describes one Windows 11 host and one Python 3.13.5 interpreter. It
is a repeatable local engineering check, not a cross-host product guarantee or
a service SLO.

## Result

Run: `research/results/p4-08-local-footprint.json`  
Source wheel: `dist/candidate-2ef5273/memory_fabric-0.14.0-py3-none-any.whl`

| Measure | Observed | Threshold | Result |
|---|---:|---:|---|
| Wheel file | 655,185 bytes | ≤ 2,000,000 bytes | PASS |
| Fresh target install | 4,393,074 bytes | ≤ 5,000,000 bytes | PASS |
| Cold `memory-fabric --version` median (15 starts) | 2,738 ms | ≤ 1,500 ms | FAIL |
| Cold CLI p95 (nearest-rank sample) | 2,940 ms | ≤ 2,000 ms | FAIL |
| SQLite file after 200 unique records | 323,584 bytes / 200 = 1,618 bytes per record | ≤ 100,000 bytes per record | PASS |
| Idle CPU, one 30-second sample | 1.2% | ≤ 5% | PASS |

The startup budget failed on this run. Keep this result visible as a performance
issue to investigate; do not interpret the other passing measurements as
overall performance qualification.

The target-install total includes the package, generated CLI, dist-info files,
and bytecode produced while exercising the install. The wheel itself is the
package artifact size. Startup is a cold process invocation of `--version`,
not import latency, web-service readiness, or request latency. The storage
fixture is a small sequential SQLite workload and does not include WAL peaks,
backups, encryption key custody, concurrent writers, or federation.

## Reproduce

```powershell
python tools/measure_local_footprint.py dist/candidate-2ef5273/memory_fabric-0.14.0-py3-none-any.whl `
  --output .task-tmp/p4-08-rerun --json research/results/p4-08-local-footprint.json
```

The tool installs the wheel with pip `--no-index --no-deps --target`, invokes
the generated CLI 15 times, writes 200 distinct memories to a fresh SQLite
file, and samples the child interpreter's CPU over 30 seconds. Thresholds are
defined in the tool and copied into the JSON output. A different machine or
package version should produce a new result record rather than replacing the
claim that these measurements were taken on this host.
