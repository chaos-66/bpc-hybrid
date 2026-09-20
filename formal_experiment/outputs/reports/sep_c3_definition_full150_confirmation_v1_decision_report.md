# Final Decision Report - Frozen R_DEF Full-150 Confirmation

## 1. Does the targeted definition improvement remain visible on the complete 150-sample corpus?
- Definition F1: A=0.461538, R_DEF=0.720000; delta=0.258462.
- Definition recall: A=0.307692, R_DEF=0.692308.
- Definition action-presence fraction: A=0.692308, R_DEF=0.923077.
- The answer is visible on the full corpus only if the definition diagnostics and official modality metrics move in the expected direction; consult the table above.

## 2. Exact official aggregate A_current -> R_DEF change
- `coarse_five_field_mean_f1`: 0.708095 -> 0.724661; delta=0.016566.
- `coarse_five_field_micro_f1`: 0.768015 -> 0.759664; delta=-0.008351.

## 3. Fields that improve
- actor, exception.

## 4. Fields that regress
- action, condition, constraint.

## 5. Input-binding, canonical-validation, and structural failures
- Input binding failed: A=2, R_DEF=3.
- Canonical validation failed: A=10, R_DEF=11.
- Transport/provider failures: A=0, R_DEF=0.
- Structural failure count: A=12, R_DEF=14.

## 6. Final Stage-2 Prompt decision
DO NOT PROMOTE R_DEF AT THIS TIME: the full-150 full-corpus confirmation shows an aggregate regression, a definition-F1 regression, or an increase in structural failures. Historical A remains the final Stage-2 Prompt candidate pending separate stronger external evidence.

## Methodological statement
Targeted A->BASE and BASE->R_DEF evidence decomposes the mechanism; the full-150 A->R_DEF evaluation estimates the effect of the final frozen package. The full-150 evaluation does not independently establish generalization because the targeted development samples are contained within EStG-150. It is described as a full-corpus confirmation or full-set evaluation.

The historical legacy A score (`0.7245765762`) is separately labeled and is not directly compared with R_DEF. The comparable A baseline is the current-contract five-field mean F1 of `0.7080951816362215`.

This report does not launch BASE, R_DEF2, Stage 3, a new prompt, or any failure repair.
