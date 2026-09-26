# Stage 3 BONUS Development Report v1

- Status: `BONUS_DEV_REPLAY_NOT_PAPER_FACING`
- `CURRENT_PAPER_BASELINE_PRESERVED = true`; `CURRENT_PAPER_TABLE3_REPLACED = false`
- `FINAL_UNSEEN_BENCHMARK_CREATED = false`; `REAL_LLM_API_CALLS = 0`
- The order supplement is development-only and uses synthetic endpoint stubs; it is not a real Stage-2 result.

## Main Table

| Method | Precision | Recall | F1 |
|---|---:|---:|---:|
| Sun | 0.4118 | 0.5385 | 0.4667 |
| Ours | 0.4643 | 0.6667 | 0.5474 |

## Breakdown

| Method | Missing F1 | Actor F1 | Order F1 | Macro-F1 | Coverage | Unknown rate |
|---|---:|---:|---:|---:|---:|---:|
| Sun | 0.4554 | 0.4262 | 0.6667 | 0.5161 | 0.6575 | 0.3425 |
| Ours | 0.4935 | 0.5684 | 0.6667 | 0.5762 | 0.8630 | 0.1370 |

## Before vs After

| Method | Baseline F1 | BONUS DEV F1 | Delta F1 |
|---|---:|---:|---:|
| Sun | 0.4458 | 0.4667 | +0.0209 |
| Ours | 0.5341 | 0.5474 | +0.0133 |

## Improvement Attribution

- Missing scope change: `delta_TP = 0`, `delta_FP = 0`, `delta_FN = 0` because no action-scope revision was implemented.
- Actor: unchanged algorithm; `delta_actor_F1 = 0`.
- Order supplement: added 18 new development-only order cells per method (9 requirements x baseline/out-of-order).

| Method | delta_TP | delta_FP | delta_FN | delta_TN | new support cells | delta unknown positive | delta unknown negative |
|---|---:|---:|---:|---:|---:|---:|---:|
| Sun | 5 | 0 | 4 | 5 | 18 | 4 | 4 |
| Ours | 5 | 0 | 4 | 5 | 18 | 4 | 4 |

## Decision Fields

- `ACTION_SCOPE_REVISION_IMPLEMENTED = false`
- `BONUS_DEV_REPLAY_COMPLETE = true`
- `BONUS_RESULT_METHOD_VALID = false`
- `BONUS_RESULT_NUMERICALLY_IMPROVED = true`
- `CANDIDATE_FOR_FUTURE_TABLE3_METHOD = false`
- `CURRENT_PAPER_BASELINE_PRESERVED = true`
- `CURRENT_PAPER_TABLE3_REPLACED = false`
- `FINAL_UNSEEN_BENCHMARK_CREATED = false`
- `MISSING_ROOT_CAUSE_RESOLVED = MAPPING_DOMINANT_NO_ALLOWED_FIX`
- `ORDER_ADAPTER_CHANGED = false`
- `ORDER_GENERALIZATION_COMPLETE = true`
- `REAL_LLM_API_CALLS = 0`
- `ACTION_SCOPE_REFINEMENT = REJECTED`

## Final Answer

- The remaining low Missing-action F1 is dominated by required-action mapping failures and BPMN-label semantic mismatches, not by a clean, removable denominator-scope contamination.
- The action-scope gate was rejected (strict gate-eligible scope FPs below 30%), so `ObligationScopedActionProjectionV1` was not implemented.
- The only new development signal is the order-supplement diagnostic. It is not a valid replacement for the paper-facing Table 3 because its endpoints are dev-only synthetic stubs, not real Stage-2 predictions.
- `CURRENT_PAPER_BASELINE_PRESERVED = true`; continue to report Sun F1 `0.4458` vs Ours F1 `0.5341` until the user decides otherwise.
