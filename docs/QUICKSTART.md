# Quickstart: ten minutes, from install to a verified correction

## One minute: see a correction change an action decision

For the shortest offline path, install the local package and run the bundled
fixture:

```bash
python -m pip install --no-index --no-deps --no-build-isolation .
python examples/getting_started.py
```

It stores and recalls an approved maintenance fact, authorizes a protected
action, applies a correction, and shows that the old action is now blocked
while the revised fact is visible. The example uses deterministic fixture
data and local storage only; the package install and example need no index,
credentials, hosted model, or external endpoint. The local Python environment
must already have the declared build backend (`setuptools>=77`).
`tests/test_examples_run.py` verifies the offline install and full path within
60 seconds.

The longer `examples/quickstart.py` walkthrough runs inside the public
`memory_fabric.offline.offline_mode()` context. While active, it refuses Python
DNS lookups and socket connection or send calls, so an accidental networking
dependency fails immediately. This is a process-local guard; use an OS sandbox
as well when untrusted native code or child processes must also be contained.

The longer walkthrough follows.

Every step below is in [examples/quickstart.py](../examples/quickstart.py),
which `tests/test_quickstart.py` runs on every CI build, on Linux, macOS and
Windows with Python 3.11 to 3.13.

## 1. Install (1 minute)

```bash
git clone https://github.com/crakashp2905-hub/memory_fabric.git
cd memory-fabric
pip install .
memory-fabric init ./memory --mode personal     # or team (default), or regulated
```

`init` creates a store, keeps its keys outside it, registers one agent,
prints an MCP client configuration and runs `doctor`. It never overwrites an
existing store.

**Pick a mode, not a dozen settings.** `personal`: one person and their
agents; what they write is usable at once. `team`: shared knowledge; new
memories wait for review. `regulated`: protected tools need two independent
sources and fresh evidence. In Python: `presets.open_store(path, "team")` and
`presets.tool_rule("team", "issue_refund")`.

**Removal is clean.** The package writes nothing outside the directories you
name:

```bash
pip uninstall memory-fabric
```

Then delete `./memory` (the store and its keys) if you no longer want the
data. There are no services, registry entries or files elsewhere.

## 2. Store, retrieve, inspect, correct, verify (5 minutes)

```bash
python -m examples.quickstart
```

| step | call | what to look at |
|---|---|---|
| store | `remember`, `derive` | every memory records who wrote it and how; `derive` records its premises |
| retrieve | `retrieve(...).exposed` | what an agent is shown; each exposure is logged with its probability |
| inspect evidence | `explain(id).narrative()`, `authority(id)` | why it is remembered, where it came from, and how far it may be trusted |
| correct | `correction.preview`, then `correction.apply` | what withdrawing it would touch, *before* you decide; then the withdrawal and the retractions owed |
| verify | `retrieve` again, `verify_recovery`, `influence.impact` | the wrong memory and the plan built on it are no longer shown; recovery is `contained`, checked from state |

## 3. Use it from your agent (4 minutes)

- **An MCP client** (Claude Code, Claude Desktop, IDE assistants): paste the
  configuration `init` printed.
- **Python:** [examples/reference_agent.py](../examples/reference_agent.py)
  is the reference agent: it retrieves before it acts, cites what it used, gets a
  grant for the exact action, executes through the fence and records the verified outcome.
- **Anything else:** see [INTEGRATIONS.md](INTEGRATIONS.md).

If something fails, `memory-fabric --db ./memory/store.db doctor` names the
failing check and the next command, and [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
lists every error message. Add `--log-format json` for structured logs.

## 4. See what an agent was given, and try changes on a branch (optional)

```bash
python examples/wrong_memory_demo.py
```

It walks one story: a policy stored and used, a corrected source, a preview
of what the correction touches (applied only if nothing changed since the
preview), the next context leaving the stale rule out, and an alternative
proposed on a branch that main never sees until a reviewer merges it. From
the command line:

```bash
memory-fabric --db demo.db context build --agent support-bot --query "refund window"
memory-fabric --db demo.db branch create trial --actor you --reviewer lead
memory-fabric --db demo.db merge preview trial --actor lead
```

Context receipts, the context planner and branches are **experimental**; the
dashboard's Capabilities tab lists what is available, experimental or not
offered, and why.
