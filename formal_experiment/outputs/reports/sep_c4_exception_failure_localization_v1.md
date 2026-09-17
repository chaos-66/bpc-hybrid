# SEP-C4 exception 失败定位 v1（只读已有结果，零 API）
## 结论
- 当前 v5 per-type: TP=3, FN_observed=0, FN_unknown=7, F1=0.4615.
- Winter-style 四类扩展对照: TP=3, FN_observed=1, FN_unknown=6, F1=0.4615.
- 7 个 unknown 的主因是 rule-action grounding unresolved/ambiguous；variant 确实缺少 handler，但 checker 无法把 exception 绑定到可靠动作锚点。
- 1 例（06）另有无关 alternate branch 被标为 dedicated handler candidate，但动作 grounding 本身 ambiguous，不能仅凭分支文本判 violation。
- 目标 per-type check 未把 unknown 读成 satisfied/violation；combined `decision` 可能因优先级给出另一个类型的 violation，但 target-paired 评测仍保留 unknown。
- 无足够证据做最小公共映射代码修复；需先解决 Stage 2 rule action 质量或另获边界授权的 action-grounding 改进。

## 逐项追踪

| item_id | sub_kind | rule_exception | rule_action | AG status | action_match | current status/reason | baseline status | primary root cause |
|---|---|---|---|---|---:|---|---|---|
| syn_v2_exception_not_handled_01 | boundary | `unless the personal data breach is unlikely to result in a risk to the rights and freedoms of natural persons` | `notify the personal data breach` | resolved | False | not_handled / `no_structurally_relevant_handler_in_closed_downstream_surface` | violated | none_current_tp_no_handler_with_resolved_action |
| syn_v2_exception_not_handled_02 | boundary | `shall not be required if the controller has implemented appropriate technical and organisational protection measures` | `referred to` | unresolved | False | unknown / `action_grounding_unresolved` | unknown | rule_action_grounding_not_resolved_or_ambiguous |
| syn_v2_exception_not_handled_03 | boundary | `shall not be required if the controller has taken subsequent measures which ensure that the high risk to the rights and freedoms of data subjects referred to in paragraph 1 is no longer likely to materialise` | `referred to` | unresolved | False | unknown / `action_grounding_unresolved` | unknown | rule_action_grounding_not_resolved_or_ambiguous |
| syn_v2_exception_not_handled_04 | boundary | `shall not apply if the decision is necessary for entering into` | `apply` | ambiguous | False | unknown / `no_handler_and_action_grounding_ambiguous` | negative | rule_action_grounding_not_resolved_or_ambiguous |
| syn_v2_exception_not_handled_05 | boundary | `shall not apply to the extent that processing is necessary for exercising the right of freedom of expression and information` | `apply to the extent that processing is necessary for exercising the right of freedom of expression and information` | resolved | False | not_handled / `no_structurally_relevant_handler_in_closed_downstream_surface` | unknown | none_current_tp_no_handler_with_resolved_action |
| syn_v2_exception_not_handled_06 | branch | `unless the personal data breach is unlikely to result in a risk to the rights and freedoms of natural persons` | `notify the personal data breach` | ambiguous | False | unknown / `dedicated_handler_candidate_exists_but_semantics_ambiguous` | violated | rule_action_grounding_not_resolved_or_ambiguous |
| syn_v2_exception_not_handled_07 | branch | `where technically feasible` | `have the right to have the personal data transmitted directly from one controller to another , where technically feasible` | ambiguous | False | unknown / `no_handler_and_action_grounding_ambiguous` | unknown | rule_action_grounding_not_resolved_or_ambiguous |
| syn_v2_exception_not_handled_08 | branch | `where technically feasible` | `have the right to have the personal data transmitted directly from one controller to another , where technically feasible` | ambiguous | False | unknown / `no_handler_and_action_grounding_ambiguous` | unknown | rule_action_grounding_not_resolved_or_ambiguous |
| syn_v2_exception_not_handled_09 | branch | `where technically feasible` | `have the right to have the personal data transmitted directly from one controller to another , where technically feasible` | ambiguous | False | unknown / `no_handler_and_action_grounding_ambiguous` | unknown | rule_action_grounding_not_resolved_or_ambiguous |
| syn_v2_exception_not_handled_10 | branch | `unless otherwise requested by the data subject` | `makes Where the request by electronic means` | resolved | False | not_handled / `no_structurally_relevant_handler_in_closed_downstream_surface` | violated | none_current_tp_no_handler_with_resolved_action |

## 根因分类

- exception 与普通 condition 混淆：0 例直接证据。
- 例外作用范围绑定错误：1 例贡献因素（06 的无关 branch candidate）。
- 动作映射失败：7 例贡献主因；另有 3 例 TP 虽 resolved 但 `action_match=false`，说明动作锚点整体不可靠。
- 流程缺少判断例外是否处理的证据：7 例 variant 缺少插入 handler；但动作不能绑定，故保留 unknown。
- unknown 被错误解释为满足或违规：target-paired check 为 0 例；combined decision 优先级可能输出其他 violation，需在论文中区分。

## 来源绑定
- `c36_target_paired_report_v2`: `outputs/reports/s3_c36_target_paired_v2.json` sha256=`d4679e06498c73dd29952720ab0a91f71f368f0195bc8220b1a4415beefbb889`
- `c36_target_paired_checks_v2`: `outputs/evidence/s3_c36_target_paired_v2/c36_winter_target_paired_checks.jsonl` sha256=`0a818244317eed6aa9ee66f1a43fd69406be40b4d78d2961608b335dcfe00830`
- `v5_predictions`: `outputs/evidence/s3_semantic_grounding_v5/predictions.jsonl` sha256=`4f6d43c8bbd23db7156f4dc07f76365bd25a701674f8c28cbe2fb6cafee8573b`
- `synthetic_panel_v2`: `data/development/stage3_synth/synthetic_controlled_error_extension_v2.json` sha256=`6a23adbdbc0d8930ff2a33411c52fed7fbbf581fdd101f830c29b2e3373e2e81`
- `constraint_checker`: `src/bpc_hybrid/s3_semantic_grounding_v1.py` sha256=`ea1907479ea02611582fe3c1adf7295a4354f2f395979e259cfc5a2dbde49983`
- `exception_checker`: `src/bpc_hybrid/s3_semantic_grounding_v1.py` sha256=`ea1907479ea02611582fe3c1adf7295a4354f2f395979e259cfc5a2dbde49983`
- `action_anchor_guard`: `src/bpc_hybrid/s3_semantic_grounding_v5.py` sha256=`dc3b931a79a9f8aa44d58b6c7c74b68d907ad8de8cf6e3770b5d0b05bfff5507`

## 边界
本报告基于 A 完成后的同一代码状态；A 未修改公共映射代码。仅重读已保存 C36 v2 与 v5 predictions，不重跑比较、不生成新预测、不调 API。开发面板不是 formal Oracle。
