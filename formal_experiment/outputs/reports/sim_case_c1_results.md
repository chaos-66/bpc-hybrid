# SIM 卡入网案例：A/B/C 三组开发性检测结果（S3.9-EXT-REAL-CASE）

- run: `sim_case_c1_run_v1`；口径：**development_case_study_not_formal_gold**（非正式 Gold、非作者原始实验复现、非企业验证）
- 主实验规则（5 条）：r8/v2, r9/v2, r10/v2, r11/v2, r13/v2；背景条目：r12
- 阈值：tau=0.8, gamma=0.8, theta=0.8, gamma_ext=0.5
- 公共 Stage 1 记录：324091aa007882ab…（扁平化 XML 29a31cfc0fa520a7…，lanes=['Phone company', 'Another phone company', 'Customer']）
- 角色绑定：{"Data Controller": "Phone company", "Data Subject": "Customer"}（打分前声明，三组共用）

## 1. 三组定义与实际组件

| 组 | Stage 2 | 原三类检测 | 四类扩展 |
|---|---|---|---|
| A | 非 LLM 确定性抽取（开发适配器） | 冻结 Sun 式（Def5-7） | 无 |
| B | 既有真实 LLM 预测（repeat-01） | 与 A 同一代码/阈值 | 无 |
| C | 与 B 完全相同 | 与 B 完全相同（复用同一结果） | 四类扩展（gamma_ext=0.5） |

## 2. 逐条结果（③ 方法实际输出）

| 规则 | 组 | missing_action | incorrect_actor | out_of_order | prohibited | condition | constraint | exception |
|---|---|---|---|---|---|---|---|---|
| r8/v2 | A | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r8/v2 | B | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r8/v2 | C | violation (1.0) | undetermined | undetermined (0.0) | undetermined | undetermined | undetermined | undetermined |
| r9/v2 | A | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r9/v2 | B | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r9/v2 | C | violation (1.0) | undetermined | undetermined (0.0) | undetermined | undetermined | undetermined | undetermined |
| r10/v2 | A | satisfied (0.0) | violation (1.0) | undetermined (0.0) | — | — | — | — |
| r10/v2 | B | satisfied (0.0) | violation (1.0) | undetermined (0.0) | — | — | — | — |
| r10/v2 | C | satisfied (0.0) | violation (1.0) | undetermined (0.0) | undetermined | violation (0.92683) | violation (0.623876) | undetermined |
| r11/v2 | A | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r11/v2 | B | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r11/v2 | C | violation (1.0) | undetermined | undetermined (0.0) | undetermined | undetermined | undetermined | undetermined |
| r13/v2 | A | violation (1.0) | undetermined | undetermined (0.0) | — | — | — | — |
| r13/v2 | B | satisfied (0.0) | violation (1.0) | undetermined (0.0) | — | — | — | — |
| r13/v2 | C | satisfied (0.0) | violation (1.0) | undetermined (0.0) | violation (0.628643) | undetermined | undetermined | undetermined |

## 3. 与开发参考判断的逐条对照（① ② ④ ⑤）

| 规则 | ① 语义问题 | ② 参考判断（来源） | 主检测视角 | C 组检出 | 未检出类型 | ⑤ A→B 变化字段 |
|---|---|---|---|---|---|---|
| r8/v2 | 当前可见模型中不存在任何超时终止机制（无计时器、无边界事件、无超时分支），规则要求的“超时即终止”义务未在模型中表达 | issue_present（user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_model_structure…） | constraint_violated | 否 | undetermined | actor_action_pairs, actors, constraint |
| r9/v2 | 模型缺少“收到个人信息后进行正确性核验”的活动；外部标注的 element_label（Sign contract）只是插入位置参照 | issue_present（user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_model_activity_inventory…） | missing_action | 是 | — | actor_action_pairs, actors, modality |
| r10/v2 | 当前激活活动由 Customer 执行，与 v2 要求的 Phone company 执行不一致 | issue_present（user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_model_lane_attribution…） | incorrect_actor | 是 | — | actor_action_pairs, actors, constraint |
| r11/v2 | 同意活动已存在，但位于取数与存数之后，违反规则要求的先后关系；问题性质是前置位置/顺序，而不是活动缺失 | issue_present（user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_model_flow_order…） | out_of_order | 否 | undetermined | actions, actor_action_pairs, modality |
| r13/v2 | 把图示连线标签作为路由条件解释时，模型门槛无法阻止欠款处于 50 到 100 欧元之间的客户继续进入后续流程 | issue_present_with_premise（user_instruction_2026_09_11_dev_policy, rule_text_v2_vs_flow_label_interval…） | required_condition_not_enforced | 否 | undetermined | actions, actor_action_pairs, modality |

## 4. 修复对照（程序构造的最小开发对照）

| 修复 | 规则 | 视角 | 操作 | C 组修复前 | C 组修复后 | 问题是否消除 |
|---|---|---|---|---|---|---|
| r8_timeout_termination | r8 | constraint_violated | 增加 30 天超时边界计时器与终止分支 | undetermined | undetermined | 否 |
| r9_add_verification | r9 | missing_action | 在 Sign contract 之前插入核验个人信息正确性的活动 | violation | violation | 否 |
| r10_activation_owner | r10 | incorrect_actor | 把 Activate SIM card 的归属从 Customer 改为 Phone company | violation | violation | 否 |
| r11_consent_before_retrieval | r11 | out_of_order | 把同意活动移到取数之前（同意 -> 取数），并恢复 Store Data 的原后继路径 | undetermined | undetermined | 否 |
| r13_threshold_50 | r13 | required_condition_not_enforced | 把路由条件标签改为 Debt <= 50，使欠款超过 50 的客户被排除 | undetermined | undetermined | 否 |

## 5. 计数（不做七类总 F1）

| 组 | 检查数 | violation | satisfied | undetermined | not_applicable |
|---|---|---|---|---|---|
| A | 15 | 5 | 1 | 9 | 0 |
| B | 15 | 5 | 2 | 8 | 0 |
| C | 35 | 8 | 2 | 25 | 0 |

## 6. 边界

- 本结果是开发性案例分析：不是正式 Gold、不是作者原始实验复现、不是独立测试、不是企业验证。
- 单案例只给逐条结果与计数，不合成七类总 F1；5 轮预测只作稳定性证据。
- Barrientos 语料按本地只读使用，不提交其原文；修复件是程序构造的开发对照。

