# 导师进度汇报内容稿（2026-09-06 定稿版）——基于 Sun 三阶段框架的合规规则抽取 LLM 化与违规检测类型扩展

> **2026-09-10 使用前修正**：第11页及其他位置引用的33条违规表目前仅可作为范围待核实的诊断。
> 这33条全部是正标签，推断输入未绑定目标活动/规范/变体；部分依据引用未输入的Article 12/19。
> 已确认材料有3条文字顺序说明，不能再说“没有顺序信息”。新开发检查器已接入这些说明并正确
> 识别局部通知活动及执行者，但原33条标签的范围仍需核实。详见
> `outputs/reports/s3_evidence_repair_v1.md`。第12页“待裁决/待API授权”也是历史状态：人工规则
> 已发布，137次调用已有授权，当前运行环境配置尚未就绪。不得按旧状态原样讲述。

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

## 第 9 页｜Stage 3：沿用 Sun，扩展四类检测

**讲解主线**：保留 Sun 的缺失动作、执行者错误、顺序错误；增加禁止动作、条件未落实、约束违反、例外未处理。参照 Sun 的受控变异方式，分别改变流程中的一种因素，检查是否识别相应错误。

**结果：40 个变体，参考确定性抽取，开发性受控数据**

| 方法 | 禁止动作 / 条件 / 约束 / 例外 F1 | Macro-F1 | Exact | 错误类型数 | 目标类型不可观察数 |
|---|---:|---:|---:|---:|---:|
| Winter-style | 0.952 / 0.235 / 0.400 / 0.308 | 0.474 | 0.425 | 9 | 18 |
| Sun-style | 0.952 / 0.000 / 0.000 / 0.000 | 0.238 | 0.250 | 1 | 30 |
| BM25 | 0.571 / 0.000 / 0.000 / 0.000 | 0.143 | 0.100 | 0 | 30 |
| TF-IDF/SVD | 1.000 / 0.000 / 0.333 / 0.167 | 0.375 | 0.325 | 1 | 27 |

这些是四个后端使用同一新增检测公式的比较；参考抽取不是人工 Gold，也不是 Direct-LLM。禁止动作有可行性证据，约束有部分证据，条件和例外仍受映射与流程可观察性限制。

**备注**：40 对合成样本，按构造预设对照/变体标签；不并入 33 条人工 Gold。表内 Macro-F1 为 variant-only。目标类型不可观察可与错误类型预测重叠。当前来源：`outputs/reports/s3_formula_repair_v2.json`；逐样本与运行 manifest：`outputs/evidence/s3_formula_repair_v2/`。

---

## 第 10 页｜Stage 2 的输出是否会影响下游

**设计**：固定法规、流程、检测器和阈值，仅替换规则记录来源。已有真实 Rules-Only 预测 74 句；Direct-LLM 的 GDPR 下游臂尚未运行。

**结果：Rules-Only，40 个变体；另用 40 个对照测误报**

| 方法 | 禁止动作 / 条件 / 约束 / 例外 F1 | Macro-F1 | Exact | 错误类型数 | 目标类型不可观察数 |
|---|---:|---:|---:|---:|---:|
| Winter-style | 0.750 / 0.222 / 0.353 / 0.000 | 0.331 | 0.275 | 10 | 23 |
| Sun-style | 0.750 / 0.000 / 0.000 / 0.000 | 0.188 | 0.150 | 0 | 32 |
| BM25 | 0.000 / 0.000 / 0.000 / 0.000 | 0.000 | 0.000 | 0 | 32 |
| TF-IDF/SVD | 0.889 / 0.000 / 0.286 / 0.154 | 0.332 | 0.275 | 6 | 28 |

| 方法 | 80 对象准确率 | 合规对照误报率 | 40 对全部判对比例 | 四违规类 Macro-F1 | 五类 Macro-F1 |
|---|---:|---:|---:|---:|---:|
| Winter-style | 0.263 | 0.450 | 0.150 | 0.264 | 0.283 |
| Sun-style | 0.200 | 0.050 | 0.150 | 0.167 | 0.205 |
| BM25 | 0.150 | 0.000 | 0.000 | 0.000 | 0.075 |
| TF-IDF/SVD | 0.263 | 0.375 | 0.225 | 0.268 | 0.287 |

结论：规则字段的差异会改变部分下游判断，但目前还不能证明 LLM 的端到端优势。必须同时看检出和误报，不能只比较违规样本的 F1。

**备注**：英文输入经德语 classifier 槽 pass-through、每字段首个有效 span 投影均会影响结果；差异不能全部归因于 Stage 2 方法。来源：`outputs/reports/s3_formula_repair_v2.json`；逐样本与运行 manifest：`outputs/evidence/s3_formula_repair_v2/`。

---

## 第 11 页｜创新点与证据对应

1. Stage 2 用 LLM 替代传统抽取：150 句正式比较支持字段级互补；action、condition、constraint 与情态准确率方面 Direct-LLM 领先，不声称全面领先。
2. 借鉴 Barrientos 的结构化生成与验证：已有提示和后处理消融，说明示例、语义规则、输出接口各自的作用及局限，不把接口失败当作语义能力崩溃。
3. Stage 3 丰富错误类型：四类字段已接入检测，禁止动作可行性证据较强，其他类型支持程度不同。
4. 原三类 33 条人工标签：参考 Macro-F1 0.389、Rules-Only 0.333。修复前后各自最终判定不变；两来源之间只有 v014 判定不同。缺失动作均为 11/11 检出；顺序类缺少可用关系或端点映射，0 分不能解释为流程合规。

**案例讲法**：同一句法规的禁止/义务标签不同，会使禁止动作检查可用或不可用；规则未提取到例外时，检测器无法检查例外。这说明抽取字段会影响下游，不能代替真实 LLM 臂的比较。

**备注**：Sun 原三类公式结构保留，本轮只修关联、时间适用范围和错误统计。原有 γ 网格复核后 0.8/0.6 的 Macro-F1 仍为 0.3889/0.8733；0.6 是同一开发集上的描述性适配值。来源：`outputs/reports/s3_formula_repair_v2.json`；逐样本与运行 manifest：`outputs/evidence/s3_formula_repair_v2/`。

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

内部备注（不进正文）：MASTER 3.6.38、Git 检查点、API 授权细节与撤回历史见内部文档。

---

## 数字与来源速查表

| 数字 | 样本量/口径/证据级别 | 来源 |
|---|---|---|
| Stage 2 逐字段 F1（0.820…0.880） | 150 句 / 句子级粗 Gold / 正式 | `stage2_formal_three_method_comparison_v1.*` |
| Prompt 消融 0.7719/0.7650/0.7759/0.7790 | 150 句 / 同一 Gold+evaluator / development（真实 450 calls） | `d1_prompt_factorial_results_v1.*` |
| 后处理 0.772/0/0.772 | 150 条 raw 离线 / development | `d_full_postprocessing_ablation_v1.md` |
| 四类修复后 macro 0.474/0.238/0.143/0.375（参考）与 0.331/0.188/0/0.332（Rules-Only 臂） | 40 变体+40 对照 / 统一五分类 / DEV_ONLY 合成 | `outputs/reports/s3_formula_repair_v2.json` |
| 原三类 macro 0.389/0.333 | 33 条人工 Gold / dev Sun-style / development | `outputs/reports/s3_formula_repair_v2.json` |
| 74 句输入、74/74 Rules-Only | 9 段条款 / Gold-blind / 已运行（零 API） | `data/input/gdpr7_stage2_input_v1.json`、`data/predictions/gdpr7_sun_rule_only_v1/` |
| Direct-LLM 74 臂 | 假响应 74/74（程序验证，非实验）→ 真实待授权 | `run_gdpr7_direct_llm_v1.py --fake-transport`；申请 §12 |

（本稿内部不使用旧条件性检出口径的数字；如需对照可查
`docs/research/S3_EXT_UNIFIED_EVALUATION_NOTE_2026-09-06.md` 的 old_vs_new。）
