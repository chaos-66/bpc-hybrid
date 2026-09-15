# SEP-C2 Stage 2B: Winter Predecessor Baseline (EStG-150)

- status: **completed_zero_api_predecessor_clause_region_run**
- input: `data/input/estg150_formal_inference_input_v2.json` (150 records)
- Gold: `data/gold/stage2/estg150_formal_gold_v1.json` (231 clause regions)
- task: **clause-region detection only** (`estg150_clause_region_detection_v1`)
- metric: global statement-level any-non-empty-character-intersection P/R/F1
- new LLM/API calls: **0**; historical Rules-Only / Direct-LLM predictions reused read-only

## Results

| method | Gold | Pred | matched GT | P | R | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Winter et al. (2020) native clause regions | 231 | 389 | 192 | 1.0000 | 0.8312 | 0.9078 |
| Rules-Only (historical B0 formal arm) | 231 | 249 | 231 | 0.9398 | 1.0000 | 0.9689 |
| Direct-LLM (historical D1 formal arm) | 231 | 229 | 225 | 0.9476 | 0.9740 | 0.9606 |

## Native Winter output retained separately

- sentences: 287
- signal-word constraint sentences: 163
- native obligation clauses: 389
- native flows: 9
- parse failures: 0
- unsupported as extraction: actor, action, condition, constraint, exception, modality, six_element_extraction

## Real cases (not synthetic)

### Winter et al. (2020) native clause regions

- full-region-match samples: 119/150
- records with >=1 matched Gold region: 129/150
- complete-miss samples: 21
- zero-prediction samples: 21
- success example: {'sample_id': 'estg_000056', 'gold_regions': 4, 'predicted_regions': 10, 'matched_predictions': 10, 'matched_ground_truth': 4, 'ground_truth_regions': 4, 'precision': 1.0, 'recall': 1.0, 'f1': 1.0}
- failure example: {'sample_id': 'estg_000071', 'gold_regions': 3, 'predicted_regions': 0, 'matched_predictions': 0, 'matched_ground_truth': 0, 'ground_truth_regions': 3, 'precision': 0.0, 'recall': 0.0, 'f1': 0.0}

### Rules-Only (historical B0 formal arm)

- full-region-match samples: 143/150
- records with >=1 matched Gold region: 150/150
- complete-miss samples: 0
- zero-prediction samples: 0
- success example: {'sample_id': 'estg_000800', 'gold_regions': 6, 'predicted_regions': 6, 'matched_predictions': 6, 'matched_ground_truth': 6, 'ground_truth_regions': 6, 'precision': 1.0, 'recall': 1.0, 'f1': 1.0}

### Direct-LLM (historical D1 formal arm)

- full-region-match samples: 139/150
- records with >=1 matched Gold region: 149/150
- complete-miss samples: 1
- zero-prediction samples: 1
- success example: {'sample_id': 'estg_000800', 'gold_regions': 6, 'predicted_regions': 6, 'matched_predictions': 6, 'matched_ground_truth': 6, 'ground_truth_regions': 6, 'precision': 1.0, 'recall': 1.0, 'f1': 1.0}
- failure example: {'sample_id': 'estg_000112', 'gold_regions': 1, 'predicted_regions': 0, 'matched_predictions': 0, 'matched_ground_truth': 0, 'ground_truth_regions': 1, 'precision': 0.0, 'recall': 0.0, 'f1': 0.0}

## Boundary

This is a zero-API first predecessor-baseline result on the frozen EStG-150 Stage 2 corpus. Winter is evaluated only on the adapted clause-region subtask; its native match/cost task on proprietary BPMN models is not reproduced. Rules-Only and Direct-LLM numbers are historical capsules reused read-only, not new calls. Sun's published Table 12 cannot be compared directly to this task.
