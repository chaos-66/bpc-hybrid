# Barrientos Ablation Comparison v2 (zero API)

## Experiment A (offline approximation sensitivity analysis)
| condition | overall F1 | note |
| full_locked | 0.7756 | persisted canonical records (locked); full chain |
| schema_only_approx | 0.7733 | first-occurrence anchoring, no deterministic unique-exact re-anchor (approximation; raw JSON not persisted) |
| raw_approx | 0.7733 | first-occurrence anchoring + drop unanchored spans as empty predictions (approximation; raw JSON not persisted) |

## Experiment B (Rules-Only module removal, structural metrics)
| flag | ΔF1 | label acc | label macro-F1 | map change | pred map validity |
| no_lexicon_extensions | -0.0066 | 0.7316 | 0.7001 | 12 | 1.0000 |
| no_modality_classifier | +0.0000 | 0.6797 | 0.5810 | 0 | 1.0000 |
| no_actor_action_ownership | +0.0000 | 0.7316 | 0.7001 | 12 | 1.0000 |
| no_multi_match_guard | +0.0053 | 0.7316 | 0.7001 | 0 | 1.0000 |
| no_de_en_alignment_validation | +0.0000 | 0.7316 | 0.7001 | 0 | 1.0000 |

## Experiment C
4-class: {'definition': 39, 'obligation': 97, 'permission': 62, 'prohibition': 33}; 3-class shared: {'obligation': 97, 'permission': 62, 'prohibition': 33}; definition excluded=39 (16.88%)

## Experiment D/E
status: ready_to_execute_not_executed
E contract v2: 36 unique records (sha 43aeeac51c49f5e9)
