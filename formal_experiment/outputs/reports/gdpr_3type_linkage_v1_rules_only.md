# GDPR Stage-2 -> Stage-3 linkage v1 (original three violation types) — arm `rules_only` (development-only)

- Arm rule-record source: EXTERNAL Rules-Only Stage-2 capsule (locked B0 v10a) via deterministic converter
- Scored: 33 violation items (v001..v033) from the frozen inference pack; loaded matching items: 25; 33-item violation Gold is read ONLY after predictions were fixed.
- Frozen Sun-style thresholds: tau/gamma/theta = tau=0.8, gamma=0.8, theta=0.8

## Per-type P/R/F1 (primary denominator keeps every item)

| type | support | precision | recall | F1 |
|---|---:|---:|---:|---:|
| missing_action | 11 | 1.0000 | 1.0000 | 1.0000 |
| incorrect_actor | 11 | 0.0000 | 0.0000 | 0.0000 |
| out_of_order | 11 | 0.0000 | 0.0000 | 0.0000 |

- macro-F1 = 0.3333  ·  micro-F1 = 0.5000  ·  exact type accuracy = 0.3333  (detected 11 / missed 22 / wrong-type 0)
- unobservable = 11 (by reason: {'action_mapping_below_gamma': 9, 'empty_rule_actor_denominator': 2})
- observable-only diagnostic macro-F1 = 0.3333 (NOT the primary metric)

## External Stage-2 accounting

- capsule records: 74; envelopes ok 74 / failed 0; failure reasons none; invalid spans 0.
- order relations absent in capsule for rules: ['article15', 'article16', 'article17', 'article20', 'article22', 'article33', 'article34', 'article6', 'article7'] (Definition-7 input unavailable by contract; never fabricated).
- item-level failure rows: 0 (none).

## Boundaries

- DEV_ONLY linkage on the frozen 33-item human-adjudicated violation Gold (original three types). The 4-type synthetic panel and the formal Oracle are separate datasets and are never merged here.
- External Rules-Only capsule = locked B0 v10a pipeline (English pass-through, classifier German-language contract); zero LLM/API/network in this experiment.
- Out-of-order in the reference arm is also denominator-0 for all items (no rule endpoint maps to a process action above gamma 0.8); in the rules_only arm the capsule provides no order relations at all.
- Item-level rows: predictions.jsonl; per-item evaluation detail in evaluation.json (items).
