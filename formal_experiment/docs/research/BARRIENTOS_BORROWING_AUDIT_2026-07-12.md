# Barrientos 借鉴审计 — 2026-07-12

> **目的**：明确 Barrientos 2026 论文哪些能借鉴、哪些不能借鉴、如何借鉴。
> **依据**：
> - `references/barrientos_2026/artifact_input/prompts/formalize_requirements_prompt.txt`（原文 prompt）
> - `references/barrientos_2026/artifact_input/formats/compliance_requirements_format.json`（输出 schema）
> - `references/barrientos_2026/evaluation/annotations_from_compliance_experts/protocol_and_results.md`（评估方法）
> - `docs/research/BARRIENTOS_LLM_ROLE.md`（项目已锁的边界）
>
> **结论先行**：✅ **可借鉴工程纪律和评估方法**；❌ **不能照搬 schema**（不同任务）；⚠️ **modality 类别需扩展**（3 → 4 类）。

---

## 1. 关键事实：Modality 类别数差异 ⚠️

| 项 | Barrientos | Sun (我们) |
|---|---|---|
| Modality 类别数 | **3 类** | **4 类** |
| 类别 | `obligation`, `permission`, `prohibition` | `obligation`, `prohibition`, `permission`, `definition` |
| Definition | ❌ 无 | ✅ 有（"X means..." / "X refers to..." 类定义性句子） |

**影响**：
- D1/H1 prompt 的 `modality` 字段必须**扩展为 4 类**（加 `definition`）
- **不能直接照抄** Barrientos 的 enum
- 这正好印证了"先查证再借鉴"——直接照搬会丢失 Sun 论文的 `definition` 类别

**对应改动**：见 §4 prompt 升级建议

---

## 2. Schema 整体差异（不能照搬）

| 字段 | Barrientos (RC4PC) | Sun (我们) |
|---|---|---|
| 顶层结构 | `id + precondition + norms + temporal_validity` | `modality + actor + action + condition + constraint + exception + spans` |
| 任务定位 | Change-impact analysis（合规要求变更影响） | Stage 2 抽 6 要素 → Stage 3 查 BPMN |
| Modality | `norms[].modality` (3 类 enum) | `modality` (4 类 enum) |
| Actor | 通过 `action.resources` 表达 | 独立字段，6 要素之一 |
| Condition | `precondition.and/or/not` 三元组 | 独立字段，6 要素之一 |
| Action | `action` 含 `dimension` + `compliance_pattern` + `activities` | 独立字段，动词短语 + 原文 span |
| Time | `temporal_validity.start/end` | `constraint` 内含时间约束 |
| Exception | ❌ 无 | 独立字段，6 要素之一 |

**结论**：**两个 schema 设计哲学不同**：
- Barrientos：**面向变更的规则表示**（precondition → norm → impact）
- Sun：**面向 BPMN 比对的 6 要素抽取**（每要素独立、字符 offset、原文证据）

**绝对不能直接照搬**——会破坏 Sun-compatible 叙事。

---

## 3. 可借鉴的具体项（按价值排序）

### 3.1 评估方法（⭐⭐⭐⭐⭐ 最高价值）

**Barrientos 做了什么**（`protocol_and_results.md` §2.2）：
- 每个专家标注对照 ground truth 评估 3 个维度：
  1. **Semantic coverage**：所有必需元素是否都覆盖
  2. **Structural encoding**：precondition vs embedded、explicit vs implicit、single vs multiple norms、control-flow vs temporal
  3. **Deontic correctness**：obligation vs permission vs prohibition 是否对、无意外加强/削弱
- 引入 **"style-equivalent alignment"** 概念：表达不同但语义相同算正确
- 专家 1：100% 语义对齐；专家 2：97.5%；平均 98.75%
- Cohen's κ = 0.52（多专家一致性）

**可借鉴到我们的 Stage 2 评估**：

| Barrientos 维度 | 我们的对应（建议） |
|---|---|
| Semantic coverage | 6 要素是否都覆盖？每条样本的 modality + actor + action + condition + constraint + exception 是否都标了 |
| Structural encoding | 多分句是否正确？actor-action 映射是否对？order_relations 是否对？ |
| Deontic correctness | modality 4 类分类是否对？P/R/F1 |
| **Style-equivalent alignment** ⭐ | **创新点**：允许标注表达不同但语义相同算正确（避免过度惩罚标注风格差异） |

**关键创新点**：style-equivalent alignment 概念。
- 我们的评估可能会遇到"两个标注都合理但格式不同"的情况
- 这种"风格差异"被 Barrientos 证明是 37.5% 的标注情况
- 借鉴这个概念能**显著提高评估稳健性**
- **CCFC 论文中可作为方法学贡献点**

### 3.2 Compliance Pattern 字典（⭐⭐⭐⭐ 高价值）

**Barrientos 提供了完整的 controlled vocabulary**（`formalize_requirements_prompt.txt` §1）：

| 维度 | 模式数 | 示例 |
|---|---|---|
| control_flow | 13 | existence_of_A, A_requires_B, A_mutex_B, A_followed_by_B, ... |
| resource | 9 | performed_by, static_SoD, dynamic_SoD, multi_bonded, ... |
| data | 14 | data_available, data_format, data_in_range, data_origin_known, ... |
| time | 8 | time_lag, duration, schedule_restricted, periodicity, ... |
| **总计** | **44** | 全是 controlled vocabulary，不允许 LLM 自创 |

**可借鉴到我们的 B0 抽取**：
- **4 维度 44 模式** 可以作为 Sun 六要素的"下游分类层"（stage 3 adapter 用）
- 让 B0 在抽完 6 要素后，再标每个 action 属于哪个 compliance pattern
- 这能**显著增强 Stage 2 → Stage 3 的可解释性**

**风险**：增加 LLM 负担，可能降 F1。要做消融。

### 3.3 Prompt 字段严格枚举（⭐⭐⭐⭐ 高价值）

**Barrientos 的优秀实践**（prompt §"IMPORTANT RULES"）：
- "Only use these patterns depending on the dimension"（明确说不允许自创）
- "do NOT invent new patterns"
- "Use the same labels across versions"（版本一致性）
- 字段定义先讲清楚再让 LLM 填

**借鉴到我们的 D1/H1 prompt**：
- modality 字段从 3 类 → **4 类**（加 `definition`，明确"X means..."触发）
- action 字段加 `dimension` + `compliance_pattern` enum（4 选 1 + 44 选 1）
- 增加 "version consistency rule"（同一句多次跑要稳定）

### 3.4 温度 0 + 固定 seed（⭐⭐⭐⭐⭐ 必须）

**Barrientos 的稳定性测试**（`analysis_of_results/analyzed_stability/`）：
- 20 个 requirement × 20 次稳定性跑 = 400 个结果文件
- 计算 stability_ratio（多次跑结果一致的比例）

**借鉴到我们的 D1**：
- 同一句跑 5 次（`temperature=0, seed=42`）
- 算 stability ratio（field/span agreement）
- 报告"5 次跑里 X% 的字段结果一致"

**当前状态**：D1 prompt 没说温度和 seed。**必须加**。

### 3.5 Temporal Validity 字段（⭐⭐ 低价值）

Barrientos 有 `temporal_validity.start/end`（ISO 8601）。
我们的 constraint 字段已包含时间约束。
**借鉴价值低**，不推荐。

---

## 4. 建议的 D1/H1 Prompt 升级（具体改动）

### 改动 1：modality 字段从 3 类 → 4 类

**当前**（`prompts/sun_compat/direct_llm_sun_record_prompt.md`）：
```text
1. "modality" — one of: "obligation", "prohibition", "permission", "definition".
```

**已正确**（Sun 4 类）。但**字段说明可以更详细**：
```text
1. "modality" — one of: "obligation", "prohibition", "permission", "definition".
   - "obligation": sentence uses "shall", "must", "is required to"
   - "prohibition": sentence uses "shall not", "must not", "may not", "is prohibited"
   - "permission": sentence uses "may", "is allowed to", "is permitted to"
   - "definition": sentence defines a term ("X means...", "X refers to...",
                   "X is defined as..."). Mark ONLY if the sentence's primary
                   purpose is to DEFINE a term, not to impose a normative rule.
```

**关键澄清**：definition 是"主要目的是定义"，不是"包含定义"。

### 改动 2：增加 temperature/seed 声明

**当前**：没说明

**建议加**：
```text
Sampling parameters:
- temperature = 0
- top_p = 1
- seed = 42
- max_tokens = 2048

These parameters must remain identical across multiple runs of the same
requirement to ensure reproducibility and stability measurement.
```

### 改动 3：增加 few-shot 例子

**当前**：无

**建议加**（在 user prompt 末尾）：
```text
Example:
Input: "The controller shall notify the supervisory authority within 72 hours."
Output: {
  "modality": "obligation",
  "actor": "the controller",
  "action": "notify the supervisory authority",
  "condition": null,
  "constraint": "within 72 hours",
  "exception": null,
  "actor_action_map": {"actor": "the controller", "action": "notify the supervisory authority"},
  "order_relations": null
}
```

### 改动 4：增加 compliance pattern 字段（可选，需要消融）

**当前**：无

**建议加**（作为可选字段）：
```text
9. "compliance_pattern" (optional) — for each action, classify its dimension
    and pattern. Use ONLY these patterns:

    - dimension: one of ["control_flow", "data", "resource", "time"]
    - pattern: see the controlled vocabulary below

    [粘贴 44 模式表]

    If uncertain, set to null. This field is optional and does not affect
    the main 6-field extraction.
```

**注意**：这是 Stage 2 → Stage 3 的"中间表示"，不是 6 要素本身。

### 改动 5：版本一致性规则

**当前**：无

**建议加**（在 system prompt 末尾）：
```text
3. Version consistency: When the same requirement is processed multiple times
   (for stability testing), the output must be identical EXCEPT for fields
   that genuinely require variation (e.g., random sampling noise from the LLM).
   Field NAMES and STRUCTURE must be byte-identical across runs.
```

---

## 5. 建议的 Stage 2 评估升级（创新点）

### 5.1 三维度评估（借鉴 Barrientos §2.2）

| 维度 | 我们的指标 |
|---|---|
| Semantic coverage | 6 要素中每要素的 F1（macro/micro） |
| Structural encoding | actor-action_map 准确率 + order_relations 准确率 + 多分句正确率 |
| Deontic correctness | modality 4 类 macro-F1 + 每类 P/R + confusion matrix |

### 5.2 Style-equivalent Alignment（新概念）

借鉴 Barrientos 的"style-equivalent alignment"：
- 允许"表达不同但语义相同"的标注算正确
- 实施：定义"语义等价"规则（如大小写、缩写、时态归一化后仍等价）
- 报告：style-equivalent rate（在所有正确标注中占多少）

**这是 CCFC 创新点**——大部分论文只看 P/R/F1，不看风格等价。

### 5.3 Stability 测试

- 同一句跑 5 次（temperature=0, seed=42）
- 算 field_agreement_rate（5 次里 X% 字段结果完全一致）
- 算 span_agreement_rate（5 次里 X% span 完全相同）
- 报告 + 画图（field × sample_id 热力图）

---

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 直接照搬 Barrientos schema → 破坏 Sun 叙事 | 严格按本文档第 2 节隔离 |
| Compliance pattern 字段增加 LLM 负担 → F1 下降 | 必做消融（D1-dual vs D1-no-pattern） |
| Few-shot 例子要选好 → 偏置 | 多版本消融 + 用 ground truth 句子 |
| Stability 5 次跑成本 | 5 次 vs 10 次 vs 20 次 消融 |

---

## 7. 工作量估算

| 任务 | 时间 |
|---|---|
| 升级 D1/H1 prompt（4 处改动） | 1-2 小时 |
| 加 compliance_pattern 字段 + 消融 | 2-3 小时 |
| Stage 2 评估升级（3 维度 + style-equivalent） | 3-4 小时 |
| Stability 测试框架 | 2-3 小时 |
| 写借鉴章节进论文 | 1-2 小时 |
| **总计** | **9-14 小时（1-2 天）** |

---

## 8. 总结一句话

> **Barrientos 是 3 类 modality + change-impact schema**（不能直接借鉴）；
> **可借鉴的是评估方法（3 维度 + style-equivalent）和工程纪律（controlled vocabulary + 温度 0 + 稳定性测试）**。
>
> D1 prompt 需要扩展 1 类 modality（4 类）+ 加温度 seed + 加 few-shot + （可选）加 compliance pattern。
> Stage 2 评估可以引入 style-equivalent alignment 概念（**CCFC 创新点**）。

---

## 9. 引用方式（论文中）

> "We adopt Barrientos et al. (2026)'s evaluation discipline — namely, multi-dimensional
> assessment (semantic coverage, structural encoding, deontic correctness) and the
> distinction between style-equivalent alignment and partial misalignment — to assess
> the validity of LLM-extracted records. We do NOT adopt the RC4PC schema, as it
> targets change-impact analysis, not the six-element extraction required by Sun
> et al. (2024)'s Stage 2. Specifically, Barrientos' 3-class modality is extended
> to Sun's 4-class scheme (adding `definition`)."

---

**记录**：本文档与 `docs/research/BARRIENTOS_LLM_ROLE.md` 共同锁定 Barrientos 借鉴边界。
**变更**：每次 prompt 改动需走 `audit_project.py --with-tests` + `record_change.py`。
