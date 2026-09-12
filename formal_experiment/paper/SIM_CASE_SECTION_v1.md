# 案例分析：SIM 卡入网流程（开发性案例，非正式 Gold）

> 本节数字取自 `outputs/development/sim_case_c1/run_v1/capsule.json`（`capsule.claim_scope =
> development_case_study_not_formal_gold`）与逐条核对表 `outputs/reports/sim_case_c1_checklist.md`；不新增运行、
> 不新增 API 调用、不把开发参考判断当正式 Gold。

## 1. 案例与数据来源

流程对象是 **Barrientos 的 Sun 派生 SIM 场景**，即**派生案例（derived case）**，不是 Sun 论文 §5.4 的原始图示，
也不是作者仓库中的可执行模型：本轮只读使用 `references/barrientos_2026/artifact_input/process_models/`
`SIM_card_scenario/SIM_card_scenario.bpmn`（sha256 `338c8144…`、67048 字节，`capsule.plan.inputs.bpmn`），不复制原文或原图。
规则集按任务书 v5 固定为 **5 条 v2 非空规则**：r8/v2、r9/v2、r10/v2、r11/v2、r13/v2（`capsule.plan.main_denominator`）；
**r12 作为“需求删除 + 外部 over-compliance”背景单列**，不进该分母（`capsule.plan.background_items`）；空文本条目
**r9/v1 与 r12/v2 不进入抽取与检测**（任务书 §10、核对表 §2）。全部输入只读使用，规则文本以长度与哈希绑定
（r8 92、r9 124、r10 136、r11 126、r13 88，`capsule.rules.<id>.rule_text_length`）。分组与政策在打分前写入计划：
`capsule.plan.written_before_scoring`、`capsule.plan.declared_policy.declared_before_scoring` 均为 `true`。

## 2. 方法与三组设置

### 2.1 公共 Stage 1 记录与声明的扁平化适配

三组共用同一份 Stage 1 公共记录（`capsule.stage1_public_record`）：`activities = 12`、`gateways = 6`、
`events = 8`、`flows = 26`，泳道 3 个（`Customer` / `Phone company` / `Another phone company`）；扁平化 XML 哈希
`bbfaf4d5…`、过程记录哈希 `33bccf7b…`。**必须声明的事实与后果**：冻结解析器只支持单流程，因此本案例做了
**声明的协作图扁平化适配**——原流程是三个 participant 的协作图，而冻结的 Stage 1 解析器要求单个 process，故进入
检测的是扁平化后的单流程记录。后果两点且均可观察：①修复件的模型证据里泳道被压成单一泳道
`SIM card scenario (flattened)`（`capsule.repairs[*].model_evidence.lanes`，5 个修复件全部如此），原图的三泳道参与者
边界在适配后不再作为泳道保留；②参与者的角色归属因此依赖声明的场景角色绑定（§2.3），角色类结论只在绑定政策成立
时可读。

### 2.2 三组定义与阈值

| 组 | Stage 2（规则记录来源） | 原三类检测 | 四类扩展检测 | 来源字段 |
|---|---|---|---|---|
| **A** | 非 LLM 确定性适配器：由 v2 规则文本按声明政策构造规则记录 | 冻结 Sun 式三类检测 | ✗ | `capsule.plan.groups.A` |
| **B** | 换成既有真实 LLM 抽取（该臂 repeat-01） | **与 A 完全相同的三类检测** | ✗ | `capsule.plan.groups.B` |
| **C** | **与 B 同一份 Stage 2** | **与 B 相同的三类结果** | ✓ 四类 | `capsule.plan.groups.C` |

隔离性由胶囊记录：参考判断在预测之后才读取、外部偏差标签不在检测输入中、step_3 基线只读用于比较
（`capsule.prediction_isolation` 三个布尔字段均为 `true`）；实现哈希 `capsule.implementation_hashes`
（core `61ddf99e…`、transforms `82f98dfd…`、runner `e0e24432…`）。阈值：τ = 0.8、γ = 0.8、θ = 0.8、
γ_ext = 0.5（`capsule.plan.thresholds.tau` / `.gamma` / `.theta` / `.gamma_ext`），来源为
`configs/sun_stage3_development_v1.json` + 冻结的扩展 γ（`capsule.plan.thresholds.source`）。

### 2.3 两个声明政策

**角色绑定政策**（打分前声明、三组统一）：`Data Controller → Phone company`、`Data Subject → Customer`
（`capsule.plan.declared_policy.role_binding`）；并禁止按结果新增角色绑定、动作同义词或规则 ID 特判
（`capsule.plan.declared_policy.forbidden`，2 条）。**顺序关系推导政策** `temporal_marker_from_condition_v1`：
抽出的 condition 以 before/after 时间标记开头时，在主动作与条件内动作之间生成一条顺序关系，由同一政策对 A/B/C
统一施加，不读取外部答案或偏离标签（`capsule.plan.declared_policy.order_relation_derivation`，
`applies_to_groups = [A, B, C]`）。该政策实际产出为空：全部行的规则侧顺序关系合计 **0** 条（核对表 §4），这直接
导致顺序类检查一律无法判断。

## 3. 结果

### 3.1 逐条状态表（规则 × 检测项 × 状态）

状态取 `violation` / `satisfied` / `undetermined`（`capsule.rows[*].status`）；四类检查仅 C 组启用，
“—”表示该组未做；`U(<code>)` 表示 `undetermined`，括注为 `capsule.rows[*].reason` 的机器值（表下给含义）。

| 规则 | 检测项 | A | B | C |
|---|---|---|---|---|
| r8 | missing_action | violation | violation | violation |
| r8 | incorrect_actor | U(action_mapping_below_gamma) | U(empty_rule_actor_denominator) | U(empty_rule_actor_denominator) |
| r8 | out_of_order | U(no_mapped_rule_order_endpoints) | U(no_mapped_rule_order_endpoints) | U(no_mapped_rule_order_endpoints) |
| r8 | prohibited_action_present | — | — | U(rule_modality_not_prohibition) |
| r8 | required_condition_not_enforced | — | — | U(action_mapping_below_gamma) |
| r8 | constraint_violated | — | — | U(action_mapping_below_gamma) |
| r8 | exception_not_handled | — | — | U(empty_rule_exception) |
| r9 | missing_action | violation | violation | violation |
| r9 | incorrect_actor | U(empty_rule_actor_denominator) | U(action_mapping_below_gamma) | U(action_mapping_below_gamma) |
| r9 | out_of_order | U(no_mapped_rule_order_endpoints) | U(no_mapped_rule_order_endpoints) | U(no_mapped_rule_order_endpoints) |
| r9 | prohibited_action_present | — | — | U(rule_modality_not_prohibition) |
| r9 | required_condition_not_enforced | — | — | U(action_mapping_below_gamma) |
| r9 | constraint_violated | — | — | U(empty_rule_constraint) |
| r9 | exception_not_handled | — | — | U(empty_rule_exception) |
| r10 | missing_action | satisfied | satisfied | satisfied |
| r10 | incorrect_actor | violation | violation | violation |
| r10 | out_of_order | U(no_mapped_rule_order_endpoints) | U(no_mapped_rule_order_endpoints) | U(no_mapped_rule_order_endpoints) |
| r10 | prohibited_action_present | — | — | U(rule_modality_not_prohibition) |
| r10 | required_condition_not_enforced | — | — | violation |
| r10 | constraint_violated | — | — | violation |
| r10 | exception_not_handled | — | — | U(empty_rule_exception) |
| r11 | missing_action | violation | violation | violation |
| r11 | incorrect_actor | U(action_mapping_below_gamma) | U(action_mapping_below_gamma) | U(action_mapping_below_gamma) |
| r11 | out_of_order | U(no_mapped_rule_order_endpoints) | U(no_mapped_rule_order_endpoints) | U(no_mapped_rule_order_endpoints) |
| r11 | prohibited_action_present | — | — | U(rule_modality_not_prohibition) |
| r11 | required_condition_not_enforced | — | — | U(action_mapping_below_gamma) |
| r11 | constraint_violated | — | — | U(empty_rule_constraint) |
| r11 | exception_not_handled | — | — | U(empty_rule_exception) |
| r13 | missing_action | violation | satisfied | satisfied |
| r13 | incorrect_actor | U(action_mapping_below_gamma) | violation | violation |
| r13 | out_of_order | U(no_mapped_rule_order_endpoints) | U(no_mapped_rule_order_endpoints) | U(no_mapped_rule_order_endpoints) |
| r13 | prohibited_action_present | — | — | violation |
| r13 | required_condition_not_enforced | — | — | U(empty_rule_condition) |
| r13 | constraint_violated | — | — | U(empty_rule_constraint) |
| r13 | exception_not_handled | — | — | U(empty_rule_exception) |

原因码含义（均为 `capsule.rows[*].reason`）：`no_mapped_rule_order_endpoints` = 规则侧顺序关系缺端点（15 行同因）；
`action_mapping_below_gamma` = 动作映射低于 γ；`empty_rule_actor_denominator` = 规则侧执行者字段为空；
`empty_rule_condition` / `empty_rule_constraint` / `empty_rule_exception` = 规则侧对应字段为空；
`rule_modality_not_prohibition` = 情态不是 prohibition。C 组三类行另带 `inherited_from = "B"` 与
`reuses_group_b = ["stage2", "three_type_rows"]`，即三类结果逐字节复用 B（5 条规则全部如此）。

### 3.2 计数表与 C 组构成

| 组 | 检查数 | violation | undetermined | satisfied | 来源字段 |
|---|---|---|---|---|---|
| A | 15 | 5 | 9 | 1 | `capsule.summary.A` |
| B | 15 | 5 | 8 | 2 | `capsule.summary.B` |
| C | 35 | 8 | 25 | 2 | `capsule.summary.C` |

**C 组构成必须写明**：C 含 **15 条继承自 B 的三类检查**（5 条规则 × 3 类）与 **20 条新增四类检查**
（5 条规则 × 4 类：`prohibited_action_present`、`required_condition_not_enforced`、`constraint_violated`、
`exception_not_handled`），15 + 20 = 35 与 `capsule.summary.C.checks` 一致；新增行均带 `added_by =
"four_extended_types"`。四类候选面固定：条件 4 条、约束 29 条、例外 6 条（`capsule.rules.<id>.sides.C.surfaces.*`）。

### 3.3 数值明细（供核对）

- **r8**：`missing_action` A/B/C 均 score 1.0、denominator 1、最佳模型动作相似度 0.7524；C 组
  `required_condition_not_enforced` / `constraint_violated` / `exception_not_handled` 候选数 4 / 29 / 6，score 为 null。
- **r9 / r10 / r11**：四类中未判定的行（r9 与 r11 的 `required_condition_not_enforced`、`constraint_violated`，
  r10 的 `exception_not_handled`）score 均为 null；r9/r11 的候选数分别为 4 与 29，r10 为 6；`missing_action` 方面
  r9 为 score 1.0（相似度 0.4219）、r11 为 score 1.0（A 侧 0.6042、B/C 侧 0.7401）。
- **r10**：`missing_action` A/B/C 均 score 0.0、denominator 1、相似度 0.8582；`incorrect_actor` A 组 score 1.0、
  denominator 1、最小参与者相似度 0.3898，B/C 组 score 1.0、最小参与者相似度 0.3334；C 组
  `required_condition_not_enforced` score 0.92683（best_candidate `Requested`、max_sim 0.07317）、
  `constraint_violated` score 0.623876（best_candidate `Receive SIM card`、max_sim 0.376124）。
- **r13**：`missing_action` A 组 score 1.0、相似度 0.5844，B/C 组 score 0.0、相似度 0.8524；`incorrect_actor`
  B/C 组 score 1.0、denominator 1、最小参与者相似度 0.3442；C 组 `prohibited_action_present` score 0.628643
  （best_candidate `Ask portability third company`、max_sim 0.628643）。四类映射活动：r8 → `Send SIM card`（0.804544）、
  r11 → `Ask for consent`（0.725865）、r9 与 r13 均 → `Ask portability third company`（0.388024 / 0.628643）；以上取
  `capsule.rows[*]` 与 `capsule.rules.<id>.sides.<group>`，未列出的四类 undetermined 行 score 均为 null。

### 3.4 实际检出、无法判断，以及与开发参考判断的一致性

- **实际检出（三类）**：r9 的 `missing_action`（A/B/C 均 violation，1.0）、r10 的 `incorrect_actor`（A/B/C 均
  violation，1.0）、r10 的 `missing_action`（三组均 satisfied，0.0）、r13 的 `missing_action`（B/C satisfied，0.0）。
- **实际检出（四类，仅 C）**：r13 的 `prohibited_action_present`（violation，0.628643）、r10 的
  `required_condition_not_enforced`（violation，0.92683）、r10 的 `constraint_violated`（violation，0.623876）；
  其余 17 条四类检查全部 undetermined。
- **与开发参考判断的一致性**：参考判断为“问题存在”的 5 条规则中，r9、r10、r13 在 C 组
  `found_corresponding_problem = true`；r8 与 r11 为 `false` 且 `all_lenses_undetermined = true`、
  `miss_kind = "undetermined"`（`capsule.comparison[*].consistency`），其三类型视角在 A 与 B 均为 `covered_lenses = []`。
  **“无法判断”没有被当作合规**：不可判行保留在分母与计数中并与判定结果同时呈现（A 9、B 8、C 25 条，§3.2）。

## 4. 阶段差异

### 4.1 A → B：规则记录的变化字段与归因

A→B 的每处变化都归因为**抽取（extraction）**，5 条规则的 `attribution` 全为 `extraction`（`capsule.stage_attribution.a_to_b.<id>`）。

| 规则 | A→B 变化字段 | 变化要点 | 归因 |
|---|---|---|---|
| r8 / r10 | actors、actor_action_pairs、constraint | r8 的 actors 变为 `[]`、constraint 变为 `more than 30 days`；r10 的 actor 由 `the customer` 变为 `the phone company` | extraction |
| r9 | modality、actors、actor_action_pairs | modality 变为 `obligation`；actors 由 `[]` 变为 `["it"]`（代词） | extraction |
| r11 / r13 | modality、actions、actor_action_pairs | r11 的 actions 变为 `ask the Data Subject for consent`；r13 的 modality 变为 `prohibition`、actions 改为 `receive new SIM cards` | extraction |

可见后果：r9 的 `incorrect_actor` 由 `empty_rule_actor_denominator` 变为 `action_mapping_below_gamma`（actor 抽成
代词 `it`）；r13 的 `missing_action` 由 violation 变为 satisfied（0.5844 → 0.8524）；r13 的 `incorrect_actor` 由
undetermined 变为 violation（0.3442）。计数上 undetermined 由 9 降到 8、satisfied 由 1 升到 2
（`capsule.summary.A.status_counts` / `capsule.summary.B.status_counts`）。

### 4.2 B → C：只是新增检测能力

B→C 不改变 Stage 2，也不改变三类结果：C 组三类行全部 `inherited_from = "B"` 且逐字节复用
（`capsule.stage_attribution.b_to_c`）。因此 B→C 的全部计数差（检查数 15 → 35、violation 5 → 8、undetermined
8 → 25）都来自新增的 20 条四类检查（3 条 violation：r10 两条、r13 一条；17 条 undetermined）。

## 5. 修复对照

5 个最小修复件在运行前固定（`data/development/sim_case_c1/repair_specs_v1.json`，`status = fixed_before_run`），原始
BPMN 永不修改，修复后的 XML 只在 gitignored 本地目录生成；下表“修复前”取 B 组、“修复后”取 C 组
（`capsule.repairs[*].group_B` / `.group_C`），行内 `U(...)` 为 undetermined 及其 `after_reason`。

| 修复件 | 最小操作 | 修复前（B） | 修复后（C） | 是否消除 |
|---|---|---|---|---|
| r8_timeout_termination | 在 `Send SIM card` 上挂 30 天边界计时器并连到终止事件 | 该检查 B 组未做（before 为 null） | U(action_mapping_below_gamma) | 否 |
| r9_add_verification | 在 `Sign contract` 之前插入核验个人信息正确性的活动 | violation (1.0) | violation (1.0) | 否 |
| r10_activation_owner | 把 `Activate SIM card` 的泳道归属由 `Customer` 改为 `Phone company` | violation (1.0) | violation (1.0) | 否 |
| r11_consent_before_retrieval | 把 `Ask for consent` 移到取数之前并恢复 `Store Data` 的后继 | U(score 0.0) | U(score 0.0) | 否 |
| r13_threshold_50 | 把该连线标签由 `Debt < 100` 改为 `Debt <= 50` | 该检查 B 组未做（before 为 null） | U(empty_rule_condition) | 否（5 条 `problem_removed` 均为 `false`） |

对**未消除**的条目，原因可具体定位：

- **r8**：修复件确实改了模型结构（事件 8 → 10、流程 26 → 27，`capsule.repairs[0].model_evidence`），但检测侧依旧
  `action_mapping_below_gamma`——**结构面已补、检测面仍不可读**；该检查在 B 组的修复前为 null（未做），故只有 C 组可
  比较。**r9**：修复件新增 1 个活动（12 → 13、流程 26 → 27，`capsule.repairs[1].model_evidence`），但 B/C 侧最佳模型
  动作仍是 `Ask portability third company`（0.4219），低于 γ，仍为 violation。**r10**：泳道归属被移动后最小参与者
  相似度由 0.3898 变为 0.3334（`capsule.rules.r10.sides.A` 对比 B 侧 `incorrect_actor.details`），**数值有变化但结论
  仍为 violation**。
- **r11**：修复件调整了顺序（`rewire_flow` + `add_sequence_flow` + `remove_sequence_flow`），结论仍是
  `no_mapped_rule_order_endpoints`——**规则侧该政策未产出任何顺序关系**，顺序检查缺规则侧端点，与模型侧如何改无关。
  **r13** 标签改为 `Debt <= 50` 后仍报 `empty_rule_condition`，即**规则侧条件字段无条件**，标签修改在这条路径上无法
  体现。**r8 与 r11 的 C 组部分四类检查**也停在 `action_mapping_below_gamma`：冻结 Def6 的 min-over-{actors ∪
  business objects} 口径加上没有词向量后端，动作映射无法越过 γ；r13 的 `required_condition_not_enforced`、r9/r11 的
  `constraint_violated` 则因规则侧对应字段为空而无从比较。

## 6. 未解决限制

1. **无有效正常对照时误报未被充分检验。** 对照只做到“5 个最小修复件的修复前后比较”（`capsule.repairs`），而
   5 条 `problem_removed` 全为 `false`、两条修复件的“修复前”为 null；因此**没有任何一条能当作“问题已消除”的
   正常对照**，本节**不得声称零误报**，误报检查覆盖止于：C 组 3 条四类 violation（r10 两条、r13 一条）与全部
   satisfied 结论（r10 的 `missing_action` 三组、r13 的 B/C 两条）。外部 `step_3_baseline` 则是**需求变更语境**的
   答案键，不是静态合规检查的天然答案键（核对表 §2、任务书 §3.5），本案例只把它当作来源冲突与阅读辅助。
2. **r13 的 50 / 100 / 500 三方冲突**：需求 v2 阈值 50、模型标签 `Debt < 100`、外部修复建议 `Debt < 500`（不采用）；
   `50 < debt < 100`（例 75）是模型未落实 v2 限制的差异区间；模型没有可执行 `conditionExpression`，条件只以连线标签
   存在（核对表 §2 `numeric_boundary_policy_r13`、§3 “conditionExpression **0**”）。**r11 的外部标注与模型事实不符**：
   外部把该条记为活动缺失，而同意活动在流程中已存在，问题性质是前置位置/顺序（核对表 §5 r11 行“冲突”列、任务书
   §3.5 第 2 条）；本节只陈述冲突，不据此改动流程。**Sun 正文与 Figure 10 的 R2/R4 冲突且正式版未取得**：本地两种
   读法在 R2 与 R4 之间互换分类，正式版本轮核对失败（付费墙/机构认证），两种读法都只作为文献原始声明，均不作可靠
   Gold（核对表 §7）。
3. **相似度后端无词向量**：规则—模型动作匹配只有字符串相似度，没有词向量后端；这解释了多处
   `action_mapping_below_gamma`，属能力限制而非结论（核对表 §6 的 `consent_before_retrieval_order` 为 partial，
   理由是 LLM 抽取 0 条 order_relations）。**扁平化适配的影响**：进入检测的是扁平化单流程记录，三泳道参与者边界被压成
   单一泳道（`capsule.repairs[*].model_evidence.lanes`），结构计数在修复前后一致（12 活动 / 6 网关 / 26 流程），但
   角色归属结论依赖声明的角色绑定而非泳道名，只在绑定政策成立时可读。

## 7. 可引用表述与不可声称

### 7.1 可直接引用的表述（每条附证据指向）

1. “在该 SIM 派生案例上，A、B、C 三组分别产生 15、15、35 条（规则 × 检查）记录，A 组为 violation 5 条、undetermined
   9 条、satisfied 1 条。” —— `capsule.summary.A.checks`、`capsule.summary.A.status_counts`。
2. “把 Stage 2 由非 LLM 确定性适配换成真实 LLM 抽取后，规则记录的变化集中在 modality、actors、
   actor_action_pairs、actions、constraint，5 条规则的归因全部为抽取（extraction）。”
   —— `capsule.stage_attribution.a_to_b.<id>.changed_fields` 与 `.attribution`。
3. “C 组没有改动 Stage 2 与三类检测，只新增四类检查：15 条三类行逐字节继承自 B，另加 20 条四类行。”
   —— `capsule.stage_attribution.b_to_c`、`capsule.rows[*].inherited_from`、`capsule.rows[*].added_by`。
4. “顺序类检查在本案例无法判定：全部行的规则侧顺序关系合计 0 条，检测报 `no_mapped_rule_order_endpoints`。”
   以及“四类扩展只新增 3 条有证据的 violation（r10 的 `required_condition_not_enforced` 与 `constraint_violated`、
   r13 的 `prohibited_action_present`），其余 17 条四类检查为 undetermined。” —— 前者见 核对表 §4、
   `capsule.rows[*].reason`（15 行同因）；后者见 `capsule.rows` 中 `added_by = "four_extended_types"` 的行、
   `capsule.summary.C.status_counts`。

### 7.2 不可声称清单

1. **不是作者原始实验的复现**：流程对象是 Sun 派生案例（`capsule.claim_scope`）。**不是正式 Gold**：参考判断是
   开发参考判断（核对表 §5 表下注、§8），本节不作性能结论。**不是独立测试**：1 个流程、5 条规则、1 个案例，且无
   正常对照（§6.1）。**不是企业验证**：修复件是程序构造的开发对照（`repair_specs_v1.json` 的 `note_zh`）。
2. **不得写“七类总 F1”或任何跨类合成指标**：本节只给逐条状态与计数（任务书 §6、§10 指标口径）。
3. **不得把 5 轮重复当独立样本**：SIM 真实预测是 10 条独立输入 × 5 轮重复 = 50 行，且 5 轮抽取结果完全一致
   （核对表 §4）；本节只用预先固定的 repeat-01 作为 B/C 组来源（核对表 §2 政策、`capsule.plan.groups.B`）。

## 8. 补充案例：Sun Figure 10 重建模型（只写范围与缺项）

**范围**：对象是**重建模型（reconstructed model）**——按 Sun 等（2024）Figure 10 与论文叙述重建的
`data/development/sim_case_c1/sun_figure10_reconstruction.bpmn`。该重建件**已存在**，并**已通过解析与 schema 校验**：
解析输出 activities 11 / gateways 4 / events 5，`validate_process_record` 返回 `valid=True`（`schema_valid=True`、
`cross_field_valid=True`、`errors=[]`）；文件 sha256 `773c4691…`、26673 字节，另含顺序流 20 条、消息流 14 条、
数据关联 4 条、participant 3 个、lane 3 个、collaboration 1 个，`cycle_detected = False`
（`sun_figure10_reconstruction_provenance.md` §10）。它**不是**作者原始文件，**不得**称为 “Sun original” 或 “exact Sun”
（同文件 §1、§11）；Figure 10 上的四个 violation 标注框不进入模型，因为它们是论文的检查结果而非流程内容（同文件 §1、§8）。

**缺项（如实列出）**：①**LLM 组缺失及原因——未做**：论文 Table 13 的规则文本与仓库中既有预测输入的规则文本不一致，
在完成一致性核验前**不得复用**这些预测作为该补充案例的 Stage 2。②**因此本补充案例只完成非 LLM 基线部分**；LLM 组、
四类扩展、A/B/C 三组对照与修复对照在本补充案例上均**未做**。③**本轮未运行，缺项如实列出**：本节没有该补充案例的
任何 A/B/C 运行证据或计数，故不给出任何状态计数、相似度或一致性结论，一律记为**未做/缺失**，待规则文本一致性核验
与非 LLM 基线实际运行后再补。④**须随文披露的歧义**：论文正文（p.23）与 Figure 10 标注（p.24）在 R2 与 R4 的分类上
互换，两套读法都不作为可靠 Gold（同文件 §9、核对表 §7）。
