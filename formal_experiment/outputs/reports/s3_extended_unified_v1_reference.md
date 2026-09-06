# S3.9-EXT unified five-class re-evaluation — source `reference`

- reference deterministic extraction (original S3.9-EXT run; NOT human Gold)
- decision: unified_five_class_decision_v1 (same rule on compliant controls and violation variants; unobservable -> skipped; all-unobservable -> None)
- old per-sample predictions preserved as `predicted_conditional_old` (labelled conditional detection for the preset type, NOT classification)
- reproduce: `python formal_experiment/scripts/reevaluate_s3_extended_unified_v1.py --source reference` (deterministic offline re-evaluation from persisted rows; per-method run dirs under outputs/development/s3_extended_unified_v1/reference/)

## Variant-only view (40 variants) — unified vs old-conditional

| method | macro (old/new) | exact (old/new) | wrong-type (old/new) | detected (old/new) | unobservable (old/new) |
|---|---:|---:|---:|---:|---:|
| winter | 0.655 / 0.499 | 0.550 / 0.450 | 0 / 9 | 22 / 18 | 17 / 17 |
| sun | 0.333 / 0.321 | 0.300 / 0.300 | 0 / 1 | 12 / 12 | 28 / 28 |
| bm25 | 0.226 / 0.226 | 0.150 / 0.150 | 0 / 0 | 6 / 6 | 28 / 28 |
| tfidf_svd | 0.379 / 0.375 | 0.325 / 0.325 | 0 / 1 | 13 / 13 | 27 / 27 |

## Paired view (40 compliant controls + 40 variants)

| method | 5-class acc (old/new) | variant exact (old/new) | control FP | paired acc (old/new) |
|---|---:|---:|---:|---:|
| winter | 0.425 / 0.375 | 0.550 / 0.450 | 0.500 | 0.225 / 0.225 |
| sun | 0.263 / 0.263 | 0.300 / 0.300 | 0.125 | 0.175 / 0.175 |
| bm25 | 0.250 / 0.250 | 0.150 / 0.150 | 0.000 | 0.100 / 0.100 |
| tfidf_svd | 0.338 / 0.338 | 0.325 / 0.325 | 0.275 | 0.300 / 0.300 |

## Per-class P/R/F1 (5 classes, unified)

| method | none | prohibited | condition | constraint | exception |
|---|---:|---:|---:|---:|---:|
| winter | 1.000/0.375/0.545 | 0.625/1.000/0.769 | 0.125/0.400/0.191 | 0.400/0.571/0.471 | 0.400/0.400/0.400 |
| sun | 1.000/0.643/0.783 | 0.625/1.000/0.769 | 0.000/0.000/0.000 | 1.000/1.000/1.000 | 0.000/0.000/0.000 |
| bm25 | 1.000/1.000/1.000 | 1.000/1.000/1.000 | 0.000/0.000/0.000 | 1.000/1.000/1.000 | 0.000/0.000/0.000 |
| tfidf_svd | 1.000/0.560/0.718 | 0.714/1.000/0.833 | 0.000/0.000/0.000 | 1.000/1.000/1.000 | 0.250/1.000/0.400 |

Predicted-None counts and variant unobservable reasons are in each method's `confusion_matrix.json`; per-sample unified predictions in `predictions.jsonl`.  Full JSON aggregate: `outputs/reports/s3_extended_unified_v1_reference.json`.

## Boundaries

- DEV_ONLY controlled synthetic panel; NOT human Gold; NOT the formal Oracle; never merged with the 33-item human Gold.
- Old conditional numbers are kept for comparison only and must be labelled accordingly (no P=1/no-wrong-type classification claims).
