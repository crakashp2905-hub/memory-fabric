# Typed SDK workflow

[`examples/sdk_workflow.py`](../examples/sdk_workflow.py) is a runnable,
offline composition of the public agent, operator, decision, correction and
action APIs. It uses a deterministic proposal and a fixed memory fixture; it
does not use a hosted model or perform an external effect. CI runs it through
[`tests/test_examples_run.py`](../tests/test_examples_run.py).

## Surface map

| Task | Typed surface | Boundary |
|---|---|---|
| Add and recall | `sdk.AgentClient.remember`, `recall`, `fetch` | Agent writes are private by default; reads are enforced and carry exposure tokens |
| Explain and review | `sdk.OperatorClient.explain`, `inspect`, `validate`, `share` | Operator inspection can see withdrawn content and must not be handed to an agent |
| Correct | `memory_fabric.correction.preview`, `apply` | Preview exposes the affected lineage; applying records the correction and invalidates dependent use |
| Decide | `decision_models.DecisionModel`, `DecisionContext`, `DecisionProposal` | A validated proposal is not authorization; the caller must still use the action gate |
| Execute safely | `actions.ActionGate.execute` | Verifies current evidence and authorization in the execution fence immediately before the tool effect |

## Typed refusal and error behavior

| Operation | Refusal or invalid-input behavior |
|---|---|
| `AgentClient.recall` | Returns only usable memories; each carries a token and possible warnings |
| `AgentClient.fetch` | Raises `sdk.NotUsable` when enforcement refuses; inspect its `.decision.reason_code`, not the content |
| `AgentClient.verify` | Returns an `AccessDecision`; callers must check `.usable` before proceeding |
| `AgentClient.require` | Raises `sdk.NotUsable` when the high-risk recheck fails |
| `AgentClient.recall/fetch(operation=EXECUTE)` | Raises `ValueError`; execution requires an `ActionGate` and certificate |
| `DecisionContext` / proposal validation | Raises `DecisionModelError` for empty or duplicate options, malformed probabilities, inconsistent abstention, or an unknown selection |
| `ActionGate.execute` | Returns an `ActionExecution` with explicit `executed`, `refused`, `timed_out`, `failed`, or retry outcome; only `executed` means the effect ran successfully |
| `correction.preview` | Raises `KeyError` for an unknown memory id |
| `correction.apply` | Raises `ValueError` for an absent/invalid actor and `StalePreview` when a supplied preview digest no longer matches; the caller must preview again before retrying |

The agent and operator clients intentionally do not combine into one broad
object: the agent client cannot inspect withdrawn memories, and the operator
client cannot use its inspection reads as action evidence. See the generated
[`API reference`](API.md), the [SDK contract](SDK_CONTRACTS_0.14.md), and the
[action fence](ACTION_IDEMPOTENCY.md) for complete signatures and stability
limits.
