# SEP-C3 Gold-driven Semantic Boundary Study v1

- 任务：`Gold-driven Semantic Boundary Study`
- 角色：evidence analyst / annotation semantics researcher
- 新增 BPC LLM/API 调用：**0**
- Gold：`data/gold/stage2/estg150_formal_gold_v1.json`
- 现有实验：`outputs/development/sep_c3_targeted_refinement_v1` A/B/C/D
- 本轮定位：只做 Gold 语义、现有 artifacts、E/S coverage 与边界审查；不设计 Prompt，不改 Prompt/Gold/parser/canonicalizer/evaluator/raw predictions。

## 0. 一句话结论

六个字段中，**actor 已有稳定且有效的 targeted guidance（R_A）**，**exception 样本太少、不足以支持 targeted refinement**；真正需要继续语义边界研究的是 **condition / constraint 的 joint boundary**。Modality 存在稳定但主要是 definition 类别混淆；action 存在 Gold 与 E4/S8 冲突的边界问题。本轮没有把任何发现写成 Prompt 规则。

**没有找到一个可直接冻结的简单通用 Prompt rule 来切分 condition/constraint。** 当前证据支持的是候选 annotation principles，而不是已验证规则。

## 1. 口径与数据分离

### 1.1 Gold 层级

- Gold 记录包含 `clauses`，span 以 clause 为局部坐标，基于 `approved_text_en`。
- 语义分析使用原始 Gold clauses，不用 evaluator 的 sentence-level 字段合并 hull 作为 annotation semantics。
- evaluator 的 coarse view 只用于复现已有 prediction metrics；它是诊断口径，不是 Gold 边界。

### 1.2 本报告同时报告两个 overlap 口径

| 口径 | 含义 | condition/constraint overlap |
|---|---|---:|
| 实际 Gold annotation geometry | 同一 clause 内 Gold condition span 与 Gold constraint span 相交 | **11 pairs / 10 clauses / 10 samples** |
| 实际 Gold sample-level geometry | 同一样本内跨 clause 统计相交 pair | **21 pairs / 14 samples** |
| evaluator coarse merged hull | evaluator 先把同字段多个 span 合并成 `[min(start), max(end))` | **43 / 150 samples** |

`43/150` 包含 Gold 原始 span 之间的空白 hull，不能解释为 "Gold 有 43 个样本把 constraint 嵌套在 condition 内"。真正可支持 nested annotation 的是前两行。

### 1.3 字段总量

| Field | Gold spans | Gold samples | Gold clauses |
|---|---:|---:|---:|
| actor | 48 | 41 | 46 |
| action | 247 | 150 | 230 |
| condition | 214 | 122 | 162 |
| constraint | 302 | 135 | 186 |
| exception | 13 | 11 | 11 |

- action 是唯一每个样本都有 Gold span 的字段。
- exception 只有 11 samples / 13 spans，这是本轮不建议 targeted refinement 的直接原因之一。

## 2. Q1：六字段 failure map 与 refinement 状态

### 2.1 Modality

**A. 当前定义**
Gold modality 是 clause-level 四类标签：`obligation`, `permission`, `prohibition`, `definition`。definition 包括分类、拟制、资格定义、适用范围拟制等，不总是无规范动词的定义句。

**B. 已观察 failure**
从 targeted A/B/C/D 的 evaluator modality label 看：

- macro F1：A `0.7451`，B `0.7359`，C `0.7500`，D `0.7656`。
- 稳定错误：150 个样本中，26 个在 A/B/C/D 四个 arm 中全部错；其中 **20 个 Gold 为 definition**，另有 obligation/permission/prohibition 各 2 个。
- 29 个 Gold-definition 样本中：20 个四臂全错，7 个四臂全对，2 个只在 C/D 修回。
- 主要混淆不是随机分布，而是 **definition -> obligation / prohibition**：`shall be deemed`, `are not eligible`, `is`, `means`, `does not apply` 等被模型按规范动词表面触发为 obligation/prohibition。

**C. 是否稳定**
稳定，且跨 A/B/C/D 重复。不是单纯整条 prediction variation；26 个 same-wrong 样本在四个 arm 中一致出现。

**D. 已有 guidance 覆盖**
S2 给出四个 label 名称；E4 给了一个 definition + obligation 的简单例子。E4 只覆盖 definition 后接 obligation 的一种形式，没有覆盖拟制、资格否定、`shall be deemed` 等 definition 形态。

**E. 状态**
`POTENTIAL_REFINEMENT_TARGET`。

主要未解决问题：definition 与 obligation/prohibition 的稳定边界没有被现有 E/S2 覆盖。该问题与 condition/constraint 不同，当前更像 modality label semantics gap，而不是 span boundary ambiguity。

### 2.2 Actor

**A. 当前定义**
R_A：只抽取显式承担 performing / refraining / being subject to regulated action 的实体；不把 object/resource/amount/salient NP 当 actor；没有 responsible entity 就返回空。

**B. 已观察 failure**
- A actor P/R/F1：`0.4725 / 0.9512 / 0.6314`，FP 48 个 unmatched，empty-Gold FP 36 个。
- B（+R_A）actor P/R/F1：`0.6429 / 0.9512 / 0.7672`，empty-Gold FP 降到 19。
- C actor：`0.5227 / 0.9756 / 0.6807`；D：`0.6000 / 0.9268 / 0.7284`。
- R_A 主要修 empty-Gold actor hallucination 和 object/resource/amount 误抽；recall 基本不降（A/B 均为 0.9512，matched Gold 39/41）。

**C. 是否稳定**
pre-R_A actor over-extraction 是稳定、可复现的 failure；R_A 有重复实验支持和跨 arm 一致效果。没有证据显示 R_A 在 EStG-150 上造成新的稳定 Gold actor recall loss。

**D. 已有 guidance 覆盖**
R_A 已经是 targeted actor clarification；E2 展示 passive actor absence，E1 展示 unresolved pronoun。Gold actor 语义与 R_A 的方向一致。

**E. 状态**
`ALREADY_ADDRESSED`。

Gold actor semantics 与 R_A 基本一致：
- 41/150 个样本有 Gold actor；109/150 个样本 empty actor。
- Gold actor 多数是有责任的显式 entity；passive/no performer 多数为空。
- 理论风险：E1/S3 说 unresolved pronoun 可以是 actor，而 R_A 说 "explicitly stated entity that bears responsibility"。如果遇到 Gold 明确保留 unresolved pronoun 的样本，R_A 理论上有误删风险。但在当前 EStG-150 和 R_A 实验中没有观察到该风险；不建议现在修改 R_A。

### 2.3 Action

**A. 当前定义**
S4：最小 verb-centred phrase，包含必要 object/complement/particle。E2/E3/E5 给出简单 action 例子；E4 给出 definition clause `actions empty` 的例子。

**B. 已观察 failure**
- A action P/R/F1：`0.8755 / 0.9333 / 0.9035`；B `0.9286 / 0.9533 / 0.9408`；C `0.9056 / 0.9333 / 0.9192`；D `0.9174 / 0.9267 / 0.9220`。
- 整体 F1 高，但错误类型反复：
  1. Gold definition clause 的 light verb / copula 被漏掉或误判。
  2. 一个 clause 内协调/从属 predicate 被拆成多个 action，或 subordinate verb 被误抽为独立 action。
  3. action 边界与 condition/constraint 相交时不稳定。
- Gold 中所有 **39 个 definition clauses 都有 action span**；E4 却说 definition clause `actors and actions empty`。这是本轮 E coverage 中最重要的反例。
- Gold clause-level action 与其他字段相交：
  - action::constraint：9 pairs / 8 samples
  - action::condition：2 pairs / 1 sample
  - actor::condition：1 pair / 1 sample
  - condition::exception：1 pair / 1 sample
- 也就是说 Gold action 可以包含 constraint/condition，而不是 S8 所暗示的 "action 到 condition/constraint 开始处就结束"。

**C. 是否稳定**
action 错误类型 heterogeneous，但两个方向是稳定的：definition/light-verb 处理不稳、nested action span 与 E4/S8 不一致。不能简单说 action 是一个大而稳定的语义 confusion；更像是 span/role boundary 与 example coverage 问题。

**D. 已有 guidance 覆盖**
S4 有最小 verb-centred phrase 定义，E4 有 definition 例子，S8 有 field partition 语句。问题是：
- E4 的 definition 例子不具 Gold 代表性。
- S8 的 "action ends where such a phrase begins" 与 Gold action::condition / action::constraint overlap 冲突。
- 当前 targeted A/B/C/D 不使用 S，仅 E；因此 action 的 definition copula miss 不能只归因于 S8。

**E. 状态**
`UNRESOLVED_BOUNDARY`。

是否需要新的 target instruction：有边界 evidence，但目前支持的是 "修正 example coverage 或 action-end wording 假设"，不是立即写一条 field-specific action rule。不能按六字段对称性机械处理。

### 2.4 Condition

**A. 当前定义**
S5：激活或决定 norm 是否/何时适用的 antecedent state/event，包含 marker 和完整 governed proposition。E1/E5 给简单 if/within 例子。Gold `estg_000052` 说明 condition 也可以是 `insofar as ... threshold ...` 的完整 predicate。

**B. 已观察 failure**
- condition 在 R_C 后出现系统性迁移：A→C、B→D 中 19 条样本×方向的 condition coverage loss；其中 8 条/5 个独立样本为 **condition-only 整段迁入 constraint**：`000039`, `000052`, `000108`, `000161`, `000210`。
- 另有 4 条/2 个样本为 condition/constraint 范围合并：`000060`, `000106`。
- 另有 3 条/2 个样本是合法嵌套或双字段同时存在时 condition 漏抽：`000028`, `000037`。
- A condition P/R/F1：`0.8782 / 0.8115 / 0.8435`；C `0.9084 / 0.7459 / 0.8192`。precision 上升但 recall 下降，说明 R_C 的 condition 迁移是真实问题。
- 还有 4 条/4 个样本 condition 丢失但没有新增重叠 constraint：`000121`, `000231`, `000509`, `000124`；机制不同，不能统一归入 condition->constraint migration。

**C. 是否稳定**
condition 整体 miss 有系统性，condition-only migration 在 A→C 和 B→D 重复出现。稳定，但不是所有 condition 错误都能由同一机制解释。

**D. 已有 guidance 覆盖**
S5、E1、E5、旧 R_C 已有 condition definition；E5 已展示 condition 内可以 nested constraint。因此"condition 内允许 constraint"不是完全未教过的新规则。真正缺的是：什么时候 internal phrase 应该成为 constraint，什么时候不应拆。

**E. 状态**
`POTENTIAL_REFINEMENT_TARGET`，但目标必须与 constraint 联合定义，不能单独为 condition 加一条脱离 constraint 的规则。

### 2.5 Constraint

**A. 当前定义**
S6：对 already applicable action 的 how / how much / where / by when 等限制；覆盖 legal reference, time/duration, quantity, purpose, exclusivity；包含 marker 和 smallest complete limit。R_C：直接限制 when/how/how much/purpose/legal reference/exclusivity 的 explicit phrase；不要只输出 isolated cue word。

**B. 已观察 failure**
- A constraint P/R/F1：`0.8015 / 0.5556 / 0.6562`；C `0.7525 / 0.7185 / 0.7351`；D `0.7553 / 0.7778 / 0.7664`。
- R_C 使 recall 上升（A→C missed 60→38；B→D 53→30），同时 unmatched FP 上升（A→C 27→50；B→D 26→58）。
- isolated `only` constraints 上升：A=5, C=9, B=5, D=11。
- 52 条 coarse recovery 中，49 条至少与细粒度 Gold constraint 相交、37 条至少精确恢复一个细粒度 constraint，3 条只命中合并 hull 空隙。恢复不是纯幻觉，但也不是全部完整正确。
- 条件迁移和 constraint FP 常常是同一个边界问题的两面：R_C 把 condition 整段或 condition predicate fragment 拉进 constraint。

**C. 是否稳定**
constraint recall/FP tradeoff 稳定重复，条件内含 predicate 被拆成 constraint 也重复出现。isolated `only` 稳定存在，但旧 R_C 已明确要求不要输出 isolated cue，说明"instruction present but execution unstable"。

**D. 已有 guidance 覆盖**
S6、R_C、E2、E5 已有 coverage。缺少的是：
- condition 内 independent restriction 与 condition predicate threshold 的边界；
- constraint 内含 condition 的反向嵌套；
- short complete phrase 与 isolated cue 的区分（`in particular` 是 Gold constraint，不能简单禁止短词）。

**E. 状态**
`POTENTIAL_REFINEMENT_TARGET`。当前 R_C 不是最终版本，但不能在未解决 Gold 边界前继续堆规则。

### 2.6 Exception

**A. 当前定义**
S7：从原本适用的 rule 中移除或缩小范围的 case，包含 marker 和完整 governed proposition。E3 用 `unless` 展示。

**B. 已观察 failure**
- Gold 只有 11 samples / 13 spans。
- A exception P/R/F1：`0.8333 / 0.4545 / 0.5882`；B `0.8571 / 0.5455 / 0.6667`；C `1.0000 / 0.4545 / 0.6250`；D `1.0000 / 0.5455 / 0.7059`。
- 11 个 exception 样本中，A 正确 5 个、B 6 个、C 5 个、D 6 个。错误不是单一方向：部分 Gold exception miss，部分 marker 与 condition 混用。
- Gold exception surface 包括 `unless`, `except`, `excluding`, `with the exception`, `even if`, `apart from`, `to the extent that ... not`；E3 只覆盖 `unless`。

**C. 是否稳定**
样本量太小；四臂变化显示一定 run/arm sensitivity，但不足以区分 semantic failure 与 sampling/context variation。

**D. 已有 guidance 覆盖**
S7 + E3 已有基础定义。当前没有足够证据说明需要 extra targeted exception instruction。

**E. 状态**
`INSUFFICIENT_EVIDENCE`。

结论：exception 目前 **NO CURRENT REFINEMENT JUSTIFICATION**（作为 evidence status）。

## 3. Q1 汇总：Field Decision Matrix

见 `sep_c3_field_refinement_decision_matrix.md`。核心状态：

| Field | Stable failure? | Already covered? | Evidence for new instruction? | Main unresolved issue | Status |
|---|---|---|---|---|---|
| modality | 是，definition 稳定混淆 | S2/E4 部分 | 有 | definition vs obligation/prohibition | `POTENTIAL_REFINEMENT_TARGET` |
| actor | pre-R_A 稳定；R_A 后改善 | R_A 强覆盖 | 无 | unresolved pronoun 的理论风险 | `ALREADY_ADDRESSED` |
| action | 部分稳定边界/role failure | E4/S4/S8 部分且冲突 | 边界 evidence | definition action；action 包含 condition/constraint | `UNRESOLVED_BOUNDARY` |
| condition | 是，R_C 下稳定迁移 | S5/E5/R_C 部分 | 有 | condition-only predicate vs nested constraint | `POTENTIAL_REFINEMENT_TARGET` |
| constraint | 是，recall/FP tradeoff | S6/R_C/E2/E5 部分 | 有 | 同一嵌套边界；isolated `only` | `POTENTIAL_REFINEMENT_TARGET` |
| exception | 证据不足 | S7/E3 基础覆盖 | 无 | 11 samples / 13 spans；run sensitivity | `INSUFFICIENT_EVIDENCE` |

目前没有理由继续为 **actor** 增加 targeted instruction；也没有足够理由为 **exception** 设计 targeted instruction。

## 4. Q4–Q6：Condition / Constraint Gold overlap 与关键样本

### 4.1 Gold 实际 overlap

| 关系 | 数量 | 说明 |
|---|---:|---|
| condition contains constraint | 7 pairs | `condition_contains_constraint` |
| constraint contains condition | 4 pairs | `constraint_contains_condition` |
| 合计 actual clause-level pairs | 11 | 10 clauses / 10 samples |
| same-sample any pair relation | 21 pairs | 14 samples |
| condition-only clauses | 152 | 116 samples |
| constraint outside condition spans | 291 | 132 samples |
| coarse hull overlap | 43 samples | evaluator diagnostic only |

关键点：**Gold 允许合法 overlap，而且两个方向都有 annotation evidence**：
- condition contains constraint：`000106`, `000214`, `000218`, `000223` 等；
- constraint contains condition：`000028`, `000037`, `000061`, `000077`。

不能规定互斥；也不能规定所有 condition 内部 threshold/time/legal/purpose 都要拆 constraint。

### 4.2 `estg_000052`

Gold：
- condition：`insofar as they, together with contributions within the meaning of item 6, do not exceed a total of 10% of the profit of the immediately preceding business year` `[38,198)`
- constraints：empty

A/B：
- 保留 condition `[38,198)`；
- 额外产生 two nested constraint FPs：`together with contributions...` `[55,111)` 和 `a total of 10%...` `[127,198)`。

C/D：
- condition 丢失；
- 整段 `[38,198)` 进入 constraint。

Gold 差异的解释（候选，不是已验证规则）：`10%` 是 `insofar as ... do not exceed ...` 这个 applicability predicate 的 threshold；它不是已适用 action `deductible` 的独立参数。因此 Gold 把它留在 condition 内部。这个解释能组织 000052，但需要 000104 的反向对照支持。

### 4.3 `estg_000106`

Gold：
- condition：`have a normal useful life in the business of at least four years` `[77,141)`
- condition：`are used in a domestic permanent establishment that serves to generate income within the meaning of Section 2(3) items 1 to 3` `[149,274)`
- constraints：`for business assets` `[49,68)`；`at least four years` `[122,141)`；`within the meaning of Section 2(3) items 1 to 3` `[227,274)`
- 后两个 constraints 分别 nested 在两个 conditions 内。

A/B：
- 保留宽 condition `[49,275)`；
- 只保留一个 nested constraint `at least four years` `[122,141)`。

C/D：
- condition 丢失；
- 整段 `[49,275)` 进入 constraint；
- 额外产生 isolated `only` `[33,37)`；
- D 还把 legal reference 拆成 `[158,274)`。

Gold 差异的解释（候选）：`at least four years` 被 Gold 看作 `normal useful life` 的独立 local restriction；`within the meaning of Section 2(3)...` 被 Gold 看作 `used in a domestic permanent establishment` 的 legal-basis restriction。因此 condition 保留完整命题，同时把 internal restrictions 也列入 constraints。这个解释与 000052 的 predicate-threshold 解释可以并置，但目前不能证明模型或 annotator 会稳定采用它。

### 4.4 000052 与 000106 是否能被同一原则解释？

可以提出一个**候选解释 P2**：

> 先判断 phrase 是否是可适用行为的独立 local restriction；若它只是 applicability predicate 的 threshold/truth condition，则留在 condition；若它修饰 distinct head，且可独立表达对 action/parameter 的限制，则同一文字也进入 constraint。

但当前只能将其标记为候选：
- 支持：`000052` vs `000104`、`000106`、`000028`。
- 反例/未决：`000569` `upon application` 是 Gold constraint，但 surface 像 precondition；`000816` `when determining income...` 是 Gold constraint 而非 condition；`000776` `in particular` 是 Gold constraint；`000210` relative clause vs participial modifier 仍不明确；`000052` 的 "predicate/threshold 不拆" 本身是解释性判断。

因此最终答案是：

> **No stable general rule identified.** P2 只能作为 candidate annotation principle，不能写成 Prompt rule。

## 5. Condition / Constraint Boundary Matrix

完整 CSV：`sep_c3_gold_condition_constraint_matrix.csv`。核心 observation：

| Semantic situation | Gold actual pattern | #samples (descriptive) | Counterexample / unresolved | Stable principle? |
|---|---|---:|---|---|
| factual applicability trigger | 多数在 condition；11 constraint spans 也含此类 cue | condition 86 / constraint 11 / nested 3 | `000052`, `000108`, `000209` | No; feature not decisive |
| threshold on eligibility | condition 与 constraint 都出现 | condition 13 / constraint 15 / nested 1 | `000052` vs `000104` | No |
| threshold on regulated action | condition 与 constraint 都出现 | condition 12 / constraint 15 / nested 1 | `000040`, `000046`, `000070` | No |
| duration | 多数 constraint，但也有 condition-only/nested | condition 19 / constraint 34 / nested 4 | `000106` vs `000062` | No |
| deadline | condition 与 constraint 都出现 | condition 23 / constraint 24 / nested 4 | `000052`, `000214` | No |
| frequency | 主要 constraint，但样本少 | condition 2 / constraint 8 / nested 0 | `000051`, `000092` | No |
| quantity threshold | 两者都常见 | condition 45 / constraint 49 / nested 2 | `000052` vs `000040` | No |
| percentage | condition-only 与 constraint outside 都有 | condition 3 / constraint 10 / nested 0 | `000052` vs `000104` | No |
| purpose | 两者都有 | condition 10 / constraint 5 / nested 1 | `000108` vs `000027` | No |
| legal reference | 两者都有 | condition 34 / constraint 34 / nested 2 | `000106` vs `000209` | No |
| manner restriction | 两者都有 | condition 25 / constraint 33 / nested 0 | `000004`, `000039` | No |
| exception-like condition | 样本少，condition/constraint/exception 边界不稳 | condition 1 / constraint 1 | `000083`, `000210` | Insufficient |
| nested restriction | Gold 明确允许两个方向 overlap | 10 clauses / 11 pairs / 10 samples | `000028` vs `000106` | Overlap allowed; inner role manual |

所有 lexical feature 只用于 descriptive retrieval，不用作 final semantic decision。表中 `manual_review_required` 均为 true。

## 6. Matched Contrastive Pairs

完整报告：`sep_c3_gold_contrastive_pairs.md`。本轮找到自然 pair，但均需人工语义复核：

1. **Percentage/threshold**: `000052`（condition-only 10% predicate） vs `000104`（condition + separate `up to 20%` constraint）。
2. **Duration/time**: `000106`（nested `at least four years`） vs `000062`（`within the last ten years` 留在 condition，无 nested constraint）。
3. **Eligibility/procedural**: `000104`（`Upon acquisition...` condition） vs `000569`（`upon application` Gold constraint）。
4. **Legal-reference/purpose**: `000106`（legal reference nested in condition） vs `000209`（legal references/purpose inside condition without nested constraint）。
5. **Purpose-like**: `000108`（purpose in condition） vs `000027`（`for the purpose of determining the tax rate` constraint）。

这些 pair 的共同结论：相同的 lexical topic 不能决定 condition/constraint；真正的差异必须在完整命题、可独立限制性、以及已适用 action 的角色中寻找。当前证据还不能把这些语义判断自动化。

## 7. E Coverage Audit

完整报告：`sep_c3_example_coverage_audit.md`。

- E1 unresolved pronoun：Gold actor 中有类似 unresolved/pronoun 形式，但数量和稳定性有限。
- E2 passive + actor absence + constraints：覆盖 actor absence；没有覆盖 condition/constraint overlap。
- E3 exception：只覆盖 `unless`；Gold exception surface 多样。
- E4 definition + obligation：**存在过度泛化风险**。E4 说 definition clause `actors and actions empty`，但 Gold 39/39 definition clauses 都有 action span。该例子可能诱导 definition copula/light verb miss。
- E5 nested condition+constraint：代表 Gold 中确实存在的 nested relation，但只覆盖 condition contains constraint 一个方向；Gold 还有 constraint contains condition（4 pairs）和 action contains condition/constraint（11 pairs）。
- E 缺少 condition-only threshold 类例子，如 `000052`。
- E5 不是单例噪声：Gold 有 10 clauses / 11 nested pairs，因此它代表一个真实 pattern；但它不是完整代表整个 condition/constraint 边界。

## 8. S Coverage / Redundancy Audit

完整报告：`sep_c3_example_coverage_audit.md`（同文件含 S audit）。

- S5 condition 定义与 S6 constraint 定义已经包含语义主题，但 S6 把 legal reference/time/duration/quantity/purpose/exclusivity 直接列为 constraint 触发，和 Gold 中这些主题同时出现在 condition 的事实冲突。
- S8 的 "constraint nested inside condition is reported in both arrays" 是正确的一部分；但它只说明单向嵌套，且 "action ends where such a phrase begins" 与 Gold action::condition / action::constraint overlap 直接冲突。
- S9/S15 的 ambiguity/normalization 规则本身没有导致明显 semantic regression。
- 当前问题不是单纯 instruction missing：condition migration 在 R_C 存在时仍发生；isolated `only` 在旧 R_C 已说"不要 isolated cue"后仍反复出现。说明存在 **instruction present but execution/stability problem**。
- 同时也有 **instruction missing/conflicting** 的部分：modality definition boundary、action 包含 condition/constraint 的 Gold 行为、condition contains constraint 反向 overlap。

## 9. R_A Stability Check

- Gold actor convention 与 R_A 基本一致：只保留对 action 负责、受约束或承受的显式 entity；passive/empty performer 通常为空。
- 41/150 个样本有 Gold actor，109/150 个 empty actor；empty-Gold 是稳定 convention。
- R_A 未在当前 EStG-150 上造成 actor recall loss（A/B matched Gold 均为 39/41）。
- 理论风险：E1/S3 允许 unresolved pronoun actor，而 R_A 的 "explicitly stated entity" 可能被解释为排除 pronoun；没有观察到实际 Gold loss，但应保留为边界说明。
- 结论：不修改 R_A。

## 10. Action / Exception 的专项结论

**Action**：当前 coarse F1 高，但有稳定 Gold conflict：
- E4 与 Gold definition action 冲突；
- S8 action-end 规则与 Gold action::condition/constraint overlap 冲突；
- 因此不需要对称地新增 action targeted instruction，但需要先澄清 Gold action span 与嵌套字段的关系。状态 `UNRESOLVED_BOUNDARY`。

**Exception**：11 samples / 13 spans，A/B/C/D 正确 5/6/5/6，变化小但样本不足以支撑 targeted refinement。状态 `INSUFFICIENT_EVIDENCE` / `NO CURRENT REFINEMENT JUSTIFICATION`。

## 11. Validation / Artifact Separation

- targeted A/B/C/D 600 条 canonical valid，四臂均 150 samples；parser warning rows = 0/0/2/3，canonicalizer warning rows = 28/23/21/25。
- condition-preservation BASE/RC1/RC_KEEP 有明确 validation/interface failure：BASE 13 failed、RC1 9 failed + 1 unknown、RC_KEEP 10 failed；其中 RC1 `estg_000074` 是 unknown unresolved response。这些不能当作 semantic regression。
- condition-preservation BASE 与 targeted B 虽然 prompt 相近，但不能直接做 pure semantic delta；有 validation failure 和 missing source_text 的 rows 必须排除。
- 本轮所有 semantic failure map 主要基于 targeted A/B/C/D，candidate 结论不依赖 condition-preservation failure rows。
- `sep_c3_source_text_anomaly_audit.md` 单独记录 source_text anomaly。

## 12. Source Text Anomaly

- targeted A/B/C/D 600 条中恰好 **4 条** source_text 追加了 E 示例 block：
  - A / `estg_000044`
  - A / `estg_000720`
  - C / `estg_000035`
  - C / `estg_000044`
- 追加内容长度均为 2351 bytes，SHA-256 相同：`771cf518d671923090a424fcc3a5e10385de74759158079faabc266889b0e607`。
- 4 条的原始源文本前缀未变；所有预测 span 仍在原始 source_text 范围内；原始 text slice check 通过。
- 因此该 anomaly 没有影响本轮 semantic coordinate analysis，但它是真实 interface anomaly，未来 API 前必须修复。
- 另在更早 `sep_c3_modular_ablation_v2/100` 的 canonical 中也发现 1 条同样的 E 追加模式（`estg_000044`）；不计入 targeted 的 4 条，但说明问题不只在 targeted 家族。

## 13. Candidate Annotation Principles（不是 Prompt rules）

### P1 — Overlap permission（证据较强）

**Candidate principle P1**：`condition` 与 `constraint` 不是互斥字段；Gold 允许 condition contains constraint 和 constraint contains condition。

- Supporting cases：`000106`, `000214`, `000218`, `000223`；反向 `000028`, `000037`, `000061`, `000077`。
- Counterexamples：无直接反例；但 Overlap permission 本身不告诉我们何时新增字段。
- Unresolved：overlap 中的 internal phrase 是否 should be co-labeled 仍需人工判断。
- 状态：`NOT YET A PROMPT RULE`。

### P2 — Applicability predicate vs independent local restriction（证据不足以冻结）

**Candidate principle P2**：先判 applicability proposition；如果 phrase 是 condition predicate/threshold，则留在 condition；如果 phrase 修饰 distinct head，并独立限制已经可适用的 action/parameter，则可以同时/单独记为 constraint。

- Supporting cases：`000052` vs `000104`；`000106` 的 two nested restrictions；`000028` 的 constraint 内 condition。
- Counterexamples / unresolved：`000569` `upon application`、`000816` `when determining income...`、`000776` `in particular`、`000210` relative vs participial、`000052` predicate partition 自身不确定。
- 状态：`NOT YET A PROMPT RULE`；不能写成 LLM instruction。

### P3 — Lexical topic is not role（negative principle）

**Candidate principle P3**：time/duration/quantity/percentage/legal-reference/purpose/manner 等 lexical topic 不能单独决定 condition/constraint role。

- Supporting cases：`000052`（quantity/time/legal in condition only）；`000104`（quantity in constraint）；`000108`（purpose in condition）；`000027`（purpose in constraint）；`000106`（legal reference in nested constraint）；`000209`（legal reference in condition）。
- Counterexamples：没有 "topic => field" 的稳定反例；这正是 P3 的 support。
- Unresolved：P3 只是负原则，不能单独指导 annotation。
- 状态：`NOT YET A PROMPT RULE`。

## 14. Manual-review-required Cases

- `sep_c3_gold_semantic_boundary_cases.jsonl` 共 223 clause-level cases，其中 133 条 `manual_review_required=true`。
- 全部 10 个含 nested conditional-constraint pair 的 clause 都要求人工复核。
- 6 个 mixed inside/outside cases 标记为 Type E：`000037`, `000061`, `000077`, `000106`, `000214`, `000223`。
- 关键 unresolved queue：`000052`, `000104`, `000106`, `000028`, `000060`, `000039`, `000108`, `000161`, `000210`, `000776`, `000569`, `000816`, `000247`, `000293`。
- isolated `only` cases：`000106`, `000108`, `000161` 等仍需人工判断。

## 15. Final Answers to the 23 Required Questions

1. 六个字段分别是否有稳定 failure：modality yes（definition 混淆）；actor pre-R_A yes、R_A 后不再是稳定未覆盖 failure；action partial/stable boundary；condition yes；constraint yes；exception insufficient。
2. 哪些字段已有 sufficient guidance：actor（R_A）；exception 有基本定义但样本不足。
3. 哪些字段目前没有理由继续 Prompt refinement：actor、exception。
4. condition/constraint Gold overlap：actual 11 clause pairs / 10 clauses / 10 samples，sample-level 21 pairs / 14 samples；coarse hull 43/150，仅 diagnostic。
5. condition-only 与 nested constraint 的主要差异：候选 P2 的角色差异；目前 **No stable general rule identified**。
6. `000052` 与 `000106` 是否能被同一原则解释：可以用 P2 候选解释，但未验证、存在 counterexamples；不能写成稳定规则。
7. 是否找到 stable candidate annotation principle：只有 P1（overlap allowed）证据较强；P2/P3 是 candidate/negative，不是 prompt rules。
8. counterexample 数量：P2 当前列出 `000569`, `000816`, `000776`, `000210` 等 unresolved，加上 `000052` predicate partition 不确定性；没有宣称某个词法规则，因此没有单一 finite counterexample 集。
9. Gold annotation inconsistency：未发现明确不一致；发现的是 context-dependent annotation 和未解决边界，不是可证明的 inconsistency。
10. E5 对 Gold 是否具有代表性：代表 nested condition contains constraint，但不代表全部；Gold 还有 constraint contains condition 和 action overlaps。
11. E coverage 缺口：condition-only threshold；definition action；双向 overlap；短限定语完整短语；更多 exception markers。
12. 当前 S 是否包含所需语义但执行不稳定：是的，部分问题（isolated `only`, condition retention）属于 instruction present but execution unstable；同时 S6/S8 有过 broad/conflicting wording。
13. R_A 是否与 Gold actor semantics 一致：基本一致，有 unresolved pronoun 的理论边界风险，但 EStG-150 未观察到 recall loss。
14. modality/action/exception 是否需要 targeted instruction：modality 有 evidence for refinement；action 是 unresolved boundary；exception insufficient。
15. source_text anomaly 是否影响分析：不影响本轮 span coordinate analysis；但接口 integrity 有问题。
16. 还有哪些 manual-review-required cases：见第 14 节和 `cases.jsonl`。
17. Field Decision Matrix：见 `sep_c3_field_refinement_decision_matrix.md` 与本文第 3 节。
18. Condition/Constraint Boundary Matrix：见 `sep_c3_gold_condition_constraint_matrix.csv`。
19. candidate principles：P1/P2/P3，均为 `NOT YET A PROMPT RULE`。
20. unresolved issues：见第 14 节与主报告各节。
21. reports 路径：见第 16 节文件列表。
22. scripts/tests：`scripts/analyze_sep_c3_gold_semantic_boundary_v1.py`；`tests/test_sep_c3_gold_semantic_boundary_v1.py`。
23. Git commit / push 状态：本轮只写新分析脚本、新报告、新测试；未修改 Gold、Prompt、raw predictions、evaluator、parser、canonicalizer。Git commit/push 状态以工作树检查为准，当前尚未 commit/push；详见最终汇报。

## 16. Artifact Paths

```text
formal_experiment/outputs/reports/sep_c3_gold_semantic_boundary_study_v1.md
formal_experiment/outputs/reports/sep_c3_gold_semantic_boundary_cases.jsonl
formal_experiment/outputs/reports/sep_c3_gold_condition_constraint_matrix.csv
formal_experiment/outputs/reports/sep_c3_gold_contrastive_pairs.md
formal_experiment/outputs/reports/sep_c3_field_refinement_decision_matrix.md
formal_experiment/outputs/reports/sep_c3_example_coverage_audit.md
formal_experiment/outputs/reports/sep_c3_source_text_anomaly_audit.md
formal_experiment/outputs/reports/sep_c3_gold_semantic_boundary_derived_v1.json
formal_experiment/scripts/analyze_sep_c3_gold_semantic_boundary_v1.py
formal_experiment/tests/test_sep_c3_gold_semantic_boundary_v1.py
```

## 17. Final Stop

本轮到此停止：

- 不设计 Prompt；
- 不启动 API；
- 不提出下一轮 experiment arms；
- 不把 P1/P2/P3 写成 instruction；
- 只向上一层研究者报告 Gold semantics 与 evidence status。
