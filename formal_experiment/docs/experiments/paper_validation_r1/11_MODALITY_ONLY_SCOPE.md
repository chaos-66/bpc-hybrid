# Paper Validation R1 — 为什么主指标只到 clause-level modality

> **本文件性质**：scope 限定说明（scope limitation note），不是新状态页，不是 roadmap
> 补充，也不是对 `09_SIX_FIELD_BLOCKER.md` 的整体重写。本文只厘清"为什么这一轮
> 论文验证的主对比表只展示 modality P/R"这一件事，避免读者误读为"实验只评估了
> 一个分类标签"。实验资产（prompt / Gold / 方法 / 评估器 / 报告）本文**一律不修改**。
>
> 关联阅读：
> - `00_AUDIT.md` §3.7（Gold 覆盖率）
> - `09_SIX_FIELD_BLOCKER.md`（原 blocker 文档，论证存在过度，本文补正）
> - `10_DOWNSTREAM_BLOCKER.md`（后续工作范围）
> - `FINAL_REPORT.md` §4 / §12

---

## 1. 一句话定位

**Paper Validation R1 的主指标是 clause-level modality 分类的 micro F1。**
这是**主动选择的 scope 限定**，不是 modality 这一项被孤立评估，也不是六要素被
丢弃。下面把"为什么"和"哪些是真卡点、哪些不是"分清楚。

---

## 2. 当前评估的真实范围

| 层级 | 范围 | 证据 |
|---|---|---|
| Prompt 端 | 要求 LLM 输出完整六要素（modality / actor / action / condition / constraint / exception）+ 各 span | `prompts/sun_compat/direct_llm_sun_record_prompt.md` L53–71；`rule_first_llm_fallback_prompt.md` L53–65 |
| Evaluator 端 | `stage2_evaluation.py` 具备六要素 P/R 算力（`primary_metrics = {modality, fields{actor, action, condition, constraint, exception}}`，每个 field 都有 strict_exact / safe_normalized / token_overlap_micro 三档） | `src/bpc_hybrid/stage2_evaluation.py` L40–46, L696–718 |
| 报告层 | `paper_validation` 的报告脚本只读 `per_modality_metrics.json`，主表只有 clause-level modality 的 P/R/F1 | `scripts/paper_validation/build_validation_report.py` L147, L157, L220, L270 |
| 副产物 | token-IoU 阈值敏感性、bootstrap、anchoring、difficulty subset、modality 混淆矩阵 | 同脚本 §6–§11 |

**所以**：evaluator 本身不"只算 modality"；是**报告层只把 modality 当主指标**。

---

## 3. 假卡点 vs 真卡点

`09_SIX_FIELD_BLOCKER.md` §1–§2 把"六要素字段 Gold 覆盖率不全"列为第一性卡点。
这个论证**过度**——它把字段空覆盖率低当成了 Gold 缺陷，但**事实不是这样**。

### 3.1 假卡点：Gold 覆盖率低 ≠ Gold 缺

`configs/schemas/stage2_prediction.schema.json` L116–149 写得很清楚：

- `actors` / `actions` / `conditions` / `constraints` / `exceptions` **都是 array**，
  没有任何一个设了 `minItems`（`actions` 设了 `minItems: 0`，其他字段连这个都没设，
  默认为 0）
- prompt 也明说：*"If an element truly has no source span, use an empty array. Empty
  means absent, not uncertain."*

**因此**：一个 clause 的 `exception: []` 是 schema 下的合法状态，不是 Gold 漏标。
现实里绝大多数条款根本不含 unless/but/except 结构，exception 字段空是**正常
语法现象**，不是数据缺陷。把 `exception` Gold 覆盖率 4.8% 当作"Gold 数据严重不全"
是**前提错误**。

同理：

| 字段 | 覆盖率 | 真实语义 |
|---|---:|---|
| modality | 100% | 几乎所有条款都有 modality，schema 也强制必须有 |
| action | 99.6% | 几乎所有条款都至少有动作短语（definition 类除外） |
| constraint | 80.5% | 大多数条款有时间/范围/方式限制 |
| condition | 70.1% | 部分条款带 if/when/provided 触发条件 |
| actor | 19.9% | 大量被动句 + definition 条款没有显式施事者 |
| exception | 4.8% | 绝大多数条款不含 unless/but/except 结构 |

**覆盖率低 = 该字段在该语料上不常出现，不是 Gold 缺。**

`09_SIX_FIELD_BLOCKER.md` §2 的"A fair `actor` evaluation would treat empty Gold as
'the method is required to abstain', which is a different evaluation regime"这句
是把**它自己加的额外评估假设**当成了 schema 约束。NLI / SRL / 句法角色标注的常规
做法是：双方都空 = TP（正确地识别为"不适用"），这才是默认且公平的 micro/macro
评估方式。"空 = 应 abstain" 是可选的设计选择，不是必需前提。

### 3.2 真卡点

实际把这一轮堵在 modality-only 的硬约束只有两个：

| # | 约束 | 性质 |
|---|---|---|
| 1 | D1 / H1 当前 prompt 让 LLM 输出 `clause_text`（**纯文本，无 char-span 字段**），而 `stage2_evaluation_v3.py` 的六要素 span-level 评估强依赖 `clause_span` 与各 field 的 `start/end` 偏移。`stage2_evaluation.py` 的 v3 评估路径**吃不下**当前 D1/H1 的输出格式 | 工具不兼容 |
| 2 | 任务 §0.3 规定"不得修改现有方法定义"（含 D1 / H1 prompt） | 任务硬约束 |

**结论**：prompt → 输出格式 → 评估器三者形成了一个**格式/工具不兼容闭环**，而任务
又禁止改 prompt，因此本轮只能退回 clause-level modality 分类（纯文本对齐就够用，
不依赖 char-span）。

---

## 4. 与 09_SIX_FIELD_BLOCKER.md 的关系

`09_SIX_FIELD_BLOCKER.md` 写于更早一轮诊断，它的：

- **结论仍然成立**（这一轮不做六要素 P/R）
- **论证链需要补正**：不能再说"Gold 不全"是真卡点；真卡点是输出格式 / 评估器
  不兼容 + 任务 §0.3

本文不重写 `09_SIX_FIELD_BLOCKER.md`，只**显式声明**：那一篇的 §1 的覆盖率数字
作为现状记录仍然准确，但 §2 的"为什么是 blocker"论证中，"Gold 覆盖率低"那一段
是**过度论证**。读者应该把 §1 当作"现状事实"，把 §3.2（本文）的"输出格式 /
任务硬约束"当作"真卡点"。

---

## 5. 主报告里应当显式声明的 scope 限定

为避免读者第一眼看到主表只展示 modality P/R 时误判"论文只评估了一个分类标签"，
在 `FINAL_REPORT.md` §4 / §12 旁边建议加一段（**目前还没加，建议补**）：

> **Scope limitation of primary metric**：本轮主指标 clause-level modality
> micro F1 不代表六要素被丢弃。Prompt 与 Stage-2 canonical schema 要求 LLM 输出
> 完整六要素（modality / actor / action / condition / constraint / exception）；
> `stage2_evaluation.py` 具备六要素 P/R 算力。本轮报告层只展示 modality 是因为：
> (a) D1 / H1 当前输出是 `clause_text` 文本、无 char-span 字段，
> `stage2_evaluation_v3.py` 的 span-level 评估器吃不下；(b) 任务 §0.3 禁止本轮
> 修改 prompt / 方法。**field 级别的 P/R 是技术可达、范围上未跑**，不属于
> 方法缺陷。详见 `11_MODALITY_ONLY_SCOPE.md` 与 `09_SIX_FIELD_BLOCKER.md`。

如果主表下方的脚注或 §0 摘要里能加这么一段，论文/汇报读者一眼就能看懂这件事。

---

## 6. 未来解锁路径（仅供参考，**本轮不承诺**）

按"是否需要改 prompt"和"是否需要新增评估器"两个维度列出，不承诺具体时间：

| 路径 | 改 prompt？ | 新评估器？ | 备注 |
|---|:---:|:---:|---|
| A. 改 D1 / H1 prompt 让其输出 `clause_span` + 各 field 的 char-span | 是 | 否 | 触发任务 §0.3 边界 |
| B. 不改 prompt，写一个**吃 `clause_text` 输出的轻量 v3 变体**（基于 token 词袋 overlap 算六要素 P/R，复用 `stage2_evaluation.py` 的 `token_overlap_micro` 逻辑） | 否 | 是 | **不违反任务约束，技术成本低** |
| C. 接受本轮 scope，明示"六要素 span-level 评估推给 future work"，主报告不补 Gold 也不补输出格式 | 否 | 否 | 最保守路径 |

路径 B 看起来最务实：**不改实验**，**不动 Gold**，**不动 prompt**，只在评估器层
加一个能吃文本输出的 token-overlap 变体，把 modality 那套 P/R 算法扩到 actor /
action / condition / constraint / exception 五个 field。

是否走 B 路径**不由本文件决定**——需要用户/导师在下一轮实验设计时明确授权。

---

## 7. 状态声明

- 本文件**不修改**任何 prompt、Gold、method、evaluator、manifest、report 资产
- 本文件**不创建**任何新事件、不修改 `EXPERIMENT_LOG.md` / `EXPERIMENT_EVENTS.jsonl`
  / `_retired/` 下的任何条目
- 本文件**不影响** `audit_project.py` 的任一 gate 状态
- 本文件仅作为对现有 blocker 文档（`09_SIX_FIELD_BLOCKER.md`）的**补正说明**，
  以及对未来论文/汇报读者的**scope 声明建议**
- 本文件添加会按 `docs/AI_CHANGE_PROTOCOL.md` §5 单独走一次 minimal change 事件
