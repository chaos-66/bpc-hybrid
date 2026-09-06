# 导师进度汇报内容稿（2026-09）——基于 Sun 三阶段框架的合规规则抽取 LLM 化与违规检测类型扩展

> 用途：约 12 页导师进度汇报的内容草稿（每节 = 1 页）。正文用于页面排版，表格按页引用，演讲备注供口播使用。
> 汇报纪律（贯穿全文）：
> 1. 只写事实与进度状态，不写"我们显著优于 / 全面优于"一类句子；无显著性推断，全部为描述性表述。
> 2. 每个结果表必须标注：**实际样本量 / 评价口径 / 证据级别（正式 | development | 受控合成）/ 来源文件路径**。
> 3. 未运行的实验一律写"未运行/待授权"，绝不编造数字。
> 4. 所有数字以文末"数字与来源速查表"为准，来自对应报告文件。
>
> 代号速查：**B0 = Rules-Only**（`sun_rule_only`，Sun 方法级重建，不调用 LLM）；**D1 = Direct-LLM**（`direct_llm`，主方法）；**H1 = Rules+LLM-Repair**（`sun_llm_fallback`，负结果对照）。旧代号仅作管线对照，不作为论文正式名称。

---

## 第 1 页｜封面与研究定位

**幻灯片标题**：基于 Sun 三阶段框架的合规规则抽取 LLM 化与违规检测类型扩展——导师进度汇报（2026-09）

**正文**：一句话定位：以 Sun et al. (2024) 的三阶段主干（流程解析 → 法规解析 → 匹配与违规检测）为**整体改进对象**，把 Stage 2 的"规则/词典抽取"替换为受约束的 LLM 结构化抽取，并把 Stage 3 违规检测从 Sun 的三类扩展出四类新类型。两处改进：① **Stage 2 规则抽取 LLM 化**（Direct-LLM 为主方法，Rules-Only 为 Sun 方法级重建对照，Rules+LLM-Repair 为负结果对照）；② **Stage 3 违规检测类型扩展**（prohibited_action_present / required_condition_not_enforced / constraint_violated / exception_not_handled，分别消费六要素中的 prohibition 情态、condition、constraint、exception 四个此前无下游消费者的字段）。与 Barrientos et al. (2026) 的关系：其是 **Stage 2 LLM 方法的借鉴来源**（结构化输出、校验、受控词汇、评价纪律），不是任务/schema 主干；项目**不承担"必须整体优于 Barrientos"**；曾计划的"原生 FULL/NO-PATTERNS 360 次真实调用"对比执行方案**已撤回**，仅保留为历史证据，不执行、不产生新数字。

**演讲备注**：
- 开场 30 秒交代三件事：框架主干是谁（Sun 2024）、方法学借鉴谁（Barrientos 2026）、本文改进在哪两处（Stage 2 抽取 LLM 化 + Stage 3 类型扩展）。
- 强调"整体改进对象 = Sun 三阶段"，与 Barrientos 的关系是"借鉴方法、不比总榜"——避免导师误读为对标竞争。
- 一句话说明撤回方案：曾计划跑 Barrientos 原生提示 360 次做全面对比，按当前定位与授权口径已撤回，历史证据保留、不再执行。
- 状态预告：正式 Stage 2 三方法比较已于 2026-08-11 发布（零新增 API）；Stage 3 formal Oracle 与端到端尚未启动（见第 12 页）。

---

## 第 2 页｜研究背景与问题

**幻灯片标题**：设计期业务流程合规检查：为什么"规则抽取"是关键瓶颈

**正文**：
- **场景**：设计期合规检查——流程（BPMN）建模阶段即对照法规（税法 EStG、GDPR 条款）检查流程是否合规，在"设计期发现问题"而非"运行期承受处罚"。
- Sun 框架把检查做成数据流（Process Record × Rule Record → Violation Report），但 Stage 2 规则抽取是当前瓶颈，具体表现为三点：
  - **规则/词典覆盖**：未收入词典的表述无法命中，覆盖率直接设定召回上限；换一种说法即漏检；
  - **字段归属错误**：同一短语若被误分到 actor / action / condition / constraint / exception 的错误字段，下游"按字段消费"的 Stage 3 检查会整体失效（第 10 页有真实案例）；
  - **换法域成本**：从 EStG 换到 GDPR 需要重建词典与规则，人工成本高且口径难以一致。
- 由此形成两个研究动作：① 把抽取交给"受控词汇 + 输出校验"的 LLM（改进 ①）；② 让更多 Rule Record 字段在 Stage 3 拥有消费者，同时诚实探测可检测边界（改进 ②）。

**演讲备注**：
- 用 1–2 个业务故事带出"设计期 vs 运行期"差异，避免把问题讲成纯 NLP 任务。
- 强调"瓶颈不是模型调用成本，而是规则体系的可维护性与覆盖"，为 LLM 抽取动机铺路。
- 预告第 10 页的 article22 情态误标与字段覆盖案例，说明"字段归属错误"不是纸面风险。
- 换法域成本是论文"为什么需要可迁移抽取"的动机句，但本页不报任何数字。

---

## 第 3 页｜Sun 三阶段框架

**幻灯片标题**：方法主干：Sun 三阶段框架（Sun et al., 2024）

**正文（文字框图）**：

```
业务流程/BPMN ──────── Stage 1 流程解析 ────────▶ Process Record
法律条款文本 ───────── Stage 2 法规解析 ────────▶ Rule Record（六要素：
                                                 modality/actor/action/
                                                 condition/constraint/exception
                                                 + 原文 evidence span）
Process Record × Rule Record ── Stage 3 匹配与违规检测 ──▶ Violation Report
（action 映射 gamma、actor/order 检查；Sun 原始三类：
 missing_action / incorrect_actor / out_of_order）
```

- **本文角色**：Stage 2 用 LLM 结构化抽取替换 Sun 原文的规则/词典抽取（主贡献 1，Schema 与输出契约不变，故三方法可比）；Stage 3 沿用 Sun 匹配思想，并以 Winter et al. (2020) 为另一基线，扩展四类新违规类型（主贡献 2）。
- **边界**：流程解析（Stage 1）不是本文贡献点；"方法级重建"不等于复刻 Sun 原始实现或原始数据集。

**演讲备注**：
- 一张图讲清三个阶段的输入输出，不展开细节。
- 强调三方法产出**同一六要素 Rule Record schema、同一 output contract**，因此能在同一 Gold / 同一 evaluator 上比较。
- 明确 Stage 1（GDPR-7）已冻结、Stage 3 面板与阈值已冻结，本文的改动集中在 Stage 2 的抽取方法与 Stage 3 的类型口径上。
- "方法级重建"措辞的纪律：不得自称 exact reproduction 或 Sun original。

---

## 第 4 页｜与 Barrientos 的关系

**幻灯片标题**：与 Barrientos et al. (2026) 的关系：借鉴方法学、不照抄、不比总榜

**正文**：
- **借鉴了什么（Stage 2 LLM 方法学）**：① 结构化输出（严格 JSON schema + 解析）；② 输出校验（validator 对无效记录计数进分母，fail-closed）；③ 受控词汇（情态/类型限定枚举）；④ 评价纪律（adapter 对齐、口径隔离、不可比不排榜）。
- **没有照抄**：schema 与提示为本文自研；Barrientos 情态为 3 类、本文为 4 类（3→4 不可直接映射）；其表示包含流程侧 activities/participants 与 resources、norm 的 precondition/temporal validity——能表达部分近似 actor/action 语义，但**与 Sun 六要素 Rule Record 加 verbatim evidence span 是不同契约**，字段级对齐须经 adapter 与 provenance 检查，不能声称其"完全无法表达 actor/action"；外部标签不自动视为 Sun 兼容 Gold（须经 adapter 与 provenance 检查）。
- **比较合同 C4（跨任务）**：跨任务 / 跨 schema / 跨语料不得用单一 F1 宣称综合优劣，只能分表并标证据等级；唯一合法的跨方法共同目标是三类 modality（同一 Gold、同一评价函数，见第 11 页：0.890 vs 0.822，照实写）。
- **已完成对照实验的诚实表述**：共享三类 modality 上 Barrientos 原生略高；把 Barrientos 风格模块直接替换进本文六字段接口得 0 分——这是**接口不兼容**，不是"Barrientos 无效"，也不是"本文全面更优"；原生 FULL/NO-PATTERNS 360 次方案已撤回（仅历史证据）。

**演讲备注**：
- 预先堵住最常见提问："为什么不做成 Barrientos 的 schema？"——因为主干是 Sun 六要素，任务不同。
- 引用论文模块对比表（THESIS_DRAFT §4.4，15 维度逐模块对比）说明"哪些相同、哪些不同、为什么不能照搬"。
- 0.890 vs 0.822 的对照要主动说（诚实优于被追问），同时解释 0 分臂的接口原因（第 8 页详解）。
- 一句话收尾：本项目用 Barrientos 的"工程纪律"，不用它的"任务与 schema"。

---

## 第 5 页｜方法与数据

**幻灯片标题**：方法与数据：四个语料/面板 × 三种方法

**正文**：
- **数据与面板**（本页只列清单，不含性能数字）：
  - **EStG-150**：150 句，独立重建 benchmark；Gold = LLM-assisted human-adjudicated Gold（2026-08-10 发布，非"纯人工从头标注"、非 exact reproduction）——正式 Stage 2 的载体；
  - **S2.11 复杂语料 36 条**（Barrientos requirements；G0.5 复杂度分层与 S2.11 语料裁决均已冻结）——复杂语料扩展载体；
  - **GDPR-7**：7 个流程（Stage 1 已冻结）——Stage 3 面板；
  - **S3.9-EXT**：40 对受控合成合规/违规样本（四类扩展）。
- **三种方法**（同一六要素输出 schema）：
  - **Rules-Only（B0）** = Sun 方法级规则/词典重建，不调用 LLM；
  - **Direct-LLM（D1）** = 主方法：端到端 LLM 生成六要素 Rule Record（受控词汇 + 校验 + 后处理链）；
  - **Rules+LLM-Repair（H1）** = 负结果对照：规则优先、LLM 修复。
- 评价纪律：正式三方法比较只在 EStG-150 上、同一冻结输入/Gold/evaluator 下进行（2026-08-11）；其余语料/面板上的结果按其证据级别单独标注。

**演讲备注**：
- 数据一句话各带"冻结状态"（S2.11 冻结 / GDPR-7 Stage1 冻结 / S3.9-EXT 冻结面板），显示治理完整。
- 强调 Gold 的性质措辞：LLM-assisted、human-adjudicated；不夸大为纯人工。
- 三方法图示建议画成同一漏斗的三条路径，收口到同一 Rule Record schema。
- 提示本页无结果表，后续每页结果表都会回注"样本量/口径/证据级别/来源"。

---

## 第 6 页｜Stage 2 主结果（正式）

**幻灯片标题**：Stage 2 主结果（正式，2026-08-11）：150 句、句子级粗 Gold、逐字段 F1

**结果表**：

| 字段（句子级粗 Gold） | Rules-Only (B0) | Direct-LLM (D1) | Rules+LLM-Repair (H1) |
|---|---:|---:|---:|
| actor（逐字段 F1） | 0.820 | 0.758 | 0.430 |
| action（逐字段 F1） | 0.893 | 0.944 | 0.895 |
| condition（逐字段 F1） | 0.774 | 0.838 | 0.777 |
| constraint（逐字段 F1） | 0.618 | 0.743 | 0.620 |
| exception（逐字段 F1） | 0.880 | 0.762 | 0.880 |
| modality 标签准确率（单列） | 0.740 | 0.833 | 0.820 |

> 注（必标）：实际样本量 = **150 句**；评价口径 = 句子级粗 Gold、五个 span 字段逐字段 F1（授权主口径），modality 四类标签 accuracy **单列**、不与 span 指标混算；证据级别 = **正式**（2026-08-11；历史调用 300 次、新增 API 调用 0；无显著性推断，均为描述性）；来源 = `outputs/reports/stage2_formal_three_method_comparison_v1.{json,md,manifest.json}`。本页**绝不混入任何 development 数字**（如 H1 历史全量 0.7621 / 0.7986 只允许在第 11 页对 Hybrid 负结果对照中单列并注明口径）。

**正文**：
- **字段级互补（描述性）**：Direct-LLM 领先 action / condition / constraint 与 modality 标签准确率；Rules-Only 领先 actor / exception（召回驱动，actor 0.820、exception 0.880）；Rules+LLM-Repair 主口径净负（actor F1 仅 0.430）。
- 共同局限：modality evidence-span 三方法均不可得（Gold 中 modality 为纯字符串），已作为不可得标注、未置零、未聚合。
- 三方法正式比较完成 ≠ S2.13 / S1.7 / S3.7 全流程完成。

**演讲备注**：
- 逐字段读表，不读"平均分"；强调 Direct-LLM 在需要跨句/跨表达泛化的 condition、constraint 字段占优。
- 明确这是描述性结果，无显著性检验，避免任何"显著"字眼。
- 如果被问到 H1：H1 是负结果对照、停止优化；development 历史数字本页不讲（口径不同）。
- fine 五字段与历史六字段 aggregate 属诊断/development，不在本页出现。

---

## 第 7 页｜Prompt 消融（严格单因素）

**幻灯片标题**：Prompt 模块单因素消融（同一 150 句 / 同一 Gold / 同一 evaluator；真实 450 次调用，DeepSeek-V4-Pro-0813）

**结果表**：

| 条件（单次单因素） | F1 | ΔF1 | 关键逐字段 Δ | 合法输出率 |
|---|---:|---:|---|---:|
| 完整方法（六个合成示例） | 0.7719 | 基准 | — | 1.0000 |
| 语义示例→纯结构模板 | 0.7650 | −0.0069 | actor −0.1317 | 1.0000 |
| 删详细语义规则 | 0.7759 | +0.0040 | action −0.0518；**exception +0.1059** | 1.0000 |
| 删显式 JSON 纪律 | 0.7790 | +0.0071 | 本批合法率仍 1.0 | 1.0000 |

> 注（必标）：实际样本量 = **150 句 × 4 条件**（真实新增调用 450 次 = 三个删除臂各 150，DeepSeek-V4-Pro-0813）；评价口径 = 同一 Gold / 同一 evaluator 的整体 F1 与逐字段 F1 差值（相对完整方法）；证据级别 = **development**（单次描述性运行，无显著性推断；不得与 Barrientos-native evaluator 的 F1 跨表比较）；来源 = `outputs/reports/d1_prompt_factorial_results_v1.{json,md}`。

**正文**：
- 六个语义示例有**小幅总体正贡献**：换成纯结构模板后 F1 −0.0069，其中 actor −0.1317 是最明显的字段级效应。
- 删详细语义规则后总体 F1 **不降反升**（+0.0040），但 action −0.0518 说明规则存在字段间权衡；**必须写清：删除规则后 exception F1 上升 +0.1059**，不得表述为"语义规则改善了 exception"。
- 删显式 JSON 纪律后 +0.0071 且本批合法输出率仍为 1.0：只说明在当前模型与数据上未测到增益，**不能推广为该校验纪律普遍无用**。
- 三个删除臂均为固定 150 条上的单次描述性运行：局部正/负 Δ 不作显著性推断，也不推广为模块普遍有效/无效。

**演讲备注**：
- 说明"严格单因素"设计：每次只动一个提示模块，其余（语义规则、JSON 纪律、示例）全部保持。
- 主动讲"删规则后 exception 上升"这一反直觉点，展示不挑数据说话。
- 强调真实调用 450 次是已授权并已记账的执行，不是合成重放。
- 说明本页回答"提示模块贡献"问题；与第 8 页"后处理模块贡献"互补，两页都不与 Barrientos 表混比。

---

## 第 8 页｜后处理消融 + D/E 模块替换边界

**幻灯片标题**：后处理链单因素消融（D-full-0813 原始响应离线重放，0 新增 API）与 D/E 套件边界

**结果表**：

| 条件（单次单因素，150 条全进分母） | P | R | F1 | ΔF1 | 有效记录 | validator 观察到无效 |
|---|---:|---:|---:|---:|---:|---:|
| 完整后处理链 | 0.820 | 0.729 | 0.772 | +0.000 | 150/150 | 0 |
| −输出适配器（relay_schema_adapter） | 0.820 | 0.729 | 0.772 | +0.000 | 150/150 | 0 |
| −坐标重锚器（span_coordinate_canonicalizer） | 0.000 | 0.000 | 0.000 | −0.772 | 1/150 | 149 |
| −canonical validator | 0.820 | 0.729 | 0.772 | +0.000 | 150/150 | 0 |

> 注（必标）：实际样本量 = **150 条**（同一批 D-full-0813 原始响应离线重放、全部进入分母）；评价口径 = 同一后处理链整体 P/R/F1 与 ΔF1；证据级别 = **development**（回顾性离线重放，新增 API 调用 0）；来源 = `outputs/reports/d_full_postprocessing_ablation_v1.{md,json}`。

**正文**：
- −适配器 Δ = +0.000：反映该模块对当前完整 Prompt 原始响应的**实际增量**；−validator Δ = +0.000 同理（本批 0 条被 validator 拦下，不能说明 validator 没有安全价值）。
- **−坐标重锚器 F1 = 0（149/150 无效）**：这是"接口 + 校验链可用性"结果——去掉坐标规范化后，坐标错误使记录被判无效并进入分母；**不是语义能力归零**，不得解读为"去掉后模型不会抽取"。
- **D/E 套件（真实 1140 次调用）一句话**：把本文模块替换为"去 few-shot / Barrientos 风格"后 F1 为 0 的主因是**接口不兼容**——no-fewshot 可解析率 0.980、Barrientos-style 0.993、minimal 0.000；**只有 minimal 臂 parse rate 为 0**，因此不能笼统说"所有 0 分臂都能被解析/进入六字段表示"，也不能说"所有 0 分臂都不可解析"；0 分 ≠ 模型完全不懂语义。

**演讲备注**：
- 强调两个 Δ=0 是"增量测量"结果，语义是"在该批响应上未测得增益"，不是"模块无价值"。
- −坐标重锚器一行的解读要分两层：可用性断裂（149/150 无效）与语义能力（无证据说归零）。
- D/E 一句带过细节，指向 barrientos_de_tables_v1.md Table D 与 classified 报告；只强调"接口不兼容 vs 语义失败"的区别。
- 预留口径说明：D/E 套件属外部/模块替换对照，不与正式三方法数字合并。

---

## 第 9 页｜Stage 3 扩展四类（受控合成）

**幻灯片标题**：Stage 3 违规检测类型扩展（DEV_ONLY 受控合成：40 变体 + 40 对照）

**表 9-1｜四类扩展合成面板（40 变体，每类 10）**：

| 方法（各方法扩展版） | variant-only Macro-F1 | variant-only Exact | paired control FP 率（40 对照） |
|---|---:|---:|---:|
| Winter-style 扩展 | 0.655 | 0.550 | 0.500 |
| Sun-style 扩展 | 0.333 | 0.300 | 0.125 |
| BM25 扩展 | 0.226 | 0.150 | 0.000 |
| TF-IDF/SVD 扩展 | 0.379 | 0.325 | 0.275 |

> 注（必标）：实际样本量 = **40 个受控合成变体 + 40 个合成合规对照**（prohibited/condition/constraint/exception 各 10）；评价口径 = variant-only 检测（40 变体）与 paired 成对（40 对照 + 40 变体）分表呈现；证据级别 = **development（受控合成 DEV_ONLY）**，非人工 Gold、非 formal Oracle，零 LLM/API；来源 = `outputs/reports/s3_extended_violation_comparison_v2.{json,md}`。

**表 9-2｜33 条人工 Gold（另行分表，绝不与上表合并）**：

| 项目 | 内容 | 本页检测数字 |
|---|---|---|
| 33 条人工裁决违规 Gold + 25 条 matching（decision-only） | 已冻结于 `data/gold/stage3/`（2026-08-10 发布） | **未运行/待授权**（formal Oracle 未启动；合成面板结果不构成对人工 Gold / 正式 Oracle 的性能声明） |

> 注（必标）：实际样本量 = 33（违规）+ 25（matching）条 decision-only 人工 Gold；评价口径 = 正式 Oracle 口径（未运行）；证据级别 = 人工 Gold（已冻结）——其**检测数字未运行**；来源 = `outputs/reports/formal_gold_publication_v1.md`、`data/gold/stage3/`。

**正文（按类型的诚实表述）**：
- 平均 variant-only F1：**prohibited_action_present 最易（0.893）**，**required_condition_not_enforced 最难（0.083）**。
- **prohibited = 可行性支持**：插入被禁止动作的任务被多数后端高精度检出（BM25 例外，受其后端刻度限制）；**constraint = 部分支持**：规则 action 可映射且模型存在约束表面时可检出；**condition / exception = 瓶颈揭示**：冻结模型缺 conditionExpression 与 boundary event，多数条件/异常变体不可观察或不可映射。**不得写成"四类均已提升/均已验证"**。
- 主要瓶颈：**action 映射（frozen gamma 门槛）与 BPMN 表面可观察性**；类型检测器与原始三类共享同一 action-mapping 前置条件。

**演讲备注**：
- 先给结论再给表：四类扩展是"消费接口存在 + 可行性/部分支持 + 两处瓶颈揭示"，不是四类全部成功。
- 强调 9-1 与 9-2 必须分表：合成数字永远不并入 33 条人工 Gold。
- 若被问"为什么 condition 最难"：归因于冻结 BPMN 无可观察的条件表面（含 subProcess 内命名网关被解析器当黑盒），与检测公式无关的部分要讲清。
- 不出现 v1 三类型 30 变体面板的数字（两面板样本/公式不同，无联合指标）。

---

## 第 10 页｜衔接实验：只替换 Stage 2，违规判断怎么变

**幻灯片标题**：Stage 2 → Stage 3 成对衔接实验（Rules-Only 臂已运行；Direct-LLM 臂待授权）

**方法（一句话）**：同一 9 段 GDPR 条款 / 74 句输入、固定 Stage 1 解析与 Stage 3 后端/阈值（gamma_ext 0.5 与各方法 action gamma）/评价，**只替换 Stage 2 预测**：外部预测经 first-valid-span 投影喂给四类型检测器，失败记显式原因、**绝不回填**参考确定性抽取。

**表 10-1｜Rules-Only 臂真实结果（development，受控合成）**：

| 方法 | variant macro-F1 | exact | unobservable | paired control FP 率 |
|---|---:|---:|---:|---:|
| winter | 0.5208 | 0.3750 | 23 | 0.45 |
| sun | 0.1875 | 0.1500 | 32 | 0.05 |
| bm25 | 0.0000 | 0.0000 | 32 | 0.00 |
| tfidf_svd | 0.3510 | 0.2750 | 28 | 0.375 |

**表 10-2｜与参考确定性抽取的逐样本变化（40 变体）**：

| 方法 | 变化数 / 40 | 主要变化 |
|---|---:|---|
| winter | 7 | 4×禁止检出丢失、2×constraint 丢失、1×exception 丢失 |
| sun | 6 | 4×禁止丢失、2×constraint 丢失 |
| bm25 | 6 | 同上（其禁止类基线本受后端刻度限制） |
| tfidf_svd | 4 | 2×禁止丢失、1×constraint 丢失、**1 个新检出**（案例 b） |

> 注（必标）：实际样本量 = **40 变体 + 40 对照**（输入：冻结 9 段 GDPR 条款 / 74 句）；评价口径 = variant-only 检测与 paired control FP，均与参考确定性抽取（仅作上下文）成对比较；证据级别 = **development（受控合成 DEV_ONLY）**；Rules-Only 臂为**真实规则法预测**（锁定 B0 v10a，与 S2.12 零 API 臂同一方法/配方；英语 GDPR 句经德语合同 classifier 槽 pass-through——披露限制），零 LLM/API；来源 = `outputs/reports/gdpr_s2_s3_linkage_v1_rules_only.{json,md}` + `docs/research/LINKAGE_RULES_ONLY_RESULTS_NOTE_2026-09-06.md`。

**案例**：
- (a) **article22 s1 情态误标**："The data subject shall have the right **not to be** subject to…"——参考确定性抽取判 prohibition，Rules-Only 整句单 clause 判 **obligation** → `syn_v2_prohibited_action_01/02` 的禁止检查以 `rule_modality_not_prohibition` 不可观察（4 方法 × 2 变体 = 8 个不可观察）：**情态标签错误使"该查的违规不再可查"**。
- (b) **tfidf 恢复可观察性**：`syn_v2_constraint_violated_04` 在参考 action 文本下不可观察（`action_mapping_below_gamma`）；换 Rules-Only 预测的 action span 后可映射并正确检出 `constraint_violated`（参考→臂 = 新检出）——**替换 Stage 2 的效应方向不唯一**。

**正文（解释）**：B0 真实预测的字段覆盖与情态标签不同于参考确定性抽取，总体上使检出下降（漏检为主），但**检出精度保持高**（被检出类型 P=1.0、无 wrong-type、对照误报未上升）——这是"**替换 Stage 2 会真实改变最终违规判断**"的直接证据（本受控设置下以负向为主）。**direct_llm 臂**：输入与 74 个冻结请求已准备，真实调用**未授权** → **未运行/待授权**，不填任何数字。

**演讲备注**：
- 讲清这个实验回答的问题：Stage 2 质量如何向下游传播（end-to-end 因果的最小闭环），而不是再报一遍 Stage 2 分数。
- 案例 (a) 建议配原文高亮，直观展示 obligation/prohibition 一字之差导致两类变体不可检。
- 明确受控合成 + DEV_ONLY 边界：不是人工 Gold、不是 formal Oracle、不与 33 条合并；不宜写"LLM 替换必然提升端到端"。
- Direct-LLM 臂只报状态不报数：已备 74 个冻结请求，等一次合并授权（与 S2.12 一并，见第 12 页）。

---

## 第 11 页｜真实成功与失败案例

**幻灯片标题**：目前能站住的成功证据与必须承认的失败/局限（不回避）

**证据索引表**：

| # | 案例 / 结论 | 方向 | 一句话证据 | 来源文件 |
|---|---|---:|---|---|---|
| 1 | Direct-LLM 高精度、constraint/condition/action 字段领先 | 成功证据 | 正式主口径 action 0.944 / condition 0.838 / constraint 0.743，modality 标签 0.833 | `stage2_formal_three_method_comparison_v1.*` |
| 2 | 规则法在 actor / exception 领先 | 规则法仍有价值 | actor 0.820、exception 0.880（召回驱动） | 同上 |
| 3 | 共享情态目标上 Barrientos 原生略高 | 诚实对照 | 三类 modality Macro-F1：Barrientos 原生 0.890 vs 本文 0.822 | `barrientos_de_tables_v1.md`（Table C） |
| 4 | H1（Rules+LLM-Repair）净负 | 负结果 | 历史 development 全量粗口径 0.7621 vs Rules-Only 0.7986（**单列并注明 development 口径，不混入正式页**）；正式主口径亦净负（actor 0.430） | `sun_llm_fallback_method_gate_decision_dry_run_v2.md`；`stage2_formal_three_method_comparison_v1.*` |
| 5 | B0 真实预测替换到 Stage 3 的负向传播 | 局限 | 检出整体下降、无 wrong-type、方向不唯一（受控合成） | `gdpr_s2_s3_linkage_v1_rules_only.*` |
| 6 | Article22 情态误标 | 失败案例 | obligation vs prohibition → 2 个禁止动作变体不可检 | 同上 + linkage 注记 |
| 7 | tfidf 恢复可观察性 | 反向案例 | `constraint_violated_04` 由不可观察变为检出 | 同上 |

> 注（必标）：本表为**证据索引**，不产生新结果；各数字的实际样本量/评价口径/证据级别随其来源文件（速查表逐项列出）。

**正文**：小结必须"两边都讲"——成功证据（描述性、无显著性）：Direct-LLM 在 action/condition/constraint 与 modality 标签占先，规则法在 actor/exception 占先；共享 modality 目标上 Barrientos 原生 0.890 略高于本文 0.822（照实写，因其 schema 无法直接表达 actor/action/exception/definition，故**不排总榜**）；H1 负结果 → 停止优化；B0 替换到 Stage 3 的负向传播为"替换 Stage 2 会改变最终违规判断"提供了直接证据，但同时存在方向不唯一的恢复案例。全文不出现"我们显著优于 / 全面优于"表述。

**演讲备注**：
- 建议把 #3、#4、#6 主动讲掉——诚实表比被抓漏洞好。
- #3 的解释脚本：较窄的三类 modality 目标上对方更强；本文展示的是六字段抽取 + 面向 BPMN 的接口适配价值，两类 schema 不可直接排榜（C4）。
- #4 的数字只在"对 Hybrid 负结果对照"语境出现一次，其余页面一律用正式口径。
- #7 说明效应方向不唯一，为第 10 页"不能写必然提升"作呼应。

---

## 第 12 页｜结论、论文剩余工作与下一步

**幻灯片标题**：结论与下一步（每项标注状态）

**正文（结论，≤4 句）**：正式 Stage 2 比较（2026-08-11）表明 Direct-LLM 与规则法在字段级互补、Rules+LLM-Repair 净负（描述性）；Prompt/后处理消融与 Stage 3 扩展、衔接实验均为 development/受控合成证据，用于定位贡献与瓶颈；论文最终数字待第 12 页所列正式化步骤完成后按正确口径回填。

**表 12-1｜必须完成项**：

| # | 任务 | 状态 | 说明 / 原因 |
|---|---|---|---|
| 1 | S2.12 两 API 臂（合计 63 次：direct_llm 36 + sun_llm_fallback 27）与 GDPR Direct-LLM 臂（74 次）**合并授权** → 运行 → S2.13 冻结 | **已准备待授权（未运行/待授权）** | 输入、冻结请求、runner 安全 v2 与预检已就绪；授权缺项已列明；未运行故不填数字 |
| 2 | 9 段 GDPR 条款人工 Gold Rule Records 裁决 | **已准备（裁决材料已备）** | 裁决界面/材料就绪，待用户逐条裁决；裁决完成前 Gold Rule Records 不存在、formal Oracle 不得启动 |
| 3 | formal Oracle（Stage 3，S3.7）与端到端正式化 | **未完成** | 依赖 1、2 及正式 Process/Rule Records、独立门禁；未运行/待授权；禁止伪 Oracle；E00/E10/E01/E11 归因消融随之 |
| 4 | 论文按正确口径回填 | **未完成** | 待 1–3 的正式结果；正式结论（如 C07/C09/C23/C24）可用，development 数字不得混入；四类扩展不得写成正式验证 |

**表 12-2｜可选增强（状态标注）**：

| 可选增强 | 状态 |
|---|---|
| Stage 2 复杂度退化曲线（G0.5 冻结的 L1/L2/L3） | **已准备待授权**（依赖 S2.12 两 API 臂结果） |
| S3.9-EXT 四类扩展 → formal Oracle 的正式化 | **未完成**（前置：人工 Gold Rule Records + Oracle 门禁） |
| 提示/后处理模块完整单因素矩阵（few-shot 因素已有结果；其余可 0 新增 API 离线重放） | **部分已运行**（离线可完成项已列出） |
| 法域可迁移性演示（EStG → GDPR 抽取口径） | **未完成**（无专门实验，属论文写作可选） |

**演讲备注**：
- 收尾给出"唯一的下一步阻塞"：**一次合并授权**（S2.12 63 次 + GDPR Direct-LLM 74 次），之后 S2.13 → Oracle/端到端 → 论文回填是一条链。
- 强调第 12 页每个任务的"状态"都不是口头判断，都有对应 readiness/授权文件可查。
- 向导师提明确的决定请求：① 是否授权合并的 137 次真实调用（63 + 74）；② 9 段 GDPR Gold Rule Records 的人工裁决时间窗口。
- 结束语重申汇报口径：表格都标了样本量/口径/证据级别/来源；未运行 = 待授权，不编数字。

---

## 数字与来源速查表

> 说明：以下列出本稿使用的每一个数字（含规模/调用数）及其实际样本量、证据级别/口径与来源文件路径。路径均相对 `formal_experiment/`。

| 数字（照抄原值） | 含义 | 实际样本量 | 证据级别 / 评价口径 | 来源文件路径 |
|---|---|---|---|---|
| actor F1 0.820 / 0.758 / 0.430 | Rules-Only / Direct-LLM / Rules+LLM-Repair | 150 句 | 正式；句子级粗 Gold 逐字段 F1 | `outputs/reports/stage2_formal_three_method_comparison_v1.{json,md}` |
| action F1 0.893 / 0.944 / 0.895 | 同上 | 150 句 | 正式；同上 | 同上 |
| condition F1 0.774 / 0.838 / 0.777 | 同上 | 150 句 | 正式；同上 | 同上 |
| constraint F1 0.618 / 0.743 / 0.620 | 同上 | 150 句 | 正式；同上 | 同上 |
| exception F1 0.880 / 0.762 / 0.880 | 同上 | 150 句 | 正式；同上 | 同上 |
| modality 标签准确率 0.740 / 0.833 / 0.820 | 三方法 | 150 句 | 正式；四类标签 accuracy，单列 | 同上 |
| F1 0.7719（完整）→ 0.7650（Δ−0.0069，actor Δ−0.1317）→ 0.7759（Δ+0.0040，action Δ−0.0518、exception Δ+0.1059）→ 0.7790（Δ+0.0071，合法率 1.0） | Prompt 单因素消融 | 150 句 × 4 条件；真实 450 次调用 | development；单次描述性，无显著性推断 | `outputs/reports/d1_prompt_factorial_results_v1.{json,md}` |
| 完整后处理 0.772；−adapter Δ0；−坐标重锚器 F1 0.000（149/150 无效）；−validator Δ0 | 后处理单因素消融 | 150 条（D-full-0813 raw，离线重放） | development（回顾性；0 新增 API） | `outputs/reports/d_full_postprocessing_ablation_v1.{md,json}` |
| D/E 套件：no-fewshot 可解析 0.980、Barrientos-style 0.993、minimal 0.000（F1 均为 0） | 模块替换 = 接口不兼容 | D/E 套件真实 1140 次调用 | development（外部/模块替换对照） | `outputs/reports/barrientos_de_tables_v1.md`；`outputs/reports/direct_llm_ablation_existing_results_classified_v1.md` |
| S3.9-EXT：Winter 0.655 / 0.550 / 0.500；Sun 0.333 / 0.300 / 0.125；BM25 0.226 / 0.150 / 0.000；TF-IDF 0.379 / 0.325 / 0.275 | variant-only Macro-F1 / Exact / paired control FP | 40 变体 + 40 对照 | development（受控合成 DEV_ONLY，零 API） | `outputs/reports/s3_extended_violation_comparison_v2.{json,md}` |
| prohibited 平均 F1 0.893（最易）；condition 平均 F1 0.083（最难） | 平均 variant-only F1 | 上表 40 变体 | development（受控合成） | 同上 |
| linkage Rules-Only：winter 0.5208 / 0.3750 / 23 / FP 0.45；sun 0.1875 / 0.1500 / 32 / 0.05；bm25 0.0000 / 0.0000 / 32 / 0.00；tfidf_svd 0.3510 / 0.2750 / 28 / 0.375 | variant macro-F1 / exact / unobservable / paired control FP | 40 变体 + 40 对照；输入 9 段条款 / 74 句 | development（受控合成；Rules-Only 真实预测 B0 v10a，英文 pass-through 披露） | `outputs/reports/gdpr_s2_s3_linkage_v1_rules_only.{json,md}`；`docs/research/LINKAGE_RULES_ONLY_RESULTS_NOTE_2026-09-06.md` |
| 逐样本变化：winter 7/40、sun 6/40、bm25 6/40、tfidf 4/40 | 相对参考确定性抽取 | 40 变体 | 同上 | 同上 |
| 共享三类 modality：Barrientos 原生 0.890 vs 本文 0.822（Macro-F1） | 外部/共享对照（诚实表述） | 同一 Gold / 同一评价函数的共享目标（报告未单列条数，见报告上下文） | development（真实调用对照；C4：不排总榜） | `outputs/reports/barrientos_de_tables_v1.md`（Table C）；`outputs/reports/direct_llm_ablation_existing_results_classified_v1.md` |
| H1 历史 development 全量粗口径 F1 0.7621 vs Rules-Only 0.7986 | H1（Hybrid）净负对照（仅第 11 页单列并注明） | 历史全量运行（development 口径） | development（与正式口径不同，不混入） | `outputs/reports/sun_llm_fallback_method_gate_decision_dry_run_v2.md`；`outputs/reports/b0_d1_experiment_closure_brief.md` |
| EStG-150 = 150 句 | 正式 Stage 2/3 benchmark | 150 句 | 正式 Gold（LLM-assisted, human-adjudicated，2026-08-10 发布） | `AGENTS.md`；`outputs/reports/formal_gold_publication_v1.md` |
| S2.11 复杂语料 = 36 条（Barrientos requirements） | 复杂语料扩展载体 | 36 条（review population = 29 可用 + 7 不可用） | 已冻结（G0.5 分层冻结；S2.11 36/36 裁决冻结，不发布 Gold） | `outputs/reports/s2_13_s3_7_transition_readiness_v7.md`（40/4/36、Checkpoint G；最新状态以 v8 为准）；`configs/g05_complexity_frozen_v1.json`（G0.5） |
| GDPR-7 = 7 个流程（Stage 1 已冻结）；S3.9-EXT = 40 对合成样本 | 数据/面板规模 | 7 流程；40 对 | 冻结状态 | `outputs/reports/s1_5_process_gold_freeze_authorization_v1.manifest.json`；`outputs/reports/s3_extended_violation_comparison_v2.md` |
| S2.12 两 API 臂合计 63 次（direct_llm 36 + sun_llm_fallback 27）；GDPR Direct-LLM 臂 74 次 | 待授权真实调用规模 | 63 次 + 74 次（均未运行） | 未运行/待授权（不填结果数字） | `docs/API_AUTHORIZATION_REQUEST.md`；`docs/research/LINKAGE_RULES_ONLY_RESULTS_NOTE_2026-09-06.md` |
| Prompt 消融真实 450 次调用；D/E 套件真实 1140 次调用 | 真实调用成本/规模 | 450；1140 | development（已授权、已记账） | `outputs/reports/d1_prompt_factorial_results_v1.md`；`outputs/reports/direct_llm_ablation_existing_results_classified_v1.md` |
