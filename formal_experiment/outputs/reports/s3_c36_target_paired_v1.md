# S3-C36-TARGET-PAIRED (development-only, zero API)

冻结 C36/Winter 原始预测与当前 v5 预测在**同一 target-paired 口径**下的比较。
C36 control 侧没有持久化布尔 `violation`，本比较使用项目冻结函数
`stage3_extended_violations.control_prediction_from_scores` 从已保存的 per-check
`observable/score/reason/exact_contradiction` 字段重建，未使用任何统一单标签预测，
也未使用 Gold/expected label 生成预测。

## Compatibility audit

- C36 item ids equal panel: **True**
- label/process/BPMN hash issues: **0/0/0/0**
- variant field gaps: **0**
- control reconstruction: **stage3_extended_violations.control_prediction_from_scores(control_scores, gamma_ext)**
- can build target-paired comparison: **True**

## Target-paired comparison

| Method | Macro-F1 | Pair success | Unknown rate | Control target FP rate |
|---|---|---|---|---|
| C36/Winter (control reconstructed) | 0.6036 | 18/40 = 0.4500 | 0.3625 | 0.0750 |
| Current v5 deterministic | 0.6737 | 21/40 = 0.5250 | 0.3375 | 0.0250 |

## Per-type checks

| Type | C36 F1 | v5 F1 | C36 variant TP/FNobs/FNunk | v5 variant TP/FNobs/FNunk | C36 control TN/FP/unknown | v5 control TN/FP/unknown |
|---|---|---|---|---|---|---|
| prohibited_action_present | 0.8696 | 1.0000 | 10/0/0 | 10/0/0 | 7/3/0 | 8/0/2 |
| required_condition_not_enforced | 0.3333 | 0.9000 | 2/0/8 | 9/0/1 | 6/0/4 | 9/1/0 |
| constraint_violated | 0.7500 | 0.3333 | 6/0/4 | 2/0/8 | 6/0/4 | 2/0/8 |
| exception_not_handled | 0.4615 | 0.4615 | 3/1/6 | 3/0/7 | 7/0/3 | 9/0/1 |

## Boundary

- Panel: development-only synthetic controlled panel `synthetic_controlled_error_extension_v2`.
- Same 40 variant/control pairs and same frozen rule/process inputs (manifest input hashes match).
- C36 variant checks are explicit in `scores_detail`; C36 control checks are reconstructed by the frozen project rule.
- No Gold, historical prediction, or existing artifact was modified; real API calls = 0.
