# Preregistration: generated-program provenance in action authorization

- Registration date: 2026-11-09
- Task: N6-10
- Status: preregistered before the confirmatory mutation matrix below was run.
- Pilot disclosure: A single append-an-extra-effect case was run while validating
  the implementation and harness. It is excluded from the confirmatory cases
  and summary; the confirmatory append case uses a different target value.

## Claim and hypothesis

**MF-N6-10-H1:** Binding human approval to the SHA-256 digest of the complete
constrained generated program, alongside each exact `ActionRequest` and evidence
certificate, prevents a source-mutated program from reusing approval when the
first effect keeps identical tool arguments.

**Null:** A simple policy-wrapped tool call that binds only tool, arguments,
identity and evidence detects the same source mutations.

## Design

Use a deterministic local `ActionGate`, one authenticated principal, one valid
evidence certificate, and a dispatch rule requiring a human approval. Approve
the source `dispatch(target="pump-7", setpoint=40)`. Compare:

1. Exact approved source through `CodeModePlan` and `GovernedToolRuntime`.
2. Ten preregistered source mutations through the same runtime and reuse the
   approval from the original source.
3. One ordinary policy-wrapped direct `ActionGate` request with identical
   tool/arguments/evidence and an approval that does not include generated
   source provenance.

The mutation set is: trailing comment; leading comment; blank line prefix;
keyword order change; multiline formatting; append a second dispatch to
`pump-9`; duplicate the first dispatch; semicolon-separated second dispatch to
`pump-10`; parenthesized call; alternate legal spacing. Each mutation must
preserve the first call's `dispatch(target="pump-7", setpoint=40)` semantics.

## Outcomes and decision rule

Primary outcome: exact source executes; all ten mutated sources return
`approval_invalid` before the handler runs. Secondary comparison: the ordinary
policy binding remains equal for the unchanged first action, and its direct
policy-wrapped call is allowed. The hypothesis is supported for this local
contract only if every condition holds. Any parse error, other refusal reason,
unexpected effect, missing baseline allow, or mismatch in first-call arguments
counts as a failure; no cases will be dropped or replaced.

The unit is one deterministic local authorization flow. There is no random
sampling, model invocation, statistical generalization, or utility score beyond
successful execution of the unchanged approved program. Report all outcomes,
including negative results.

## Scope and limitations

This tests one workflow, one policy, and ten fixed source mutations. The exact
source digest makes comments and whitespace approval-relevant. It does not
prove that source provenance improves broad agent utility or protects arbitrary
Python execution; Code Mode remains a constrained literal-call grammar.
