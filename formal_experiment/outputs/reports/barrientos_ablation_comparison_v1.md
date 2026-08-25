# Barrientos Ablation Comparison v1 (zero API)

## Experiment A: Direct-LLM validation chain (locked D1-R3)
| condition | overall F1 | action F1 |
| full | 0.7756 | 0.8800 |
| schema_only | 0.7733 | 0.8705 |
| raw_approximation | 0.7733 | 0.8705 |

canonicalizer: reanchored=126 degraded=23 unchanged=1; spans re-anchored=966; dropped spans=42 edges=18; samples changed=149/150

## Experiment B: Rules-Only module removal (same 150/Gold/evaluator)
| flag | overall F1 | delta | label acc |
| full | 0.7186 | — | 0.7316 |
| no_lexicon_extensions | 0.7120 | -0.0066 | 0.7316 |
| no_modality_classifier | 0.7186 | +0.0000 | 0.6797 |
| no_actor_action_ownership | 0.7186 | +0.0000 | 0.7316 |
| no_multi_match_guard | 0.7239 | +0.0053 | 0.7316 |
| no_de_en_alignment_validation | 0.7186 | +0.0000 | 0.7316 |

## Experiment C: 4-class vs 3-class modality
4-class: {'definition': 39, 'obligation': 97, 'permission': 62, 'prohibition': 33}; 3-class: {'obligation': 97, 'permission': 62, 'prohibition': 33}; definition excluded=39 (16.88%)

## Experiment D/E: prepared, not executed (zero API)
nonempty requirements = 38; status = {'D_full_v6_6shot': 'reuse_locked_formal_result', 'D_no_fewshot': 'prepared_not_executed_no_api', 'D_barrientos_style': 'prepared_not_executed_no_api', 'D_minimal_prompt': 'prepared_not_executed_no_api', 'E_arms': 'prepared_not_executed_no_api'}
