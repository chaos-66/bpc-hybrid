# SEP-C4 动作锚点消歧与证据作用范围最小离线修复候选 v1

本候选（`s3_semantic_grounding_v6`）只复用冻结 v2 predictions 中已保存的候选标签、相似度和词面覆盖度，以及 panel 中冻结 BPMN 流程输入；真实 API=0，未启动模型推理，未重算相似度。所有检查与最终 decision 均由新锚点重新计算，历史 v2/v5/C36 产物未被覆盖。

## 四类 target-paired 结果（40 对 / 80 条，分母完整）

| Type | V6 variant TP/FN_obs/FN_unknown | V6 control TN/FP/unknown | V6 F1 | V2 F1 | V5 F1 | Pair success |
|---|---|---|---:|---:|---:|---:|
| prohibited_action_present | 10/0/0 | 8/0/2 | 1.0 | 1.0 | 1.0 | 8/10 |
| required_condition_not_enforced | 9/0/1 | 9/1/0 | 0.9 | 0.9 | 0.9 | 8/10 |
| constraint_violated | 1/0/9 | 1/0/9 | 0.1818 | 0.3333 | 0.3333 | 1/10 |
| exception_not_handled | 7/0/3 | 3/0/7 | 0.8235 | 0.4615 | 0.4615 | 2/10 |

- V6 target-paired macro-F1: **0.7263**
- V2 baseline macro-F1: **0.6737**
- V6 pair success: **19/40** (0.475)
- V6 target-field unknown rate: **0.3875**
- V6 control target-field FP rate: **0.025**

## TP / unknown / control FP 变化

- prohibited_action_present: variant TP 10->10; lost []; gained []; variant unknown 0->0; control FP 0->0; control unknown 2->2
- required_condition_not_enforced: variant TP 9->9; lost []; gained []; variant unknown 1->1; control FP 1->1; control unknown 0->0
- constraint_violated: variant TP 2->1; lost ['syn_v2_constraint_violated_01:variant']; gained []; variant unknown 8->9; control FP 0->0; control unknown 8->9
- exception_not_handled: variant TP 3->7; lost []; gained ['syn_v2_exception_not_handled_04:variant', 'syn_v2_exception_not_handled_07:variant', 'syn_v2_exception_not_handled_08:variant', 'syn_v2_exception_not_handled_09:variant']; variant unknown 7->3; control FP 0->0; control unknown 1->7

## 逐条变化

- Changed rows: **22** / **80**
- Action-grounding status/id changes: **11**
- Action-grounding reason-only changes: **37**
- Check behavior changes by target: `{"constraint_violated": 6, "exception_not_handled": 12}`
- Check reason-only changes by target: `{"exception_not_handled": 6, "constraint_violated": 2}`

变化条目保留 before/after 的 action grounding、各检查 status/observable/violation/reason；完整列表在 `change_report.changed_rows`。

## 边界

- 唯一精确匹配仍优先；词面 winner 与 semantic winner 冲突时保留 ambiguous。
- 缺少 action/field 支持时 anchor 为 `unconfirmed`，不再写 `resolved_label_is_action_consistent`。
- resolved 时 constraint/exception 只从锚点动作和允许的局部结构取证据；ambiguous 时按候选逐一评估，非一致证据不做确定结论。
- 抽象约束仍为 unsupported/unknown；上游 action 抽取问题本轮不改。
- 这不是形式 Oracle，不要求 F1 上升；论文结论只能引用本 manifest 中已冻结的离线范围。

## 来源

- v2 predictions SHA-256: `b17b859465e6ee5ebbdefcfc7e4ecb93a5b4d58ada5baca6cfd9746e8bdd2092`
- panel SHA-256: `6a23adbdbc0d8930ff2a33411c52fed7fbbf581fdd101f830c29b2e3373e2e81`
- implementation: `{'module': 'src/bpc_hybrid/s3_semantic_grounding_v6.py', 'module_sha256': '48f3f675145387b3351e3566a524475869814d2b9c09100755cd813205882a44', 'runner': 'scripts/run_sep_c4_action_anchor_scope_v1.py', 'runner_sha256': '955fe0f7aeaaf78f051705042f7a48e9a527155799d572be214ba950359db8a3', 'tests': 'tests/test_s3_semantic_grounding_v6.py', 'tests_sha256': '130c408316d3761d25ae2c47560985cd73832efb088182a4d34f8d882c4ad73a'}`
