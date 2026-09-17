# SEP-C4 constraint 失败定位 v1（只读已有结果，零 API）
## 结论
- 当前 v5 per-type: TP=2, FN_observed=0, FN_unknown=8, F1=0.3333.
- Winter-style 四类扩展对照: TP=6, FN_observed=0, FN_unknown=4, F1=0.7500.
- 02 个 timer 数值上限冲突均被正确判为 violation；8 个 unknown 全部来自 `unsupported_abstract_constraint_kind`，按 v1 配置规定保留 unknown，不能做确定性相似度判定。
- 8 个 unknown 同时伴随 rule-action grounding 不一致：03-06 resolved 但 `action_match=false` 且部分标签语义明显不对应；07-10 ambiguous/unresolved。该问题不足以单独修复，因为抽象约束种类门控仍会阻断。
- 这 8 例的合成标签来自“control 插入 annotation/dataObject，variant 保持原 source”的参考对应约定，并非 variant 中的运行时可观察矛盾。无代码、阈值、Gold、样本或历史预测修改依据。

## 逐项追踪

| item_id | sub_kind | rule_constraint | AG status | action_match | grounded label | current status/reason | baseline status | primary root cause |
|---|---|---|---:|---|---|---|---|---|
| syn_v2_constraint_violated_01 | timer | `not later than 72 hours` | resolved | False | `Retrieve breached data` | violated / `explicit_numeric_time_bound_exceeds_rule_limit` | violated | none_current_tp_numeric_timer_contradiction |
| syn_v2_constraint_violated_02 | timer | `within 72 hours` | resolved | False | `Handle delay` | violated / `explicit_numeric_time_bound_exceeds_rule_limit` | unknown | none_current_tp_numeric_timer_contradiction |
| syn_v2_constraint_violated_03 | annotation | `without undue delay` | resolved | False | `Communicate the rectification` | unknown / `unsupported_abstract_constraint_kind` | unknown | bpmn_variant_does_not_express_abstract_constraint_evidence |
| syn_v2_constraint_violated_04 | annotation | `without undue delay` | resolved | False | `Retrieve breached data` | unknown / `unsupported_abstract_constraint_kind` | violated | bpmn_variant_does_not_express_abstract_constraint_evidence |
| syn_v2_constraint_violated_05 | annotation | `without undue delay` | resolved | False | `Communication with data subject` | unknown / `unsupported_abstract_constraint_kind` | violated | bpmn_variant_does_not_express_abstract_constraint_evidence |
| syn_v2_constraint_violated_06 | annotation | `without undue delay` | resolved | False | `Retrieve available data of the data subject` | unknown / `unsupported_abstract_constraint_kind` | violated | bpmn_variant_does_not_express_abstract_constraint_evidence |
| syn_v2_constraint_violated_07 | annotation | `without hindrance` | ambiguous | False | `` | unknown / `unsupported_abstract_constraint_kind` | unknown | bpmn_variant_does_not_express_abstract_constraint_evidence |
| syn_v2_constraint_violated_08 | dataobject | `without hindrance` | ambiguous | False | `` | unknown / `unsupported_abstract_constraint_kind` | unknown | bpmn_variant_does_not_express_abstract_constraint_evidence |
| syn_v2_constraint_violated_09 | dataobject | `without undue delay` | ambiguous | False | `` | unknown / `unsupported_abstract_constraint_kind` | violated | bpmn_variant_does_not_express_abstract_constraint_evidence |
| syn_v2_constraint_violated_10 | dataobject | `clear and plain language` | ambiguous | False | `` | unknown / `unsupported_abstract_constraint_kind` | violated | bpmn_variant_does_not_express_abstract_constraint_evidence |

## 根因分类

- 动作映射或作用范围错误：8 例均为贡献因素；03-06 动作锚点未命中真实 action，07-10 动作锚点未解析。
- 时间、数量等约束解释错误：0 例。01-02 的 timer 数值比较与生成冲突一致。
- BPMN 没有表达所需信息：8 例。variant 是 source bytes，control 才插入抽象约束 annotation/dataObject；variant 无可观察的上限/数量/限制值。
- 评价目标或参考对应关系不明确：8 例。合成控制面板把“缺少抽象约束复述”定义为 violation，与流程运行时语义不一一对应。

## 来源绑定
- `c36_target_paired_report_v2`: `outputs/reports/s3_c36_target_paired_v2.json` sha256=`d4679e06498c73dd29952720ab0a91f71f368f0195bc8220b1a4415beefbb889`
- `c36_target_paired_checks_v2`: `outputs/evidence/s3_c36_target_paired_v2/c36_winter_target_paired_checks.jsonl` sha256=`0a818244317eed6aa9ee66f1a43fd69406be40b4d78d2961608b335dcfe00830`
- `v5_predictions`: `outputs/evidence/s3_semantic_grounding_v5/predictions.jsonl` sha256=`4f6d43c8bbd23db7156f4dc07f76365bd25a701674f8c28cbe2fb6cafee8573b`
- `synthetic_panel_v2`: `data/development/stage3_synth/synthetic_controlled_error_extension_v2.json` sha256=`6a23adbdbc0d8930ff2a33411c52fed7fbbf581fdd101f830c29b2e3373e2e81`
- `constraint_checker`: `src/bpc_hybrid/s3_semantic_grounding_v1.py` sha256=`ea1907479ea02611582fe3c1adf7295a4354f2f395979e259cfc5a2dbde49983`
- `exception_checker`: `src/bpc_hybrid/s3_semantic_grounding_v1.py` sha256=`ea1907479ea02611582fe3c1adf7295a4354f2f395979e259cfc5a2dbde49983`
- `action_anchor_guard`: `src/bpc_hybrid/s3_semantic_grounding_v5.py` sha256=`dc3b931a79a9f8aa44d58b6c7c74b68d907ad8de8cf6e3770b5d0b05bfff5507`

## 边界
本报告仅重读已保存的 C36 v2 与 v5 predictions，不重跑比较、不生成新预测、不调 API。开发面板不是 formal Oracle，也不宣称泛化提升。

## V6 锚点解释校正（后加说明；原始逐项数据、hash、分母均未改写）

- action_match=false 是标签是否词面命中 rule action 的检查结果，不是语义错误判定；有独立词面或语义支持路径时，锚点仍可能可用。
- 旧实现的 resolved 仅表示从多个候选中排序取首；若词面 winner 与 semantic winner 冲突，v6 候选会保留 ambiguous，不以排序、activity_id 或遍历顺序强制 resolved。
- 缺少 action/field 支持时，v6 锚点状态为 unconfirmed，不再写 resolved_label_is_action_consistent。
- 本校正不修改本文件原始表格、输入绑定或历史结果。v6 候选的逐条变化和重新计算的 checks/decision 见 outputs/reports/sep_c4_action_anchor_scope_v1.json 和 .md。
