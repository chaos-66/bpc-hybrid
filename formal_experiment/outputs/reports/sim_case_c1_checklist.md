# Case C（SIM 卡入网）逐条核对表（可提交摘要）

- 状态：**development_case_checklist_pending_user_confirmation**；`is_gold=false`；未运行比较；零 LLM/API。
- 本文件只含 ID / 标签 / 短片段（<40 字符）/ 计数 / 哈希 / 判定；完整文本在 gitignored 的 local-only 目录。

## 1. 输入绑定（sha256 前 16 位）

| 输入 | 路径 | sha256 |
|---|---|---|
| process_model | `references/barrientos_2026/artifact_input/process_models/SIM_card_scenario/SIM_card_scenario.bpmn` | `338c8144cd2802f0…` |
| requirements | `references/barrientos_2026/artifact_input/requirements/SIM_card_scenario/SIM_card_scenario.json` | `e13d9a2a208c83ff…` |
| step_1_baseline | `references/barrientos_2026/evaluation/ground_truth/step_1_baseline.json` | `83146ef0e3e47334…` |
| step_2_baseline | `references/barrientos_2026/evaluation/ground_truth/step_2_baseline.json` | `ecd3aa81cfa92c68…` |
| step_3_baseline | `references/barrientos_2026/evaluation/ground_truth/step_3_baseline.json` | `96b3c1e8f10e0ad4…` |
| sun_2024_local_pdf | `references/papers/Sun_2024_Design_time_BPC.pdf` | `08a26b7d4e6716eb…` |
| curated_items | `formal_experiment/data/development/sim_case_c1/case_items_v2.json` | `a5324734a4dbe95c…` |
| predictions | `formal_experiment/outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-01/canonical_predictions.jsonl` | `6fab1108b311e105…` |
| predictions | `formal_experiment/outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-02/canonical_predictions.jsonl` | `16685a58eea1ca91…` |
| predictions | `formal_experiment/outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-03/canonical_predictions.jsonl` | `6d96729de0fb1328…` |
| predictions | `formal_experiment/outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-04/canonical_predictions.jsonl` | `17e298b033898b94…` |
| predictions | `formal_experiment/outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-05/canonical_predictions.jsonl` | `61dbc4ec7cfb5fac…` |

## 2. 绑定政策

```json
{
 "process_version": "single BPMN file (sha256 bound in the manifest); no second model version exists locally",
 "rule_version_under_evaluation": "version 2",
 "evaluation_unit": "one requirement id",
 "detection_input_rule": "predictions never see the external deviations, the reference judgments, or the figure's violation callouts",
 "role_binding_policy": {
  "fixed_before_scoring": true,
  "bindings": {
   "Data Controller": "Phone company",
   "Data Subject": "Customer"
  },
  "boundary_zh": "该绑定是场景语义绑定，三组共用；不得按预测结果新增角色、动作同义词或规则 ID 特判"
 },
 "numeric_boundary_policy_r13": {
  "natural_language_meaning": "debt > 50 EUR is prohibited from receiving a new SIM card; debt = 50 does not trigger this prohibition (it does not imply every other issuance condition is met)",
  "flow_label_meaning": "the label 'Debt < 100' gates the portability branch; read as a routing condition it admits customers whose debt is below 100",
  "difference_interval": "50 < debt < 100 (example debt = 75) is the explicit interval where the model does not enforce the v2 restriction",
  "executable_condition_expression": "absent: the model has no conditionExpression; the condition exists only as a sequence-flow label",
  "detector_semantics": "recorded separately by the run; it does not change the reference judgment",
  "external_suggestion": "the external mitigation proposing 'Debt < 500' is kept as a source conflict and is NOT adopted"
 }
}
```

## 3. 流程结构事实（实测）

- task 11 / subProcess 1 / gateway 6 / event 8 / flow 26
- timer 定义 **0**、boundary event **0**、conditionExpression **0**、带标签 flow **4**
- 带标签 flow：[{'id': 'sid-8A897978-076F-4C58-91C2-A82506C35F92', 'source': 'sid-A0EC90A7-DC2C-4CC6-9590-F3BE114A2605', 'target': 'Assign new number', 'label': 'Not requested', 'condition_expression': None}, {'id': 'sid-910AED7B-8C2F-4DC4-A241-80471E267B36', 'source': 'sid-A0EC90A7-DC2C-4CC6-9590-F3BE114A2605', 'target': 'Ask old number', 'label': 'Requested', 'condition_expression': None}, {'id': 'sid-ACA2A7F7-B0A2-4D10-85B5-052F50428721', 'source': 'sid-0DA99902-C027-4988-A2EB-2823F6D87794', 'target': 'sid-5DB79A16-AE0E-4F99-9754-6D6ADB14DA79', 'label': 'Granted', 'condition_expression': None}, {'id': 'sid-E888F2BE-1037-4B0C-AE98-CFABE0C44D29', 'source': 'sid-B8D4B659-96BF-4003-A00D-7951C7E0C0BE', 'target': 'Ask portability', 'label': 'Debt < 100', 'condition_expression': None}]
- consent：存在=True，前驱=['Store Data']，紧跟 Store Data=True

## 4. 预测复用审计

- 独立输入 **10** 条；重复轮次 **5**；总行数 **50**
- 全部行的 order_relations 合计：**0**
- 5 轮抽取结果完全一致：**True**（重复不作独立样本）
- 独立输入 ID：['SIM_card_scenario/r10/v1', 'SIM_card_scenario/r10/v2', 'SIM_card_scenario/r11/v1', 'SIM_card_scenario/r11/v2', 'SIM_card_scenario/r12/v1', 'SIM_card_scenario/r13/v1', 'SIM_card_scenario/r13/v2', 'SIM_card_scenario/r8/v1', 'SIM_card_scenario/r8/v2', 'SIM_card_scenario/r9/v2']

## 5. 逐条核对表（① 语义问题 / ② 开发参考判断）

| 规则 | 在 5 条分母 | ① 语义问题 | ② 开发参考判断 | ② 来源 | 外部原始标注 | 冲突 | 候选检测视角 |
|---|---|---|---|---|---|---|---|
| r8/v2 | 是 | 当前可见模型中不存在任何超时终止机制（无计时器、无边界事件、无超时分支），规则要求的“超时即终止”义务未在模型中表达 | issue_present | user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_model_structure, external_step3_change_context:mitting_timer | non_compliant / `missing_timer` / process termination | — | constraint_violated |
| r9/v2 | 是 | 模型缺少“收到个人信息后进行正确性核验”的活动；外部标注的 element_label（Sign contract）只是插入位置参照 | issue_present | user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_model_activity_inventory, external_step3_change_context:missing_activity_anchor_sign_contract | non_compliant / `missing_activity` / Sign contract | 外部 element_label 指向已存在的 Sign contract；把定位参照当作缺失动作会误判 | missing_action |
| r10/v2 | 是 | 当前激活活动由 Customer 执行，与 v2 要求的 Phone company 执行不一致 | issue_present | user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_model_lane_attribution, external_step3_change_context:wrong_role | non_compliant / `wrong_role` / Activate SIM card | — | incorrect_actor |
| r11/v2 | 是 | 同意活动已存在，但位于取数与存数之后，违反规则要求的先后关系；问题性质是前置位置/顺序，而不是活动缺失 | issue_present | user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_model_flow_order, external_step3_change_context:missing_activity_label_disagreed | non_compliant / `missing_activity` / Request personal data | 外部标注称活动缺失，实际是前置位置缺失；两种说法不能混用，且不得为符合外部标注而改动流程 | out_of_order, required_condition_not_enforced |
| r13/v2 | 是 | 把图示连线标签作为路由条件解释时，模型门槛无法阻止欠款处于 50 到 100 欧元之间的客户继续进入后续流程 | issue_present_with_premise（前提：前提：把连线标签 'Debt < 100' 解释为该分支的路由条件（该模型没有可执行 conditionExpression，条件只以标签形式存在）） | user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_flow_label_interval, external_step3_change_context:xor_condition_modification_mitigation_not_adopted | non_compliant / `XOR_condition_modification` / Debt < 100 | 需求 v2 阈值 50、模型标签 100、外部修复建议 500 三者不一致；保留原始文件，冲突如实记录 | required_condition_not_enforced, constraint_violated |
| r12/v1_to_v2_change | 否（背景） | v2 已删除该需求，因此“删除个人数据”活动在 v2 语境下成为外部所称的 over-compliance；这不是五条静态规则意义上的违规 | background_only（前提：作为“需求删除 + 外部 over-compliance”的背景说明单列，不进入 5 条静态规则的评价分母） | user_instruction_2026_09_11_dev_policy, external_step3_change_context:redundant_activity | over_compliant / `redundant_activity` / Delete personal data | 外部偏差以“需求被删除”为前提，属变化影响评价 | — |

> ③ 方法实际输出、④ 一致性、⑤ 差异阶段**不在本表中**：由 `scripts/run_sim_case_c1_v1.py` 的运行胶囊填充。
> 本表是开发参考判断，不是正式 Gold，也不声称用户已逐条完成人工标注。


## 6. 能力核实（§5.6）

| 探针 | 结论 | 说明 |
|---|---|---|
| condition_triggered_termination | unsupported_by_current_checks | 现有时限比较判断数值边界是否满足，不判断“终止分支是否存在”；不得把两者等同 |
| numeric_boundary_condition | partial | 4 条带标签 flow 中只有一条是数值条件，其余为状态标签；现有条件检查针对“条件未被落实”，不针对“条件数值与规则不一致”，故本探针只部分支持 |
| consent_before_retrieval_order | partial | 模型顺序可读；但现有 LLM 抽取全部 0 条 order_relations，顺序检查在 B/C 组缺少规则侧关系 |
| cross_participant_attribution | supported_if_actor_resolution_holds | 活动归属可由参与者/泳道解析；需在运行报告给出解析证据 |

## 7. Sun 论文图文冲突

```json
{
 "source": "local pre-publication manuscript (references/papers/Sun_2024_Design_time_BPC.pdf; page 23 text vs page 24 Figure 10)",
 "reading_text": "R1 and R4 = missing action; R2 = out-of-order execution; R3 = incorrect actor",
 "reading_figure": "V1/R1 and V2/R2 = Missing Action; V3/R3 = Incorrect Actor; V4/R4 = Out-of-order Execution",
 "difference": "R2 and R4 are swapped between the two readings",
 "version_of_record_status": "not_obtainable_in_this_environment (publisher authentication / paywall)",
 "handling": "keep both original readings as literature statements; treat neither as reliable Gold; obtaining the version of record is not a precondition for continuing this case"
}
```

## 8. 边界

- 本核对表是**提案**，未经用户确认；不含 Gold，不构成性能结论。
- 外部 `bpmn_element → 我们七类` 的映射表仅为**阅读辅助**，不作评分键、不用于合成预期结果。
- Barrientos 语料许可为 `unknown_pending_confirmation`；本文件不含其长文本。

