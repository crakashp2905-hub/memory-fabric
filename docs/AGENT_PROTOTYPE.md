# Agent-outcome prototype: run it in five commands

This page is the shortest path through the working prototype. It runs offline,
on the standard library, with no hosted service, downloaded data or model.

| | |
|---|---|
| **What it is** | An observer, planner and executor that share Memory Fabric memory, run on one canonical episode runtime (`memory_fabric.outcome_typed`) against simulated worlds, and are graded by an evaluator they cannot see |
| **What it shows** | On five designed world families, governance (tenant access control plus the action gate) and recovery (re-planning when evidence changes) each improve safe outcomes where their mechanism applies, against fair baselines given the same recovery |
| **What it does not show** | Anything about learned agents, prevalence in real tasks, or production readiness. No local model has been run, and the deployment decision is HOLD ([decision record](../research/results/agent-outcomes/LAUNCH_DECISION.md)) |

## 1. One episode, start to finish

```bash
python -m benchmarks.outcome_episode --seed 1
```

The observer records the world's events, and the planner recalls them and
proposes. A correction arrives after the plan, so the runtime re-plans, the
action gate authorizes the corrected value, the executor commits it, and the
evaluator grades the world at the task horizon: `evaluator: COMPLETED`.

## 2. Matched arms on the same tasks

```bash
python -m benchmarks.outcome_arms --seeds 8 --out arms.json
python -m benchmarks.outcome_scorecard --arms arms.json --out-json score.json --out-md SCORE.md
```

The seven actor arms are listed below. A7 is the evaluator's ceiling, never an
actor. The scorecard reports every
metric with its eligibility rule and denominator. For scripted evidence its
decision is **HOLD** at best. Committed rows:
[SCRIPTED_ARMS_DEV.md](../research/results/agent-outcomes/SCRIPTED_ARMS_DEV.md) and
[SCRIPTED_SCORECARD_DEV.md](../research/results/agent-outcomes/SCRIPTED_SCORECARD_DEV.md).

- A0: no memory
- A1: agent-local memory
- A2: pooled memory
- A3: pooled memory with a retraction recheck and recovery
- A4: Memory Fabric with the gate, recovery off
- A5: Memory Fabric with the gate, recovery on
- A6: A5 plus dependence-first counterfactual dispatch. It is advisory: it flags
  past decisions that later evidence would change and never acts

## 3. Where each effect comes from, and how much room there is

```bash
python -m benchmarks.outcome_ablation --seeds 8 --out ablation.json
```

This runs a memory × recovery factorial and reports the main effects and
their interaction per family, plus which tasks the fair baseline already
solves ([SCRIPTED_ABLATION_DEV.md](../research/results/agent-outcomes/SCRIPTED_ABLATION_DEV.md)).

## 4. Qualify a commit

```bash
python tools/agent_outcome_end_to_end_gate.py --offline --all --out gate-run
```

This one command checks contracts, the adversarial gate and secret scan, the
demo, the arms and scorecard, and provenance. It writes `report.json` and
`REPORT.md` even when a stage fails, and exits 1 on any required failure.
Committed record:
[candidate-offline/42af56d](../research/results/agent-outcomes/candidate-offline/42af56d/REPORT.md).

## 5. What is available here, and what is missing

```bash
python tools/agent_outcome_doctor.py --model qwen2.5:1.5b
```

The doctor reports:

- the runtime and package versions;
- which outcome package is canonical and which are deprecated;
- each role's tools;
- whether recovery is on by default;
- whether a local model is installed (loopback only, nothing downloaded);
- the task-ledger totals;
- whether this commit has an end-to-end gate record.

## Tenants and authorization

```bash
python examples/agent_outcome_tenant_setup.py
```

This sets up a tenant from nothing:

- agent keys are generated with `os.urandom` and never printed;
- the action policy grants one tool to one agent;
- a second agent in the same tenant is registered without that grant.

The script prints `ops: allowed` and `intern: refused (tool_not_granted)`.
Nothing in it is a default credential. For the high-level API
(`memory_fabric.outcome_typed.api`), requests are checked against
[`docs/schemas/outcome-api.v1.json`](schemas/outcome-api.v1.json). Grants,
certificates, callbacks and code are refused as request fields; effects are
host-registered.

## With a local model

If an Ollama runtime on 127.0.0.1 already has a model, run:

```bash
python -m benchmarks.outcome_model_team --model qwen2.5:1.5b --out model-team.json
python tools/agent_outcome_end_to_end_gate.py --offline --all --out gate-run --local-model qwen2.5:1.5b
```

Every role then calls the model through a strict JSON contract. A failed call
ends the episode as a distinct incomplete outcome, never as a scripted answer.
Without a model, both commands report `REAL_AGENT_NOT_RUN`. The test suite's
loopback server (`benchmarks/fake_local_model.py`) is labelled
`FAKE_BACKEND_NOT_EVIDENCE` and never counts as inference.

## Decisions

```bash
python tools/launch_decision.py --gate research/results/agent-outcomes/candidate-offline/42af56d/report.json \
    --out-json decision.json --out-md DECISION.md
```

This writes two separate decisions from hashed, committed inputs:

- **Engineering: GO**, for continuing to build this as a local scripted prototype.
- **Deployment: HOLD**, until confirmatory evidence, a local-model pass,
  model-attack evidence and an independent review each exist for one commit.
