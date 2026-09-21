# GDPR Stage-2 → Stage-3 linkage v1 — arm `human_rules` (development-only)

- Stage-2 arm: human-adjudicated Gold Rule Records (Oracle standard answer; the projection keeps the first confirmed item per sentence)
- Stage-2 input: `data\input\gdpr7_stage2_input_v1.json` (sha256 558b80131394…)
- Arm predictions: `data\predictions\gdpr7_human_rule_record_v1\predictions.json` (sha256 9d86e1b4360a…)
- Fixed Stage 1/3: frozen panel BPMN copies + frozen structural contract + the original panel runner's four backends, scorer formulas, gamma_ext 0.5 and per-method action gammas (winter=0.4, sun=0.8, bm25=0.5, tfidf_svd=0.5).
- Substitution: per-variant six-element sentence records come ONLY from the external Stage-2 predictions (first-valid-span projection); failures are counted, never back-filled with the locked reference extraction.

## Variant-only detection (40 synthetic variants) and paired control+variant (80 objects)

| method | variant macro-F1 | variant exact | unobservable | 5-class acc (80) | control FP rate (40) | paired acc (40) |
|---|---:|---:|---:|---:|---:|---:|
| winter | 0.341 | 0.225 | 29 | 0.163 | 0.250 | 0.100 |
| sun | 0.045 | 0.025 | 37 | 0.050 | 0.000 | 0.025 |
| bm25 | 0.000 | 0.000 | 37 | 0.037 | 0.000 | 0.000 |
| tfidf_svd | 0.206 | 0.125 | 33 | 0.163 | 0.175 | 0.100 |

### Per-type variant-only P/R/F1

| method | prohibited | condition | constraint | exception |
|---|---:|---:|---:|---:|
| winter | 1.000/0.100/0.182 | 1.000/0.100/0.182 | 1.000/0.500/0.667 | 1.000/0.200/0.333 |
| sun | 1.000/0.100/0.182 | 0.000/0.000/0.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| bm25 | 0.000/0.000/0.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 | 0.000/0.000/0.000 |
| tfidf_svd | 1.000/0.300/0.462 | 0.000/0.000/0.000 | 1.000/0.100/0.182 | 1.000/0.100/0.182 |

## Substitution changes vs reference deterministic extraction

| method | same | changed | total |
|---|---:|---:|---:|
| winter | 27 | 13 | 40 |
| sun | 29 | 11 | 40 |
| bm25 | 34 | 6 | 40 |
| tfidf_svd | 30 | 10 | 40 |

Per-item change details (reference prediction → arm prediction, observability reasons) are in each method's `substitution_changes.json`; per-sample rows in `predictions.jsonl`.

## Stage-2 projection accounting

- winter: failed projections 0 (none); empty-action sentences 11; empty-modality sentences 0; invalid predicted spans 0.
- sun: failed projections 0 (none); empty-action sentences 11; empty-modality sentences 0; invalid predicted spans 0.
- bm25: failed projections 0 (none); empty-action sentences 11; empty-modality sentences 0; invalid predicted spans 0.
- tfidf_svd: failed projections 0 (none); empty-action sentences 11; empty-modality sentences 0; invalid predicted spans 0.

## Boundaries

- DEV_ONLY controlled synthetic panel (40 variants + 40 controls); NOT human Gold, NOT the formal Oracle; never merged with the 33-item human Gold.
- human_rules rows come from the formal GDPR-7 Gold Rule Records capsule (user-confirmed 74 sentences / 92 items). This panel uses the first-valid-span projection, so for a multi-item sentence only the first confirmed item reaches the backend; the multi-clause Oracle surface is reported separately in outputs/reports/s3_oracle_gold_rules_v1.json.
- Zero LLM/API/network; frozen BPMN, thresholds and panel bytes unchanged.
