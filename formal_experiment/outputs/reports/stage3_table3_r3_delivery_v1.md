# S3-TABLE3-R3-INTEGRATION delivery (M0/M1/M2)

Development/retrospective result. Reference is AI-constructed and is not formal Gold.

## Overall metrics

| Config | Method | P | R | F1 | Coverage | Unknown+ | Unknown- | N/A |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| M0_R2 | sun | 0.3 | 0.4 | 0.34285714285714286 | 0.46 | 9 | 18 | 10 |
| M0_R2 | ours | 0.3 | 0.4 | 0.34285714285714286 | 0.46 | 9 | 18 | 10 |
| M0_R2 | winter | 0.5384615384615384 | 0.4666666666666667 | 0.5 | 0.7 | 5 | 10 | 10 |
| M1_P2_v4_sm | sun | 0.36363636363636365 | 0.5333333333333333 | 0.43243243243243246 | 0.64 | 6 | 12 | 10 |
| M1_P2_v4_sm | ours | 0.35 | 0.4666666666666667 | 0.4 | 0.52 | 8 | 16 | 10 |
| M1_P2_v4_sm | winter | 0.5384615384615384 | 0.4666666666666667 | 0.5 | 0.7 | 5 | 10 | 10 |
| M2_P2_v4_lg | sun | None | None | None | None | None | None | None |
| M2_P2_v4_lg | ours | None | None | None | None | None | None | None |
| M2_P2_v4_lg | winter | None | None | None | None | None | None | None |

## Event-projection fix

- changed rule/method pairs: `3`
- predicate-bearing new rows: `2`

- article18p3/sun: old `[['be informed by the controller', 'the restriction of processing']]` -> new `[['be informed by the controller', 'the restriction of processing is lifted']]`; predicates `['lifted']`

## M1/M2 backend contrast

- status: `m2_not_run`; `{'m1_rows': 460, 'm2_rows': 0, 'changed_rows': 0}`

## Mechanism/development samples

- M1: `{'limitations_observed': 1, 'matching_cases': 6, 'matching_passed': 6, 'projection_cases': 8, 'projection_passed': 8, 'total_cases': 14, 'total_passed': 14}`
- M2: `None`

## Resolved

- Stage1 P2 activity semantics are now explicitly wired into Stage3 model-side action/object/actor views.
- Named events receive an independently documented R3 extension of the same frozen P2 label analysis.
- Order projection v4 preserves a unique local event predicate in the selected complement; article18p3 now retains 'is lifted' / 'lifted' rather than truncating to 'the restriction of processing'.
- Action/order mapping returns stable node IDs and resolves equal scores by ascending node ID while retaining all tied candidates.
- M1/M2 share parser, P2 views, projection, candidates, formulas, and thresholds; only the Sun/Ours similarity backend differs.

## Remaining

- Stage2 prediction errors remain: some canonical actions/actors are missing or fragmented before Stage3; R3 does not repair them.
- Frozen P2 limitations remain: e.g. some capitalized imperative labels lose their business object because the frozen verb-root resource does not contain the verb (observed limitation fixture).
- Similarity-threshold limitations remain: the fixed gamma=0.8 still rejects the article18p3 after-endpoint mapping even after predicate preservation, because the M1 sm best score is below gamma.
- Winter remains native with before/prior-to unsupported; its R2 result is reused and is not rerun.
- M2 is development-retrospective and cannot be reported as an independent test or as proof that lg is generally better.

## Artifacts

- wiring: `outputs/reports/stage3_table3_r3_wiring_evidence_v1.json`
- projection fix: `outputs/reports/stage3_table3_r3_projection_fix_v1.json`
- backend diff: `outputs/reports/stage3_table3_r3_backend_diff_v1.json`
