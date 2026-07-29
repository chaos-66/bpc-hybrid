# Stage 2 Evaluation Spec (S2.10-E v3)

> **版本**：v3.1 (2026-07-21)
> **依据**：`docs/research/BARRIENTOS_BORROWING_AUDIT_2026-07-12.md` §3.1 + Wave 1.1 §5 修正
> **目的**：定义 Stage 2 输出的评估指标体系，包括主指标、3 维度的准确拆分、和语义等价性测试方式
> **范围**：spec + 未来 development 候选实现 `src/bpc_hybrid/stage2_evaluation_v3.py`
> **配套**：`docs/STYLE_EQUIVALENT_SPEC.md`（评估体系内的 normalization-aware matching 部分）
> **状态**：S2.10-E v1.2 offline evaluator 与 immutable B0 development re-evaluation verified；正式主数据结果尚未运行

## 0. 实现与证据状态

S2.10-E 已把本规范落成统一 evaluator。未来 B0/H1/D1 development 运行共用
`configs/stage2_evaluator_s210_v3.json`、canonical prediction schema 和 v1.2 aggregate report
schema。评价器按 exact `sample_id` membership 拒绝缺行/多行，terminal API error、
recovered provider error 与 schema-invalid 记录均保留在请求分母；其中 H1 recovered error
可携带 canonical-valid B0 fallback，并保持 H1 method identity 继续计分。输出包含 clause-level 四类 modality、五类 span 的 strict/safe/token
指标、coverage/hallucination、结构边、错误与成本。`safe-legal-v1` 仅启用 Unicode NFC、
lowercase、空白折叠和尾部标点删除。

验收证据是 `s210_stage2_evaluator_contract_synthetic_v3.manifest.json` 的 5 条 synthetic
attempt 和 method-local-ID/boundary adversarial case。其中的分数只是合同回归常数，不是
B0/H1/D1 性能。v1.2 已复用 immutable B0 attempts 生成 development-only 重算报告；它不
等于 formal 主数据结果。formal scope 仍必须等待 Gold/输入和方法门禁，无命令行绕过开关。

v1.1 的 exact-ID/exact-span evaluator 及旧 B0 报告保留为 provenance，但 RWI-0014 已确认
其对 independently generated method IDs 和近似 clause boundary 存在系统性低计。以后不得
把旧报告当作 B0 性能估计，也不得覆盖或删除它。

---

## 1. 旧版 v1 的错误（必须改的）

旧 v1 的 semantic coverage 定义是 `prediction non-null / 6`，这是**错的**：

* 它把"预测了不存在的字段"算作"覆盖" → **奖励 hallucination**
* 它把"Gold 不要求该字段"算作"漏抽" → **惩罚正确 null**
* 它不能区分"系统决定该字段不存在" vs "系统没找到该字段"

旧 v1 的 structural encoding 把 `TP/(TP+FP+FN)` 称为 **accuracy**——这是**错的**：这个公式是 Jaccard / edge IoU，不是 accuracy。

旧 v1 的 "correct order pairs / predicted order pairs" 只算 **precision**，漏了 recall / F1。

旧 v1 的 clause_id uniqueness 是 **validation invariant**，不是准确率指标——它必须是 1（或者样本拒绝）。

旧 v1 的 deontic 单元是"整句顶层 modality"，这**不对**：multi-clause 句中不同 clause 有不同 modality，单元必须是 clause。

---

## 2. 主指标（必须保留）

这些是 Stage 2 的核心指标，**与 Sun 论文保持一致**，便于审稿人对照。

### 2.1 Modality 4 类分类

| 指标 | 公式 | 用途 |
|---|---|---|
| Macro-F1 | 4 类 F1 算术平均 | 主报告数字 |
| Per-class P/R/F1 | 4 类分别 | 哪类最差 |
| Confusion matrix | 4×4 | 哪两类易混 |
| Per-class support | 4 类样本数 | 解释 F1 异常 |

- 4 类固定：`obligation`, `prohibition`, `permission`, `definition`
- 单元：**clause**（不是整句）
- 缺失类（某类 support = 0）规则：F1 = 0、recall = 0、precision = NaN → 报告中显式标 N/A

### 2.2 六要素抽取

每个要素单独算：

| 要素 | 指标 |
|---|---|
| modality | 4 类 macro-F1 + 4 类 P/R + 4×4 confusion（见 §2.1） |
| actor | exact span P/R/F1 + token overlap P/R/F1 |
| action | exact span P/R/F1 + token overlap P/R/F1 |
| condition | exact span P/R/F1 + token overlap P/R/F1 |
| constraint | exact span P/R/F1 + token overlap P/R/F1 |
| exception | exact span P/R/F1 + token overlap P/R/F1 |

exact span = text == gold.text AND start == gold.start AND end == gold.end
token overlap = IoU of token sets (Jaccard)

micro 和 macro **分别报告**：
- micro：所有样本所有 token 一起算
- macro：按样本平均

### 2.3 报告表（主表）

| Method | obl-F1 | pro-F1 | perm-F1 | def-F1 | macro-F1 | actor span P/R/F1 | action span P/R/F1 | ... |
|---|---|---|---|---|---|---|---|---|
| B0 | | | | | | | | |
| H1 | | | | | | | | |
| D1 | | | | | | | | |

主表是 **"primary metrics"**。3 维度（§3）和 style-equivalent（§4）是 **"secondary metrics"**，在副表 / 补充材料里。

---

## 3. 3 维度分项（修正后的定义）

### 3.1 Semantic Coverage（覆盖度）— 必须拆分

旧定义 `prediction non-null / 6` 是错的。新定义拆成 6 个独立指标：

| 指标 | 公式 | 含义 |
|---|---|---|
| **Gold-required presence recall** | (# gold-required fields predicted) / (# gold-required fields) | **不**漏抽 Gold 要求的字段 |
| **Predicted-field precision** | (# predicted fields that are gold-required) / (# predicted fields) | **不** hallucinate 字段 |
| **Hallucinated-field rate** | 1 - precision | predicted 但 gold 不要求 |
| **Complete-record rate** | (# records where all gold-required fields are present) / (# records) | 整条记录完整 |
| **Schema-valid rate** | (# records passing schema) / (# records) | 记录格式合法 |
| **Unsupported/ambiguous rate** | (# records with non-empty `unsupported_or_ambiguous`) / (# records) | 系统说"不知道"的比例 |
| **Terminal API-error rate** | (# terminal API errors with `record=null`) / (# requests) | 无可计分记录的调用失败率 |
| **Recovered API-error rate** | (# provider errors recovered by a canonical fallback) / (# requests) | 调用失败但记录仍可计分的比例 |
| **Any API-error rate** | (# terminal + # recovered API errors) / (# requests) | 任意调用失败率；两类不重复 |
| **Invalid/API-error rate** | (# invalid records + # terminal API errors) / (# requests) | 无有效可计分记录的比例；recovered fallback 不重复算 invalid |

**关键**：Gold 中**不适用的字段**不计入 gold-required。**系统决定不输出**不算 hallucination（如果它在 `unsupported_or_ambiguous` 里说明）。

例如：
- 句 1 是 definition，Gold actors=[]，actions=[]。B0 输出 actors=[]，actions=[]。→ gold-required=0，全部正确
- 句 1 是 obligation，Gold actors=[a1, a2]。B0 输出 actors=[a1]。→ recall=0.5, precision=1.0
- 句 1 是 obligation，Gold actors=[a1]。B0 输出 actors=[a1, a3]（a3 是 hallucination）。→ recall=1.0, precision=0.5

### 3.2 Structural Encoding（结构编码）— 必须改

**不是** accuracy，是 **edge-based**：

| 子指标 | 公式 | 含义 |
|---|---|---|
| **Actor-action edge P/R/F1** | precision/recall/F1 over actor_action_map edges | actor→action 配对 |
| **Order-relation edge P/R/F1** | precision/recall/F1 over order_relations edges | 顺序关系 |
| **Clause segmentation exact-match rate** | (# clauses with exact set of spans matching gold) / (# clauses) | 拆句 |
| **Clause span overlap / IoU** | mean IoU between pred clause_span and gold clause_span | 拆句边界 |
| **Schema-valid rate** | (# records passing schema) / (# records) | （重复列在 §3.1，单列在此） |

`TP/(TP+FP+FN)` 必须命名为 **Jaccard / edge IoU**，不能叫 accuracy。

`correct order pairs / predicted order pairs` 只是 precision，必须补 recall/F1：
- precision = (# correct order pairs) / (# predicted order pairs)
- recall = (# correct order pairs) / (# gold order pairs)
- F1 = 2 * P * R / (P + R)

clause_id uniqueness 是 **validation invariant**，不是准确率：
- 任何一对 clause 内重复 id → 记录 invalid
- 不参与 P/R/F1 报告

**clause/entity 对齐算法**（明确规则）：
- **不**按预测数组位置直接对齐
- **不**要求预测 ID 和 Gold ID 字面相同
- record：exact `sample_id`
- clause：按 `(start,end)` 字符区间 IoU 建权重矩阵，用全局最大总权重的一对一 assignment；
  IoU≥0.5 才允许匹配。0.5 是“至少多数区间重叠”的预结果固定阈值，不得以论文分数或
  当前结果搜索。排序和 Hungarian 列优先规则保证确定性。
- exact clause segmentation：另按完全相同 `(text,start,end)` 计算，不因 semantic alignment
  放宽而消失。
- entity ID：均视为 method-local，禁止直接作为 Gold 身份。strict 指标按 exact raw span；
  safe 指标按 frozen safe-normalized text；token 指标按全局最大正 token-IoU 一对一匹配。
- shared ID 不能覆盖不相交 span；数组位置不能决定匹配；三种 entity metric 不得相互混用。
- v1.2 之后如需改 threshold/alignment，必须新建版本、先做 synthetic/adversarial gate，再读
  主数据结果；不得在同一结果上反复调节。

**文献数字边界**：本地已核 Sun P/R/F1=0.77/0.83/0.80 属 Stage 3 violation checking，
不是本 Stage 2 六要素 extraction evaluator 的可比 target。差异超过 0.10 只能触发任务/数据/
实现诊断，不能作为调 evaluator、改 Gold、删困难样本或搜索阈值的验收条件。

### 3.3 Deontic Correctness（道义正确性）— 单元改

- 4 类固定 labels
- 单元：**clause**，不是整句
- 缺失类（support = 0）规则：F1 = 0、recall = 0、precision = NaN → 报告显式标 N/A
- 每类 support 必须报告（避免 macro-F1 被大样本类拉偏）
- evaluation 范围：所有 gold clause

---

## 4. 报告组合

### 4.1 主表

| Method | obl-F1 | pro-F1 | perm-F1 | def-F1 | macro-F1 | actor span F1 | action span F1 | ... |
|---|---|---|---|---|---|---|---|---|

（见 §2.3）

### 4.2 副表 A：3 维度

| Method | gold-required recall | predicted-field precision | complete-record rate | schema-valid rate | unsupported rate | invalid/api rate |
|---|---|---|---|---|---|---|

### 4.3 副表 B：结构编码

| Method | actor-action edge F1 | order-relation edge F1 | clause seg exact-match | clause span IoU | schema-valid rate |
|---|---|---|---|---|---|

### 4.4 副表 C：deontic 详情

| Method | obl P/R/F1 | pro P/R/F1 | perm P/R/F1 | def P/R/F1 | macro-F1 | per-class support |
|---|---|---|---|---|---|---|

### 4.5 副表 D：normalization-aware matching

见 `docs/STYLE_EQUIVALENT_SPEC.md` §3-4。

**注意**：副表 D 是**敏感性分析**，不是主结果。

---

## 5. 实施完成顺序

1. 主表（§2）：已实现
2. 副表 A（§3.1）：已实现
3. 副表 C（§3.3）：已实现
4. 副表 B（§3.2）：已实现，固定 Hybrid 对齐
5. 副表 D（§4.5）：strict/safe 自动指标与空白人工复核模板已实现；人工判断待正式预测后填写

---

## 6. 已冻结决策与仍在其他任务中的事项

- **clause/entity 对齐算法**：已冻结 Hybrid（exact ID，未匹配项再 exact raw span）；禁止按数组位置对齐
- **缺失类 macro-F1**：已冻结 F1=0、recall=0、precision=null/N/A，仍计入四类 macro-F1
- **失败分母**：API error、schema-invalid 和 cross-field-invalid 均保留；缺/多 attempt 直接拒绝整批
- **归一化**：strict 是主结果；safe 是 secondary；高风险 loose 规则未进入冻结实现
- **stage 3 是否需要单独 1 张表**：B0/H1/D1 三组分别送入同一冻结 Stage 3，看下游增量。这是另一个 spec（`docs/ROUTE_LOCK.md` 提到）— 跟本 spec 分开

---

## 7. 与 Barrientos 的对比

借鉴：3 维度（semantic / structural / deontic）+ style-equivalent 概念

不借鉴：
- "output 是什么"（用 Sun 4 类，不用 Barrientos 3 类）
- "哪个类做主类"（Sun 的 obligation / definition 是主类，Barrientos 的 obligation / permission 是主类）
- "评估单元"（Sun 的单元是 clause，Barrientos 的单元是 requirement）

引用方式：
> "We adopt Barrientos et al. (2026)'s 3-dimension evaluation discipline
> (semantic coverage, structural encoding, deontic correctness) and
> the distinction between style-equivalent alignment and partial
> misalignment. We do NOT adopt the RC4PC schema; we evaluate against
> Sun et al. (2024)'s 4-class modality and 6-element extraction."
