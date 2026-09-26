# Stage 3 BONUS Development: Missing-Action Root-Cause Analysis v1

- Status: `BONUS_DEVELOPMENT_ANALYSIS_NOT_PAPER_FACING`
- `ALL_EXISTING_CASES_SEEN = true`
- `FINAL_TEST_ELIGIBLE = false`
- `REAL_LLM_API_CALLS = 0`
- Frozen gamma: `0.55`; source signals: frozen final-development signals.

## Confusion Matrix

| Method | TP | FP | FN | TN | Unknown negative | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sun | 23 | 45 | 10 | 26 | 9 | 0.3382 | 0.6970 | 0.4554 |
| Ours | 19 | 25 | 14 | 55 | 0 | 0.4318 | 0.5758 | 0.4935 |

## Failure Category Counts

`Action-level` counts count each failing denominator action occurrence; `primary-cell` assigns each FP/FN cell to one primary category.

| Failure category | Sun action-level | Sun primary-cell | Ours action-level | Ours primary-cell |
|---|---:|---:|---:|---:|
| M10_STAGE2_MISSING_ACTION | 4 | 4 | 0 | 0 |
| M1_REQUIRED_ACTION_MAPPING_FAILURE | 31 | 31 | 15 | 15 |
| M2_EXTRA_FRAGMENT_ACTION | 4 | 4 | 5 | 5 |
| M3_CONDITION_ACTION_IN_DENOMINATOR | 6 | 6 | 0 | 0 |
| M7_SUBORDINATE_NON_OBLIGATION_ACTION | 0 | 0 | 9 | 5 |
| M9_BPMN_LABEL_SEMANTIC_MISMATCH | 11 | 10 | 14 | 14 |

## Root-Cause Quantification

- FP total: `70`
- Mapping-related FP cells: `50`
- Broad scope-related FP cells (including fragments): `20`
- Gate-eligible scope FP cells (condition/constraint/exception/context/subordinate non-obligation): `11`
- Stage-2 extraction-related FN cells: `4`
- Key answer: Missing-action errors are dominated by action-mapping/label-semantic failures, not by a clean removable scope action. Strict gate-listed non-mandatory/condition/constraint/exception/context/subordinate FP evidence is below 30%.

## Action-Scope Gate

- Gate threshold: `0.30`
- Gate-eligible scope ratio: `0.1571`
- Broad scope ratio: `0.2857`
- Decision: `REJECTED`
- Reason: Even under the broad fragment-inclusive count, the strict gate-listed scope categories are far below 30% of Missing FP; the dominant errors are required-action mapping and BPMN-label semantic mismatch.

## FP/FN Evidence Ledger

The complete per-cell evidence ledger is in `stage3_bonus_missing_analysis_v1.json`.
