# 案例分析：SIM 卡入网流程（派生案例，开发性案例研究，非正式 Gold）

> 本节全部数字取自当前运行胶囊 `formal_experiment/outputs/development/sim_case_c1/run_v1/capsule.json`（run `sim_case_c1_run_v1`；`capsule.claim_scope = development_case_study_not_formal_gold`），每个数字后括注来源字段；渲染报告 `formal_experiment/outputs/reports/sim_case_c1_results.md` 仅作一致性参照。本轮不新增运行、不新增 API/LLM 调用、不修改任何输入，缺失项一律写“未做/缺失”。

## 1. 案例与数据来源

流程对象是 **Barrientos 的 Sun 派生 SIM 场景**，即**派生案例（derived case）**：它不是 Sun 论文 §5.4 的原始图示，也不是作者仓库中的可执行模型；本轮只读使用其 BPMN 文件（sha256 `338c8144…`、67048 字节，`capsule.plan.inputs.bpmn.sha256` / `.bytes`）。规则输入为需求文件（sha256 `e13d9a2a…`、1707 字节，`capsule.plan.inputs.requirements.sha256` / `.bytes`）；外部答案键 `step_3_baseline.json`（sha256 `96b3c1e8…`，`capsule.plan.inputs.step_3_baseline.sha256`）只读且只用于比较；开发参考判断存 `data/development/sim_case_c1/case_items_v2.json`（sha256 `a5324734…`、12037 字节，`capsule.plan.inputs.curated_reference_judgments`），方法输出单独成胶囊，二者分开存放。

主实验规则集固定为 **5 条 v2 非空规则**：r8/v2、r9/v2、r10/v2、r11/v2、r13/v2（`capsule.plan.main_denominator`，5 项）；**r12 只作“需求删除 + 外部 over-compliance”背景单列**，不进该分母（`capsule.plan.background_items`，1 项）；空文本条目 **r9/v1 与 r12/v2 不进入抽取与检测**（任务书 §10 已决事项，胶囊侧体现为上述 5 项分母与 1 项背景）。规则文本以长度与哈希绑定：r8 92、r9 124、r10 136、r11 126、r13 88 字符（`capsule.rules.<id>.rule_text_length`）；全部输入只读，不复制原文或原图。

分组、阈值、角色绑定与顺序推导政策均在打分前写入计划（`capsule.plan.written_before_scoring = true`、`capsule.plan.declared_policy.declared_before_scoring = true`）；输入隔离由三个布尔记录：参考判断在预测之后才读取、外部偏差标签不在检测输入中、`step_3_baseline` 只读用于比较（`capsule.plan.prediction_isolation.reference_judgments_read_after_predictions` / `.external_deviations_not_in_detection_input` / `.step_3_baseline_read_only_for_comparison`，均为 `true`）。

## 2. 方法与三组设置

### 2.1 公共 Stage 1 记录与声明的协作图扁平化适配

三组共用同一份 Stage 1 公共记录（`capsule.plan.stage1_public_record`）：activities 12、gateways 6、events 8、flows 26，泳道 3 个（`Phone company` / `Another phone company` / `Customer`）；扁平化 XML 哈希 `29a31cfc…`、过程记录哈希 `324091aa…`（`capsule.plan.stage1_public_record.flattened_xml_sha256` / `.process_record_sha256`）。

**必须随文声明的适配事实**：冻结的 Stage 1 解析器只接受单个 process，而原流程是多 participant 的协作图，因此进入检测的是**声明的协作图扁平化**结果——参与者边界以**命名泳道**保留（3 个泳道名即三个 participant 名，`capsule.plan.stage1_public_record.lanes`），而 **collaboration 下的 message flow 未建模**（任务书 §11 第 8 行；胶囊内**没有消息流计数字段，未做/缺失**）。该适配的后果是：跨参与者的角色归属只能依赖声明的角色绑定（§2.3），角色类结论仅在绑定成立时可读。

### 2.2 三组设置

| 组 | Stage 2（规则记录来源） | 三类检测 | 四类扩展检测 | 来源字段 |
|---|---|---|---|---|
| **A** | 项目锁定非 LLM 基线 B0 v10a：入口 `bpc_hybrid.estg150_b0_development_v10.run_b0_batch_v10`、`PROFILE_V10A`（CoreNLP + Tregex + BERT-TextCNN） | 冻结 Sun 式 `sun_stage3.sun_scorer.SunScorer`（Def5-7） | `not run` | `capsule.plan.components.A.stage2` / `.A.stage3` |
| **B** | 既有真实 LLM 预测 `outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-01`，经 `bpc_hybrid.gdpr_s2_s3_projection.project_external_sentence` 投影 | 与 A **同一代码与阈值** | `not run` | `capsule.plan.components.B.stage2` / `.B.stage3` |
| **C** | 与 B 完全相同（同一行对象，`identical to B (same row objects)`） | 三类行逐行复用 B（`identical rows reused from B`） | `RepairedExtendedScorerV2`（v3 = EvidenceChecksV3 γ 0.8、标签回退 0.4、γ_ext 0.5）+ `aggregate_with_comparison_gate` | `capsule.plan.components.C.stage2` / `.C.stage3` |

**必须披露的语言边界**：A 组的 Stage 2 是英文句子经由**德语合同分类器槽**（`English sentences through the German-contract classifier slot`，`capsule.plan.components.A.stage2.language_boundary`）；A 组 5 条规则的 `stage2_meta.source` 均为 `sun_rule_only_b0_v10a`（`capsule.rules.<id>.sides.A.stage2_meta.source`），其基线胶囊为 `outputs/development/sim_case_c1/stage2_baseline_v1/capsule.json`（sha256 `cd13e08a…`、17358 字节，`capsule.plan.inputs.stage2_baseline_capsule`）；B 组预测输入文件 sha256 `6fab1108…`、63932 字节（`capsule.plan.inputs.predictions_repeat01`），本轮只用**预先固定的 repeat-01**，不择优、不把重复当独立样本。A 组规则记录由**公共适配政策**构造，其中按声明的角色绑定把场景角色写回记录（例如 r11 的 `sides.A.sentence.actor_bound_from = "Data Controller"` 被绑定为 `Phone company`，`capsule.rules.r11.sides.A.sentence`）。

相似度后端为 `bpc_hybrid.winter_stage3.winter_similarity.WinterSimilarity`（`nlp = en_core_web_sm`），行为是 `Doc.similarity over context-sensitive tensors`（spaCy W007：模型不带静态词向量）——**它不是字符串相似度，也不是静态向量相似度**（`capsule.plan.components.similarity_backend`）。实现哈希：core `6f9679c0…`、transforms `a7e34eb0…`、runner `abd16969…`（`capsule.plan.implementation_hashes`）。

### 2.3 阈值、角色绑定与顺序推导政策

- **阈值**：τ = 0.8、γ = 0.8、θ = 0.8、γ_ext = 0.5、标签回退 γ = 0.4（`capsule.plan.thresholds.tau` / `.gamma` / `.theta` / `.gamma_ext` / `.label_fallback_gamma`），来源 `configs/sun_stage3_development_v1.json + REPAIR-V2 arm C configuration`（`capsule.plan.thresholds.source`）。
- **角色绑定**（打分前声明、三组统一）：`Data Controller → Phone company`、`Data Subject → Customer`（`capsule.plan.declared_policy.role_binding`，2 对）；同时声明 2 条禁止项：不得按结果新增角色绑定、动作同义词或规则 ID 特判，不得用外部偏差标签或参考判断回填规则记录（`capsule.plan.declared_policy.forbidden`）。
- **顺序推导政策** `temporal_marker_from_condition_v2`，`comma_handling = comma_optional_v2`（`capsule.plan.declared_policy.order_relation_derivation.name` / `.comma_handling`）：当抽出的 condition 以 before/after 时间标记开头时，在主动作与条件内动作之间生成一条顺序关系（`Before X, Y` → (Y, X)；`After X, Y` → (X, Y)），端点取逗号前的条件片段，**没有逗号时取整个条件片段**（两种写法语义相同）；非时间标记条件（if / when 等）不生成顺序关系。该政策对 A/B/C 三组统一施加（`…order_relation_derivation.applies_to_groups`，3 项），不读取任何外部答案或偏离标签；其 v1 要求条件片段含逗号，而本案例的抽取结果没有逗号，导致 r9/r11 在三组都报 `no_mapped_rule_order_endpoints`，v2 改为逗号可选（`…order_relation_derivation.fix_note_zh`）。

## 3. 结果

### 3.1 逐条状态表（规则 × 检查 × 组）

表中状态来源字段为 `capsule.rows[*].status`（35 行），括号内为 `capsule.rows[*].score`；`U(...)` 表示 `undetermined`，括号内为 `capsule.rows[*].reason` 的机器值；`n/a(...)` 表示 `not_applicable`；`—` 表示该组未做该检查（A/B 组 `four_types = not run`，`capsule.plan.components.A.stage3.four_types` / `.B.stage3.four_types`）。列名与检查名对应：`prohibited` = `prohibited_action_present`、`condition` = `required_condition_not_enforced`、`constraint` = `constraint_violated`、`exception` = `exception_not_handled`。

| 规则 | 组 | missing_action | incorrect_actor | out_of_order | prohibited | condition | constraint | exception |
|---|---|---|---|---|---|---|---|---|
| r8/v2 | A | violation (1.0) | U(empty_rule_actor_denominator) | U(no_mapped_rule_order_endpoints) | — | — | — | — |
| r8/v2 | B | violation (1.0) | U(empty_rule_actor_denominator) | U(no_mapped_rule_order_endpoints) | — | — | — | — |
| r8/v2 | C | violation (1.0) | U(empty_rule_actor_denominator) | U(no_mapped_rule_order_endpoints) | U(rule_modality_not_prohibition) | violation (1.0) | violation (0.674966) | U(empty_rule_exception) |
| r9/v2 | A | n/a(empty_rule_action) | U(empty_rule_actor_denominator) | U(no_mapped_rule_order_endpoints) | — | — | — | — |
| r9/v2 | B | violation (1.0) | U(action_mapping_below_gamma) | U(no_mapped_rule_order_endpoints) | — | — | — | — |
| r9/v2 | C | violation (1.0) | U(action_mapping_below_gamma) | U(no_mapped_rule_order_endpoints) | U(rule_modality_not_prohibition) | U(label_argmax_below_action_gamma) | U(empty_rule_constraint) | U(empty_rule_exception) |
| r10/v2 | A | violation (1.0) | U(action_mapping_below_gamma) | U(no_mapped_rule_order_endpoints) | — | — | — | — |
| r10/v2 | B | satisfied (0.0) | violation (1.0) | U(no_mapped_rule_order_endpoints) | — | — | — | — |
| r10/v2 | C | satisfied (0.0) | violation (1.0) | U(no_mapped_rule_order_endpoints) | U(rule_modality_not_prohibition) | violation (0.92683) | violation (0.623876) | U(empty_rule_exception) |
| r11/v2 | A | violation (1.0) | U(action_mapping_below_gamma) | U(no_mapped_rule_order_endpoints) | — | — | — | — |
| r11/v2 | B | violation (1.0) | U(action_mapping_below_gamma) | U(no_mapped_rule_order_endpoints) | — | — | — | — |
| r11/v2 | C | violation (1.0) | U(action_mapping_below_gamma) | U(no_mapped_rule_order_endpoints) | U(rule_modality_not_prohibition) | U(v3_localization_undetermined) | U(empty_rule_constraint) | U(empty_rule_exception) |
| r13/v2 | A | n/a(empty_rule_action) | U(empty_rule_actor_denominator) | U(no_mapped_rule_order_endpoints) | — | — | — | — |
| r13/v2 | B | satisfied (0.0) | violation (1.0) | U(no_mapped_rule_order_endpoints) | — | — | — | — |
| r13/v2 | C | satisfied (0.0) | violation (1.0) | U(no_mapped_rule_order_endpoints) | violation (0.628643) | U(empty_rule_condition) | U(empty_rule_constraint) | U(empty_rule_exception) |

C 组的三类行与 B 组完全一致并带 `inherited_from = "B"`，四类行带 `added_by = "four_extended_types"`（`capsule.rows[*].inherited_from` / `.added_by`）。四类候选面在 5 条规则上固定：条件候选 4 条、约束候选 29 条、例外候选 6 条（`capsule.rules.<id>.sides.C.surfaces.condition_candidates` / `.constraint_candidates` / `.exception_candidates`）。

### 3.2 哪些是 violation、哪些是 undetermined、哪些是 not_applicable

**violation（有证据）**：A 组 3 条（`capsule.summary.A.status_counts.violation`）——r8 `missing_action`（1.0）、r10 `missing_action`（1.0）、r11 `missing_action`（1.0）；B 组 5 条（`capsule.summary.B.status_counts.violation`）——r8 `missing_action`（1.0）、r9 `missing_action`（1.0）、r10 `incorrect_actor`（1.0）、r11 `missing_action`（1.0）、r13 `incorrect_actor`（1.0）；C 组 10 条（`capsule.summary.C.status_counts.violation`）= 继承 B 的 5 条 + 四类新增 5 条：r8 `required_condition_not_enforced`（1.0）与 `constraint_violated`（0.674966）、r10 `required_condition_not_enforced`（0.92683）与 `constraint_violated`（0.623876）、r13 `prohibited_action_present`（0.628643）（`capsule.rows[*]`）。

**satisfied**：B 组 2 条、C 组 2 条（`capsule.summary.B.status_counts.satisfied` / `.C.status_counts.satisfied`）——r10 `missing_action` 与 r13 `missing_action`，分数均为 0.0（`capsule.rows[*]`）。

**not_applicable（A 组 2 条，`capsule.summary.A.status_counts.not_applicable`）**：r9 `missing_action` 与 r13 `missing_action`，机器原因均为 `empty_rule_action`（`capsule.rows[*].reason`）。其含义是 **A 组规则记录没有动作字段**：B0 v10a 对 r9、r13 的原始抽取动作为 0 条（`capsule.rules.r9.chain.groups.A.field_flow.actions.raw_count`、`capsule.rules.r13.chain.groups.A.field_flow.actions.raw_count` 均为 0，`verdict = not_extracted`），因此该检查没有规则侧单位——这是“规则侧无对象”，不等于“模型合规”，也不等于“问题不存在”。

**undetermined（A 组 10、B 组 8、C 组 23 条，`capsule.summary.<组>.status_counts.undetermined`）** 的机器原因分布如下（逐行取自 `capsule.rows[*].reason`）：

| 机器原因 | A | B | C |
|---|---|---|---|
| `no_mapped_rule_order_endpoints` | 5 | 5 | 5 |
| `empty_rule_actor_denominator` | 3 | 1 | 1 |
| `action_mapping_below_gamma` | 2 | 2 | 2 |
| `rule_modality_not_prohibition` | 0 | 0 | 4 |
| `empty_rule_exception` | 0 | 0 | 5 |
| `empty_rule_constraint` | 0 | 0 | 3 |
| `label_argmax_below_action_gamma` | 0 | 0 | 1 |
| `v3_localization_undetermined` | 0 | 0 | 1 |
| `empty_rule_condition` | 0 | 0 | 1 |

不可判断的行**没有被当作合规**：它们保留在分母与计数中并与判定结果同时呈现（`capsule.summary.<组>.checks` 与 `capsule.summary.<组>.status_counts`）。

### 3.3 计数表、C 组构成与门控输出

| 组 | 检查数 | violation | satisfied | undetermined | not_applicable | 来源字段 |
|---|---|---|---|---|---|---|
| A | 15 | 3 | 0 | 10 | 2 | `capsule.summary.A` |
| B | 15 | 5 | 2 | 8 | 0 | `capsule.summary.B` |
| C | 35 | 10 | 2 | 23 | 0 | `capsule.summary.C` |

**C 组构成必须写明**：C 含 **15 条继承自 B 的三类检查**（5 条规则 × 3 类）与 **20 条新增四类检查**（5 条规则 × 4 类），15 + 20 = 35 与 `capsule.summary.C.checks` 一致。四类扩展的映射活动为：r8 → `New client acquired`（0.446202）、r9 → `Ask portability third company`（0.388024）、r10 → `Send SIM card`（0.804544）、r11 → `Ask for consent`（0.725865）、r13 → `Ask portability third company`（0.628643）（`capsule.rules.<id>.sides.C.mapped_activity.name` / `.similarity`）。C 组门控输出（`capsule.rules.<id>.sides.C.gate`）如下：

| 规则 | `predicted` | 证据比较次数 | 禁止比较执行 | `all_unobservable` |
|---|---|---|---|---|
| r8/v2 | `required_condition_not_enforced` | 2 | false | false |
| r9/v2 | null | 0 | false | true |
| r10/v2 | `required_condition_not_enforced` | 2 | false | false |
| r11/v2 | null | 0 | false | true |
| r13/v2 | `prohibited_action_present` | 0 | true | false |

即：r8、r10 的判定**执行过 2 次证据比较**；r9、r11 无任何可观测类型（`all_unobservable = true`，比较次数 0）；r13 只做了禁止类比较（`prohibition_comparison_performed = true`）。门控统一声明 `explicit_compliance_requires_an_evidence_comparison = true`，即“明确合规必须有一次证据比较”。

## 4. 信息去向（没抽出来，还是抽出来后在适配里丢了）

下表逐字段给出 A/B 两组的去向判定（`capsule.rules.<id>.chain.groups.<A|B>.field_flow.<字段>.verdict`），括号内为该字段的 `raw_count`（原始抽取条数）。判定含义：`carried` = 抽到且进入适配记录；`not_extracted` = 原始抽取里就没有；`derived_by_declared_policy` = 原始无该字段、由已声明的顺序推导政策生成（不是回填答案）；`lost_in_adaptation` = 抽到但适配后丢失。C 组的 `chain.groups.C.field_flow` 为空对象（`capsule.rules.<id>.chain.groups.C.field_flow`），因为它逐行复用 B。

| 规则 | 组 | actions | actors | condition | constraint | exception | order_relations |
|---|---|---|---|---|---|---|---|
| r8/v2 | A | carried(1) | not_extracted(0) | carried(1) | carried(1) | not_extracted(0) | not_extracted(0) |
| r8/v2 | B | carried(1) | not_extracted(0) | carried(1) | carried(1) | not_extracted(0) | not_extracted(0) |
| r9/v2 | A | not_extracted(0) | not_extracted(0) | not_extracted(0) | carried(1) | not_extracted(0) | not_extracted(0) |
| r9/v2 | B | carried(1) | carried(1) | carried(1) | not_extracted(0) | not_extracted(0) | derived_by_declared_policy(0) |
| r10/v2 | A | carried(2) | carried(1) | carried(2) | not_extracted(0) | not_extracted(0) | not_extracted(0) |
| r10/v2 | B | carried(1) | carried(1) | carried(1) | carried(1) | not_extracted(0) | not_extracted(0) |
| r11/v2 | A | carried(1) | carried(1) | not_extracted(0) | carried(1) | not_extracted(0) | not_extracted(0) |
| r11/v2 | B | carried(1) | carried(1) | carried(1) | not_extracted(0) | not_extracted(0) | derived_by_declared_policy(0) |
| r13/v2 | A | not_extracted(0) | not_extracted(0) | not_extracted(0) | carried(1) | not_extracted(0) | not_extracted(0) |
| r13/v2 | B | carried(1) | carried(1) | not_extracted(0) | not_extracted(0) | not_extracted(0) | not_extracted(0) |

三条必须点明的后果：

1. **B0 基线对 r9 与 r13 未抽出任何动作**（`capsule.rules.r9.chain.groups.A.field_flow.actions` 与 `capsule.rules.r13.chain.groups.A.field_flow.actions`：`raw_count = 0`、`verdict = not_extracted`）。这直接对应 A 组两条 `not_applicable / empty_rule_action`（§3.2），也解释了为什么 A 组在这两条规则上无法给出动作类结论。
2. **LLM 臂的原始输出没有任何顺序关系**：B 组 5 条规则的 `order_relations.raw_count` 全为 0，其中 r9 与 r11 的顺序关系由已声明政策补出（`verdict = derived_by_declared_policy`，`capsule.rules.r9.chain.groups.B.field_flow.order_relations.verdict`、`capsule.rules.r11.chain.groups.B.field_flow.order_relations.verdict`），另外 3 条为 `not_extracted`。因此 r9/r11 的顺序断言来自**政策**而不是抽取结果；即便如此，三组的 `out_of_order` 仍全部报 `no_mapped_rule_order_endpoints`（§3.1），说明瓶颈在端点映射而不在该政策是否产出关系。
3. **本案例没有任何字段被判为 `lost_in_adaptation`**：A/B 两组全部 60 个字段判定只出现 `carried`、`not_extracted`、`derived_by_declared_policy` 三种（`capsule.rules.<id>.chain.groups.<组>.field_flow`）。A 与 B 的字段值差异（§5）来自两次**抽取**结果不同，不是适配丢失；可对照的细节是 r10 的 A 组 actions `raw_count = 2` 而 B 组为 1（`capsule.rules.r10.chain.groups.A.field_flow.actions.raw_count` 与 `…groups.B…`），以及 r9/r11 的 condition 与 constraint 在两组之间互换（A 有 constraint 无 condition，B 有 condition 无 constraint）。

## 5. 阶段差异

### 5.1 A → B：变化字段与归因

A→B 的每处变化都归因为**抽取（extraction）**，5 条规则的 `attribution` 全为 `extraction`（`capsule.stage_attribution.a_to_b.<id>.attribution`）。

| 规则 | A→B 变化字段 | 变化要点的读法 | 归因 |
|---|---|---|---|
| r8/v2 | actions、constraint | actions 由被动不定式（`be terminated`）变为被动分词（`terminated`）；constraint 由含 `for any reason` 的长片段收缩为纯时限片段 | extraction |
| r9/v2 | modality、actions、actors、actor_action_pairs、condition、constraint、order_relations | modality 由 definition 变 obligation；actions/actors 由空变为核验动作与**代词**执行者；条件类片段由 constraint 槽移入 condition 槽 | extraction |
| r10/v2 | actions、actor_action_pairs、constraint | actions 由带角色的长片段收缩为纯动作片段；constraint 由空变为目的性片段 | extraction |
| r11/v2 | condition、constraint、order_relations | 时间标记条件由 constraint 槽移入 condition 槽；order_relations 由空变为 1 条 | extraction |
| r13/v2 | modality、actions、actors、actor_action_pairs、constraint | modality 由 definition 变 prohibition；actions/actors 由空变为禁止动作与其主体片段；constraint 由非空变空（数值门槛转入 actor 片段） | extraction |

字段级细节见 `capsule.stage_attribution.a_to_b.<id>.detail`。可见后果：r9 的 `incorrect_actor` 由 `empty_rule_actor_denominator` 变为 `action_mapping_below_gamma`（执行者抽成代词）；r13 的 `missing_action` 由 `not_applicable` 变为 `satisfied`（0.0）、`incorrect_actor` 由 `empty_rule_actor_denominator` 变为 `violation`（1.0）；r10 的 `missing_action` 由 violation 变为 satisfied。计数上 undetermined 由 10 降到 8、satisfied 由 0 升到 2（`capsule.summary.A.status_counts` 对比 `capsule.summary.B.status_counts`）。

### 5.2 B → C：只新增四类检查，三类行逐字复用

B→C 不改变 Stage 2，也不改变三类结果：胶囊原文为 `group C adds exactly the four extended checks on the SAME rule side as B; three-type rows are reused byte-identically (reuses_group_b)`（`capsule.stage_attribution.b_to_c`），5 条规则的 `sides.C.reuses_group_b` 均为 `["stage2", "three_type_rows"]`（`capsule.rules.<id>.sides.C.reuses_group_b`）。因此 B→C 的全部计数差（检查数 15 → 35、violation 5 → 10、undetermined 8 → 23，`capsule.summary.B` 对比 `capsule.summary.C`）都来自新增的 20 条四类检查（5 条 violation、15 条 undetermined），与三类检测的代码、阈值和规则侧记录无关。

## 6. 修复对照

5 个最小修复件在运行前固定（`data/development/sim_case_c1/repair_specs_v1.json`，`status = fixed_before_run`），原始 BPMN 永不修改。修复**是否正确表达**由独立结构核验判定（`fix_expressed`），与检测器是否识别无关；下表“修复前/后”取 C 组（`capsule.repairs[*].group_C.before_status` / `.before_score` 与 `.after_status` / `.after_score` / `.after_reason`），`problem_removed` 取 `capsule.repairs[*].group_C.problem_removed`。

| 修复件 | 规则 | 视角 | 最小操作 | 独立结构核验 | C 组修复前 | C 组修复后 | `problem_removed` |
|---|---|---|---|---|---|---|---|
| `r8_timeout_termination` | r8 | `constraint_violated` | 在 `Send SIM card` 上挂 30 天边界计时器（`P30D`）并新增终止结束事件与连线 | `fix_expressed = true`（`boundary_event` / `timer_definition` / `has_termination_path` 均 true） | violation (0.674966) | violation (0.663005) | false |
| `r9_add_verification` | r9 | `missing_action` | 在 `Sign contract` 之前插入核验任务并改接前驱流 | `fix_expressed = true`（`activity_present` / `reachable_from_request_personal_data` / `reaches_sign_contract` 均 true） | violation (1.0) | violation (1.0) | false |
| `r10_activation_owner` | r10 | `incorrect_actor` | 把 `Activate SIM card` 由 `Customer` 泳道移入 `Phone company` 泳道 | `fix_expressed = true`（`lane = Phone company = expected_lane`） | violation (1.0) | violation (1.0) | false |
| `r11_consent_before_retrieval` | r11 | `out_of_order` | 把 `Ask for consent` 移到取数之前并恢复 `Store Data` 的后继路径 | `fix_expressed = true`（`consent_reaches_retrieval = true`、`retrieval_reaches_consent = false`） | U(0.0) | U(0.0, `no_mapped_rule_order_endpoints`) | false |
| `r13_threshold_50` | r13 | `required_condition_not_enforced` | 把路由连线标签 `Debt < 100` 改为 `Debt <= 50` | `fix_expressed = true`（`new_label_present = true`、`old_label_present = false`） | U(null) | U(null, `empty_rule_condition`) | false |

结构计数上，修复确实改变了模型：r8 的事件由 8 增至 10、流程由 26 增至 27；r9 的活动由 12 增至 13、流程增至 27；其余三条保持 12 活动 / 6 网关 / 8 事件 / 26 流程（`capsule.repairs[*].model_evidence.activities` / `.events` / `.flows`，对照 `capsule.plan.stage1_public_record`）。

**r8 修复件的范围限制（原文含义照录）**：`independent_verification.scope = task_scoped_timeout`、`scope_matches_rule_semantics = false`——计时器挂在**单个任务**（`Send SIM card`）上，它表达的是“发卡任务超时即中断”，而规则要求的是“**整个流程**耗时超过 30 天则终止流程”；在扁平化单流程模型里，进程级超时需要重构控制流（如事件子流程或事件网关包住全流程），已超出“最小修复”的范围，因此本修复件只**部分**表达该要求，检测结果按此前提解读（`capsule.repairs[0].independent_verification.scope_note_zh`）。

**结论**：5 个修复件的 `fix_expressed` **全为 `true`**（`capsule.repairs[*].independent_verification.fix_expressed`），即修复**确实表达了**对应修复意图；而同一批修复件的 `problem_removed` **全为 `false`**、C 组状态在修复前后完全不变（`capsule.repairs[*].group_C`），即**检测器一个都没有识别出来**。两件事必须并列陈述：前者由独立结构核验判定，后者只是方法表现在本案例下的观察结果。另需注明：r8 与 r13 的两条检查在 B 组本来就没做，其 `capsule.repairs[*].group_B.before_status` 为 null，只有 C 组可比较。

## 7. 未解决限制

1. **规则—模型映射受 γ 与相似度后端限制。** 阈值 γ = 0.8（`capsule.plan.thresholds.gamma`），而后端是**无静态词向量的 tensor 相似度**（`capsule.plan.components.similarity_backend.behaviour`，spaCy W007），因此低于 γ 的数值不构成语义不同义的证据。被该限制直接命中的行（`capsule.rules.<id>.sides.<组>.checks.<检查>.details[0].similarity` / `.best_candidate` / `.max_sim`）：r8 `missing_action` 最佳模型动作 `Ask portability`（0.5308）与 `Sign contract`（0.7524）、r9 `missing_action` `Ask portability third company`（0.4219）、r10 A 组 `missing_action` `Activate SIM card`（0.691）与 B/C 组同项（0.8582）、r11 `missing_action` `Ask for consent`（0.7401）、r13 B/C `missing_action` `Receive SIM card`（0.8524），以及 r8 C 组 `constraint_violated` 的 `max_sim = 0.325034`、r10 C 组 `required_condition_not_enforced` 的 `max_sim = 0.07317` 与 `constraint_violated` 的 `max_sim = 0.376124`。
2. **没有独立的人工合规对照，误报只能启发式筛查。** 胶囊内**没有**独立人工合规对照字段（**未做/缺失**），也没有误报筛查标签（**未做/缺失**）；`capsule.plan.prediction_isolation` 的 3 个布尔只说明输入隔离，不构成合规对照。渲染报告 §6 记录的启发式筛查不在本胶囊字段内，故本节**不得声称零误报**，也不得把“未被筛查标出”当作“已证实合规”。
3. **r13 的 50 / 100 冲突区间。** 规则侧 50 € 门槛在 A 组记录中以 constraint 形式出现（`capsule.rules.r13.sides.A.rule.constraint`），在 B/C 组记录中该字段为空、数值门槛落在 actor 片段（`capsule.rules.r13.sides.B.rule.actors`）；模型侧条件只以连线标签 `Debt < 100` 存在（`capsule.rules.r13.sides.C.surfaces.condition_candidates`）。因此 `50 < debt < 100`（例 75）落在“规则要求排除、模型门槛放行”的差异区间；外部 mitigation 的第三个数值（任务书记为 `Debt < 500`）**在胶囊内未记录**（胶囊只以 `capsule.comparison[4].reference_sources` 的 `…mitigation_not_adopted` 标记其未被采用）→ 该数值**未做/缺失**，本节不采用、不引用。
4. **r11 的外部标签与模型事实不一致。** 胶囊记录外部把该条记为活动缺失（`capsule.comparison[3].reference_sources` 含 `external_step3_change_context:missing_activity_label_disagreed`），而参考判断本身写明同意活动**已存在**、问题是前置位置/顺序（`capsule.comparison[3].semantic_issue_zh`）；模型侧也确实映射到 `Ask for consent`（0.725865，`capsule.rules.r11.sides.C.mapped_activity`）。方法侧的顺序检查仍报 `no_mapped_rule_order_endpoints`（`capsule.rows`），故本节只陈述冲突，不据此改动流程。
5. **Sun 正文与 Figure 10 的 R2–R4 冲突，且正式版不可取得。** 主胶囊没有该字段（**未做/缺失**）；补充胶囊 `sim_case_c1_supplement_v1` 记录两种读法在 R2 与 R4 上互换（`SupplementCapsule.plan.paper_readings.text` / `.figure` / `.conflict_zh`），并说明正式版本轮未取得。两种读法都只作文献原始声明，均不作可靠 Gold。
6. **扁平化适配丢失消息流。** 任务书 §11 第 8 行记：扁平化只保留 process 子元素，消息流位于 collaboration 下、未建模；参与者边界以命名泳道保留。胶囊侧可观察的是 3 个泳道名与结构计数（`capsule.plan.stage1_public_record.lanes`、`.activities` / `.gateways` / `.events` / `.flows`），而**消息流条数在胶囊内未记录（未做/缺失）**。角色归属类结论因此依赖声明的角色绑定（`capsule.plan.declared_policy.role_binding`），只在绑定政策成立时可读。

## 8. 可引用表述与不可声称清单

### 8.1 可直接引用的表述（每条附胶囊字段）

1. “在该 SIM 派生案例上，A、B、C 三组各产生 15、15、35 条（规则 × 检查）记录；A 组为 violation 3、undetermined 10、not_applicable 2，B 组为 violation 5、satisfied 2、undetermined 8，C 组为 violation 10、satisfied 2、undetermined 23。”—— `capsule.summary.A` / `capsule.summary.B` / `capsule.summary.C`。
2. “把 Stage 2 由项目锁定非 LLM 基线换成既有真实 LLM 抽取后，规则记录的变化全部归因于**抽取**：5 条规则的 `attribution` 均为 `extraction`，变化字段为 r8 [actions, constraint]、r9 [actions, actor_action_pairs, actors, condition, constraint, modality, order_relations]、r10 [actions, actor_action_pairs, constraint]、r11 [condition, constraint, order_relations]、r13 [actions, actor_action_pairs, actors, constraint, modality]。”—— `capsule.stage_attribution.a_to_b.<id>.changed_fields` 与 `.attribution`。
3. “C 组没有改动 Stage 2 与三类检测，只新增四类检查：三类行逐字复用 B（`reuses_group_b = ["stage2", "three_type_rows"]`、`inherited_from = "B"`），另加 20 条四类行（`added_by = "four_extended_types"`）。”—— `capsule.stage_attribution.b_to_c`、`capsule.rules.<id>.sides.C.reuses_group_b`、`capsule.rows[*]`。
4. “5 个最小修复件的独立结构核验 `fix_expressed` 全为 `true`，说明修复确实表达了修复意图；同一批修复件的 `problem_removed` 全为 `false`，C 组状态在修复前后完全不变。”—— `capsule.repairs[*].independent_verification.fix_expressed`、`capsule.repairs[*].group_C`。
5. “顺序断言在本案例不可判定：规则侧顺序关系在三组都缺端点，5 条规则 × 3 组的 `out_of_order` 全部报 `no_mapped_rule_order_endpoints`；LLM 臂原始输出中 `order_relations` 的 `raw_count` 全为 0，r9/r11 的关系由已声明政策补出。”—— `capsule.rows[*].reason`、`capsule.rules.<id>.chain.groups.B.field_flow.order_relations`。

### 8.2 不可声称清单

1. **不是作者原始实验的复现**：流程对象是 Sun 派生案例，`capsule.claim_scope = development_case_study_not_formal_gold`。
2. **不是正式 Gold**：参考判断是开发参考判断，与检测器能力解耦，只存于 `case_items_v2.json`（`capsule.plan.inputs.curated_reference_judgments`），本节不作性能结论。
3. **不是独立测试**：1 个流程、5 条规则、1 个案例，且胶囊内没有独立人工合规对照（**未做/缺失**）。
4. **不是企业验证**：修复件是程序构造的最小开发对照（`repair_specs_v1.json` 的 `note_zh` 与 `status = fixed_before_run`），不是真实企业流程。
5. **不得给出“七类总 F1”或任何跨类合成指标**：本节只给逐条状态与计数（`capsule.rows`、`capsule.summary`）。
6. **5 轮重复不是独立样本**：B/C 组只使用预先固定的 repeat-01（`capsule.plan.components.B.stage2.source`、`capsule.plan.inputs.predictions_repeat01`），不择优、不合并 5 轮。
7. **“检测器没识别”不等于“流程没修复”**：5 条 `fix_expressed` 为 `true` 而 `problem_removed` 为 `false`（`capsule.repairs[*]`），两件事必须并列陈述。

## 9. 补充案例：Sun Figure 10 重建模型（只写范围与缺项）

**范围**：对象是**重建模型（reconstructed model）**，按 Sun 等（2024）Figure 10 重建，存于 `data/development/sim_case_c1/sun_figure10_reconstruction.bpmn`（sha256 `773c4691…`、26673 字节，`SupplementCapsule.plan.inputs.reconstruction`）；`claim_scope = development_supplement_reconstructed_model_not_authors_model`（`SupplementCapsule.claim_scope`）。该重建件**已存在并已被解析**：activities 11、gateways 4、events 5、flows 20、泳道 3 个、`unreachable = 3`（`SupplementCapsule.model_evidence`）。它不是作者原文件，**不得**称为 “Sun original” 或 “exact Sun”。

**缺项（如实列出）**：

1. **真实 LLM 组缺失**（`SupplementCapsule.plan.groups_missing.B`；C 组随 B 一并缺失，`…groups_missing.C`）：原因是论文 Table 13 的规则文本与已绑定预测的规则串**不一致**——4 条映射的 `reusable` **全为 `false`**（`SupplementCapsule.plan.prediction_reuse_audit[*].reusable`；`exact_text_match` 4 条均为 `false`，`normalised_text_match` 3 条 `true`、1 条 `false`），而 span 偏移绑定在原始字符串上，故在一致性核验完成前不得复用（`…prediction_reuse_audit[*].reason`）。
2. **本轮该补充案例只运行了 A 组**（`SupplementCapsule.plan.groups_run.A`，1 组）；B/C 对照、四类扩展与修复对照**未做/缺失**。按“只写范围与缺项”的要求，本节不复述该补充运行的任何计数，也不把它并入主案例的表格。
3. **本轮未授权重跑**：本节没有新的运行证据，规则文本一致性核验与 LLM 组补跑均**未做/缺失**，待授权后另起批次。
