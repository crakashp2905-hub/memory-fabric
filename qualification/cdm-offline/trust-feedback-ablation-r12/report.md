# CDM-R12 trust and evaluator-feedback ablation

Frozen synthetic factorial comparison. Utility, robustness, and correct-memory withholding are separate metrics.

## Held-out results

| Arm | Condition | Mean utility (95% interval) | Proposal accuracy | Correct memories withheld |
|---|---|---:|---:|---:|
| annotations_off_feedback_off | clean | 0.220 [-0.140, 0.580] | 0.500 | 9/10 (90.0%) |
| annotations_off_feedback_off | annotation_inversion | 0.220 [-0.140, 0.580] | 0.500 | 9/10 (90.0%) |
| annotations_off_feedback_off | feedback_inversion | 0.220 [-0.140, 0.580] | 0.500 | 9/10 (90.0%) |
| annotations_on_feedback_off | clean | 0.240 [-0.116, 0.596] | 0.700 | 8/10 (80.0%) |
| annotations_on_feedback_off | annotation_inversion | 0.240 [-0.116, 0.596] | 0.700 | 8/10 (80.0%) |
| annotations_on_feedback_off | feedback_inversion | 0.240 [-0.116, 0.596] | 0.700 | 8/10 (80.0%) |
| annotations_off_feedback_on | clean | 0.220 [-0.140, 0.580] | 0.500 | 9/10 (90.0%) |
| annotations_off_feedback_on | annotation_inversion | 0.220 [-0.140, 0.580] | 0.500 | 9/10 (90.0%) |
| annotations_off_feedback_on | feedback_inversion | 0.220 [-0.140, 0.580] | 0.500 | 9/10 (90.0%) |
| annotations_on_feedback_on | clean | 0.240 [-0.116, 0.596] | 0.700 | 8/10 (80.0%) |
| annotations_on_feedback_on | annotation_inversion | 0.330 [-0.053, 0.713] | 0.700 | 9/10 (90.0%) |
| annotations_on_feedback_on | feedback_inversion | 0.240 [-0.116, 0.596] | 0.700 | 7/10 (70.0%) |

## Paired robustness deltas

Positive clean-minus-challenge values indicate lower utility or accuracy under the challenge.

| Arm | Challenge | Utility change | Accuracy change |
|---|---|---:|---:|
| annotations_off_feedback_off | annotation_inversion | 0.000 | 0.000 |
| annotations_off_feedback_off | feedback_inversion | 0.000 | 0.000 |
| annotations_on_feedback_off | annotation_inversion | 0.000 | 0.000 |
| annotations_on_feedback_off | feedback_inversion | 0.000 | 0.000 |
| annotations_off_feedback_on | annotation_inversion | 0.000 | 0.000 |
| annotations_off_feedback_on | feedback_inversion | 0.000 | 0.000 |
| annotations_on_feedback_on | annotation_inversion | -0.090 | 0.000 |
| annotations_on_feedback_on | feedback_inversion | 0.000 | 0.000 |

## Scope and safety

Seeds: training 20261801–20261810, held-out 20261811–20261820; oracle exceeded: False; safety: `{"authority_changes": 0, "model_calls": 0, "network_calls": 0, "tool_calls": 0, "truth_visible_to_proposer": false}`.

- Finite synthetic seeds; not population evidence.
- Correctness means sensor value agrees with evaluator-only latent truth.
- The one-removal ceiling is an in-simulator mechanism check, not a deployment oracle.
