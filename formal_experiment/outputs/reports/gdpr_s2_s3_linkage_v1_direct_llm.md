# GDPR Stage-2 → Stage-3 linkage v1 — arm `direct_llm` (development-only)

- Stage-2 arm: Direct-LLM (locked D1 recipe, English sentences)
- Stage-2 input: `data\input\gdpr7_stage2_input_v1.json` (sha256 558b80131394…)
- Arm predictions: `data\predictions\gdpr7_direct_llm_v1\predictions.json` (sha256 b625692d1e4e…)
- Fixed Stage 1/3: frozen panel BPMN copies + frozen structural contract + the original panel runner's four backends, scorer formulas, gamma_ext 0.5 and per-method action gammas (winter=0.4, sun=0.8, bm25=0.5, tfidf_svd=0.5).
- Substitution: per-variant six-element sentence records come ONLY from the external Stage-2 predictions (first-valid-span projection); failures are counted, never back-filled with the locked reference extraction.

## Variant-only detection (40 synthetic variants) and paired control+variant (80 objects)

| method | variant macro-F1 | variant exact | unobservable | 5-class acc (80) | control FP rate (40) | paired acc (40) |
|---|---:|---:|---:|---:|---:|---:|
| winter | 0.462 | 0.325 | 24 | 0.300 | 0.350 | 0.125 |
| sun | 0.167 | 0.125 | 32 | 0.175 | 0.075 | 0.075 |
| bm25 | 0.083 | 0.050 | 32 | 0.175 | 0.000 | 0.050 |
| tfidf_svd | 0.351 | 0.275 | 27 | 0.312 | 0.275 | 0.250 |

### Per-type variant-only P/R/F1

| method | prohibited | condition | constraint | exception |
|---|---:|---:|---:|---:|
| winter | 1.000/0.500/0.667 | 1.000/0.100/0.182 | 1.000/0.500/0.667 | 1.000/0.200/0.333 |
| sun | 1.000/0.500/0.667 | 0.000/0.000/0.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| bm25 | 1.000/0.200/0.333 | 0.000/0.000/0.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| tfidf_svd | 1.000/0.800/0.889 | 0.000/0.000/0.000 | 1.000/0.200/0.333 | 1.000/0.100/0.182 |

## Substitution changes vs reference deterministic extraction

| method | same | changed | total |
|---|---:|---:|---:|
| winter | 31 | 9 | 40 |
| sun | 33 | 7 | 40 |
| bm25 | 36 | 4 | 40 |
| tfidf_svd | 36 | 4 | 40 |

Per-item change details (reference prediction → arm prediction, observability reasons) are in each method's `substitution_changes.json`; per-sample rows in `predictions.jsonl`.

## Stage-2 projection accounting

- winter: failed projections 0 (none); empty-action sentences 0; empty-modality sentences 0; invalid predicted spans 0.
- sun: failed projections 0 (none); empty-action sentences 0; empty-modality sentences 0; invalid predicted spans 0.
- bm25: failed projections 0 (none); empty-action sentences 0; empty-modality sentences 0; invalid predicted spans 0.
- tfidf_svd: failed projections 0 (none); empty-action sentences 0; empty-modality sentences 0; invalid predicted spans 0.

## Boundaries

- DEV_ONLY controlled synthetic panel (40 variants + 40 controls); NOT human Gold, NOT the formal Oracle; never merged with the 33-item human Gold.
- Direct-LLM rows come from the promoted formal arm capsule data/predictions/gdpr7_direct_llm_v1 (real authorized executor output; coordinate-only, containment-scanned).
- Zero LLM/API/network; frozen BPMN, thresholds and panel bytes unchanged.
