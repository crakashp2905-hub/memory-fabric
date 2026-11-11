# Pre-registration — O1-r: O1 rerun with both of its fixes, on fresh seeds

**Registered 2026-11-11, after the fixes were written and before any seed in
5–9 was run.** The parent registration is
[o1-live-poisonworld.md](o1-live-poisonworld.md). Everything not stated here
is unchanged from it: the world, the model (`gemma3:4b`, temperature 0, same
prompt and schema), k, the oracle, the metrics, λ ∈ {1, 5, 20}, the
thresholds, the abandonment rule and the checks.

## 1. What changed, and why it is not tuning

O1 traced every one of `fabric`'s 267 misreads to two product behaviours, and
both are now fixed in the library, covered by tests in `tests/test_o1_fixes.py`:

1. **Origin, not author.** A hostile withdrawal of a memory that declares
   `context["ingested_from"]` discredits that origin. Before, it discredited
   the honest agent that stored it, along with all of that agent's true notes.
2. **Certificates name their target.** `certify(..., about=(unit, site))` is
   refused (`evidence_off_target`) unless some usable supporting memory
   mentions both.

Neither fix was tuned on a registered seed. The only measurement after the
fixes is one model-free check on seed 5: the hostile set holds the 8 injected
pages and no agent. It says nothing about outcomes.

## 2. The one arm under test

`fabric_v2`: the current library, default configuration, used as the fixes
ask callers to use it.

- **Only injection writes declare an origin** (`ingested_from = page:<n>`,
  one page each). The world defines these as honest agents who ingested a
  poisoned page. Agent 0's poison and its verbatim forwards declare nothing:
  an attacker does not label its own writes, and declaring the forwards would
  hand `fabric_v2` information about the attack.
- The agent certifies with `about=(unit, site)`.

The baseline arms (`shared`, `provenance_blanket`, `abstain`, `oracle`) are
re-run on seeds 5–9 **before** `fabric_v2` (AGENTS.md 8d). They cannot read
`ingested_from`, so the declaration gives them nothing. That is the claim
under test: provenance is information only a store that reads it can use.

## 3. Seeds and output

Seeds **5–9**, which no part of O1 or this design has seen. Raw output goes to
`research/results/o1r-fixed-fabric-raw.json`. O1a, O1b and O1c are judged on
`fabric_v2`.

## 4. Disclosed

- The fixes came from reading O1's failure on seeds 0–4, so O1-r tests whether
  they **generalise to fresh seeds of the same world**. It does not test them
  on an independent world.
- The exploratory O1 arm (`fabric_nowithhold`, 0.320 at every λ) is not a
  prediction for this run, and no threshold is moved because of it.
