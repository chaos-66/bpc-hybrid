# 导师进度汇报内容稿（2026-09-06 定稿版）——基于 Sun 三阶段框架的合规规则抽取 LLM 化与违规检测类型扩展

> 用途：约 12 页导师进度汇报（每节 1 页）。正文用于页面排版，演讲备注供口播。
> 纪律：只写事实与状态；无显著性推断；未运行项写“未运行/待授权”，不填预期数字。
> 每个结果表标注：样本量 / 评价口径 / 证据级别 / 来源。
> 代号：Rules-Only（=sun_rule_only，Sun Stage 2 方法级重建，非 LLM）；Direct-LLM
> （=direct_llm，主方法）；Rules+LLM-Repair（=sun_llm_fallback，负结果对照）。

---

## 第 1 页｜封面与研究定位

**幻灯片标题**：规则抽取 LLM 化 + 违规类型扩展——在 Sun 三阶段框架上的两项改进

**正文**：研究以 Sun et al. (2024) 的三阶段框架（流程解析 → 法规解析 → 匹配与违规
检测）为整体主干与改进对象。两处改进：(1) **Stage 2 用受约束 LLM 直接抽取 Sun
六要素 Rule Record**（Direct-LLM 为主方法；Rules-Only 为 Sun Stage 2 方法级重建的
强对照；Rules+LLM-Repair 为负结果对照）；(2) **Stage 3 扩展四类违规类型**
（prohibited_action_present / required_condition_not_enforced / constraint_violated /
exception_not_handled），消费六要素中此前无下游消费者的字段。Barrientos et al.
(2026) 是 Stage 2 LLM 方案的**方法借鉴来源**（结构化输出、校验、受控词汇、评价
纪律），不是必须整体战胜的对象；原“原生 FULL/NO-PATTERNS 360 次”执行方案已撤回，
仅历史证据。

**演讲备注**：30 秒讲清“主干 Sun、借鉴 Barrientos、改在两处”；明说实验尚未全部
结束（第 12 页状态表）。

---

## 第 2 页｜研究背景与问题

**幻灯片标题**：设计期合规检查为什么卡在“规则抽取”

**正文**：
- 场景：流程建模阶段即对照法规（税法 EStG、GDPR）检查 BPMN 是否合规。
- Sun 框架把检查做成数据流（Process Record × Rule Record → Violation Report），
  但 Stage 2 规则/词典抽取有三个软肋：词典覆盖决定召回上限；字段归属错误让下游
  “按字段消费”的检查整体失效（第 10 页有真实案例）；换法域需重建词典规则。
- 由此形成两个动作：LLM 化抽取（改进 1）与让更多 Rule Record 字段拥有 Stage 3
  消费者并诚实测出可检测边界（改进 2）。

**演讲备注**：强调瓶颈不是“调用成本”，而是规则体系可维护性与字段质量。

---

## 第 3 页｜Sun 三阶段框架

**幻灯片标题**：方法主干：Sun 的三阶段数据流

**正文（文字框图）**：
```
法规文本 ──► Stage 2 法规解析 ──► Rule Record（六要素：modality/actor/action/
                                        condition/constraint/exception + 原文证据位置）
BPMN    ──► Stage 1 流程解析 ──► Process Record（活动/执行者/控制流）
Process Record × Rule Record ──► Stage 3 匹配与违规检测 ──► Violation Report
（Sun 原三类：missing_action / incorrect_actor / out_of_order）
```
- 本项目改动集中在 Stage 2 抽取方法与 Stage 3 类型接口；Stage 1（GDPR-7，7 个
  流程）沿用 Sun 方法思路并已冻结，不作为创新点；“方法级重建”≠作者原代码/原始
  数据，禁止 exact reproduction 表述。

**演讲备注**：一张图讲清 I/O；强调三方法输出同一 Rule Record schema 才能在同一
Gold/evaluator 上比较。

---

## 第 4 页｜与 Barrientos 的关系

**幻灯片标题**：借鉴方法学，不照抄任务与 schema，不比“总榜”

**正文**：
- 借鉴（Stage 2 LLM 方法学）：严格 JSON 结构输出+解析、输出校验与失败入分母
  （fail-closed）、受控词汇/受控 schema、归一化与评估纪律（adapter 对齐、口径隔离）。
- 不照抄：schema/提示为本项目自研；Barrientos 情态 3 类 vs 本文 4 类；其表示包含
  流程侧 activities/participants 与 resources、norm 的 precondition/temporal
  validity——能表达部分近似 actor/action 语义，但与 Sun 六要素 Rule Record 及
  verbatim evidence span 是不同契约（不能声称其“完全无法表达 actor/action”）。
- 比较合同：跨任务/跨 schema 禁止用单一 F1 排序（C4）；唯一合法跨方法共享目标是
  三类 modality（同一 Gold 同一度量函数）：Barrientos 原生 0.890 vs 本文 0.822，
  照实写；模块替换进六字段接口=0 分（接口不兼容证据，不是 Barrientos 无效）。
- 已撤回：原“FULL/NO-PATTERNS 原生提示 360 次”执行方案（2026-09-05 误准备、
  2026-09-06 撤回；入口/合同/预检保留为历史证据，真实 API=0）。

**演讲备注**：主动回答“为什么不直接做 Barrientos 那套”——因为主干任务是 Sun 六要素。

---

## 第 5 页｜数据与公平比较条件

**幻灯片标题**：四块冻结数据 × 三方法，统一输入/输出/Gold/evaluator

**正文表**：

| 数据 | 内容 | 状态 | 用途 |
|---|---|---|---|
| EStG-150 | 150 句税法英文工作文本，项目独立重建 benchmark（非 Sun 原 150） | LLM-assisted human-adjudicated Gold 已冻结（2026-08-10） | Stage 2 正式主比较 |
| S2.11 复杂语料 | 36 条（Barrientos requirements） | 已冻结 + Gold 已发布（2026-08-17） | 复杂度分层（S2.12） |
| GDPR-7 | 7 个 BPMN 流程 + 9 段条款（article6/7/15/16/17/20/22/33/34） | Stage 1 冻结；33 条原三类违规 decision Gold 冻结 | Stage 3 / 衔接 |
| S3.9-EXT 面板 | 四类 × 10 变体 + 10×4 合规对照（受控合成） | 冻结（DEV_ONLY，非 Gold） | Stage 3 类型扩展 |

公平条件：三方法共享同一冻结输入 ID、Gold、schema、normalization、evaluator 与
Stage 3 配置；Gold 对 runner 不可见；禁止用 EStG 预测接 GDPR 流程（同法才可衔接）。

**演讲备注**：一句带过“同一数据同一裁判”是全部比较的前提。

---

## 第 6 页｜Stage 2 主结果（正式，2026-08-11）

**幻灯片标题**：同条件三方法比较：字段级互补，无整体胜者

**正文表（150 句，句子级粗 Gold 主口径，逐字段 F1 + modality 标签）**：

| 字段 | Rules-Only | Direct-LLM | Rules+LLM-Repair |
|---|---:|---:|---:|
| actor | 0.820 | 0.758 | 0.430 |
| action | 0.893 | **0.944** | 0.895 |
| condition | 0.774 | **0.838** | 0.777 |
| constraint | 0.618 | **0.743** | 0.620 |
| exception | **0.880** | 0.762 | 0.880 |
| modality 标签 accuracy | 0.740 | **0.833** | 0.820 |

样本量 150 句；口径=句子级粗 Gold（609 spans）逐字段 F1 + modality label 另表；
证据级别=**正式**（零新增 API，历史真实调用 300 次）；来源=
`outputs/reports/stage2_formal_three_method_comparison_v1.*`。
结论（描述性）：Direct-LLM 在 action/condition/constraint 与标签准确率领先；
Rules-Only 在 actor/exception（高召回）领先；**无整体胜者声明**。Rules+LLM-Repair
为对照臂：其全量 150 运行（development，commit 74614e3）主口径 F1 0.7621 vs
Rules-Only 0.7986（净负、actor 过抽）——该数字只在对 Hybrid 负结果的备注中单列，
**不混入正式主表**。

**演讲备注**：讲“互补”而非“谁赢”；把负结果对照作为“需要证据约束的修复”的论据。

---

## 第 7 页｜提示消融（真实 450 calls，严格单因素）

**幻灯片标题**：删了什么、结果如何：语义示例有小幅正贡献，规则/JSON 纪律无总体增益

**正文表（150 句 / 同一 Gold / 同一 evaluator / 单次描述性；DeepSeek-V4-Pro-0813）**：

| 条件 | F1 | ΔF1 | 逐字段要点 |
|---|---:|---:|---|
| 完整方法（6 个合成示例） | 0.7719 | — | 基线 |
| 语义示例 → 纯结构模板 | 0.7650 | −0.0069 | actor −0.1317（最明显） |
| 删详细语义规则（9–19、25–27） | 0.7759 | +0.0040 | action −0.0518；**exception +0.1059（删规则后上升，不得写成规则改善 exception）** |
| 删显式 JSON 纪律 | 0.7790 | +0.0071 | 合法输出率仍 1.0 |

真实调用 450/450、失败 0、USD 3.37；来源 `d1_prompt_factorial_results_v1.*`。
表述纪律：总体无正增益≠模块无用；字段间权衡如实写；单次运行不做显著性推断。

**演讲备注**：讲清“为什么删、删了看什么、证明什么”；避免把 Δ+0.004 讲成提升。

---

## 第 8 页｜后处理消融（离线重放，0 新增 API）

**幻灯片标题**：坐标重锚是接口必需件；adapter/validator 的 Δ0 是安全职责

**正文表（固定 D-full-0813 原始响应 150 条离线重放）**：

| 条件 | F1 | 说明 |
|---|---:|---|
| 完整链 | 0.772 | 150/150 有效、148 非空 |
| −输出适配器 | 0.772 | 本批响应无额外分数增量 |
| −坐标重锚器 | **0.000** | 149/150 被 validator 拒绝——**接口+校验链可用性结果，不是语义能力归零** |
| −canonical validator | 0.772 | 0 条无效被观测（Δ0 不取消安全职责） |

另（D/E 套件，真实 1140 calls，2026-08-29）：模块替换的三条零分臂必须逐臂写
parse 率——no-fewshot parse 0.980、Barrientos-style 0.993（可解析但 canonical
非空=0，接口/格式失配）、**minimal 臂 parse=0.000（未产出可解析 JSON）**。
来源：`d_full_postprocessing_ablation_v1.md`、`paper/ABLATION_MATRIX.md` 实验 D/E。

**演讲备注**：讲“机制 vs 语义”分层，防止审阅人把接口错误读成语义失败。

---

## 第 9 页｜Stage 3 扩展（统一五分类口径，DEV_ONLY 受控合成）

**幻灯片标题**：四类新违规类型——按类型分列证据，不做“四类均已提升”结论

**正文（口径修正说明）**：历史运行器把违规侧预测做成“预置类型或 None”（条件性
检出，读取 expected），不是分类；本次已把**合规与违规两侧统一为同一五分类决策**
（固定类型优先级、同一阈值与不可观察规则；决策不读 expected/Gold；失败与不可观察
全部入分母）。旧数字仅作为“条件性检出”备用（
`docs/research/S3_EXT_UNIFIED_EVALUATION_NOTE_2026-09-06.md`）。

**正文表（40 变体 variant-only，统一口径；参考确定性抽取——非人工 Gold）**：

| 方法 | prohibited/condition/constraint/exception F1 | Macro-F1 | Exact | wrong-type | Unobservable |
|---|---:|---:|---:|---:|---:|
| Winter-style | 0.952 / 0.235 / 0.500 / 0.308 | 0.499 | 0.450 | 9 | 17 |
| Sun-style | 0.952 / 0.000 / 0.333 / 0.000 | 0.321 | 0.300 | 1 | 28 |
| BM25 | 0.571 / 0.000 / 0.333 / 0.000 | 0.226 | 0.150 | 0 | 28 |
| TF-IDF/SVD | 1.000 / 0.000 / 0.333 / 0.167 | 0.375 | 0.325 | 1 | 27 |

paired（40 合规 + 40 变体，control FP 两口径一致）：winter 0.375 / FP 0.500；sun
0.263 / 0.125；bm25 0.250 / 0.000；tfidf 0.338 / 0.275。
按类型结论：prohibited=可行性支持（除 BM25 长度刻度外 F1 高）；constraint=部分
支持；condition/exception=主要揭示 BPMN 表面与动作映射的可观察性瓶颈。**不得写
“四类均已有效提升”或“全部字段证明下游价值”**；33 条人工 Gold、40 对合成面板与
正式 Oracle 严格分表。来源：`outputs/reports/s3_extended_unified_v1_reference.*`。

**演讲备注**：先讲口径修正（为什么不能看旧 P=1），再给数字；把“诚实测边界”讲成贡献。

---

## 第 10 页｜衔接实验：只替换 Stage 2，违规判断怎么变

**幻灯片标题**：同法规/同流程/同检测器，Rules-Only 预测接入四类检测（真实运行；
Direct-LLM 臂待授权）

**正文**：输入=冻结 9 段 GDPR 条款分句 74 句（Gold-blind，分句与面板锁定一致）；
Rules-Only（锁定 B0 v10a）真实零 API 预测 74/74；同一固定四类型检测器消费外部
预测（first-valid-span 衔接适配投影，失败/缺失显式计数、绝不回填面板锁定抽取）。

**正文表（Rules-Only 臂，统一五分类口径，40 变体 + 40 对照）**：

| 方法 | variant macro-F1 | variant exact | wrong-type | control FP | paired 5-class |
|---|---:|---:|---:|---:|---:|
| Winter-style | 0.331 | 0.275 | 10 | 0.450 | 0.263 |
| Sun-style | 0.188 | 0.150 | 0 | 0.050 | 0.200 |
| BM25 | 0.000 | 0.000 | 0 | 0.000 | 0.150 |
| TF-IDF/SVD | 0.332 | 0.275 | 6 | 0.375 | 0.263 |

与参考确定性抽取的逐样本变化（统一口径）：winter 10/40、sun 7/40、bm25 8/40、
tfidf 6/40。案例：
- (a) article22 s1（“shall have the right **not to be** subject…”）两种方法情态
  标签不同（参考判 prohibition、Rules-Only 判 obligation）→ 2 个禁止动作变体
  在 Rules-Only 臂不可检。**无人工裁决前不认定谁正确**；只陈述“标签不同改变下游
  可检性”。(b) tfidf 下 2 个原不可观察项（action 映射 <γ）替换后变为可观察并检出
  constraint_violated——替换效应方向不唯一。
归因限制（必须讲）：Rules-Only 的英文句经**德语合同 classifier 槽 pass-through
（跨语言适用限制）**；first-valid-span 投影逐字段只取第一个有效 span（衔接适配
规则）——**下游差异不能全部归因于原始抽取方法或 LLM 创新**。
来源：`outputs/reports/s3_extended_unified_v1_rules_only.*` +
`docs/research/LINKAGE_RULES_ONLY_RESULTS_NOTE_2026-09-06.md`（含修正栏）。

**演讲备注**：此页是“误差传播真实证据”：替换 Stage 2 会改变最终判断（本受控设置以
漏检为主、类型错误出现、无合规误报整体上升结论——tfidf 臂 FP 由 0.275 升到 0.375
照实写）。

---

## 第 11 页｜成功与失败案例

**幻灯片标题**：值得写进论文的正反证据索引

**正文表（每条：结论 → 证据与来源）**：
1. Direct-LLM 高精度 + constraint 字段领先（正式比较；正式）。
2. Rules-Only actor/exception 高召回（正式比较；正式）。
3. 语义示例小幅正贡献；语义规则/JSON 纪律无总体增益但字段权衡（450-call 单因素；
   development，描述性）。
4. Rules+LLM-Repair 净负对照（development 全量 150；负结果保留）。
5. 共享 3 类情态目标：Barrientos 原生 0.890 vs 本文 0.822（真实 1140 calls 中
   D/E Table C；development，照实写对方高）。
6. 统一口径下参考/受控四类：prohibited 可行性、condition/exception 瓶颈
   （DEV_ONLY 合成）。
7. 衔接：Rules-Only 替换后检出下降为主、wrong-type 出现、tfidf FP 升 0.10，
   但存在“不可观察→新检出”反向案例（DEV_ONLY 合成；规则预测为真实运行）。
8. 原三类 33 条（dev，人工 Gold 评价）：参考抽取 macro 0.389 vs Rules-Only
   0.333（exact 0.364/0.333），逐样本 24 同/9 变，唯一判定翻转 v014
   （incorrect_actor→None）；missing_action 两侧均 11/11 F1=1.0；
   **out_of_order 两侧均 0：规则记录无 order_relations（胶囊为空）与端点相似度
   不足——是缺失输入契约+检测瓶颈，不是方法差异**（来源
   `outputs/reports/gdpr_3type_linkage_v1_{reference,rules_only}.*`）。

**演讲备注**：讲“哪些是已验证、哪些是开发性观察、哪些仍未完成”，不声称实验全部结束。

---

## 第 12 页｜结论与剩余工作

**幻灯片标题**：可汇报结论 + 只剩外部依赖的三件事

**正文（结论 ≤4 句）**：正式 Stage 2 比较表明 Direct-LLM 与 Rules-Only 字段级互补、
Hybrid 对照净负（描述性）；提示与后处理消融定位了模块贡献与接口风险；Stage 3
四类扩展与两条衔接链路在受控/开发口径给出可复现证据，统一规则下不再有
“P=1/无 wrong-type”式结论；所有结果不并入 33 条人工 Gold、不冒充正式 Oracle。

**剩余工作表（状态标注）**：
| 事项 | 状态 | 具体依赖 |
|---|---|---|
| GDPR Direct-LLM 74 臂真实调用 | 已实现并离线验证（74/74 假响应全流程）→ **待授权** | 授权句（scope gdpr7_direct_llm_v1:74）+ 预算（硬上限 USD 2.61/1.31、输入 74M、输出 303,104）；执行命令见 `API_AUTHORIZATION_REQUEST.md` §12 |
| S2.12 复杂语料 63 臂真实调用 | 执行器与计划已就绪 → **待授权** | 63 calls（输入≤63M、输出≤258,048、USD≤84.18/42.09），见申请 §11 |
| 9 段条款人工 Gold Rule Records（74 句） | 核对材料已备 → **待你裁决** | `gdpr7_six_element_review_blank_v1.json` + 指南 |
| 正式 Oracle / 端到端正式化 | **未完成（如实）** | 上面两项 + S2.13/S3.7 门禁 |
| 论文结果回填与投稿 | 部分（数字口径已统一） | 授权结果后按 manifest 回填 |

内部备注（不进正文）：MASTER 3.6.37、Git 检查点、API 授权细节与撤回历史见内部文档。

---

## 数字与来源速查表

| 数字 | 样本量/口径/证据级别 | 来源 |
|---|---|---|
| Stage 2 逐字段 F1（0.820…0.880） | 150 句 / 句子级粗 Gold / 正式 | `stage2_formal_three_method_comparison_v1.*` |
| Prompt 消融 0.7719/0.7650/0.7759/0.7790 | 150 句 / 同一 Gold+evaluator / development（真实 450 calls） | `d1_prompt_factorial_results_v1.*` |
| 后处理 0.772/0/0.772 | 150 条 raw 离线 / development | `d_full_postprocessing_ablation_v1.md` |
| 四类统一口径 macro 0.499/0.321/0.226/0.375（参考）与 0.331/0.188/0/0.332（Rules-Only 臂） | 40 变体+40 对照 / 统一五分类 / DEV_ONLY 合成 | `outputs/reports/s3_extended_unified_v1_{reference,rules_only}.*` |
| 原三类 macro 0.389/0.333 | 33 条人工 Gold / dev Sun-style / development | `outputs/reports/gdpr_3type_linkage_v1_*.{json,md}` |
| 74 句输入、74/74 Rules-Only | 9 段条款 / Gold-blind / 已运行（零 API） | `data/input/gdpr7_stage2_input_v1.json`、`data/predictions/gdpr7_sun_rule_only_v1/` |
| Direct-LLM 74 臂 | 假响应 74/74（程序验证，非实验）→ 真实待授权 | `run_gdpr7_direct_llm_v1.py --fake-transport`；申请 §12 |

（本稿内部不使用旧条件性检出口径的数字；如需对照可查
`docs/research/S3_EXT_UNIFIED_EVALUATION_NOTE_2026-09-06.md` 的 old_vs_new。）
