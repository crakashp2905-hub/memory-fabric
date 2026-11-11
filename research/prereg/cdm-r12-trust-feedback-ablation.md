# CDM-R12: trust annotations and evaluator-feedback ablation

Status: frozen before fixture execution. Version 1. Date: 2026-11-08.

## Question and registered arms

Estimate the separate and joint effects of using per-source trust annotations
and updating those annotations from post-proposal evaluator feedback. This is a
first-party synthetic mechanism check, not a reproduction of an external system.

The factorial arms are: annotations off / feedback off; annotations on /
feedback off; annotations off / feedback on; and annotations on / feedback on.
All arms receive identical worlds and select exactly one observation for
temporary removal. When annotations are off, selection uses the greatest
leave-one-out posterior change. When on, it uses the highest stored source
score, with stable source-name tie breaking. Trust scores start at 0.5 and use
the R6 bounded EMA update (alpha 0.1, maximum 20 observations). Outcomes become
available only after each proposal is emitted.

## Seeds, scenarios, and estimands

Training seeds are 20261801–20261810. Held-out seeds are 20261811–20261820;
the splits are disjoint and the held-out worlds are not used to set parameters.
Each held-out world is evaluated in three registered conditions: clean; trust
annotation inversion (`score` becomes `1 - score` at selection time); and
feedback inversion (`reward` becomes `1 - reward` before the bounded update).
Challenge streams start from each arm's post-training state and are independent
from the clean held-out feedback stream.

Report separately for every arm and condition: mean task utility and its
normal-approximation 95% interval; proposal accuracy; and correct-memory
withholding, defined as the fraction of removed observations whose recorded
value agrees with evaluator-only latent truth, with numerator and denominator.
Robustness is the paired clean-minus-challenge utility and accuracy change per
arm and challenge, computed on identical held-out seeds. A one-removal oracle
ceiling evaluates all three possible one-observation removals under the same
policy and chooses the best utility after proposal generation; it never feeds
labels to a scored selector. Any scored arm exceeding this ceiling is a protocol
failure.

## Safety and limits

World generation is deterministic and local. Proposers receive observations,
the public Bayesian model, policy, and (for the relevant arm) trust scores; the
latent label is available only to the evaluator after selection and proposal.
No Memory Fabric lifecycle, authorization or source-truth state is mutated. No
network, model or tool calls occur. Finite synthetic results do not establish
population performance, causal effects in physical systems, or deployment
safety. Protocol changes require a new version and fresh seeds.
