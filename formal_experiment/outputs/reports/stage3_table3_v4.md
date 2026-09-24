# Stage 3 Table 3 v4 (scoped GDPR checking)

Reference is AI-constructed (`is_gold=false`, `human_adjudicated=false`). Metrics are given applicable-scope checking, not full GDPR end-to-end F1.

| Method | Type | TP | FP | FN | TN | Unknown-positive | Unknown-negative | Positive | Negative | P | R | F1 | Coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sun | missing_action | 5 | 12 | 0 | 3 | 0 | 0 | 5 | 15 | 0.2941 | 1.0000 | 0.4545 | 1.0000 |
| sun | incorrect_actor | 1 | 2 | 4 | 0 | 4 | 8 | 5 | 10 | 0.3333 | 0.2000 | 0.2500 | 0.4667 |
| sun | out_of_order | 0 | 0 | 5 | 0 | 5 | 10 | 5 | 10 | null | 0.0000 | 0.0000 | 0.3333 |
| sun | OVERALL | 6 | 14 | 9 | 3 | 9 | 18 | 15 | 35 | 0.3000 | 0.4000 | 0.3429 | 0.6400 |
| ours | missing_action | 0 | 0 | 5 | 0 | 5 | 15 | 5 | 15 | null | 0.0000 | 0.0000 | 0.2500 |
| ours | incorrect_actor | 0 | 0 | 5 | 0 | 5 | 10 | 5 | 10 | null | 0.0000 | 0.0000 | 0.3333 |
| ours | out_of_order | 0 | 0 | 5 | 0 | 5 | 10 | 5 | 10 | null | 0.0000 | 0.0000 | 0.3333 |
| ours | OVERALL | 0 | 0 | 15 | 0 | 15 | 35 | 15 | 35 | null | 0.0000 | 0.0000 | 0.3000 |
| winter | missing_action | 3 | 6 | 2 | 9 | 0 | 0 | 5 | 15 | 0.3333 | 0.6000 | 0.4286 | 1.0000 |
| winter | incorrect_actor | 0 | 0 | 5 | 10 | 0 | 0 | 5 | 10 | null | 0.0000 | 0.0000 | 1.0000 |
| winter | out_of_order | 0 | 0 | 5 | 0 | 5 | 10 | 5 | 10 | null | 0.0000 | 0.0000 | 0.3333 |
| winter | OVERALL | 3 | 6 | 12 | 19 | 5 | 10 | 15 | 35 | 0.3333 | 0.2000 | 0.2500 | 0.8000 |

## Method status

- sun: available; overall F1=0.3429
- ours: blocked_missing_d1_predictions; overall F1=0.0000
- winter: available_native; overall F1=0.2500

## Diagnostics

- acceptance: `needs_method_review`
- flag: `sun/out_of_order: extreme_f1=0.0`
- flag: `sun/out_of_order: constant_prediction=unknown`
- flag: `sun/out_of_order: all_denominators_zero`
- flag: `ours/missing_action: extreme_f1=0.0`
- flag: `ours/incorrect_actor: extreme_f1=0.0`
- flag: `ours/out_of_order: extreme_f1=0.0`
- flag: `ours: overall_extreme_f1=0.0`
- flag: `ours: blocked_status=blocked_missing_d1_predictions`
- flag: `ours/missing_action: constant_prediction=unknown`
- flag: `ours/missing_action: all_denominators_zero`
- flag: `ours/incorrect_actor: constant_prediction=unknown`
- flag: `ours/incorrect_actor: all_denominators_zero`
- flag: `ours/out_of_order: constant_prediction=unknown`
- flag: `ours/out_of_order: all_denominators_zero`
- flag: `winter/incorrect_actor: extreme_f1=0.0`
- flag: `winter/out_of_order: extreme_f1=0.0`
- flag: `winter/incorrect_actor: constant_prediction=satisfied`
- flag: `winter/out_of_order: constant_prediction=unknown`
- flag: `winter/out_of_order: all_denominators_zero`
