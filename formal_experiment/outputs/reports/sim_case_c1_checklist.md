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
| curated_items | `formal_experiment/data/development/sim_case_c1/case_items_v1.json` | `bdd33299c0f4e556…` |
| predictions | `formal_experiment/outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-01/canonical_predictions.jsonl` | `6fab1108b311e105…` |
| predictions | `formal_experiment/outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-02/canonical_predictions.jsonl` | `16685a58eea1ca91…` |
| predictions | `formal_experiment/outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-03/canonical_predictions.jsonl` | `6d96729de0fb1328…` |
| predictions | `formal_experiment/outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-04/canonical_predictions.jsonl` | `17e298b033898b94…` |
| predictions | `formal_experiment/outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-05/canonical_predictions.jsonl` | `61dbc4ec7cfb5fac…` |

## 2. 绑定政策

```json
{
 "process_version": "single BPMN file (sha256 recorded in manifest); no second model version exists locally",
 "rule_version_under_evaluation": "version 2 (post-change requirement text)",
 "evaluation_unit": "one requirement id (r8-r13)",
 "excluded_from_evaluation": [
  {
   "item": "r9/v1",
   "reason": "requirement text is empty in version 1 (requirement added in v2)",
   "rule": "must not enter extraction or detection as a normative rule"
  },
  {
   "item": "r12/v2",
   "reason": "requirement text is empty in version 2 (requirement deleted)",
   "rule": "must not enter extraction or detection as a normative rule"
  }
 ],
 "step3_baseline_context": "external deviations are stated in a requirement-change context (v1 -> v2), not as a static compliance answer key; evidence: r12/v2 is empty yet carries an over_compliant deviation, r10 mitigation matches v2 text"
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

## 5. 逐条核对表

| 规则 | 版本 | 规则含义（我方转述） | 流程证据要点 | 外部原始标注 | 冲突 | 建议预期 | 需确认 |
|---|---|---|---|---|---|---|---|
| r8 | v2 | 流程耗时超过 30 天时，必须终止流程 | 模型中完全没有计时器/边界事件，也没有任何条件表达式；不存在“超时即终止”的分支 | non_compliant / `missing_timer` / process termination | — | capability_gap_not_violation（unsupported） | Q7 |
| r9 | v2 | 收到客户个人信息后，必须核验其正确性 | 流程中没有任何“核验正确性”的活动；外部标注的 element_label 是插入位置基准（Sign contract），不是缺失的动作本身 | non_compliant / `missing_activity` / Sign contract | element_label 指向已存在的 Sign contract；真正的缺失动作是核验正确性活动。以 element_label 直接映射到 missing_action 会把已存在的活动当作缺失动作 | violation_if_action_mappable（supported） | Q1 |
| r10 | v2 | 客户收到 SIM 卡时，必须由电话公司激活 SIM 卡 |  | non_compliant / `wrong_role` / Activate SIM card | — | violation_if_actor_mapping_works（supported） | — |
| r11 | v2 | 从数据主体取任何个人数据之前，必须先取得其同意 | 同意活动已存在，但位于取数与存储之后；缺的是“前置位置”，不是活动本身 | non_compliant / `missing_activity` / Request personal data | 外部标注称活动缺失，但当前模型已含同名活动且位置在取数/存数之后。必须区分“活动完全缺失 / 前置位置缺失 / 顺序错误”三种情形 | violation_order_semantics（partial） | Q2 |
| r12 | v1_to_v2_change | 第三方拒绝携号转网时须删除个人数据（v2 已删除该需求） |  | over_compliant / `redundant_activity` / Delete personal data | 该偏差以“需求在 v2 被删除”为前提，属变化影响评价；我们的分类体系没有 over_compliant 类别，不能计入违规评分 | outside_taxonomy_report_only（not_applicable） | Q4 |
| r13 | v2 | 欠款超过 50 EUR 的客户不得领取新 SIM 卡 | 模型侧唯一数值条件表面是该连线标签；没有 conditionExpression，网关本身无名 | non_compliant / `XOR_condition_modification` / Debt < 100 | 需求 v2 阈值=50；模型标签=100；外部修复建议=500。三处互不一致，保留原始文件不改，冲突如实记录；“exceeding 50” 是严格大于；模型标签 “Debt < 100” 是严格小于；等于阈值的情形两侧都没有覆盖，比较时必须显式说明边界处理 | capability_partial_plus_extraction_gap（partial） | Q3 |

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
 "version_of_record_status": "not_obtainable_in_this_environment (publisher authentication / paywall); therefore no claim is made about the published version",
 "handling": "keep both original readings; treat neither as reliable Gold; do not merge them into one label set"
}
```

## 8. 边界

- 本核对表是**提案**，未经用户确认；不含 Gold，不构成性能结论。
- 外部 `bpmn_element → 我们七类` 的映射表仅为**阅读辅助**，不作评分键、不用于合成预期结果。
- Barrientos 语料许可为 `unknown_pending_confirmation`；本文件不含其长文本。

