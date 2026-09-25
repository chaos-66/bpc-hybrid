# Stage 3 Table 3 R1 (scoped GDPR checking)

Reference is AI-constructed (`is_gold=false`, `human_adjudicated=false`). Metrics are given applicable-scope checking, not full GDPR end-to-end F1.

Coverage = `(cells - unknown_positive - unknown_negative) / cells`; positive unknowns remain FN, negative unknowns are not TN.

## Primary comparison

| Method | Missing-F1 | Actor-F1 | Order-F1 | Overall-P | Overall-R | Overall-F1 | Coverage | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| sun | 0.5333 | 0.4706 | 0.0000 | 0.3636 | 0.5333 | 0.4324 | 0.6400 | available |
| ours | 0.5263 | 0.3636 | 0.0000 | 0.3500 | 0.4667 | 0.4000 | 0.5200 | available |
| winter | 0.4286 | 0.8889 | 0.0000 | 0.5385 | 0.4667 | 0.5000 | 0.7000 | available_native |

## Per-type counts and unknown

| Method | Type | TP | FP | FN | TN | Unknown-positive | Unknown-negative | N/A | P | R | F1 | Coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sun | missing_action | 4 | 6 | 1 | 9 | 0 | 0 | 0 | 0.4000 | 0.8000 | 0.5333 | 1.0000 |
| sun | incorrect_actor | 4 | 8 | 1 | 0 | 1 | 2 | 5 | 0.3333 | 0.8000 | 0.4706 | 0.8000 |
| sun | out_of_order | 0 | 0 | 5 | 0 | 5 | 10 | 5 | null | 0.0000 | 0.0000 | 0.0000 |
| sun | OVERALL | 8 | 14 | 7 | 9 | 6 | 12 | 10 | 0.3636 | 0.5333 | 0.4324 | 0.6400 |
| ours | missing_action | 5 | 9 | 0 | 6 | 0 | 0 | 0 | 0.3571 | 1.0000 | 0.5263 | 1.0000 |
| ours | incorrect_actor | 2 | 4 | 3 | 0 | 3 | 6 | 5 | 0.3333 | 0.4000 | 0.3636 | 0.4000 |
| ours | out_of_order | 0 | 0 | 5 | 0 | 5 | 10 | 5 | null | 0.0000 | 0.0000 | 0.0000 |
| ours | OVERALL | 7 | 13 | 8 | 6 | 8 | 16 | 10 | 0.3500 | 0.4667 | 0.4000 | 0.5200 |
| winter | missing_action | 3 | 6 | 2 | 9 | 0 | 0 | 0 | 0.3333 | 0.6000 | 0.4286 | 1.0000 |
| winter | incorrect_actor | 4 | 0 | 1 | 10 | 0 | 0 | 5 | 1.0000 | 0.8000 | 0.8889 | 1.0000 |
| winter | out_of_order | 0 | 0 | 5 | 0 | 5 | 10 | 5 | null | 0.0000 | 0.0000 | 0.0000 |
| winter | OVERALL | 7 | 6 | 8 | 19 | 5 | 10 | 10 | 0.5385 | 0.4667 | 0.5000 | 0.7000 |

## Method status

- sun: available; overall F1=0.4324
- ours: available; overall F1=0.4000
- winter: available_native; overall F1=0.5000

## Diagnostics

- acceptance: `needs_method_review`
- flag: `sun/out_of_order: extreme_f1=0.0`
- flag: `sun/out_of_order: constant_prediction=unknown`
- flag: `sun/out_of_order: all_denominators_zero`
- flag: `ours/out_of_order: extreme_f1=0.0`
- flag: `ours/out_of_order: constant_prediction=unknown`
- flag: `ours/out_of_order: all_denominators_zero`
- flag: `winter/out_of_order: extreme_f1=0.0`
- flag: `winter/out_of_order: constant_prediction=unknown`
- flag: `winter/out_of_order: all_denominators_zero`

## R2 exact ID-set check

- case IDs equal frozen inference_view: `['case_06bacb820524', 'case_0adc59ea1a26', 'case_0f7180438501', 'case_3d2aaae29b37', 'case_44fc51ad7da0', 'case_5c2cca2ca4cf', 'case_7dc164f81677', 'case_89c44a45c04d', 'case_8cbb7ad90a6d', 'case_92fe183843b7', 'case_9a62a7fd9853', 'case_aa37540e7989', 'case_bbe530084075', 'case_c4d9054721a1', 'case_d038f52f8cf3', 'case_d8a82d59687d', 'case_f65436fd6574', 'case_f8aaa652c17b', 'case_fb254253b6dd', 'case_fd4b197b953b']`
- rule IDs equal frozen input set: `['article13p3', 'article14p4', 'article18p3', 'article35p1', 'article36p1']`

## R2 order failure categories

| Method | Category | Count |
|---|---|---:|
| sun | no_rule_order_endpoints | 100 |
| ours | no_rule_order_endpoints | 100 |
| winter | no_rule_order_relation | 100 |
