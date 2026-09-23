# Stage 3 grounding intervention test v1

Diagnostic only. The formal Ours predictions and Table 3 were not modified, re-scored or overwritten.

- benchmark: `data/development/stage3_synth/stage3_paired_benchmark_v1.json`
- grounding input sha256: `f39da0ef3a318d1690652d1357cd4cff5ff0dc61486e2eff65371467cceae395`
- formal predictions sha256: `659355be0c867c6b33f65c520911aa750eeccb0e5a6aa26976c49bb9e0b038ba`
- baseline reproduces formal predictions: `True`

## Macro-F1 by intervention

| Test | Perturbation | Macro-F1 | Micro-F1 | Specificity | Exact type |
|---|---|---:|---:|---:|---:|
| baseline (persisted grounding) | `none` | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| A1 literal action-order shuffle | `action_order_rotation_within_pair` | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| A2 cross-pair action-grounding shuffle | `cross_pair_action_grounding_payload_permutation` | 0.3478 | 0.4848 | 0.0769 | 0.6154 |
| B wrong-lane injection | `expected_lane_replaced_by_variant_observed_lane` | 0.5000 | 0.6154 | 0.6154 | 0.6154 |
| C null grounding | `all_grounding_fields_null` | 0.0000 | 0.0000 | 1.0000 | 0.0000 |

## Per-type F1

| Test | missing_action | incorrect_actor | out_of_order |
|---|---:|---:|---:|
| baseline (persisted grounding) | 1.0000 | 1.0000 | N/A |
| A1 literal action-order shuffle | 1.0000 | 1.0000 | N/A |
| A2 cross-pair action-grounding shuffle | 0.6957 | 0.0000 | N/A |
| B wrong-lane injection | 1.0000 | 0.0000 | N/A |
| C null grounding | 0.0000 | 0.0000 | N/A |

## Interpretation

Null grounding and adversarial lane injection remove detector recall; cross-pair binding-content shuffle lowers macro-F1. Within-pair action-order rotation stays at baseline because the detector consumes the union of candidate activity IDs and the per-ID lane map, not the per-action top-1 order.  This does not indicate missing grounding dependency; it localises the dependency in the candidate-set/lane representation.

A1 is intentionally reported separately: it permutes action records but keeps the candidate-set union and per-ID lane map unchanged, so the detector is invariant. A2 demonstrates that changing the actual consumed grounding payload changes the output. B and C demonstrate direct causal reliance on lane and presence grounding respectively.

Diagnostic prediction files:

- `outputs/development/stage3_grounding_intervention_v1/baseline_unchanged_grounding_predictions.jsonl`
- `outputs/development/stage3_grounding_intervention_v1/a1_within_pair_action_order_shuffle_predictions.jsonl`
- `outputs/development/stage3_grounding_intervention_v1/a2_cross_pair_action_grounding_shuffle_predictions.jsonl`
- `outputs/development/stage3_grounding_intervention_v1/b_wrong_lane_injection_predictions.jsonl`
- `outputs/development/stage3_grounding_intervention_v1/c_null_grounding_predictions.jsonl`

