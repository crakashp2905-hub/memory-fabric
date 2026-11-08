# Reproducibility appendix: local correction and provenance comparisons

This appendix defines its scope explicitly: the three deterministic comparison
tables below. They are generated from repository fixtures, use no API keys or
external datasets, and make no live-agent or population claim. It is not a
reproduction protocol for every model-based or external result elsewhere in the
repository.

## Environment and protocol

- Python: 3.13.5; reference run OS: Windows 11.
- Dependencies: repository core runtime and its checked-in test dependencies;
  no model SDK, API key, network service, external corpus or database server.
- Random seed: `0` for the `MemoryFabric` instances. The fixtures themselves
  are deterministic and contain fixed claims and actions.
- Data generator: inline records in each example; no downloaded data.
- Protocol: start a fresh in-memory store, run the example to completion,
  capture stdout and exit status, then run `tests.test_examples_run` to check
  the output contract. These are local demonstrations, not independently
  authored benchmark arms.

## Result tables and replay commands

| Table | Data and seed | Replay command | Expected table-level observation | Result artifact |
|---|---|---|---|---|
| Correction strategies | Fixed 30-second pump value, corrected to 45 seconds, independent 34-psi tyre fact; seed 0 | `python examples/correction_strategy_comparison.py` | Naive deletion leaves one stale proposal; blanket blocks one unrelated action; selective gate blocks stale and allows unrelated action | `research/results/p4-04-correction-strategy-comparison.json` and `.txt` |
| Selective correction | Fixed pump source, correction, and unrelated tyre evidence; seed 0 | `python examples/correction_spares_unrelated_action.py` | Dependent action changes from executed to refused; unrelated action remains executable | `research/results/p4-05-selective-correction-demo.json` and `.txt` |
| Provenance dispute | One root with four derived copies, one independent 14-bar report, then a second independent report; seed 0 | `python examples/multi_agent_provenance_dispute.py` | Five copies remain one root; one root on each side is contested; second independent root changes support without proving truth | `research/results/p4-06-provenance-dispute-demo.json` and `.txt` |

Run all three plus output-contract checks with:

```powershell
python -m unittest tests.test_examples_run
```

## Version and integrity

For a fresh reproduction, record `git rev-parse HEAD`, Python/OS, command exit
codes, stdout, and SHA-256 hashes of the three example files and result outputs.
Do not overwrite historical artifacts: write new results under a new run
identifier and compare them with the pinned historical records. The historic
P4-04 execution record was made from a dirty source snapshot; its source-file
hashes are retained, and this appendix does not represent that old run as an
exact-clean-SHA execution.

These outputs can be regenerated locally without API keys or external datasets.
They establish only deterministic fixture behavior; they are not live-model,
human, independent, customer or physical-deployment results.
