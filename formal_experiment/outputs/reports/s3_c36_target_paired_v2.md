# S3-C36-TARGET-PAIRED v2 (gated, development-only, zero API)

Baseline: **Winter-style four-type extension baseline**.  This is not a direct Winter paper result.
兼容性检查通过后才生成比较；control 侧布尔值已持久化在 80 条检查记录中，
不需要再次写文件来产生独立证据。

## Compatibility gate

- Gate status: **pass**
- Blocking issues: **0**
- Reconstruction dependency verified frozen match: **True**
- Dependency verification basis: `canonical_lf_utf8_text hash match`
- Frozen gamma_ext: **0.5**

## Target-paired comparison

| Method | Macro-F1 | Pair success | Target unknown | Control target FP |
|---|---:|---:|---:|---:|
| Winter-style four-type extension baseline | 0.6036 | 18/40 | 0.3625 | 0.0750 |
| Current v5 deterministic | 0.6737 | 21/40 | 0.3375 | 0.0250 |

## Per-type checks

| Type | Baseline F1 | v5 F1 | Baseline variant TP/FNobs/FNunk | v5 variant TP/FNobs/FNunk | Baseline control TN/FP/unknown | v5 control TN/FP/unknown |
|---|---:|---:|---|---|---|---|
| prohibited_action_present | 0.8696 | 1.0000 | 10/0/0 | 10/0/0 | 7/3/0 | 8/0/2 |
| required_condition_not_enforced | 0.3333 | 0.9000 | 2/0/8 | 9/0/1 | 6/0/4 | 9/1/0 |
| constraint_violated | 0.7500 | 0.3333 | 6/0/4 | 2/0/8 | 6/0/4 | 2/0/8 |
| exception_not_handled | 0.4615 | 0.4615 | 3/1/6 | 3/0/7 | 7/0/3 | 9/0/1 |

## Boundary

- Development-only synthetic controlled panel; not formal Oracle or human Gold.
- Expected labels are used only after fixed predictions for evaluation grouping.
- Control-side final booleans are reconstructed from the frozen C36 score fields; they are now persisted in the v2 80-row check artifact.
- No historical prediction, manifest or Gold was modified; real API calls = 0.
