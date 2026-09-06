# S3.9-EXT unified five-class re-evaluation — source `rules_only`

- external Stage-2 arm: Rules-Only (locked B0 v10a, English pass-through)
- decision: unified_five_class_decision_v1 (same rule on compliant controls and violation variants; unobservable -> skipped; all-unobservable -> None)
- old per-sample predictions preserved as `predicted_conditional_old` (labelled conditional detection for the preset type, NOT classification)
- reproduce: `python formal_experiment/scripts/reevaluate_s3_extended_unified_v1.py --source rules_only` (deterministic offline re-evaluation from persisted rows; per-method run dirs under outputs/development/s3_extended_unified_v1/rules_only/)

## Variant-only view (40 variants) — unified vs old-conditional

| method | macro (old/new) | exact (old/new) | wrong-type (old/new) | detected (old/new) | unobservable (old/new) |
|---|---:|---:|---:|---:|---:|
| winter | 0.521 / 0.331 | 0.375 / 0.275 | 0 / 10 | 15 / 11 | 23 / 23 |
| sun | 0.188 / 0.188 | 0.150 / 0.150 | 0 / 0 | 6 / 6 | 32 / 32 |
| bm25 | 0.000 / 0.000 | 0.000 / 0.000 | 0 / 0 | 0 / 0 | 32 / 32 |
| tfidf_svd | 0.351 / 0.332 | 0.275 / 0.275 | 0 / 6 | 11 / 11 | 28 / 28 |

## Paired view (40 compliant controls + 40 variants)

| method | 5-class acc (old/new) | variant exact (old/new) | control FP | paired acc (old/new) |
|---|---:|---:|---:|---:|
| winter | 0.312 / 0.263 | 0.375 / 0.275 | 0.450 | 0.150 / 0.150 |
| sun | 0.200 / 0.200 | 0.150 / 0.150 | 0.050 | 0.150 / 0.150 |
| bm25 | 0.150 / 0.150 | 0.000 / 0.000 | 0.000 | 0.000 / 0.000 |
| tfidf_svd | 0.263 / 0.263 | 0.275 / 0.275 | 0.375 | 0.225 / 0.225 |

## Per-class P/R/F1 (5 classes, unified)

| method | none | prohibited | condition | constraint | exception |
|---|---:|---:|---:|---:|---:|
| winter | 1.000/0.357/0.526 | 0.750/0.750/0.750 | 0.133/0.400/0.200 | 0.188/0.500/0.273 | 0.000/0.000/0.000 |
| sun | 1.000/0.833/0.909 | 0.750/1.000/0.857 | 0.000/0.000/0.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| bm25 | 1.000/1.000/1.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| tfidf_svd | 1.000/0.400/0.571 | 0.667/0.800/0.727 | 0.000/0.000/0.000 | 0.222/0.667/0.333 | 0.200/1.000/0.333 |

Predicted-None counts and variant unobservable reasons are in each method's `confusion_matrix.json`; per-sample unified predictions in `predictions.jsonl`.  Full JSON aggregate: `outputs/reports/s3_extended_unified_v1_rules_only.json`.

## Boundaries

- DEV_ONLY controlled synthetic panel; NOT human Gold; NOT the formal Oracle; never merged with the 33-item human Gold.
- Old conditional numbers are kept for comparison only and must be labelled accordingly (no P=1/no-wrong-type classification claims).
