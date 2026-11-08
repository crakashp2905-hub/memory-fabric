# Read-only advisory degradation

`assess_read_only_advisory` gives a host an explicit policy decision for
presenting retrieval as a read-only advisory. `ReadOnlyAdvisoryPolicy` denies
insufficient and review-required packages by default; a host must separately
opt into `allow_insufficient` or `allow_review` for the corresponding
disclosed presentation.

An insufficient advisory carries its answerability reasons and the disclosure
that evidence is insufficient or undetermined and that the result does not
authorize action. Invalid, conflicting, or otherwise review-required evidence
has a separate opt-in and a review disclosure. The result only controls
presentation: `action_authorized` is always false, and the function does not
call a tool or return an execution capability.

Protected execution remains governed independently by `ActionGate`. A
read-only advisory permission cannot substitute for a certificate, satisfy a
requirement graph, or authorize a protected tool. Hosts must keep advisory
presentation separate from consequential execution and retain the disclosure
when displaying the advisory.
