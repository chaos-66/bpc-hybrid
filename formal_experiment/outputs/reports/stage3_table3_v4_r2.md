# Stage 3 Table 3 R1 (scoped GDPR checking)

Reference is AI-constructed (`is_gold=false`, `human_adjudicated=false`). Metrics are given applicable-scope checking, not full GDPR end-to-end F1.

Coverage = `(cells - unknown_positive - unknown_negative) / cells`; positive unknowns remain FN, negative unknowns are not TN.

## Primary comparison

| Method | Missing-F1 | Actor-F1 | Order-F1 | Overall-P | Overall-R | Overall-F1 | Coverage | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| sun | 0.4545 | 0.2500 | 0.0000 | 0.3000 | 0.4000 | 0.3429 | 0.4600 | available |
| ours | 0.4545 | 0.2500 | 0.0000 | 0.3000 | 0.4000 | 0.3429 | 0.4600 | available |
| winter | 0.4286 | 0.8889 | 0.0000 | 0.5385 | 0.4667 | 0.5000 | 0.7000 | available_native |

## Per-type counts and unknown

| Method | Type | TP | FP | FN | TN | Unknown-positive | Unknown-negative | N/A | P | R | F1 | Coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sun | missing_action | 5 | 12 | 0 | 3 | 0 | 0 | 0 | 0.2941 | 1.0000 | 0.4545 | 1.0000 |
| sun | incorrect_actor | 1 | 2 | 4 | 0 | 4 | 8 | 5 | 0.3333 | 0.2000 | 0.2500 | 0.2000 |
| sun | out_of_order | 0 | 0 | 5 | 0 | 5 | 10 | 5 | null | 0.0000 | 0.0000 | 0.0000 |
| sun | OVERALL | 6 | 14 | 9 | 3 | 9 | 18 | 10 | 0.3000 | 0.4000 | 0.3429 | 0.4600 |
| ours | missing_action | 5 | 12 | 0 | 3 | 0 | 0 | 0 | 0.2941 | 1.0000 | 0.4545 | 1.0000 |
| ours | incorrect_actor | 1 | 2 | 4 | 0 | 4 | 8 | 5 | 0.3333 | 0.2000 | 0.2500 | 0.2000 |
| ours | out_of_order | 0 | 0 | 5 | 0 | 5 | 10 | 5 | null | 0.0000 | 0.0000 | 0.0000 |
| ours | OVERALL | 6 | 14 | 9 | 3 | 9 | 18 | 10 | 0.3000 | 0.4000 | 0.3429 | 0.4600 |
| winter | missing_action | 3 | 6 | 2 | 9 | 0 | 0 | 0 | 0.3333 | 0.6000 | 0.4286 | 1.0000 |
| winter | incorrect_actor | 4 | 0 | 1 | 10 | 0 | 0 | 5 | 1.0000 | 0.8000 | 0.8889 | 1.0000 |
| winter | out_of_order | 0 | 0 | 5 | 0 | 5 | 10 | 5 | null | 0.0000 | 0.0000 | 0.0000 |
| winter | OVERALL | 7 | 6 | 8 | 19 | 5 | 10 | 10 | 0.5385 | 0.4667 | 0.5000 | 0.7000 |

## Method status

- sun: available; overall F1=0.3429
- ours: available; overall F1=0.3429
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
| sun | endpoint_similarity_below_gamma | 60 |
| sun | projection_rejected_range | 40 |
| ours | endpoint_similarity_below_gamma | 60 |
| ours | projection_rejected_syntax | 40 |
| winter | no_rule_order_relation | 100 |

