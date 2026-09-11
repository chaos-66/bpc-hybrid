# 任务书（提案）：真实案例 Stage 1 → Stage 3 端到端示例（S3.9-EXT-REAL-CASE）

> **状态：PROPOSED — 未授权、未登记、未执行。**
> 本文只是方案与验收标准的提案，供用户审阅。它**不是** pipeline 任务行、**不是**状态页、
> **不是**实验结论。在用户明确批准前，不写代码、不跑运行、不改任何 Gold / 合同 / 门禁 / 预测。
> 批准后按 §11 完成治理登记（MASTER_PIPELINE §9.5 新行 + AGENT_RUNBOOK prompt +
> PROJECT_AUDIT 派工行），届时本文降级为该任务的附件设计说明。
>
> 日期：2026-09-11　范围：`formal_experiment/`　真实 API 调用：**0**
>
> **v3 修订（2026-09-11，用户确认 Sun §5.4 案例路线后）**：新增 **Case C = Sun et al. (2024) §5.4 案例研究
> （电话公司 SIM 卡入网）**，并确定 **C-E2 为主（本地 Sun 派生 SIM 场景 + 机器可读答案键）、
> C-E1 为补充（按 Figure 10 重建 BPMN 做忠实复刻）**。§3.4 给出实测答案键与类型映射，
> §9 新增 B5/B6 批次与 B5 入口检查（版本绑定）。
>
> **v2 修订**：v1 曾把"真实规则 → 六要素绑定器"列为新增模块；只读契约测绘证明**不需要**——
> 四类检查器（`ExtendedViolationScorer`）与外部预测投影（`gdpr_s2_s3_projection.project_external_sentence`）
> 都已存在，缺的只是"把它们接到真实原图"的 runner。

---

## 1. 为什么需要这个任务（问题陈述）

用户要求：**拿一张真实的业务流程图和一套真实的法律法规，从第一阶段跑到第三阶段，看结果**；
并在后续澄清中指出：**具体指的是 Sun et al. (2024) §5.4 案例研究**那个实验
（电话公司获取新客户／SIM 卡入网流程 × Table 13 的 R1–R4 → Figure 10 的 Violation 1–4）。

现状核实结论（2026-09-11，只读核对）：

1. **这条链没有做过**：
   - Stage 1：7 张 GDPR BPMN 的**我方解析器 Process Record** 已存在（人工 Process Gold 已发布）；
   - Stage 2：9 条 GDPR 条款 / 74 句的 **Rules-Only（B0 v10a）真实预测**已跑（74/74，零 API），
     人工确认的 92 条规范条目 → 正式 Gold Rule Records 已发布；
   - Stage 3：真实规则记录 + 真实 BPMN 上只跑过**原三类**的 33 个人工 Gold 项
     （`s3_real_rule_diagnostic_v1`：Sun 与 v3 结果完全相同，missing_action 10 violation + 1 unknown，
     incorrect_actor 11 unknown，out_of_order 11 unknown）。
2. **Stage 3 从来没有读过我们的 Stage 1 产物**：`grep stage1_gdpr7_process_records_v1` 在
   `scripts/run_s3_*` 中零命中；现有真实输入的三类臂（`run_gdpr_3type_linkage_v1.py --arm human_rules`、
   `run_s3_oracle_gold_rules_v1.py`）都是**重新解析 BPMN**，而不是消费 Stage 1 记录。
3. **四类扩展在真实原图上没有判定路径**：所有四类 runner 都只在
   `data/development/stage3_synth/<vid>/<side>/<pid>.bpmn` 上打分；真实原图只进过 TF-IDF 拟合语料
   或作为"对照侧误报计数"。
4. **Sun §5.4 案例的输入缺口**：Table 13 的 R1–R4 有原文；但 **Figure 10 的流程模型没有任何本地机器可读副本**——
   官方 supplement 的三份本地副本（`references/winter_2020_model_check`、`references/合规性检查模型代码`、
   `archive/external_metadata/sun_program_macos`）的 `input/models/` 只有 7 个 GDPR 模型；
   全仓库唯一的 SIM BPMN 属 Barrientos artifact。

## 2. 目标与非目标

**目标**

- **G1**：对选定的真实 (流程, 法规/规则) 组合，用**我方 Stage 1 产物 + 我方 Stage 2 产物 + 现有 Stage 3 检查器**，
  产出逐检查判定：`violation` / `compliant` / `unobservable` / `not_applicable` + 原因码 + 证据。
- **G2**：让**四类扩展违规**第一次在真实原图 + 真实规则上被消费，如实报告哪些类型在该案例的
  流程表面上可判、哪些不可判（附原因码）。
- **G3**：对比不同 Stage 2 规则来源（Rules-Only 预测 vs 人工确认 Gold Rule Records vs 已有真实 LLM 预测）
  对最终判定的影响，逐检查给出变化与归类（抽取 / 投影 / 检测）。
- **G4**：产出可复核的机器 JSON + 人类可读案例报告，作为论文案例章节的**开发级**素材。
- **G5（v3 新增）**：Case C 与**外部答案键**对照——Barrientos artifact 的
  `evaluation/ground_truth/step_3_baseline.json`（机器可读偏差）+ 两位 compliance expert 标注 +
  Winter et al. 2020 在该语料上的结果 + 我们已有的 1140 次真实 LLM 预测（含 11 条 SIM 记录）。

**非目标（明确不做）**

- 不做正式 Oracle、不做 S3.7 主表、不做端到端误差传播（S3.10）、不做 Stage 3 冻结（S3.11）；
- 不修改 33 条人工 Gold、25 条 matching Gold、40 对合成面板、任何冻结 BPMN、阈值、公式、原因枚举；
- **不修改冻结抽取器与 `gdpr_capsule_converter`**（已确认不需要；确需改动时停止实现并先改任务书）；
- 不为本案例搜索阈值、不加白名单/同义词/ID 特判、不新增合成变体；
- 不评价 detection 指标（单案例样本不足以算 P/R/F1）；
- 不调用真实 LLM/API（Case C 复用已授权的 1140 次运行产物；其余默认不跑）。

## 3. 案例选择（实测数据，非预判）

### 3.1 Case A：`gdpr_2_consent_to_use_the_data` × `article22`（v013–v015）

流程有 24 activities / 6 events（含 intermediateCatchEvent）/ 15 gateways（exclusive、eventBased、parallel）；
article22 项是 33 项里**唯一**同时具备 prohibition 子句（2）与非零 condition 候选（2）的，
另有 38 constraint / 25 exception 候选 → 四类均可进入判定。

### 3.2 Case B：`gdpr_1_data_breach` × `article33` / `article34`（论文主锚，作为对照）

实测：`condition_candidates=0`、`constraint_candidates=25`、`exception_candidates=3`；
article33/34 的 Gold 中 prohibition 子句 = **0**。因此：

- `prohibited_action_present` → 必然 `unobservable: rule_modality_not_prohibition`；
- `required_condition_not_enforced` → 必然 `unobservable: no_condition_candidates`（有名网关与 `72 hours`
  计时器都在 subProcess 内部）；
- `constraint_violated` / `exception_not_handled` 在规则动作映射 ≥ gamma 时可判。

### 3.3 Case C：Sun et al. (2024) §5.4 案例研究（SIM 卡入网）—— 本任务的核心案例

**C-E2（主路线）：本地 Sun 派生 SIM 场景 + 机器可读答案键**

资产（`references/barrientos_2026/`，只读）：

| 用途 | 路径 |
|---|---|
| 流程模型 | `artifact_input/process_models/SIM_card_scenario/SIM_card_scenario.bpmn`（+ 同名 PDF） |
| 需求（规则） | `artifact_input/requirements/SIM_card_scenario/SIM_card_scenario.json`（r8–r13 × v1/v2） |
| **机器可读答案键** | `evaluation/ground_truth/step_3_baseline.json`：每条需求 `deviations[] = {type, bpmn_element, element_label}` + `mitigation_action` |
| 变更推理答案键（可选） | `evaluation/ground_truth/step_2_baseline.json`（`changes`） |
| 需求表示答案键（可选） | `evaluation/ground_truth/step_1_baseline.json`（`precondition` / `norm`，含 v1/v2） |
| 专家标注 | `evaluation/annotations_from_compliance_experts/`（两位 expert + protocol） |
| 前人结果对照 | `evaluation/results_from_Winter_et_al_2020/` |
| 我方真实 LLM 预测（已在手） | `outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-01..05`（36 条，含 **11 条 SIM**；2026-08-29 授权的 1140 次运行） |

**SIM 答案键（实测 6 条）与类型映射**：

| 需求 | `type` | `bpmn_element` | 涉及元素 | 映射到我们的类型 | 与 Sun 论文的关系 |
|---|---|---|---|---|---|
| r8 | non_compliant | `missing_timer` | process termination | **constraint_violated** | ≈ Sun R1（超 30 天终止） |
| r9 | non_compliant | `missing_activity` | Sign contract | missing_action | — |
| r10 | non_compliant | `wrong_role` | Activate SIM card | **incorrect_actor** | ≈ Sun R3（激活者错误） |
| r11 | non_compliant | `missing_activity` | Request personal data | missing_action | ≈ Sun R4（取数前同意） |
| r12 | over_compliant | `redundant_activity` | Delete personal data | **过度合规，不在我们七类**（必须单列，不得计为漏检） | — |
| r13 | non_compliant | `XOR_condition_modification` | Debt < 100 | **required_condition_not_enforced** | — |

全语料（20 条需求）偏差种类 → 我们的七类：

| 外部 `bpmn_element` | 我们 | 出现在 |
|---|---|---|
| `missing_activity` | missing_action | 三场景 |
| `wrong_role` | incorrect_actor | emergencies、SIM |
| `sequence_constraint_removal` | out_of_order | **仅 emergencies** |
| `missing_timer`、`time_constraint_removal`、`time_constraint_relaxation` | constraint_violated | SIM、emergencies、blood |
| `XOR_condition_modification`、`missing_XOR`、`XOR_removal` | required_condition_not_enforced | 三场景 |
| `redundant_activity`、`unexpected_activity`、`redundant_constraint` | **不在我们分类（过度合规）** | 三场景 |
| — | **exception_not_handled** | **答案键中没有真实实例**（如实报告为空缺，不编造） |

**C-E1（补充路线）：按 Figure 10 忠实复刻**

- 从论文 Figure 10（本地 PDF 第 24 页）按图重建 BPMN，活动集合与顺序照图；
  Table 13 的 R1–R4 用原文规则文本；
- 重建件必须：通过 `validate_process_record` 结构校验、在报告中标注为
  **reconstructed from the published figure（非作者原文件）**；
- **必须同时给出两种答案键读法**：论文正文版（R1、R4 = missing action；R2 = out-of-order；R3 = incorrect actor）
  与 Figure 10 标注版（V1/R1、V2/R2 = missing action；V3/R3 = incorrect actor；V4/R4 = out-of-order）——
  两者在 R2/R4 上互换，复刻结果按两种口径分别报，不择一当作唯一真值；
- 本地 PDF 按合同登记为**预印本**，报告需注明"以本地版本为准，正式版可能不同"。

### 3.4 案例组合建议

**B + A（GDPR 七流程）+ C（SIM）**：B 给论文主锚的诚实结果（含两类结构性不可判），A 给四类全可跑的演示，
C 给**带外部答案键**的论文案例对照。只做其一时，C 的信息量最大。

> 案例选择是**内容决定**，不是结果决定：先按表面/答案键是否支持该类型检查选，再看结果；
> 不可判就如实报告，不换案例凑结论。

## 4. 输入与复用清单（全部已存在；契约已核实）

| 用途 | 路径 / 符号 | 复用方式 |
|---|---|---|
| Stage 1 流程记录（我方） | `data/development/human_review/stage1_gdpr7_process_records_v1.json` | **直接可用，无需适配器**：7 条记录与按冻结合同重新解析逐项 canonical 相等，schema 校验通过，`process_id` 与 Stage 3 使用键一致 |
| 流程模型对象 | `src/bpc_hybrid/sun_stage3/sun_model.py` `SunProcessModel(process_id, record, nlp)` | 原样复用（可达关系 71–75 行） |
| 原始 XML（四类候选面） | 记录内 `source.path` → `ET.fromstring(...)` | 原样复用 |
| Stage 2 来源 ①（真实预测） | `data/predictions/gdpr7_sun_rule_only_v1/predictions.json` | 原三类走 `gdpr_capsule_converter.build_rule_records(..., ("obligation",))` |
| 四类要素投影（缺的那根线） | `src/bpc_hybrid/gdpr_s2_s3_projection.py` `project_external_sentence()` | **原样复用**；目前唯一调用方是合成面板 runner |
| Stage 2 来源 ②（人工确认） | `gdpr7_human_confirmed_v1/confirmed_rule_items.json`、`data/gold/stage3/gdpr7_gold_rule_records_v1.json` | 只读；clause span 切片对齐 `run_s3_oracle_gold_rules_v1.py:236–241` |
| Stage 2 来源 ③（Case C 真实 LLM） | `outputs/development/barrientos_ablation_suite_v2/OURS-FULL/repeat-01..05/canonical_predictions.jsonl` | 只读复用（11 条 SIM 记录），**零新增 API** |
| 三类检查器 | `sun_stage3/sun_scorer.py`、`s3_evidence_checks_v1.py`、`s3_action_matching_v2/v3.py` | 原样复用 |
| 四类检查器 | `src/bpc_hybrid/stage3_extended_violations.py`、`s3_extended_evidence_scope_v1.py` | 原样复用（四值版本用 `ScopedEvidenceScorer`） |
| 打分循环样板 | `scripts/run_s3_extended_repair_v2_v1.py:289–382` | 复制形态，不导入面板逻辑 |
| 真实原图三类基线（可比对） | `run_gdpr_3type_linkage_v1.py --arm human_rules`、`run_s3_oracle_gold_rules_v1.py` | 只读比对 |
| 既有真实诊断口径 | `outputs/development/s3_real_rule_diagnostic_v1/`、`..._corrections_v1/` | 引用其两套覆盖口径，不新造 |
| Case C 外部资产 | `references/barrientos_2026/**`（见 §3.3） | **只读**；不得再分发（见 §7.6） |

**真正新增的只有**：1 个 runner、1 个输出 schema、1 个测试文件、1 个 Case C 答案键适配/对照模块
（把 `deviations[].bpmn_element` 映射到我们的七类并生成对照表；不含任何推断）。

## 5. 方法设计

### 5.1 新增：`scripts/run_real_case_s3_v1.py`（约 250–350 行）

- 组合维度：`(case, rule_source, method, check_type)`；method ∈ {sun_2024_frozen, evidence_checks_v3,
  winter-style, bm25, tfidf}；check_type ∈ 3 原三类 + 4 扩展类；
- 流程侧：Stage 1 记录 → `SunProcessModel`；Case C 的流程侧为 SIM BPMN（或 C-E1 的重建件）；
- 规则侧：按 §4 三条路径构造；
- 逐检查输出：四值判定 + 原因码 + 证据（文本/ID/hash）+ 目标活动/网关/事件 ID；
- **逐 requirement 证据**（见 §7.5）；
- `plan.json` 打分前写盘并绑定实现哈希；`--check` / `--replay` 只读模式；no-overwrite。

### 5.2 新增：`configs/schemas/stage3_extended_prediction.schema.json`

现有 `stage3_prediction.schema.json` 的 `predicted_violation_type` 枚举**只有原三类**，四类结果无法通过校验；
需新增一个显式 development 的 schema（沿用 `stage3_extended_prediction@1.0.0` 形状 + 运行级判定字段）。

### 5.3 新增：Case C 答案键对照模块与报告

- 输入：`step_3_baseline.json` 的 `deviations[]`（+ 可选 step_1/step_2 与专家标注）；
- 输出：逐需求对照表（外部偏差种类 ↔ 我们的检查类型 ↔ 我们的判定 ↔ 是否一致 ↔ 原因），
  并把 `over_compliant`（`redundant_activity` 等）**单列**为"不在本分类体系内"；
- **不做任何推断映射以外的补齐**：外部没有的实例（如 exception）就报空缺。

### 5.4 复用边界（不得顺手改）

`stage1_formal_dataset.build_formal_process_records`、`stage1_process.parse_bpmn_bytes/validate_process_record`、
`sun_model.SunProcessModel`、`sun_scorer.SunScorer`、`s3_action_matching_v3.EvidenceChecksV3`、
`gdpr_capsule_converter.*`、`gdpr_s2_s3_projection.project_external_sentence`、
`stage3_extended_violations.*`、`s3_extended_evidence_scope_v1.ScopedEvidenceScorer`、
`winter_similarity.WinterSimilarity`、`evaluate_stage3_common`、`s3_extended_unified`、
`control_prediction_from_scores` / `aggregate_scope_verdicts`
一律**只读复用**。确需改动时：停止实现 → 更新本任务书 → 取得用户批准。

### 5.5 四值与原因语义

| 判定 | 含义 |
|---|---|
| `violation` | 证据支持下落判违规（附证据） |
| `compliant` | 该检查**真正比较过**且未发现违规（比较门：condition/constraint/exception 至少一项实际比较过） |
| `unobservable` | 规则元素为空 / 动作低于 gamma / 候选面为空 / 流程表面不存在（附原因码） |
| `not_applicable` | 规则本身没有该元素（第三种状态，不得与 unknown 混算） |

禁止：`unknown` 与 `not_applicable` 合并统计；把 `none` 解释为"整条流程法律合规"。

### 5.6 Case C 的 B5 入口检查（不确定就停）

实现前必须先确定并记录：

1. **版本绑定**：`step_3_baseline.json` 的 `deviations` 绑定到需求的哪个版本（v1 / v2 / 变更对），
   以及 SIM BPMN 对应哪一版流程；`step_1` 的 `both_versions` 标志如何解释；
2. **元素解析**：`element_label` 到 BPMN 元素 ID 的解析规则（同名/空白标签须 fail-closed，不猜）；
3. **`mitigation_action` 的用途**：仅作报告中的"论文式建议"呈现，不参与判定。

## 6. 输出物与 DoD

| 产物 | 路径 |
|---|---|
| 运行胶囊 | `outputs/development/s3_real_case_e2e_v1/{plan.json,predictions.jsonl,metrics.json,diagnostics.json,manifest.json}` |
| 案例报告 | `outputs/reports/s3_real_case_e2e_v1.{json,md}`（分案例后缀 `_caseA/_caseB/_caseC`；Case C 另出 `_caseC_e1`） |
| 输出 schema | `configs/schemas/stage3_extended_prediction.schema.json` |
| 测试 | `tests/test_s3_real_case_e2e_v1.py`（哈希绑定、逐检查守恒、原因码枚举、确定性重放、Gold 只读与写盘顺序、零网络零 API、Stage 1 记录只读、Case C 答案键映射表完整性） |
| 复核命令 | `python formal_experiment/scripts/run_real_case_s3_v1.py --check` / `--replay` |

**DoD**：选定案例逐检查判定齐备；四类各自可判/不可判计数与原因分布；不同 Stage 2 来源的逐检查差异表；
原三类与既有 `--arm human_rules` 逐项一致或显式解释差异；**Case C 有与外部答案键的逐需求对照表
（含 `over_compliant` 单列与 exception 空缺声明）**；C-E1 给出两种论文答案键读法的分别结果；
报告明确 DEV_ONLY 与许可证边界；`--check`、`--replay` 与 focused tests 通过；
`record_change.py` 事件；Git checkpoint（scoped commit + push）。

## 7. 口径与评价纪律

1. **不给逐类 P/R/F1**：单案例样本量不足，不可判既非正也非负；只给计数、原因分布与逐条判定。
2. **不新增指标**：与既有真实诊断对齐时，只用已冻结的"检查引用计数 / 去重数量"两套口径并注明关系。
3. **Gold 只读且顺序固定**：预测先落盘，答案键后读取；v001/v002 的检查范围争议标注为未解决。
4. **外部标签不等于我们的标签**：`bpmn_element` 到七类的映射表必须显式列出；
   `over_compliant` 类不得计为我们的漏检；不得把 Barrientos 的标签当作 Sun-compatible Gold。
5. **逐 requirement 证据**：Rules-Only 的 first-valid-span 投影会产生碎片 action span
   （如 article33 出现 `", it shall be accompanied by reasons for the delay."`），使 `missing_action`
   机械得 1.0；必须记录每个 requirement 的证据与映射情况。
6. **许可证与发布边界（Case C 强制）**：Barrientos artifact 许可为
   `unknown_pending_confirmation`，仅**本地只读非再分发**研究使用；提交产物只允许
   ID / 标签 / 计数 / hash / 判定，**不得写入或转载其原文文本**；报告需写明该边界。
7. **不新增 API**：Case C 复用 2026-08-29 已授权的 1140 次运行产物；其余默认零调用。

## 8. 已知限制与不可声称事项

### 8.1 数据与表面限制

- `gdpr_1` 顶层无 timer / boundary / error 表面，计时器位于 `Handle delay` 子流程内；子流程不展开时，
  constraint / exception 只能记 `unobservable` —— 不是方法失败，也不是流程合规的证据。
- Rules-Only 为英文 GDPR 句经德语合同 classifier 槽的 **pass-through**（跨语言限制）；
  first-valid-span 投影是适配规则，不是方法能力。
- **Sun Figure 10 的模型不存在于任何本地资产**：C-E1 是重建件；官方 supplement 只含 7 个 GDPR 模型。

### 8.2 答案键的已知缺陷

- **论文图文自相矛盾**：正文（L957–973）称 R1、R4 = missing action、R2 = out-of-order、R3 = incorrect actor；
  Figure 10 标注称 V1/R1、V2/R2 = missing action、V3/R3 = incorrect actor、V4/R4 = out-of-order
  ——**R2 与 R4 互换**。本地 PDF 为预印本，非正式版（"non-controlling where it differs from the version of record"）。
- 外部答案键覆盖不到 `exception_not_handled`；`out_of_order` 只在 emergencies 场景出现。
- 无"合规对照"人工 Gold；v001/v002 检查范围冲突未解决；整图合规与 72 小时计时器疑点按原意保留。

### 8.3 不可声称

- 不得称"我们的方法在真实案件上有效 / 优于 Sun / 优于 Winter / 优于 Barrientos"；
- 不得称"四类都已在真实数据上验证"（只能说：在选定案例上，四类各自的可判定性与结果如下）；
- 不得称复刻了作者原始模型（C-E1 是重建件）；
- 不得称正式 Oracle、独立验证或真实法律合规结论；
- 不得把案例结果并入 33 条人工 Gold、40 对合成面板或 36 条 Barrientos 正式 Gold 的任何表格。

## 9. 分批计划（每批独立可交付、独立 checkpoint）

| 批次 | 内容 | 交付 |
|---|---|---|
| B0 | 本任务书 + 治理登记（用户批准后） | 任务行、prompt、派工行 |
| B1 | runner 骨架 + 输出 schema + **原三类**在 Case B 上重跑，与 `human_rules` 臂逐项比对 | 一致性证明或差异解释（**关键门**：对不齐则 B2 起不得继续） |
| B2 | 四类接入（`project_external_sentence` + `ExtendedViolationScorer`/`ScopedEvidenceScorer`），Case B 全量 | 可判/不可判计数与原因分布 |
| B3 | Case A（gdpr_2 × article22）+ 多 Stage 2 来源对照 | 四类全跑案例 + 差异表 |
| B4 | 报告与论文素材（明确 DEV_ONLY） | 报告 JSON/MD + 论文可用小节草稿 |
| **B5** | **Case C-E2**：SIM BPMN + r8–r13 + step_3 答案键四方对照（先做 §5.6 入口检查） | 逐需求对照表（含 over_compliant 单列、exception 空缺声明） |
| **B6** | **Case C-E1**：Figure 10 重建 + Table 13 R1–R4，两种论文读法分别报告 | 复刻结果 + 图文冲突披露页 |

## 10. 已决与待决事项

**已决（2026-09-11 用户确认）**

- 路线：**C-E2 为主 + C-E1 补充**；
- Case C 写入本任务书（本文即 v3）。

**待决**

1. 案例范围：是否 A、B、C 全做（建议全做；只做其一时优先 C）？
2. 是否把 emergencies 场景也纳入（为了 `out_of_order` 有真实答案实例）？
3. 是否跑 GDPR Direct-LLM 74 calls（需确认进程环境凭据；默认不跑）？
4. 任务 ID：拟用 `S3.9-EXT-REAL-CASE`（development-only），批准后写入 MASTER_PIPELINE §9.5；
5. 是否允许新增 development 专用输出 schema（§5.2；不动现有三类 schema）？

## 11. 批准后要做的治理动作

1. `docs/MASTER_PIPELINE.md` §9.5 增加任务行（依赖、DoD、边界与本文一致）；
2. `docs/AGENT_RUNBOOK.md` 增加 copy-ready prompt；
3. `docs/PROJECT_AUDIT.md` 当前派工行登记；
4. 每批结束：focused tests + `record_change.py` 事件 + scoped Git commit + push；
5. 本文降级为该任务的附件设计说明，并在文件头标注已登记状态。
