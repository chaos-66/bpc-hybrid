# Style-Equivalent Alignment Spec (Wave 1.1 v2)

> **版本**：v2 (2026-07-12)
> **依据**：`docs/research/BARRIENTOS_BORROWING_AUDIT_2026-07-12.md` §3.1 + Wave 1.1 §6 修正
> **目的**：明确"什么是 style-equivalent" 和 "如何测"
> **范围**：仅 spec；**不**实现 evaluator（Wave 2 才开始）
> **配套**：`docs/EVAL_3DIM_SPEC.md` §4.5 副表 D

---

## 1. 旧版 v1 的错误（必须改的）

旧 v1 把"lowercase + lemma 后的字符串相等"称为 **style-equivalent**——**这是错的**。Barrientos 的 "style-equivalent alignment" 指的是**人工**对"语义相同但表达不同"的判断**类别**，不是字符串归一化。

旧 v1 的 over-claim：
- 把"自动归一化匹配"伪装成 Barrientos 风格等价
- 声称"本项目/CCFC 的原创创新"——这是**错的**。CCFC 不是原创，是**借鉴并适配** Barrientos 的人工评价思想
- 内部矛盾：默认开 article removal，但单元测试 `test_lowercase` 又保留 the
- 内部矛盾：deletes→delete 已被 lemma 判等，但 `overall_rate` 测试又判为不等
- 内部矛盾：数字归一同时被写成"默认关闭"和 "constraint 必做"
- "simple plural removal" 会破坏法律语义和不规则词
- 消融伪装成"6 种新方法"——实际是同一预测在 3 套 scoring config 下重评
- loose 结果被当主结果——必须**只**是敏感性分析

---

## 2. 修正后的概念

### 2.1 自动指标：normalization-aware matching

**这是机器自动算的**指标。给定：
- 预测 span（text, start, end）
- Gold span（text, start, end）

经过一组**显式版本化的归一化规则**（默认安全规则见 §3）后，比较：
- normalized_pred.value == normalized_gold.value
- 或 normalized_pred.text 字符集 == normalized_gold.text 字符集

如果匹配 → 算"normalized-equivalent correct"；不匹配但字面相等 → 算"strict correct"；都不匹配 → 算"error"。

**报告**：
- Strict P/R/F1（不归一化）
- Normalized-aware P/R/F1（按归一化规则）
- Normalized lift = Normalized-aware F1 - Strict F1

**关键**：
- Normalized-aware **不**能覆盖 Strict（两套都报）
- 默认安全归一化只允许 Unicode / case / whitespace 等低风险操作
- 高风险归一化（article removal, plural collapse, verb lemma, 缩写展开, 同义词, 数字/单位转换）默认**关闭**且**版本化**

### 2.2 人工判断：style-equivalent alignment

**这是人工盲审/抽样复核**的判断**类别**。给定：
- 一对 prediction/gold（已经过字面 + normalized-aware 评估）
- 专家看这对记录，标一个三档类别：
  - `full_alignment`：完全相同（字面或归一化）
  - `style_equivalent_alignment`：语义相同但表达不同（lowercase / abbreviation / synonym / 等等）
  - `partial_misalignment`：真实错误

**报告**（在副表 / 补充材料）：
- 在 N 个抽样的 prediction/gold 对中，每类占多少 %
- 这是**人类一致性**指标，**不**能完全自动化

**关键**：
- 这是 Barrientos 2026 的核心思想
- 本项目**借鉴**这个思想，**不**声称原创
- Normalized-aware 是**机器**自动归一化；Style-equivalent 是**人类**判断；两者不是一回事

### 2.3 引用方式（论文中）

> "We distinguish two evaluation lenses. The first is **strict
> string matching** against the gold span. The second is
> **normalization-aware matching** that applies a small, versioned
> set of low-risk string normalizations (Unicode, case, whitespace)
> and reports the lift over strict matching. The third is
> **style-equivalent alignment** in the sense of Barrientos et al.
> (2026): a human-judged, three-way category (full / style-equivalent
> / partial) over a sampled subset. Normalized-aware and
> style-equivalent are not equivalent \u2014 the former is mechanical,
> the latter is human \u2014 and we report both as secondary metrics."

---

## 3. 默认安全归一化（normalized-aware matching）

| 操作 | 字段 | 默认 | 风险 |
|---|---|---|---|
| Case normalization (lowercase) | 全部 | ✅ on | 低 |
| Unicode NFC | 全部 | ✅ on | 低 |
| Whitespace collapse | 全部 | ✅ on | 低 |
| Trailing punctuation strip | 全部 | ✅ on | 低 |
| Article removal (the, a, an) | actor | ❌ off | 中（"the data" vs "data" 可能不同） |
| Article removal | action | ❌ off | 中（"the file" vs "file" 可能不同） |
| Article removal | condition/constraint/exception | ❌ off | 中 |
| Plural collapse (simple +s) | 全部 | ❌ off | 中（"controller" vs "controllers" 在法律语境可能不同） |
| Verb lemma (notifies→notify) | action | ❌ off | 中（被动/进行时可能有不同语义） |
| Abbreviation expansion (GDPR→General Data Protection Regulation) | 全部 | ❌ off | 中（缩写展开可能引入歧义） |
| Synonym replacement (shall/must) | modality | ❌ off | 中（法律语义可能不同） |
| Number normalization (72 hours / three days) | constraint | ❌ off | 高（单位转换易错） |

**关闭**原因：法律语义敏感，归一化会改变含义。

**版本化**：每条归一化规则带 `rule_set_version` 字段，**禁止**默默修改。

---

## 4. 字段级归一化配置

| 字段 | 默认安全规则 (on) | 可选规则 (off) |
|---|---|---|
| `modality.label` | Case, Unicode, whitespace | 无（无字符串归一化的必要） |
| `modality.evidence.text` | Case, Unicode, whitespace, trailing punct | None |
| `actor.text` | Case, Unicode, whitespace, trailing punct | Article removal, plural |
| `action.text` | Case, Unicode, whitespace, trailing punct | Lemma, plural |
| `condition.text` | Case, Unicode, whitespace, trailing punct | Article removal, plural |
| `constraint.text` | Case, Unicode, whitespace, trailing punct | Number normalization |
| `exception.text` | Case, Unicode, whitespace, trailing punct | Article removal, plural |
| `*.normalized` | **不归一化**（这是显式 normalized value，gold 给出时已经归一） | — |

---

## 5. 消融设计

按 Wave 1.1 §6.8：**同一预测在 3 套 scoring config 下重评**，不假装 6 种新方法。

| 配置 | 规则集 | 用途 |
|---|---|---|
| **strict** | 全部 off | 主结果（最严） |
| **safe** | 默认安全 4 条 on | 默认报告（normalization-aware matching） |
| **loose** | safe + article removal + plural collapse | **敏感性分析**（仅附录/补充） |

**报告**：
- 主表：strict F1 + safe F1（normalization-aware lift = safe - strict）
- 附录：loose F1（敏感性分析）
- **不**声称 loose 是新方法
- **不**把 loose 当主结果

---

## 6. 修正后的测试（替代 v1 的矛盾测试）

### 6.1 必须修复的 v1 矛盾

| v1 测试 | 问题 | 修正后 |
|---|---|---|
| `test_lowercase` 期望 `the controller` 保留 the | 默认开了 article removal | 默认关 article removal，所以 "the" 保留 |
| `deletes→delete` lemma 判等 vs `overall_rate` 判不等 | lemma 默认开 vs 关 | lemma **默认关**，所以 deletes ≠ delete |
| 数字归一同时默认关 + constraint 必做 | 自相矛盾 | 数字归一**默认关**且**不强制**对任何字段开 |
| "simple plural removal" 破坏法律语义 | 简单加 s 规则会误伤 | plural collapse **默认关**且不实现简单加 s 规则 |

### 6.2 新测试（Wave 2 实施时再写）

| 测试 | 覆盖 |
|---|---|
| `test_strict_no_normalization` | strict 模式只比字面 |
| `test_safe_normalization_lift_safe_substrict` | safe 模式 F1 ≥ strict F1 |
| `test_loose_normalization_changes_some_but_not_all` | loose 模式 lift > safe 模式 lift（不一定，loose 可能反而低） |
| `test_field_specific_rules` | actor 不开 article removal（如果实现"非默认 on"） |
| `test_rule_set_version_pinned` | 配置变更不影响主结果（除非显式改版本号） |
| `test_human_style_equivalent_sampling_protocol` | 抽样 N 条，人工标 full/style/partial，报告分布 |

### 6.3 不再断言 v1 的矛盾测试

v1 的：
- ❌ "默认 actor 去冠词与 test_lowercase 保留 the 冲突"——已通过关闭 article removal 解决
- ❌ "deletes→delete 已被 lemma 规则判等"——lemma 已关
- ❌ "数字归一同时默认关闭和 constraint 必做"——数字归一关闭且不强制
- ❌ "simple plural removal 会破坏法律语义"——simple plural 未实现

---

## 7. Wave 2 实施优先级

1. strict 模式（最简单）—— 复用 `evaluator.py` 的现有 span P/R/F1
2. safe 模式（默认开 4 条低风险规则）—— 加 1 个 `Normalizer` 类
3. 抽样人工 style-equivalent 协议—— 文档化抽样方法 + 评分表
4. loose 模式（敏感性分析）—— 加 article removal + plural collapse

---

## 8. 不再 claim 的事情

- ❌ "style-equivalent 是本项目/CCFC 的原创创新"——借鉴 Barrientos 2026
- ❌ "auto-normalization 就是 style-equivalent alignment"——auto ≠ human
- ❌ "loose 是新方法"——loose 是 sensitivity analysis
- ❌ "loose 是主结果"——loose 只在附录/补充

---

## 9. 未解决的设计决策

- **safe 模式是否包含 trailing punctuation strip？** 当前规划是 on
- **article removal 何时开启？** 仅在用户明确 "ignore article differences" 时
- **样本人工 style-equivalent 协议 N 值？** 默认 30-50 条，看 reviewer 时间
- **loose 模式的报告位置？** 附录或 supplementary，不进主表
