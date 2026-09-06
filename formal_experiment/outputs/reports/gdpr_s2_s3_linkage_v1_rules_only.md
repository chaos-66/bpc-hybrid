# GDPR Stage-2 → Stage-3 linkage v1 — arm `rules_only` (development-only)

- Stage-2 arm: Rules-Only (locked B0 v10a, English pass-through)
- Stage-2 input: `data\input\gdpr7_stage2_input_v1.json` (sha256 558b80131394…)
- Arm predictions: `data\predictions\gdpr7_sun_rule_only_v1\predictions.json` (sha256 a993ef533489…)
- Fixed Stage 1/3: frozen panel BPMN copies + frozen structural contract + the original panel runner's four backends, scorer formulas, gamma_ext 0.5 and per-method action gammas (winter=0.4, sun=0.8, bm25=0.5, tfidf_svd=0.5).
- Substitution: per-variant six-element sentence records come ONLY from the external Stage-2 predictions (first-valid-span projection); failures are counted, never back-filled with the locked reference extraction.

## Variant-only detection (40 synthetic variants) and paired control+variant (80 objects)

| method | variant macro-F1 | variant exact | unobservable | 5-class acc (80) | control FP rate (40) | paired acc (40) |
|---|---:|---:|---:|---:|---:|---:|
| winter | 0.521 | 0.375 | 23 | 0.312 | 0.450 | 0.150 |
| sun | 0.188 | 0.150 | 32 | 0.200 | 0.050 | 0.150 |
| bm25 | 0.000 | 0.000 | 32 | 0.150 | 0.000 | 0.000 |
| tfidf_svd | 0.351 | 0.275 | 28 | 0.263 | 0.375 | 0.225 |

### Per-type variant-only P/R/F1

| method | prohibited | condition | constraint | exception |
|---|---:|---:|---:|---:|
| winter | 1.000/0.600/0.750 | 1.000/0.200/0.333 | 1.000/0.500/0.667 | 1.000/0.200/0.333 |
| sun | 1.000/0.600/0.750 | 0.000/0.000/0.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| bm25 | 0.000/0.000/0.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| tfidf_svd | 1.000/0.800/0.889 | 0.000/0.000/0.000 | 1.000/0.200/0.333 | 1.000/0.100/0.182 |

## Substitution changes vs reference deterministic extraction

| method | same | changed | total |
|---|---:|---:|---:|
| winter | 33 | 7 | 40 |
| sun | 34 | 6 | 40 |
| bm25 | 34 | 6 | 40 |
| tfidf_svd | 36 | 4 | 40 |

Per-item change details (reference prediction → arm prediction, observability reasons) are in each method's `substitution_changes.json`; per-sample rows in `predictions.jsonl`.

## Stage-2 projection accounting

- winter: failed projections 0 (none); empty-action sentences 0; empty-modality sentences 0; invalid predicted spans 0.
- sun: failed projections 0 (none); empty-action sentences 0; empty-modality sentences 0; invalid predicted spans 0.
- bm25: failed projections 0 (none); empty-action sentences 0; empty-modality sentences 0; invalid predicted spans 0.
- tfidf_svd: failed projections 0 (none); empty-action sentences 0; empty-modality sentences 0; invalid predicted spans 0.

## Boundaries

- DEV_ONLY controlled synthetic panel (40 variants + 40 controls); NOT human Gold, NOT the formal Oracle; never merged with the 33-item human Gold.
- Rules-Only modality labels come from the locked B0 v10a pipeline with the disclosed English pass-through (German classifier contract) — a descriptive Stage-2 arm.
- Zero LLM/API/network; frozen BPMN, thresholds and panel bytes unchanged.
