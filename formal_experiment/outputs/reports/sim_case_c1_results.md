# SIM 卡入网案例：A/B/C 三组开发性检测结果（S3.9-EXT-REAL-CASE）

- run: `sim_case_c1_run_v1`；口径：**development_case_study_not_formal_gold**（非正式 Gold、非作者原始实验复现、非企业验证）
- 主实验规则（5 条）：r8/v2, r9/v2, r10/v2, r11/v2, r13/v2；背景条目：r12
- 阈值：tau=0.8, gamma=0.8, theta=0.8, gamma_ext=0.5
- 公共 Stage 1 记录：324091aa007882ab…（扁平化 XML 29a31cfc0fa520a7…，lanes=['Phone company', 'Another phone company', 'Customer']）
- 角色绑定：{"Data Controller": "Phone company", "Data Subject": "Customer"}（打分前声明，三组共用）

## 1. 组件对应表（P1：这三组究竟跑了什么）

| 组 | Stage 2（实际入口/模型） | Stage 3 三类 | Stage 3 四类 |
|---|---|---|---|
| A | 项目锁定非 LLM 基线 `run_b0_batch_v10`（B0 v10a：CoreNLP+Tregex+BERT-TextCNN，英文句经德语合同分类器槽 pass-through） | 冻结 Sun 式 Def5-7 | 无 |
| B | 既有真实 LLM 预测（`OURS-FULL/repeat-01`，经 `project_external_sentence` 投影） | 与 A 同一代码与阈值 | 无 |
| C | 与 B 完全相同（复用同一行对象） | 与 B 完全相同（逐行复用） | REPAIR-V2 C 臂：`RepairedExtendedScorerV2`（v3 γ=0.8 + 标签回退 0.4 + γ_ext=0.5）+ 比较门 |

- 相似度后端：`bpc_hybrid.winter_stage3.winter_similarity.WinterSimilarity`，nlp=`en_core_web_sm`；行为：Doc.similarity over context-sensitive tensors (spaCy warns W007: the model ships no static word vectors); it is NOT a string similarity and NOT a static-embedding similarity
- 阈值：tau=0.8, gamma=0.8, theta=0.8, gamma_ext=0.5, label_fallback=0.4
- 角色绑定：{"Data Controller": "Phone company", "Data Subject": "Customer"}；顺序推导政策：`temporal_marker_from_condition_v2`（comma_optional_v2）

## 2. 逐条结果（③ 方法实际输出）

| 规则 | 组 | missing_action | incorrect_actor | out_of_order | prohibited | condition | constraint | exception |
|---|---|---|---|---|---|---|---|---|
| r8/v2 | A | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r8/v2 | B | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r8/v2 | C | violation (1.0) | undetermined | undetermined (0.0) | undetermined | violation (1.0) | violation (0.674966) | undetermined |
| r9/v2 | A | not_applicable (0.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r9/v2 | B | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r9/v2 | C | violation (1.0) | undetermined | undetermined (0.0) | undetermined | undetermined | undetermined | undetermined |
| r10/v2 | A | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r10/v2 | B | satisfied (0.0) | violation (1.0) | undetermined (0.0) | — | — | — | — |
| r10/v2 | C | satisfied (0.0) | violation (1.0) | undetermined (0.0) | undetermined | violation (0.92683) | violation (0.623876) | undetermined |
| r11/v2 | A | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r11/v2 | B | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r11/v2 | C | violation (1.0) | undetermined | undetermined (0.0) | undetermined | undetermined | undetermined | undetermined |
| r13/v2 | A | not_applicable (0.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r13/v2 | B | satisfied (0.0) | violation (1.0) | undetermined (0.0) | — | — | — | — |
| r13/v2 | C | satisfied (0.0) | violation (1.0) | undetermined (0.0) | violation (0.628643) | undetermined | undetermined | undetermined |

## 3. 逐条证据与错误来源（③ 方法实际输出 + ⑤ 归因）

| 规则 | 组 | 映射活动（相似度） | 检测项 | 状态 | 分数 | 机器原因 | 候选面计数 |
|---|---|---|---|---|---|---|---|
| r8/v2 | A | — | missing_action | violation | 1.0 | — | — |
| r8/v2 | A | — | incorrect_actor | undetermined | None | empty_rule_actor_denominator | — |
| r8/v2 | A | — | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | — |
| r8/v2 | B | — | missing_action | violation | 1.0 | — | — |
| r8/v2 | B | — | incorrect_actor | undetermined | None | empty_rule_actor_denominator | — |
| r8/v2 | B | — | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | — |
| r8/v2 | C | New client acquired (0.446202) | missing_action | violation | 1.0 | — | cond=4, cons=29, exc=6 |
| r8/v2 | C | New client acquired (0.446202) | incorrect_actor | undetermined | None | empty_rule_actor_denominator | cond=4, cons=29, exc=6 |
| r8/v2 | C | New client acquired (0.446202) | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | cond=4, cons=29, exc=6 |
| r8/v2 | C | New client acquired (0.446202) | prohibited_action_present | undetermined | None | rule_modality_not_prohibition | cond=4, cons=29, exc=6 |
| r8/v2 | C | New client acquired (0.446202) | required_condition_not_enforced | violation | 1.0 | — | cond=4, cons=29, exc=6 |
| r8/v2 | C | New client acquired (0.446202) | constraint_violated | violation | 0.674966 | — | cond=4, cons=29, exc=6 |
| r8/v2 | C | New client acquired (0.446202) | exception_not_handled | undetermined | None | empty_rule_exception | cond=4, cons=29, exc=6 |
| r9/v2 | A | — | missing_action | not_applicable | 0.0 | empty_rule_action | — |
| r9/v2 | A | — | incorrect_actor | undetermined | None | empty_rule_actor_denominator | — |
| r9/v2 | A | — | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | — |
| r9/v2 | B | — | missing_action | violation | 1.0 | — | — |
| r9/v2 | B | — | incorrect_actor | undetermined | None | action_mapping_below_gamma | — |
| r9/v2 | B | — | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | — |
| r9/v2 | C | Ask portability third company (0.388024) | missing_action | violation | 1.0 | — | cond=4, cons=29, exc=6 |
| r9/v2 | C | Ask portability third company (0.388024) | incorrect_actor | undetermined | None | action_mapping_below_gamma | cond=4, cons=29, exc=6 |
| r9/v2 | C | Ask portability third company (0.388024) | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | cond=4, cons=29, exc=6 |
| r9/v2 | C | Ask portability third company (0.388024) | prohibited_action_present | undetermined | None | rule_modality_not_prohibition | cond=4, cons=29, exc=6 |
| r9/v2 | C | Ask portability third company (0.388024) | required_condition_not_enforced | undetermined | None | label_argmax_below_action_gamma | cond=4, cons=29, exc=6 |
| r9/v2 | C | Ask portability third company (0.388024) | constraint_violated | undetermined | None | empty_rule_constraint | cond=4, cons=29, exc=6 |
| r9/v2 | C | Ask portability third company (0.388024) | exception_not_handled | undetermined | None | empty_rule_exception | cond=4, cons=29, exc=6 |
| r10/v2 | A | — | missing_action | violation | 1.0 | — | — |
| r10/v2 | A | — | incorrect_actor | undetermined | None | action_mapping_below_gamma | — |
| r10/v2 | A | — | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | — |
| r10/v2 | B | — | missing_action | satisfied | 0.0 | — | — |
| r10/v2 | B | — | incorrect_actor | violation | 1.0 | — | — |
| r10/v2 | B | — | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | — |
| r10/v2 | C | Send SIM card (0.804544) | missing_action | satisfied | 0.0 | — | cond=4, cons=29, exc=6 |
| r10/v2 | C | Send SIM card (0.804544) | incorrect_actor | violation | 1.0 | — | cond=4, cons=29, exc=6 |
| r10/v2 | C | Send SIM card (0.804544) | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | cond=4, cons=29, exc=6 |
| r10/v2 | C | Send SIM card (0.804544) | prohibited_action_present | undetermined | None | rule_modality_not_prohibition | cond=4, cons=29, exc=6 |
| r10/v2 | C | Send SIM card (0.804544) | required_condition_not_enforced | violation | 0.92683 | — | cond=4, cons=29, exc=6 |
| r10/v2 | C | Send SIM card (0.804544) | constraint_violated | violation | 0.623876 | — | cond=4, cons=29, exc=6 |
| r10/v2 | C | Send SIM card (0.804544) | exception_not_handled | undetermined | None | empty_rule_exception | cond=4, cons=29, exc=6 |
| r11/v2 | A | — | missing_action | violation | 1.0 | — | — |
| r11/v2 | A | — | incorrect_actor | undetermined | None | action_mapping_below_gamma | — |
| r11/v2 | A | — | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | — |
| r11/v2 | B | — | missing_action | violation | 1.0 | — | — |
| r11/v2 | B | — | incorrect_actor | undetermined | None | action_mapping_below_gamma | — |
| r11/v2 | B | — | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | — |
| r11/v2 | C | Ask for consent (0.725865) | missing_action | violation | 1.0 | — | cond=4, cons=29, exc=6 |
| r11/v2 | C | Ask for consent (0.725865) | incorrect_actor | undetermined | None | action_mapping_below_gamma | cond=4, cons=29, exc=6 |
| r11/v2 | C | Ask for consent (0.725865) | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | cond=4, cons=29, exc=6 |
| r11/v2 | C | Ask for consent (0.725865) | prohibited_action_present | undetermined | None | rule_modality_not_prohibition | cond=4, cons=29, exc=6 |
| r11/v2 | C | Ask for consent (0.725865) | required_condition_not_enforced | undetermined | None | v3_localization_undetermined | cond=4, cons=29, exc=6 |
| r11/v2 | C | Ask for consent (0.725865) | constraint_violated | undetermined | None | empty_rule_constraint | cond=4, cons=29, exc=6 |
| r11/v2 | C | Ask for consent (0.725865) | exception_not_handled | undetermined | None | empty_rule_exception | cond=4, cons=29, exc=6 |
| r13/v2 | A | — | missing_action | not_applicable | 0.0 | empty_rule_action | — |
| r13/v2 | A | — | incorrect_actor | undetermined | None | empty_rule_actor_denominator | — |
| r13/v2 | A | — | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | — |
| r13/v2 | B | — | missing_action | satisfied | 0.0 | — | — |
| r13/v2 | B | — | incorrect_actor | violation | 1.0 | — | — |
| r13/v2 | B | — | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | — |
| r13/v2 | C | Ask portability third company (0.628643) | missing_action | satisfied | 0.0 | — | cond=4, cons=29, exc=6 |
| r13/v2 | C | Ask portability third company (0.628643) | incorrect_actor | violation | 1.0 | — | cond=4, cons=29, exc=6 |
| r13/v2 | C | Ask portability third company (0.628643) | out_of_order | undetermined | 0.0 | no_mapped_rule_order_endpoints | cond=4, cons=29, exc=6 |
| r13/v2 | C | Ask portability third company (0.628643) | prohibited_action_present | violation | 0.628643 | — | cond=4, cons=29, exc=6 |
| r13/v2 | C | Ask portability third company (0.628643) | required_condition_not_enforced | undetermined | None | empty_rule_condition | cond=4, cons=29, exc=6 |
| r13/v2 | C | Ask portability third company (0.628643) | constraint_violated | undetermined | None | empty_rule_constraint | cond=4, cons=29, exc=6 |
| r13/v2 | C | Ask portability third company (0.628643) | exception_not_handled | undetermined | None | empty_rule_exception | cond=4, cons=29, exc=6 |

## 4. 信息去向（P2：没抽出来，还是抽出来后在适配里丢了）

| 规则 | 组 | actions | actors | condition | constraint | exception | order_relations |
|---|---|---|---|---|---|---|---|
| r8/v2 | A | carried | not_extracted | carried | carried | not_extracted | not_extracted |
| r8/v2 | B | carried | not_extracted | carried | carried | not_extracted | not_extracted |
| r9/v2 | A | not_extracted | not_extracted | not_extracted | carried | not_extracted | not_extracted |
| r9/v2 | B | carried | carried | carried | not_extracted | not_extracted | derived_by_declared_policy |
| r10/v2 | A | carried | carried | carried | not_extracted | not_extracted | not_extracted |
| r10/v2 | B | carried | carried | carried | carried | not_extracted | not_extracted |
| r11/v2 | A | carried | carried | not_extracted | carried | not_extracted | not_extracted |
| r11/v2 | B | carried | carried | carried | not_extracted | not_extracted | derived_by_declared_policy |
| r13/v2 | A | not_extracted | not_extracted | not_extracted | carried | not_extracted | not_extracted |
| r13/v2 | B | carried | carried | not_extracted | not_extracted | not_extracted | not_extracted |

判定含义：`carried`=抽取到且进入适配记录；`not_extracted`=原始抽取里就没有；`lost_in_adaptation`=抽取到但适配后丢失；`derived_by_declared_policy`=原始无该字段、由已声明的顺序推导政策生成（不是回填答案）。

## 5. 与开发参考判断的逐条对照（① ② ④ ⑤）

| 规则 | ① 语义问题 | ② 参考判断（来源） | 主检测视角 | C 组检出 | 未检出类型 | ⑤ A→B 变化字段 |
|---|---|---|---|---|---|---|
| r8/v2 | 当前可见模型中不存在任何超时终止机制（无计时器、无边界事件、无超时分支），规则要求的“超时即终止”义务未在模型中表达 | issue_present（user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_model_structure…） | constraint_violated | 是 | — | actions, constraint |
| r9/v2 | 模型缺少“收到个人信息后进行正确性核验”的活动；外部标注的 element_label（Sign contract）只是插入位置参照 | issue_present（user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_model_activity_inventory…） | missing_action | 是 | — | actions, actor_action_pairs, actors, condition, constraint, modality, order_relations |
| r10/v2 | 当前激活活动由 Customer 执行，与 v2 要求的 Phone company 执行不一致 | issue_present（user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_model_lane_attribution…） | incorrect_actor | 是 | — | actions, actor_action_pairs, constraint |
| r11/v2 | 同意活动已存在，但位于取数与存数之后，违反规则要求的先后关系；问题性质是前置位置/顺序，而不是活动缺失 | issue_present（user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_model_flow_order…） | out_of_order | 否 | undetermined | condition, constraint, order_relations |
| r13/v2 | 把图示连线标签作为路由条件解释时，模型门槛无法阻止欠款处于 50 到 100 欧元之间的客户继续进入后续流程 | issue_present_with_premise（user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_flow_label_interval…） | required_condition_not_enforced | 否 | undetermined | actions, actor_action_pairs, actors, constraint, modality |

## 6. 误报检查（未修改原图上的检出，启发式筛查）

> 没有独立的人工合规对照，因此这里只能按**证据强度**做启发式筛查：`likely_spurious` 表示判定依赖的相似度低于 0.75（本后端无词向量，该数值不构成语义同义的证据），`incidental` 表示检出落在参考问题视角之外。这两类**不等于已证实的误报**，也不改变上面的状态与计数。

| 规则 | 检测项 | 分数 | 最强候选 | 相似度 | 与参考问题关系 | 筛查标记 |
|---|---|---|---|---|---|---|
| r8/v2 | required_condition_not_enforced | 1.0 | None | 0.0 | 参考问题视角内 | likely_spurious |
| r8/v2 | constraint_violated | 0.674966 | sid-2673F7BE-190B-4A29-B042-F26FE1273508 sid-E965697A-165F-4586-B050-908E907A73E2 sid-dcc02dd6-4d40-4a5c-9c7a-e7f2289d157a sid-23CD283E-EBC8-4855-94D0-525EC56A6361 sid-dcc02dd6-4d40-4a5c-9c7a-e7f2289d157a | 0.325034 | 参考问题视角内 | likely_spurious |
| r10/v2 | required_condition_not_enforced | 0.92683 | Requested | 0.07317 | 参考问题视角之外（附带检出） | incidental |
| r10/v2 | constraint_violated | 0.623876 | Receive SIM card | 0.376124 | 参考问题视角之外（附带检出） | incidental |
| r13/v2 | prohibited_action_present | 0.628643 | Ask portability third company | 0.628643 | 参考问题视角之外（附带检出） | incidental |

## 7. 修复对照（程序构造的最小开发对照）

> 修复正确性由**独立结构核验**判定（`independent_verification.fix_expressed`），与检测器是否识别无关；最后一列只说明方法表现。

| 修复 | 规则 | 视角 | 操作 | 独立核验：表达了修复 | C 组修复前 | C 组修复后 | 检测器是否识别 |
|---|---|---|---|---|---|---|---|
| r8_timeout_termination | r8 | constraint_violated | 增加 30 天超时边界计时器与终止分支 | 是（范围限制：任务级计时≠进程级终止） | violation | violation | 否 |
| r9_add_verification | r9 | missing_action | 在 Sign contract 之前插入核验个人信息正确性的活动 | 是 | violation | violation | 否 |
| r10_activation_owner | r10 | incorrect_actor | 把 Activate SIM card 的归属从 Customer 改为 Phone company | 是 | violation | violation | 否 |
| r11_consent_before_retrieval | r11 | out_of_order | 把同意活动移到取数之前（同意 -> 取数），并恢复 Store Data 的原后继路径 | 是 | undetermined | undetermined | 否 |
| r13_threshold_50 | r13 | required_condition_not_enforced | 把路由条件标签改为 Debt <= 50，使欠款超过 50 的客户被排除 | 是 | undetermined | undetermined | 否 |

## 8. 计数（不做七类总 F1）

| 组 | 检查数 | violation | satisfied | undetermined | not_applicable |
|---|---|---|---|---|---|
| A | 15 | 3 | 0 | 10 | 2 |
| B | 15 | 5 | 2 | 8 | 0 |
| C | 35 | 10 | 2 | 23 | 0 |

## 9. 边界

- 本结果是开发性案例分析：不是正式 Gold、不是作者原始实验复现、不是独立测试、不是企业验证。
- 单案例只给逐条结果与计数，不合成七类总 F1；5 轮预测只作稳定性证据。
- Barrientos 语料按本地只读使用，不提交其原文；修复件是程序构造的开发对照。

