# SEP-C3 Definition Full-150 Confirmation Analysis

- Suite: `SEP-C3-DEFINITION-FULL150-CONFIRMATION-001`
- Scope: **full-corpus confirmation; not independent held-out generalization test**
- API calls in this analysis: **0**
- A: historical frozen raw responses rescored under current contract
- R_DEF: exactly 150 new calls, retry=0

## Official Stage-2 metrics

| Metric | A_current_contract | R_DEF | Delta (R_DEF - A) |
|---|---:|---:|---:|
| coarse_five_field_mean_f1 | 0.708095 | 0.724661 | 0.016566 |
| coarse_five_field_micro_f1 | 0.768015 | 0.759664 | -0.008351 |
| modality_label_accuracy | 0.746667 | 0.806667 | 0.060000 |
| modality_label_macro_f1 | 0.713389 | 0.822410 | 0.109021 |

## Per-field official metrics

| Field | A F1 | R_DEF F1 | Delta F1 | A P | R_DEF P | A R | R_DEF R |
|---|---:|---:|---:|---:|---:|---:|---:|
| actor | 0.623895 | 0.631520 | 0.007625 | 0.476744 | 0.530303 | 0.902439 | 0.780488 |
| action | 0.877821 | 0.861066 | -0.016755 | 0.896396 | 0.849138 | 0.860000 | 0.873333 |
| condition | 0.810063 | 0.802000 | -0.008063 | 0.875000 | 0.878571 | 0.754098 | 0.737705 |
| constraint | 0.640462 | 0.622839 | -0.017622 | 0.837398 | 0.815789 | 0.518519 | 0.503704 |
| exception | 0.588235 | 0.705882 | 0.117647 | 0.833333 | 1.000000 | 0.454545 | 0.545455 |

## Definition-specific diagnostics (full 150 gold clauses)

| Metric | A_current_contract | R_DEF | Delta (R_DEF - A) |
|---|---:|---:|---:|
| Definition precision | 0.923077 | 0.750000 | -0.173077 |
| Definition recall | 0.307692 | 0.692308 | 0.384615 |
| Definition F1 | 0.461538 | 0.720000 | 0.258462 |
| Definition -> obligation count | 17.000000 | 4.000000 | -13.000000 |
| Obligation -> definition count | 1.000000 | 6.000000 | 5.000000 |
| Prohibition -> definition count | 0.000000 | 0.000000 | 0.000000 |
| Permission -> definition count | 0.000000 | 3.000000 | 3.000000 |
| Definition action-presence fraction | 0.692308 | 0.923077 | 0.230769 |
| Definition empty-action count | 12.000000 | 3.000000 | -9.000000 |
| Non-definition false-definition rate | 0.005208 | 0.046875 | 0.041667 |

## Side-effect diagnostics

| Diagnostic | A_current_contract | R_DEF |
|---|---:|---:|
| Request/API status ok | 138 | 136 |
| Output parse passed | 150 | 150 |
| Input binding passed | 148 | 147 |
| Canonical validation passed | 138 | 136 |
| Canonical validation failed | 10 | 11 |
| Transport/provider failures | 0 | 0 |
| Structural failure count | 12 | 14 |

## A -> R_DEF field change counts

| Field | Samples changed | Rate |
|---|---:|---:|
| actor | 31 | 0.206667 |
| action | 85 | 0.566667 |
| condition | 28 | 0.186667 |
| constraint | 47 | 0.313333 |
| exception | 4 | 0.026667 |

## Paired bootstrap (10,000 resamples over the same 150 samples)

| Metric | Observed delta | 95% percentile CI | Contains zero |
|---|---:|---:|---:|
| coarse_five_field_mean_f1 | 0.016566 | [-0.048932, 0.091347] | True |
| coarse_five_field_micro_f1 | -0.008351 | [-0.042541, 0.026717] | True |
| actor_f1 | 0.007625 | [-0.070012, 0.088090] | True |
| action_f1 | -0.016755 | [-0.068703, 0.035789] | True |
| condition_f1 | -0.008063 | [-0.049408, 0.032635] | True |
| constraint_f1 | -0.017622 | [-0.084134, 0.049196] | True |
| exception_f1 | 0.117647 | [-0.166667, 0.436097] | True |
| clause_modality_accuracy | -0.004329 | [-0.076596, 0.065502] | True |
| clause_definition_precision | -0.173077 | [-0.333333, 0.000000] | True |
| clause_definition_recall | 0.384615 | [0.200000, 0.574468] | False |
| clause_definition_f1 | 0.258462 | [0.095062, 0.447828] | False |
| clause_definition_action_presence_fraction | 0.230769 | [0.071429, 0.390244] | False |
| clause_non_definition_false_definition_rate | 0.041667 | [0.014851, 0.075474] | False |

Targeted A->BASE and BASE->R_DEF evidence decomposes the mechanism; the full-150 A->R_DEF evaluation estimates the effect of the final frozen package. The full-150 evaluation does not independently establish generalization because the targeted development samples are contained within EStG-150. It is described as a full-corpus confirmation or full-set evaluation.

The bootstrap intervals describe sample-composition uncertainty only; they are not a binary significance rule.
