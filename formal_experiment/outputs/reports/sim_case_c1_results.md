# SIM 卡入网案例：A/B/C 三组开发性检测结果（同一 capsule）

- run: `sim_case_c1_run_v1`；口径：**development_case_study_not_formal_gold**（非正式 Gold，非作者原始实验复现，非企业验证）。
- 主评价单位：r8/v2, r9/v2, r10/v2, r11/v2, r13/v2（5 条 v2 规则）；背景条目：r12。
- 阈值：tau=0.8, gamma=0.8, theta=0.8, gamma_ext=0.5, label_fallback=0.4。
- 公共 Stage 1 记录：324091aa007882ab…；扁平化 XML 29a31cfc0fa520a7…；lanes=['Phone company', 'Another phone company', 'Customer']。
- 角色绑定（打分前声明）：{"Data Controller": "Phone company", "Data Subject": "Customer"}。

## 1. 组件对应

| 组 | Stage 2 | Stage 3 三类 | Stage 3 四类 |
|---|---|---|---|
| A | 项目锁定非 LLM 基线 B0 v10a (`sun_rule_only_b0_v10a`) | 冻结 Sun 式 Def5–7 | 未运行 |
| B | 已有真实 LLM 预测 `OURS-FULL/repeat-01`，经 `project_external_sentence` | 与 A 同一代码和阈值 | 未运行 |
| C | 与 B 同一 Stage 2 行和适配记录 | 逐行复用 B | REPAIR-V2 C 实现：`RepairedExtendedScorerV2` + `aggregate_with_comparison_gate` |

## 2. 五条规则的逐项实际输出

> `status` 是修正抽取失败后的评价状态；`machine_status` 保留冻结公式在分母为 0 等情形下的原始机器状态。A 组 r9/r13 的 `empty_rule_action` 不再写成 `not_applicable`。

| 规则 | 组 | missing_action | incorrect_actor | out_of_order | prohibited | condition | constraint | exception |
|---|---|---|---|---|---|---|---|---|
| r8/v2 | A | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r8/v2 | B | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r8/v2 | C | violation (1.0) | undetermined | undetermined (0.0) | undetermined | violation (1.0) | violation (0.674966) | undetermined |
| r9/v2 | A | undetermined (0.0); raw_machine=not_applicable; empty_rule_action_rule_element_not_extracted | undetermined | undetermined (0.0) | — | — | — | — |
| r9/v2 | B | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r9/v2 | C | violation (1.0) | undetermined | undetermined (0.0) | undetermined | undetermined | undetermined | undetermined |
| r10/v2 | A | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r10/v2 | B | satisfied (0.0) | violation (1.0) | undetermined (0.0) | — | — | — | — |
| r10/v2 | C | satisfied (0.0) | violation (1.0) | undetermined (0.0) | undetermined | violation (0.92683) | violation (0.623876) | undetermined |
| r11/v2 | A | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r11/v2 | B | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r11/v2 | C | violation (1.0) | undetermined | undetermined (0.0) | undetermined | undetermined | undetermined | undetermined |
| r13/v2 | A | undetermined (0.0); raw_machine=not_applicable; empty_rule_action_rule_element_not_extracted | undetermined | undetermined (0.0) | — | — | — | — |
| r13/v2 | B | satisfied (0.0) | violation (1.0) | undetermined (0.0) | — | — | — | — |
| r13/v2 | C | satisfied (0.0) | violation (1.0) | undetermined (0.0) | violation (0.628643) | undetermined | undetermined | undetermined |

## 3. 机器报警与参考问题对应（评价栏与检测器输出分栏）

> 只有同时具备动作绑定、流程事实、时间/终止语义等可核验证据的报警才计为对应检出；类型相同且 `status=violation` 本身不算证据。

| 规则 | 组 | 机器报警（原始输出） | 对应判断 | 有证据对应的报警 | 评价证据链 |
|---|---|---|---|---|---|
| r8/v2 | A | missing_action=violation/1.0  | machine_alarm_but_reference_correspondence_unverified | — | missing_action: machine alarm retained, but no model-side alarm value supplies an actual 30-day bound or terminate label; process-scope fields are absent. Reference correspondence remains unverified. r8 requires time, termination, and process-scope evidence from explicit sources; keyword co-occurrence in the alarm object is not used. |
| r8/v2 | B | missing_action=violation/1.0  | machine_alarm_but_reference_correspondence_unverified | — | missing_action: machine alarm retained, but no model-side alarm value supplies an actual 30-day bound or terminate label; process-scope fields are absent. Reference correspondence remains unverified. r8 requires time, termination, and process-scope evidence from explicit sources; keyword co-occurrence in the alarm object is not used. |
| r8/v2 | C | missing_action=violation/1.0 ；required_condition_not_enforced=violation/1.0 best=None max_sim=0.0 ；constraint_violated=violation/0.674966 best='sid-2673F7BE-190B-4A29-B042-F26FE1273508 sid-E965697A-165F-4586-B050-908E907A73E2 sid-dcc02dd6-4d40-4a5c-9c7a-e7f2289d157a sid-23CD283E-EBC8-4855-94D0-525EC56A6361 sid-dcc02dd6-4d40-4a5c-9c7a-e7f2289d157a' max_sim=0.325034  | machine_alarm_but_reference_correspondence_unverified | — | missing_action: machine alarm retained, but no model-side alarm value supplies an actual 30-day bound or terminate label; process-scope fields are absent. Reference correspondence remains unverified. required_condition_not_enforced: machine alarm retained, but no model-side alarm value supplies an actual 30-day bound or terminate label; process-scope fields are absent. Reference correspondence remains unverified. constraint_violated: machine alarm retained, but no model-side alarm value supplies an actual 30-day bound or terminate label; process-scope fields are absent. Reference correspondence remains unverified. r8 requires time, termination, and process-scope evidence from explicit sources; keyword co-occurrence in the alarm object is not used. |
| r9/v2 | A | 无 positive alarm | no_positive_machine_alarm | — | r9 correspondence needs an extracted action, a missing_action alarm with a concrete best candidate/similarity, and an activity inventory lacking verify/correctness semantics; Sign contract is only an anchor. |
| r9/v2 | B | missing_action=violation/1.0  | found_with_reference_evidence | missing_action | Extracted verification action is checked by missing_action; best process candidate is Ask portability third company at similarity 0.4219, and the original activity inventory has no verify/correctness activity. Sign contract (sid-6B3F7867-7939-43B6-8F6E-8B8A12ECCB7C) is only the positional anchor, not the missing action. |
| r9/v2 | C | missing_action=violation/1.0  | found_with_reference_evidence | missing_action | Extracted verification action is checked by missing_action; best process candidate is Ask portability third company at similarity 0.4219, and the original activity inventory has no verify/correctness activity. Sign contract (sid-6B3F7867-7939-43B6-8F6E-8B8A12ECCB7C) is only the positional anchor, not the missing action. |
| r10/v2 | A | missing_action=violation/1.0  | machine_alarm_but_reference_correspondence_unverified | — | r10 correspondence needs the rule action to bind to Activate SIM card, with concrete owner Customer and a required actor that is not an owner. A union of all matched candidates is not used. |
| r10/v2 | B | incorrect_actor=violation/1.0  | found_with_reference_evidence | incorrect_actor | Rule action maps to Activate SIM card (sid-D80682C2-0CD4-4B60-93BA-E9C747E28950); its concrete owner evidence is ['Customer']; required actor is the phone company. This is the fixed r10 actor-mismatch evidence. Other matched candidates are listed separately and are not attributed to Customer. |
| r10/v2 | C | incorrect_actor=violation/1.0 ；required_condition_not_enforced=violation/0.92683 best='Requested' max_sim=0.07317 ；constraint_violated=violation/0.623876 best='Receive SIM card' max_sim=0.376124  | found_with_reference_evidence | incorrect_actor | Rule action maps to Activate SIM card (sid-D80682C2-0CD4-4B60-93BA-E9C747E28950); its concrete owner evidence is ['Customer']; required actor is the phone company. This is the fixed r10 actor-mismatch evidence. Other matched candidates are listed separately and are not attributed to Customer. |
| r11/v2 | A | missing_action=violation/1.0  | machine_alarm_but_reference_correspondence_unverified | — | r11 correspondence requires a positive out_of_order alarm whose mapped endpoints include consent and request personal data. The present missing_action alarm is retained as a machine alarm but cannot substitute for the order issue; consent activity present=True, retrieval activity present=True. |
| r11/v2 | B | missing_action=violation/1.0  | machine_alarm_but_reference_correspondence_unverified | — | r11 correspondence requires a positive out_of_order alarm whose mapped endpoints include consent and request personal data. The present missing_action alarm is retained as a machine alarm but cannot substitute for the order issue; consent activity present=True, retrieval activity present=True. |
| r11/v2 | C | missing_action=violation/1.0  | machine_alarm_but_reference_correspondence_unverified | — | r11 correspondence requires a positive out_of_order alarm whose mapped endpoints include consent and request personal data. The present missing_action alarm is retained as a machine alarm but cannot substitute for the order issue; consent activity present=True, retrieval activity present=True. |
| r13/v2 | A | 无 positive alarm | no_positive_machine_alarm | — | No condition/constraint alarm contains the locatable 50 EUR rule threshold, the model Debt < 100 threshold, and an alarm-level mapping between them. Single numbers, isolated number co-occurrence, and similarity-score digits are not accepted. Actor threshold text is recorded as a field-attribution gap, not copied into condition/constraint. Other alarms are []. |
| r13/v2 | B | incorrect_actor=violation/1.0  | machine_alarm_but_reference_correspondence_unverified | — | No condition/constraint alarm contains the locatable 50 EUR rule threshold, the model Debt < 100 threshold, and an alarm-level mapping between them. Single numbers, isolated number co-occurrence, and similarity-score digits are not accepted. Actor threshold text is recorded as a field-attribution gap, not copied into condition/constraint. Other alarms are ['incorrect_actor']. |
| r13/v2 | C | incorrect_actor=violation/1.0 ；prohibited_action_present=violation/0.628643 best='Ask portability third company' max_sim=0.628643  | machine_alarm_but_reference_correspondence_unverified | — | No condition/constraint alarm contains the locatable 50 EUR rule threshold, the model Debt < 100 threshold, and an alarm-level mapping between them. Single numbers, isolated number co-occurrence, and similarity-score digits are not accepted. Actor threshold text is recorded as a field-attribution gap, not copied into condition/constraint. Other alarms are ['incorrect_actor', 'prohibited_action_present']. |

## 4. 信息传递与部分丢失（原始抽取→投影→规则记录→检测器消费）

判定：`full_carry`=各层数量一致；`partially_carried_by_declared_policy`=出现多值截断；`lost_in_adaptation`=抽取/投影有值但规则记录丢失；`not_extracted`=原始即无；`derived_by_declared_policy`=顺序关系由事先声明的 temporal policy 派生。

| 规则 | 组 | actions | actors | conditions | constraints | exceptions | order_relations | actor_action_pairs |
|---|---|---|---|---|---|---|---|---|
| r8/v2 | A | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | full_carry [raw=1→proj=1→adapted=1→consumed=0; not_used_by_group_pipeline] | full_carry [raw=1→proj=1→adapted=1→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | not_extracted |
| r8/v2 | B | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | full_carry [raw=1→proj=1→adapted=1→consumed=0; not_used_by_group_pipeline] | full_carry [raw=1→proj=1→adapted=1→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | invalid_in_raw_no_valid_pair |
| r8/v2 | C | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | invalid_in_raw_no_valid_pair |
| r9/v2 | A | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | full_carry [raw=1→proj=1→adapted=1→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | not_extracted |
| r9/v2 | B | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | derived_by_declared_policy [raw=0→proj=0→adapted=1→consumed=1; fully_consumed] | full_carry |
| r9/v2 | C | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | derived_by_declared_policy [raw=0→proj=0→adapted=1→consumed=1; fully_consumed] | full_carry |
| r10/v2 | A | partially_carried_by_declared_policy [raw=2→proj=2→adapted=1→consumed=1; partially_consumed_relative_to_projected] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | partially_carried_by_declared_policy [raw=2→proj=2→adapted=1→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | full_carry |
| r10/v2 | B | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=0; not_used_by_group_pipeline] | full_carry [raw=1→proj=1→adapted=1→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | full_carry |
| r10/v2 | C | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | full_carry |
| r11/v2 | A | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | full_carry [raw=1→proj=1→adapted=1→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | full_carry |
| r11/v2 | B | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | derived_by_declared_policy [raw=0→proj=0→adapted=1→consumed=1; fully_consumed] | full_carry |
| r11/v2 | C | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | derived_by_declared_policy [raw=0→proj=0→adapted=1→consumed=1; fully_consumed] | full_carry |
| r13/v2 | A | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | full_carry [raw=1→proj=1→adapted=1→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | not_extracted |
| r13/v2 | B | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; not_used_by_group_pipeline] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | full_carry |
| r13/v2 | C | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | full_carry [raw=1→proj=1→adapted=1→consumed=1; fully_consumed] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | not_extracted [raw=0→proj=0→adapted=0→consumed=0; no_value_to_consume] | full_carry |

### 4.1 值级变化与角色绑定（防止 1->1 计数掩盖回退）

| 规则 | 组 | 字段/配对 | original | final | source | reason |
|---|---|---|---|---|---|---|
| r9/v2 | B | order_relations | None | ('receiving the customer’s personal information', 'verify the correctness of their personal information') | — | binding_or_declared_derivation |
| r9/v2 | C | order_relations | None | ('receiving the customer’s personal information', 'verify the correctness of their personal information') | — | binding_or_declared_derivation |
| r10/v2 | A | actions | use the SIM card normally | None | — | not_selected_or_not_consumed |
| r10/v2 | A | conditions | that the customer can use the SIM card normally | None | — | not_selected_or_not_consumed |
| r11/v2 | A | actors | the Data Controller | Phone company | Data Controller | declared_role_binding |
| r11/v2 | A | actor_action_pairs | the Data Controller | Phone company | Data Controller | declared_role_binding |
| r11/v2 | B | actors | the Data Controller | Phone company | Data Controller | declared_role_binding |
| r11/v2 | B | order_relations | None | ('ask the Data Subject for consent', 'retrieving any kind of personal data from the Data Subject') | — | binding_or_declared_derivation |
| r11/v2 | B | actor_action_pairs | the Data Controller | Phone company | Data Controller | declared_role_binding |
| r11/v2 | C | actors | the Data Controller | Phone company | Data Controller | declared_role_binding |
| r11/v2 | C | order_relations | None | ('ask the Data Subject for consent', 'retrieving any kind of personal data from the Data Subject') | — | binding_or_declared_derivation |
| r11/v2 | C | actor_action_pairs | the Data Controller | Phone company | Data Controller | declared_role_binding |

### 4.2 A→B 归因

| 规则 | A→B changed_fields | 直接差异归因 | 组内适配损失 |
|---|---|---|---|
| r8/v2 | actions, constraint | extraction | 无 |
| r9/v2 | actions, actor_action_pairs, actors, condition, constraint, modality, order_relations | extraction | 无 |
| r10/v2 | actions, actor_action_pairs, constraint | extraction | A/actions=partially_carried_by_declared_policy (2→2→1); A/conditions=partially_carried_by_declared_policy (2→2→1) |
| r11/v2 | actor_action_pairs, condition, constraint, order_relations | extraction | 无 |
| r13/v2 | actions, actor_action_pairs, actors, constraint, modality | extraction | 无 |

## 5. 修复对照：有效、部分/无效与可评价性

> `effective_repair_control=true` 要求：修复语义独立成立、修复信息确实进入检测链、对应规则元素可用、修复后检查可执行。r8 的过程级事件子流程在冻结 Stage 1 中为 opaque activity，计时/终止作用域不能进入结构化检测链；旧任务级修复保留为部分/无效对照。

| 修复 | 规则 | 视角 | 修复语义有效 | 进入检测链 | 有效分母 | 排除原因 | C_original | C_repaired | 问题移除 |
|---|---|---|---|---|---|---|---|---|---|
| r8_timeout_termination | r8 | constraint_violated | True | False | False | repair_semantics_not_carried_by_stage1 | violation (0.674966) | violation (0.674966) | False |
| r9_add_verification | r9 | missing_action | True | True | True | — | violation (1.0) | violation (1.0) | False |
| r10_activation_owner | r10 | incorrect_actor | True | True | True | — | violation (1.0) | violation (1.0) | False |
| r11_consent_before_retrieval | r11 | out_of_order | True | True | True | — | undetermined (0.0) | undetermined (0.0) | False |
| r13_threshold_50 | r13 | required_condition_not_enforced | True | True | False | empty_rule_condition | undetermined (None) | undetermined (None) | False |

### 5.1 r8 旧任务级对照（保留但不进入有效分母）

- 旧件 `r8_timeout_termination_task_scoped_legacy`：`scope_matches_rule_semantics=False`；有效分母=False；C_original violation -> C_repaired violation。

## 6. 计数（逐检测项，不是七类总 F1，也不混用规则数）

| 组 | checks | violation | satisfied | undetermined | not_applicable | machine_status 计数 |
|---|---|---|---|---|---|---|
| A | 15 | 3 | 0 | 12 | 0 | {"violation": 3, "undetermined": 10, "not_applicable": 2} |
| B | 15 | 5 | 2 | 8 | 0 | {"violation": 5, "undetermined": 8, "satisfied": 2} |
| C | 35 | 10 | 2 | 23 | 0 | {"violation": 10, "undetermined": 23, "satisfied": 2} |

### 6.1 参考问题对应计数

| 组 | 参考问题数 | 有证据对应检出 | 有报警但对应未证实 | 无 positive alarm |
|---|---|---|---|---|
| A | 5 | 0 | 3 | 2 |
| B | 5 | 2 | 3 | 0 |
| C | 5 | 2 | 3 | 0 |

### 6.2 有效修复对照计数

- 主修复件：5。
- 有效修复对照分母：3。
- 排除：{"r8_timeout_termination": "repair_semantics_not_carried_by_stage1", "r13_threshold_50": "empty_rule_condition"}。

## 7. 边界

- 这是开发性单案例结果，不是正式 Gold、不是独立人工准确率、不是作者原始实验复现。
- 单案例只给逐条与逐检查计数，不合成七类总 F1。
- B 组复用已有 repeat-01 预测；重复运行只作稳定性证据，不作为新增独立样本。
- 原始 BPMN、需求、Gold、预测均未修改；参考判断只在评价阶段读取。

