# 任务书（提案）：真实案例 Stage 1 → Stage 3 端到端示例（S3.9-EXT-REAL-CASE）

> **状态：PROPOSED — 未授权、未登记、未执行。**
> 本文只是方案与验收标准的提案，供用户审阅。它**不是** pipeline 任务行、**不是**状态页、
> **不是**实验结论。在用户明确批准前，不写代码、不跑运行、不改任何 Gold / 合同 / 门禁 / 预测。
> 批准后按 §11 完成治理登记（MASTER_PIPELINE §9.5 新行 + AGENT_RUNBOOK prompt +
> PROJECT_AUDIT 派工行），届时本文降级为该任务的附件设计说明。
>
> 日期：2026-09-11　范围：`formal_experiment/`　真实 API 调用：**0**（见 §7.4 例外项）
> **v2 修订说明（2026-09-11，只读契约测绘之后）**：v1 曾把"真实规则 → 六要素绑定器"列为新增模块；
> 测绘证明**不需要**——四类检查器（`ExtendedViolationScorer`）与外部预测投影
> （`gdpr_s2_s3_projection.project_external_sentence`）都已存在，缺的只是"把它们接到真实原图"的 runner。
> 本版同时把 §3 的案例可判性从"预判"改为**实测数字**，并新增 §5.4 复用边界与 §6 输出 schema 要求。

---

## 1. 为什么需要这个任务（问题陈述）

用户要求：**拿一张真实的业务流程图和一套真实的法律法规，从第一阶段跑到第三阶段，看结果。**

现状核实结论（2026-09-11，只读核对）——**这件事没有做过**：

1. 真实数据的三个环节**分别**跑过，但**从未拼成一条完整案例链**：
   - Stage 1：7 张 GDPR BPMN 的**我方解析器 Process Record** 已存在（人工 Process Gold 已发布）；
   - Stage 2：9 条 GDPR 条款 / 74 句的 **Rules-Only（B0 v10a）真实预测**已跑（74/74，零 API），
     人工确认的 92 条规范条目 → 正式 Gold Rule Records 已发布；
   - Stage 3：真实规则记录 + 真实 BPMN 上只跑过**原三类**的 33 个人工 Gold 项
     （`s3_real_rule_diagnostic_v1`：Sun 与 v3 结果完全相同，missing_action 10 violation + 1 unknown，
     incorrect_actor 11 unknown，out_of_order 11 unknown）。
2. **Stage 3 从来没有读过我们的 Stage 1 产物**：`grep stage1_gdpr7_process_records_v1` 在
   `scripts/run_s3_*` 中零命中；现有真实输入的三类臂（`run_gdpr_3type_linkage_v1.py --arm human_rules`、
   `run_s3_oracle_gold_rules_v1.py`）都是**重新解析 BPMN**，而不是消费 Stage 1 记录。
3. **四类扩展在真实原图上没有判定路径**：所有四类 runner（`run_s3_extended_violation_panel_v2`、
   `run_s3_extended_repair_v2_v1`、`run_s3_extended_evidence_scope_v1`、`run_gdpr_s2_s3_linkage_v1`、
   `run_s3_oracle_gold_rules_v1::run_four_types`）都只在
   `data/development/stage3_synth/<vid>/<side>/<pid>.bpmn` 上打分；`_variant_bpmn()` 硬编码该路径。
   真实原图只进过 TF-IDF 拟合语料（`_frozen_tfidf_corpus()`）或作为"对照侧误报计数"。
4. 因此目前无法回答用户的问题："这套方法在真实流程图 + 真实法规上，最终说了什么、哪些判不了、为什么判不了。"

本任务的产出就是这条缺失的案例链。

## 2. 目标与非目标

**目标**

- **G1**：对选定的真实 (流程, 法规条款) 组合，用**我方 Stage 1 产物 + 我方 Stage 2 产物 + 现有 Stage 3 检查器**，
  产出逐检查判定：`violation` / `compliant` / `unobservable` / `not_applicable` + 原因码 + 证据。
- **G2**：让**四类扩展违规**第一次在真实原图 + 真实规则上被消费，并如实报告哪些类型在该案例的
  流程表面上可判、哪些不可判（附原因码）。
- **G3**：对比两种 Stage 2 规则来源（Rules-Only 真实预测 vs 人工确认 Gold Rule Records）对最终判定的影响，
  逐检查给出变化与归类（抽取 / 投影 / 检测）。
- **G4**：产出可复核的机器 JSON + 人类可读案例报告，作为论文案例章节的**开发级**素材。

**非目标（明确不做）**

- 不做正式 Oracle、不做 S3.7 主表、不做端到端误差传播（S3.10）、不做 Stage 3 冻结（S3.11）；
- 不修改 33 条人工 Gold、25 条 matching Gold、40 对合成面板、任何冻结 BPMN、阈值、公式、原因枚举；
- **不修改冻结抽取器与 `gdpr_capsule_converter`**（本任务已确认不需要；若实现中发现确需改动，
  必须停下来先改任务书并取得用户批准）；
- 不为本案例搜索阈值、不加白名单/同义词/ID 特判、不新增合成变体；
- 不评价 detection 指标（单案例样本不足以算 P/R/F1）；
- 不调用真实 LLM/API（除非用户单独批准 §7.4 的可选臂）。

## 3. 案例选择（实测数据，非预判）

### 3.1 流程侧表面（我方 Stage 1 Process Record）

| 流程 | activities | events | gateways | 关键表面 |
|---|---:|---:|---:|---|
| `gdpr_1_data_breach` | 6（3 task + 3 **subProcess**） | 2 | 2（**仅 parallel**） | `condition_candidates=0`、`constraint_candidates=25`、`exception_candidates=3`；`72 hours` 计时器位于 `Handle delay` 子流程内 |
| `gdpr_2_consent_to_use_the_data` | 24 | 6（含 intermediateCatchEvent） | 15（exclusive / eventBased / parallel） | 四类表面最全；article22 项另有 38 constraint / 25 exception 候选 |

### 3.2 规则侧（人工确认条目与 Gold Rule Records）

- 全量：`article33` = 4 condition / 8 constraint / 1 exception；`article34` = 4 / 6 / 3；
  `article22` = 3 / 2 / 4；`article6/7/15/17` 更多。
- Stage-2 Rules-Only 真实预测（82 clause）：79 有 actions、58 conditions、64 constraints、15 exceptions。
- **article33 / article34 的 Gold 中 prohibition 子句 = 0**。

### 3.3 结论：案例组合

| 方案 | 组合 | 四类结果预期（基于实测表面） |
|---|---|---|
| **A（推荐，四类最全）** | `gdpr_2_consent_to_use_the_data` × `article22`（33 项中的 v013–v015） | 33 项里**唯一**同时具备 prohibition 子句（2）与非零 condition 候选（2）的项 → 四类均可进入判定（constraint / exception 另有 38 / 25 候选） |
| **B（论文主锚，作为对照）** | `gdpr_1_data_breach` × `article33` / `article34` | `prohibited_action_present` → 必然 `unobservable: rule_modality_not_prohibition`；`required_condition_not_enforced` → 必然 `unobservable: no_condition_candidates`；`constraint_violated` / `exception_not_handled` 在动作映射 ≥ gamma 时可判 |

**建议**：A + B 都做——B 给出"论文主锚点的诚实结果（含两类结构性不可判）"，A 给出"四类都能跑的完整演示"。
只做其一时，A 更能回答"四类到底能不能用"，B 更能对上论文已有的案例叙事。

> 案例选择是**内容决定**，不是结果决定：先按表面是否支持该类型检查选，再看结果；
> 若不可判成立，如实报告，不换案例凑结论。

## 4. 输入与复用清单（全部已存在；契约已核实）

| 用途 | 路径 / 符号 | 复用方式 |
|---|---|---|
| Stage 1 流程记录（我方） | `data/development/human_review/stage1_gdpr7_process_records_v1.json` | **直接可用，无需适配器**：7 条记录已按冻结合同与重新解析逐项 canonical 相等（唯一差异是文档化的 identity adapter），schema 校验通过，`process_id` 与 Stage 3 使用的键一致 |
| 流程模型对象 | `src/bpc_hybrid/sun_stage3/sun_model.py` `SunProcessModel(process_id, record, nlp)` | 原样复用（可达关系在 71–75 行构建） |
| 原始 XML（四类候选面需要） | 记录内 `source.path` → `ET.fromstring(...)` | 原样复用，不重新解析流程结构 |
| Stage 2 来源 ①（真实预测） | `data/predictions/gdpr7_sun_rule_only_v1/predictions.json` | 原三类走 `gdpr_capsule_converter.build_rule_records(..., ("obligation",))`；四类走下一行 |
| 四类要素投影（缺的那根线） | `src/bpc_hybrid/gdpr_s2_s3_projection.py` `project_external_sentence()` | **原样复用**；目前唯一调用方是合成面板 runner，本任务把它接到真实原图 |
| Stage 2 来源 ②（人工确认） | `data/development/human_review/gdpr7_human_confirmed_v1/confirmed_rule_items.json`、`data/gold/stage3/gdpr7_gold_rule_records_v1.json` | 只读；clause span 切片方式对齐 `run_s3_oracle_gold_rules_v1.py:236–241` |
| 三类检查器 | `sun_stage3/sun_scorer.py`、`src/bpc_hybrid/s3_evidence_checks_v1.py`、`s3_action_matching_v2/v3.py` | 原样复用 |
| 四类检查器 | `src/bpc_hybrid/stage3_extended_violations.py`（`ExtendedViolationScorer`、候选面函数） | 原样复用；四值版本可用 `s3_extended_evidence_scope_v1.py`（`ScopedEvidenceScorer`） |
| 打分循环样板 | `scripts/run_s3_extended_repair_v2_v1.py:289–382`（`score_side` 形态） | 复制形态，不导入面板逻辑 |
| 真实原图三类基线（可比对） | `scripts/run_gdpr_3type_linkage_v1.py --arm human_rules`、`scripts/run_s3_oracle_gold_rules_v1.py` | 只读比对；本任务结果必须与之兼容或显式解释差异 |
| 既有真实诊断口径 | `outputs/development/s3_real_rule_diagnostic_v1/`、`..._corrections_v1/` | 引用其"检查引用计数 / 去重数量"两套口径，不新造 |

**只有三样东西是真正新增的**：1 个 runner、1 个输出 schema、1 个测试文件。

## 5. 方法设计

### 5.1 新增：`scripts/run_real_case_s3_v1.py`（约 250–350 行）

- 组合维度：`(case, rule_source ∈ {rules_only, human_gold}, method ∈ {sun_2024_frozen, evidence_checks_v3, winter-style, bm25, tfidf}, check_type ∈ 3 原三类 + 4 扩展类)`；
- 流程侧：Stage 1 记录 → `SunProcessModel`；XML 候选面直接从 `source.path` 读取；
- 规则侧：按 §4 两条路径构造；
- 逐检查输出：判定（四值）+ 原因码 + 证据（文本/ID/hash）+ 目标活动/网关/事件 ID；
- **逐 requirement 证据**：不得只给聚合判定（见 §7.5）；
- `plan.json` 在打分前写盘并绑定实现哈希；`--check`（哈希绑定复核）与 `--replay`（只从已存行复算）两个只读模式；
- 不写任何正式目录，不覆盖既有产物（no-overwrite）。

### 5.2 新增：`configs/schemas/stage3_extended_prediction.schema.json`

现有 `configs/schemas/stage3_prediction.schema.json` 的 `predicted_violation_type` 枚举**只有原三类**，
四类结果无法在其下通过校验；因此需要一个新的、显式标注 development 的 schema
（沿用 runner 内联的 `stage3_extended_prediction@1.0.0` 形状 + 运行级判定字段）。

### 5.3 新增：`scripts/report_s3_real_case_e2e_v1.py`（或 runner 的 `--report-only`）

机器 JSON + 人类可读 MD；逐条：条款位置与要素、目标活动/网关/事件、证据文本、判定、原因码、
两种 Stage 2 来源下的差异；并含"本案例不能证明什么"小节（§8.3）。

### 5.4 复用边界（不得顺手改）

`stage1_formal_dataset.build_formal_process_records`、`stage1_process.parse_bpmn_bytes/validate_process_record`、
`sun_model.SunProcessModel`、`sun_scorer.SunScorer`、`s3_action_matching_v3.EvidenceChecksV3`、
`gdpr_capsule_converter.*`、`gdpr_s2_s3_projection.project_external_sentence`、
`stage3_extended_violations.*`（含 `ExtendedViolationScorer` 与三个候选面函数）、
`s3_extended_evidence_scope_v1.ScopedEvidenceScorer`、`winter_similarity.WinterSimilarity`、
`evaluate_stage3_common`、`s3_extended_unified`、`control_prediction_from_scores` /
`aggregate_scope_verdicts`
一律**只读复用**。确需改动时：停止实现 → 更新本任务书 → 取得用户批准。

### 5.5 四值与原因语义

| 判定 | 含义 |
|---|---|
| `violation` | 证据支持下落判违规（附证据） |
| `compliant` | 该检查**真正比较过**且未发现违规（比较门：condition/constraint/exception 至少一项实际比较过） |
| `unobservable` | 规则元素为空 / 动作低于 gamma / 候选面为空 / 流程表面不存在（附原因码，如 `rule_modality_not_prohibition`、`no_condition_candidates`、`action_mapping_below_gamma`） |
| `not_applicable` | 规则本身没有该元素（第三种状态，不得与 unknown 混算） |

禁止：`unknown` 与 `not_applicable` 合并统计；把 `none` 解释为"整条流程法律合规"。

## 6. 输出物与 DoD

| 产物 | 路径 |
|---|---|
| 运行胶囊 | `outputs/development/s3_real_case_e2e_v1/{plan.json,predictions.jsonl,metrics.json,diagnostics.json,manifest.json}` |
| 案例报告 | `outputs/reports/s3_real_case_e2e_v1.{json,md}`（分案例时加 `_caseA` / `_caseB`） |
| 输出 schema | `configs/schemas/stage3_extended_prediction.schema.json` |
| 测试 | `tests/test_s3_real_case_e2e_v1.py`（哈希绑定、逐检查守恒、原因码枚举、确定性重放、Gold/预测写盘顺序证明、零网络零 API 断言、Stage 1 记录只读断言） |
| 复核命令 | `python formal_experiment/scripts/run_real_case_s3_v1.py --check` / `--replay` |

**DoD**：选定案例逐检查判定齐备；四类各自给出可判/不可判计数与原因分布；两种 Stage 2 来源的逐检查差异表；
与 `run_gdpr_3type_linkage_v1.py --arm human_rules` 的原三类结果逐项一致或显式解释差异；
报告明确 DEV_ONLY 边界；`--check`、`--replay` 与 focused tests 通过；`record_change.py` 事件；
Git checkpoint（scoped commit + push）。

## 7. 口径与评价纪律

1. **不给逐类 P/R/F1**：单案例样本量不足，不可判既非正也非负；只给计数、原因分布与逐条判定。
2. **不新增指标**：需要与既有真实诊断对齐时，只用已冻结的"检查引用计数 / 去重数量"两套口径并注明关系。
3. **Gold 只读且顺序固定**：预测先落盘，答案键后读取；v001/v002 的检查范围争议在报告中标注为未解决。
4. **可选 API 臂（需用户单独批准）**：GDPR Direct-LLM 74 calls（授权事件已存在
   `configs/gdpr7_direct_llm_authorization_event_v1.json`，需要进程环境凭据）。默认**不跑**；
   跑与不跑都要在报告里写明。
5. **逐 requirement 证据**：Rules-Only 的 first-valid-span 投影会产生碎片化 action span
   （如 article33 出现 `", it shall be accompanied by reasons for the delay."` 这类片段），
   使 `missing_action` 机械得 1.0。新 runner 必须记录每个 requirement 的证据与映射情况，
   不得只用聚合判定掩盖该投影缺陷。

## 8. 已知限制与不可声称事项

### 8.1 数据与表面限制

- `gdpr_1` 顶层无 timer / boundary / error 表面，计时器位于 `Handle delay` 子流程内；子流程不展开时，
  constraint / exception 只能记 `unobservable` —— 这**不是**方法失败，也**不是**流程合规的证据。
- Rules-Only 为英文 GDPR 句经德语合同 classifier 槽的 **pass-through**（跨语言限制）；
  first-valid-span 投影是适配规则，不是方法能力。

### 8.2 案例标准答案不完整

- 无"合规对照"人工 Gold（不能证明 specificity / 误报率）；
- v001/v002 与用户已确认的局部通知意见存在检查范围冲突，未解决；
- 整图合规、72 小时计时器与主通知期限的疑点按原意保留，**不**自动变成 none/timeout 标签。

### 8.3 不可声称

- 不得称"我们的方法在真实案件上有效 / 优于 Sun"；
- 不得称"四类都已在真实数据上验证"（只能说：在选定的真实案例上，四类各自的可判定性与结果如下）；
- 不得称正式 Oracle、独立验证或真实法律合规结论；
- 不得把本案例结果并入 33 条人工 Gold 或 40 对合成面板的任何表格。

## 9. 分批计划（每批独立可交付、独立 checkpoint）

| 批次 | 内容 | 交付 |
|---|---|---|
| B0 | 本任务书 + 治理登记（用户批准后） | 任务行、prompt、派工行 |
| B1 | runner 骨架 + 输出 schema + **原三类**在案例 B 上重跑，与 `human_rules` 臂逐项比对 | 一致性证明或差异解释（这是"接线正确"的门槛） |
| B2 | 四类接入（复用 `project_external_sentence` + `ExtendedViolationScorer`/`ScopedEvidenceScorer`），案例 B 全量 | 可判/不可判计数与原因分布 |
| B3 | 案例 A（gdpr_2 × article22）+ 双 Stage 2 来源对照 | 四类可判案例 + 差异表 |
| B4 | 报告与论文素材（明确 DEV_ONLY） | 报告 JSON/MD + 论文可用小节草稿 |

B1 是关键门：**若原三类在案例 B 上无法与既有 `human_rules` 臂对齐，B2 起不得继续**，
先查接线而不是解释结果。

## 10. 需要用户决定的事项

1. **案例选择**：A（四类最全）／B（论文主锚）／A+B（建议）？
2. **Stage 2 来源**：只用 Rules-Only／只用人工确认 Gold／两者都报（建议两者）？
3. **是否跑 GDPR Direct-LLM 74 calls**（需确认进程环境凭据；默认不跑）？
4. **任务 ID**：拟用 `S3.9-EXT-REAL-CASE`（development-only），批准后写入 MASTER_PIPELINE §9.5。
5. **是否允许新增一个 development 专用输出 schema**（§5.2；不改现有三类 schema）？

## 11. 批准后要做的治理动作

1. `docs/MASTER_PIPELINE.md` §9.5 增加任务行（依赖、DoD、边界与本文一致）；
2. `docs/AGENT_RUNBOOK.md` 增加 copy-ready prompt；
3. `docs/PROJECT_AUDIT.md` 当前派工行登记；
4. 每批结束：focused tests + `record_change.py` 事件 + scoped Git commit + push；
5. 本文降级为该任务的附件设计说明，并在文件头标注已登记状态。
