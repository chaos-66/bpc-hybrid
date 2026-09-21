# GDPR Stage-2 -> Stage-3 linkage v1 (original three violation types) — arm `direct_llm` (development-only)

- Arm rule-record source: EXTERNAL Direct-LLM Stage-2 capsule (locked D1 recipe) via deterministic converter
- Scored: 33 violation items (v001..v033) from the frozen inference pack; loaded matching items: 25; 33-item violation Gold is read ONLY after predictions were fixed.
- Frozen Sun-style thresholds: tau/gamma/theta = tau=0.8, gamma=0.8, theta=0.8

## Per-type P/R/F1 (primary denominator keeps every item)

| type | support | precision | recall | F1 |
|---|---:|---:|---:|---:|
| missing_action | 11 | 1.0000 | 0.9091 | 0.9524 |
| incorrect_actor | 11 | 0.0000 | 0.0000 | 0.0000 |
| out_of_order | 11 | 0.0000 | 0.0000 | 0.0000 |

- macro-F1 = 0.3175  ·  micro-F1 = 0.4651  ·  exact type accuracy = 0.3030  (detected 10 / missed 23 / wrong-type 0)
- unobservable = 11 (by reason: {'action_mapping_below_gamma': 8, 'external_stage2_failure:stage2_empty_envelope:gdpr_article6_s010': 1, 'incomplete_rule_actor_action_map': 2})
- observable-only diagnostic macro-F1 = 0.3175 (NOT the primary metric)

## External Stage-2 accounting

- capsule records: 74; envelopes ok 73 / failed 1; failure reasons {'stage2_empty_envelope:gdpr_article6_s010': 1}; invalid spans 14.
- order relations absent in capsule for rules: ['article15', 'article16', 'article17', 'article20', 'article22', 'article33', 'article34', 'article6', 'article7'] (Definition-7 input unavailable by contract; never fabricated).
- capsule integrity: schema gdpr7_direct_llm_predictions@1.0.0 == expected gdpr7_direct_llm_predictions@1.0.0; rows 74/74 all ok; unique samples 74.
- item-level failure rows: 3 (v010, v011, v012).

## Per-sample changes vs the reference arm (machine-classified)

- same verdict 0 / changed 33 / total 33.
- machine reason counts: {'order_relations_missing': 29, 'other': 3, 'action_mapping_below_gamma': 1}.
- Item details (before/after + reason) in `changes_vs_reference.json` inside the run dir.

## Boundaries

- DEV_ONLY linkage on the frozen 33-item human-adjudicated violation Gold (original three types). The 4-type synthetic panel and the formal Oracle are separate datasets and are never merged here.
- External Direct-LLM capsule = locked D1 recipe, real authorized executor output promoted to data/predictions/gdpr7_direct_llm_v1 by promote_gdpr7_direct_llm_arm_v1.py; coordinate-only rows, no raw text and no Gold fields (containment-scanned).
- Out-of-order in the reference arm is also denominator-0 for all items (no rule endpoint maps to a process action above gamma 0.8); in the rules_only arm the capsule provides no order relations at all.
- Item-level rows: predictions.jsonl; per-item evaluation detail in evaluation.json (items).
