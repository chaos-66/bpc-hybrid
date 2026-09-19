# SEP-C3 R_C condition preservation draft v1

## 1. 旧 R_C 完整原文及来源

- 来源：`formal_experiment/prompts/sun_compat/modular_refinement_v1/R_C_constraint_recall.md`
- 来源 SHA-256：`cfcbbc45e278ab3ad4fad8784c5a6bcc551c0b51a2e1833ac2c4e56d0571fcae`
- 既有 D 实际使用：`formal_experiment/prompts/sun_compat/modular_refinement_v1/generated/direct_llm_refinement_D_v1.md`
- 核对结果：旧 R_C 来源文件内容与既有 D 中嵌用的 R_C 段落逐字一致；未发现差异。manifest 中记录的 `source_R_C_sha256` 同为 `cfcbbc45e278ab3ad4fad8784c5a6bcc551c0b51a2e1833ac2c4e56d0571fcae`。

```text
Constraint: extract an explicit phrase when it directly restricts when, how, how much, for what purpose, under what legal reference, or with what exclusivity the regulated action applies. Extract the complete restrictive phrase rather than an isolated cue word such as ‘only’.
```

## 2. 追加新句后的完整候选

唯一新增句（逐字）：

```text
Keep each applicability condition as a complete proposition in conditions; extracting an overlapping or nested constraint must not replace or remove that condition.
```

完整候选：

```text
Constraint: extract an explicit phrase when it directly restricts when, how, how much, for what purpose, under what legal reference, or with what exclusivity the regulated action applies. Extract the complete restrictive phrase rather than an isolated cue word such as ‘only’.
Keep each applicability condition as a complete proposition in conditions; extracting an overlapping or nested constraint must not replace or remove that condition.
```

## 3. diff

```diff
@@
+Keep each applicability condition as a complete proposition in conditions; extracting an overlapping or nested constraint must not replace or remove that condition.
```

diff 以旧 R_C 文字为基线；除上述一句外，没有其他文字新增、删除或改写。候选中的旧 R_C 原句逐字保留。

## 4. 固定设计解释

1. 唯一设计变量：在旧 R_C 后增加一条明确的 condition 保留指令。
2. 唯一目标：针对新增 constraint 时原有 applicability condition 消失的现象。
3. 不处理的问题：
   - 不决定某种数量、时间、目的或法律引用一律属于哪个字段；
   - 不解决 000052 的 10% 与 000106 的四年期限应如何细分的全部争议；
   - 不保证消除整段 condition 被额外复制到 constraint 的 FP；
   - 不承诺解决 isolated only、actor regression 或运行方差。
4. 选择保留旧 R_C 的原因：当前不知道旧 R_C 各条类型提示的独立贡献。本次不同时删除类型枚举、重写语义定义、增加多个保护规则，以便保持改动可解释。
5. 与现有 E5 的关系：E5 已经提供 condition/constraint 嵌套示例。新句不是新的语义理论，而是在 R_C 内明确重申“抽取 constraint 不得替代 condition”。这种重申是否有实际增益，现有数据无法证明。
6. 当前状态：未验证、未冻结、未进入活动 Prompt。不得写“已经修复”“提高了分数”“通过了实验”。

## 5. 案例事实核对

### estg_000052

- sample_id: `estg_000052`
- 原文片段：`The contributions are only deductible insofar as they, together with contributions within the meaning of item 6, do not exceed a total of 10% of the profit of the immediately preceding business year. 6.`
- Gold 坐标：condition `insofar as they, together with contributions within the meaning of item 6, do not exceed a total of 10% of the profit of the immediately preceding business year` `[38,198)`；constraints 为空。
- 既有预测变化：A/B 保留 condition `[38,198)`，constraints 为 `[55,111)` 与 `[127,198)` 两个内部短语；C/D 的 condition 为空，constraints 为完整段落 `[38,198)`。
- 本候选明确要求什么：新增句要求保留 applicability condition；抽取 overlapping 或 nested constraint 不得替换或删除该 condition。候选没有要求删除 constraints 中的整段复制。
- 仍未解决什么：不保证消除整段 condition 被额外复制到 constraint 的 FP；不解决 10% 应如何细分的全部争议；未验证。

### estg_000028

- sample_id: `estg_000028`
- 原文片段：`The income shall be taxed at the tax rate that results when taking into account the converted income; however, the tax to be assessed may not be higher than that which would result from the taxation of all emoluments.`
- Gold 坐标：c1 condition `when taking into account the converted income` `[55,100)`；c1 constraint `at the tax rate that results when taking into account the converted income` `[26,100)`；c2 constraint `than that which would result from the taxation of all emoluments` `[152,216)`。c1 condition `[55,100)` 位于 c1 constraint `[26,100)` 内部，两字段均有 Gold 标注依据。
- 既有预测变化：A/B 的 c1 condition 为 `[26,100)`，c1 constraints 为空；C/D 的 c1 condition 为空，c1 constraint 为 `[26,100)`；B、D 另有 c2 constraint `[152,216)`。
- 本候选明确要求什么：新增句要求当 constraint 与 condition 重叠或嵌套时，抽取 constraint 不得替换或删除 condition。候选没有新增数量、时间、目的或法律引用分类规则。
- 仍未解决什么：不保证模型输出会保留细粒度 condition 或同时保留两字段；不承诺解决 actor regression 或运行方差；未验证。

### estg_000106

- sample_id: `estg_000106`
- 原文片段：

  ```text
  (2) The investment allowance may only be claimed for business assets which
  — have a normal useful life in the business of at least four years, and
  — are used in a domestic permanent establishment that serves to generate income within the meaning of Section 2(3) items 1 to 3.
  ```

- Gold 坐标：condition `have a normal useful life in the business of at least four years` `[77,141)`；condition `are used in a domestic permanent establishment that serves to generate income within the meaning of Section 2(3) items 1 to 3` `[149,274)`；constraint `for business assets` `[49,68)`；constraint `at least four years` `[122,141)`；constraint `within the meaning of Section 2(3) items 1 to 3` `[227,274)`。四年期限 `[122,141)` 位于 condition `[77,141)` 内，法律引用 `[227,274)` 位于 condition `[149,274)` 内。
- 既有预测变化：A/B 保留 condition `[49,275)`/`[49,274)`，并只有嵌套 constraint `[122,141)`；C/D 的 condition 为空，完整段落搬入 constraint `[49,275)`，C 另有 `only` `[33,37)`，D 另有拆出的 `[122,141)` 与 `[158,274)`。
- 本候选明确要求什么：新增句只要求保留 applicability condition；没有“禁止拆 threshold”的规则，也没有新增数量、时间、目的或法律引用分类规则。
- 仍未解决什么：不解决四年期限与法律引用应如何细分的全部争议；不承诺修复 isolated `only` FP；未验证。

### estg_000104

- sample_id: `estg_000104`
- 原文片段：`(1) Upon the acquisition or production of depreciable fixed assets, the taxpayer may claim an investment allowance of up to 20% of the acquisition or production costs as a profit-reducing deduction.`
- Gold 坐标：condition `Upon the acquisition or production of depreciable fixed assets` `[4,66)`；constraint `up to 20% of the acquisition or production costs` `[118,166)`；constraint `as a profit-reducing deduction` `[167,197)`。
- 既有预测变化：A/B 保留 condition `[4,66)`，constraints 为空；C/D 保留 condition `[4,66)`，并新增数量 constraint `of up to 20% of the acquisition or production costs` `[115,166)`。
- 本候选明确要求什么：新增句没有“数量一律属于 condition”或“数量一律属于 constraint”的规则；它只要求保留 applicability condition，因此没有笼统禁止数量短语进入 constraint。
- 仍未解决什么：不保证 span 边界纠正到 Gold `[118,166)`；不决定数量字段应如何细分；未验证。

### estg_000776

- sample_id: `estg_000776`
- 原文片段：`An exercise of public authority shall be assumed in particular where services are involved the acceptance of which the recipient is obliged to accept by virtue of a statutory or official order.`
- Gold 坐标：c1 condition `where services are involved the acceptance of which the recipient is obliged to accept by virtue of a statutory or official order` `[63,192)`；c1 constraint `in particular` `[49,62)`；c2 constraint `by virtue of a statutory or official order` `[150,192)`。
- 既有预测变化：A 保留 condition `[63,192)`，constraints 为 `in particular` `[49,62)` 与 `by virtue of a statutory or official order` `[150,192)`；B 保留 condition `[63,192)`，constraints 为空；C/D 保留 condition `[63,192)`，constraints 仅剩 `in particular` `[49,62)`。
- 本候选明确要求什么：新增句没有新增短词黑名单或新的短词豁免分类；它只处理 condition 保留，未新增针对 `in particular` 或 `only` 的专门规则。
- 仍未解决什么：不承诺模型输出会保留 Gold 的 `in particular` 或法律引用 constraint；isolated `only` 仍未解决；未验证。

## 6. 尚未验证与 API=0

- 本候选未验证、未冻结、未进入活动 Prompt。
- 活动 Prompt、正式默认配置、Gold、评价器、历史预测和分数均未修改。
- 本轮未调用真实 LLM/API；新增 API=0；未运行项目审计或代码测试。
- 现有数据不能证明新句有实际增益；没有“已经修复”“提高了分数”“通过了实验”的证据。
- 目前没有效果验证，不具备启动实验的新增授权。

---

## 7. 假设性诊断：`D_condition_retention_simulation`

> **边界声明**：这项计算只描述一种指定的假设性输出变化。它没有证明新句会让模型产生这种变化；真实运行也可能新增 condition FP、改变其他字段，或没有任何收益。

本节使用已有 targeted refinement B/D 的 150 个 canonical predictions、原冻结 Gold、原 coarse-view 与同字段字符 overlap 计数规则，只做内存计算和报告。

### 7.1 固定复现检查与计算口径

- 输入：`B/repeat-01/canonical_predictions.jsonl`、`D/repeat-01/canonical_predictions.jsonl`、`data/gold/stage2/estg150_formal_gold_v1.json`。
- 复现检查：用冻结 `evaluate_coarse` 对 B/D 重新计算，`coarse_five_field_mean_f1`、`coarse_five_field_micro`、五个 span 字段的计数及 P/R/F1 与现有各自 `evaluation.json` 一致；因此继续派生本模拟分数。
- D 新增 constraint：在整数 record 范围内，对 D 与 B 的全部 constraints 按 `(start, end, text)` 比较、忽略 `id`；D 中存在且 B 中不存在的 constraint 视为新增。
- 保留条件触发条件：该样本 record 的全部 clause conditions 汇总为空，且 B 的某个 condition 与至少一个 D 新增 constraint 有非空字符交集。
- 去重：恢复片段按 `(start, end, text)` 去重。
- 恢复放置：将 B condition 原对象追加到 D 副本中 `clause_id` 相同的 clause；若不存在，则放入 clause_span 与该 condition 相交字符最多的 clause。该放置只用于构造有效 record，不改变 coarse-view 的 span 计数。
- 除新增 condition 外，不删除 constraint、不修改 actor，也不修正任何坐标或文字。
- 本副本只命名为 `D_condition_retention_simulation`；它不是 R_C v2 的预测或实验结果。

### 7.2 机械规则选中样本

- 逐一检查 150 个样本；其中 D conditions 汇总为空且存在 D 新增 constraint 的样本：**29 个**。
- 按上述 overlap 规则实际进入内存副本的样本：**12 个**。
- 恢复 condition 片段（`(start,end,text)` 去重后）：**13 个**。
- 选中 sample_id 清单：`estg_000027`, `estg_000028`, `estg_000037`, `estg_000039`, `estg_000052`, `estg_000060`, `estg_000071`, `estg_000106`, `estg_000108`, `estg_000161`, `estg_000210`, `estg_000507`

### 7.3 每个样本恢复的 condition、相交约束与冻结评价

#### 7.3.1 `estg_000027`

- 恢复 condition：`only for part of the calendar year` `[66,100)`
- 相交的新增 D constraint：
  - `only for part of the calendar year` `[66,100)`
- 冻结 coarse Gold condition 判定：**未匹配预测（FP）**；该样本冻结 coarse Gold condition 为空。

#### 7.3.2 `estg_000028`

- 恢复 condition：`at the tax rate that results when taking into account the converted income` `[26,100)`
- 相交的新增 D constraint：
  - `at the tax rate that results when taking into account the converted income` `[26,100)`
- 冻结 coarse Gold condition 判定：**命中**；匹配的 Gold condition span：`when taking into account the converted income` `[55,100)`

#### 7.3.3 `estg_000037`

- 恢复 condition：`to the extent that these institutions serve health, old-age, invalidity and survivors’ provision.` `[280,377)`
- 相交的新增 D constraint：
  - `to the extent that these institutions serve health, old-age, invalidity and survivors’ provision` `[280,376)`
- 冻结 coarse Gold condition 判定：**命中**；匹配的 Gold condition span：`to the extent that these institutions serve health, old-age, invalidity and survivors’ provision` `[280,376)`

#### 7.3.4 `estg_000037`

- 恢复 condition：`subject to the following conditions:\naa) the fund must be subject to state supervision;\nbb) the fund must grant a legal entitlement to benefits for the purpose of old-age and survivors’ provision.` `[415,611)`
- 相交的新增 D constraint：
  - `subject to the following conditions` `[415,450)`
  - `subject to state supervision` `[473,501)`
  - `for the purpose of old-age and survivors’ provision` `[559,610)`
- 冻结 coarse Gold condition 判定：**未匹配预测（FP）**；该样本存在 Gold condition span `to the extent that these institutions serve health, old-age, invalidity and survivors’ provision` `[280,376)`，但与其无交集。

#### 7.3.5 `estg_000039`

- 恢复 condition：`to the extent that they are required under the articles of association for benefit entitlements of current and former members of the taxpayer’s enterprises` `[234,389)`
- 相交的新增 D constraint：
  - `to the extent that they are required under the articles of association for benefit entitlements of current and former members of the taxpayer’s enterprises` `[234,389)`
- 冻结 coarse Gold condition 判定：**命中**；匹配的 Gold condition span：`the taxpayer’s ongoing contribution payments may only be suspended or restricted for compelling economic reasons and only after consultation with the works council. dd) The contributions are deductible to the extent that they are required under the articles of association for benefit entitlements of current and former members of the taxpayer’s enterprises` `[32,389)`

#### 7.3.6 `estg_000052`

- 恢复 condition：`insofar as they, together with contributions within the meaning of item 6, do not exceed a total of 10% of the profit of the immediately preceding business year` `[38,198)`
- 相交的新增 D constraint：
  - `insofar as they, together with contributions within the meaning of item 6, do not exceed a total of 10% of the profit of the immediately preceding business year` `[38,198)`
- 冻结 coarse Gold condition 判定：**命中**；匹配的 Gold condition span：`insofar as they, together with contributions within the meaning of item 6, do not exceed a total of 10% of the profit of the immediately preceding business year` `[38,198)`

#### 7.3.7 `estg_000060`

- 恢复 condition：`in the case of the sale or abandonment of the entire business, of a part-business or of a co-entrepreneur’s interest` `[134,250)`
- 相交的新增 D constraint：
  - `in the case of the sale or abandonment of the entire business, of a part-business or of a co-entrepreneur’s interest in the profit of the last profit determination period before the sale or abandonment` `[134,335)`
- 冻结 coarse Gold condition 判定：**命中**；匹配的 Gold condition span：`in the case of the sale or abandonment of the entire business, of a part-business or of a co-entrepreneur’s interest` `[134,250)`

#### 7.3.8 `estg_000071`

- 恢复 condition：`only to the extent that no partial write-down under subparagraph a was claimed for the receivables` `[80,178)`
- 相交的新增 D constraint：
  - `only to the extent that no partial write-down under subparagraph a was claimed for the receivables` `[80,178)`
- 冻结 coarse Gold condition 判定：**未匹配预测（FP）**；该样本存在 Gold condition span `For registered traders` `[0,22)`，但与其无交集。

#### 7.3.9 `estg_000106`

- 恢复 condition：`for business assets which\n— have a normal useful life in the business of at least four years, and\n— are used in a domestic permanent establishment that serves to generate income within the meaning of Section 2(3) items 1 to 3` `[49,274)`
- 相交的新增 D constraint：
  - `for business assets which\n— have a normal useful life in the business of at least four years, and\n— are used in a domestic permanent establishment that serves to generate income within the meaning of Section 2(3) items 1 to 3.` `[49,275)`
  - `in a domestic permanent establishment that serves to generate income within the meaning of Section 2(3) items 1 to 3` `[158,274)`
- 冻结 coarse Gold condition 判定：**命中**；匹配的 Gold condition span：`have a normal useful life in the business of at least four years, and\n— are used in a domestic permanent establishment that serves to generate income within the meaning of Section 2(3) items 1 to 3` `[77,274)`

#### 7.3.10 `estg_000108`

- 恢复 condition：`to the extent that they directly serve the business purpose or are intended for residential purposes of employees of the business` `[64,193)`
- 相交的新增 D constraint：
  - `to the extent that they directly serve the business purpose or are intended for residential purposes of employees of the business` `[64,193)`
- 冻结 coarse Gold condition 判定：**命中**；匹配的 Gold condition span：`to the extent that they directly serve the business purpose or are intended for residential purposes of employees of the business` `[64,193)`

#### 7.3.11 `estg_000161`

- 恢复 condition：`only under the following conditions` `[33,68)`
- 相交的新增 D constraint：
  - `only under the following conditions` `[33,68)`
- 冻结 coarse Gold condition 判定：**命中**；匹配的 Gold condition span：`only under the following conditions` `[33,68)`

#### 7.3.12 `estg_000210`

- 恢复 condition：`for which guarantees regarding value or dividend claims are provided` `[7,75)`
- 相交的新增 D constraint：
  - `for which guarantees regarding value or dividend claims are provided` `[7,75)`
- 冻结 coarse Gold condition 判定：**命中**；匹配的 Gold condition span：`for which guarantees regarding value or dividend claims are provided are not eligible.\nb) Stock corporations within the meaning of paragraph 1 item 4 are stock corporations having their registered seat and place of management in the country,\naa) which belong to the "Trade" or "Industry" sections of a chamber of commerce and whose main business focus, according to the articles of association and the preparatory acts or the actual management, is demonstrably the industrial manufacture of tangible assets in the country, excluding the generation of electrical energy, gas or heat, and\nbb) for which no general deficiency guarantees for the event of insolvency have been assumed` `[7,686)`

#### 7.3.13 `estg_000507`

- 恢复 condition：`At the tax rate which, according to the tax scale, corresponds to the wages of the last full calendar year` `[29,135)`
- 相交的新增 D constraint：
  - `At the tax rate which, according to the tax scale, corresponds to the wages of the last full calendar year` `[29,135)`
- 冻结 coarse Gold condition 判定：**未匹配预测（FP）**；该样本存在 Gold condition span `which are made alongside current wages from the same employer or in bankruptcy proceedings and are not based on an arbitrary deferral of the payment date` `[490,643)`，但与其无交集。

本模拟共恢复 13 个 condition 片段：**9 个命中冻结 coarse Gold condition，4 个成为未匹配预测（FP）**。

### 7.4 B、原 D、模拟副本对照

| 版本 | condition GT | condition extracted | condition matched predictions | condition unmatched predictions | condition matched Gold | condition missed Gold | condition P | condition R | condition F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B | 122 | 155 | 136 | 19 | 97 | 25 | 0.877419 | 0.795082 | 0.834224 |
| 原 D | 122 | 128 | 117 | 11 | 88 | 34 | 0.914062 | 0.721311 | 0.806328 |
| D_condition_retention_simulation | 122 | 141 | 126 | 15 | 97 | 25 | 0.893617 | 0.795082 | 0.841475 |

| 版本 | 原主口径 five-field mean F1 | micro precision | micro recall | micro F1 |
| --- | ---: | ---: | ---: | ---: |
| B | 0.780640 | 0.855025 | 0.799564 | 0.826365 |
| 原 D | 0.785802 | 0.827124 | 0.819172 | 0.823129 |
| D_condition_retention_simulation | 0.792832 | 0.824561 | 0.838780 | 0.831610 |

| 差值（模拟副本 − 原 D） | condition P | condition R | condition F1 | five-field mean F1 | micro F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 数值 | -0.020445 | 0.073770 | 0.035147 | 0.007029 | 0.008481 |

补充微计数：D extracted/matched/matched Gold = 671/555/376；模拟副本 = 684/564/385。

### 7.5 其他字段未变化核对

| 字段 | D extracted | 模拟副本 extracted | D matched predictions | 模拟副本 matched predictions | D missed Gold | 模拟副本 missed Gold | 预测 span 元组逐样本一致 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| actor | 70 | 70 | 42 | 42 | 3 | 3 | 是 |
| action | 230 | 230 | 211 | 211 | 11 | 11 | 是 |
| constraint | 237 | 237 | 179 | 179 | 30 | 30 | 是 |
| exception | 6 | 6 | 6 | 6 | 5 | 5 | 是 |

- 对 `actor`、`action`、`constraint`、`exception` 逐样本比较 `(start, end, text)` 扁平化顺序列表，D 与 `D_condition_retention_simulation` 完全一致；对应计数和匹配计数也完全一致。
- 未修改 `actor`、`action`、`constraint`、`exception`、`actor_action_map`、`order_relations`、modality 或任何其他预测字段；模拟副本仅增加 condition。

### 7.6 模拟后仍存在的 constraint FP

按冻结 coarse-view 字符 overlap 规则，模拟副本仍有 **58 个未匹配预测 constraint（FP）**，分布于 38 个样本；这些 constraint 预测与坐标跟原 D 完全相同。完整清单如下：

- `estg_000002`:
  - `for that calendar year in which the business year ends` `[217,271)`
- `estg_000004`:
  - `only` `[63,67)`
  - `prior` `[151,156)`
  - `by official notice` `[165,183)`
- `estg_000027`:
  - `only for part of the calendar year` `[66,100)`
- `estg_000037`:
  - `subject to state supervision` `[473,501)`
  - `for the purpose of old-age and survivors’ provision` `[559,610)`
- `estg_000039`:
  - `to the extent that they are required under the articles of association for benefit entitlements of current and former members of the taxpayer’s enterprises` `[234,389)`
- `estg_000052`:
  - `insofar as they, together with contributions within the meaning of item 6, do not exceed a total of 10% of the profit of the immediately preceding business year` `[38,198)`
- `estg_000055`:
  - `not subject to capitalization for advisory, suretyship, borrowed funds, guarantee, rental, trust, brokerage, distribution and administration costs` `[16,162)`
- `estg_000062`:
  - `within the last ten years` `[25,50)`
- `estg_000070`:
  - `on foreign receivables` `[698,720)`
- `estg_000071`:
  - `For registered traders` `[0,22)`
- `estg_000083`:
  - `under Section 12(10) and (11) of the Turnover Tax Act 1972` `[49,107)`
- `estg_000087`:
  - `on the basis of a merger that does not result in liquidation taxation` `[120,189)`
- `estg_000095`:
  - `for acquisition or construction costs incurred for listed commercial buildings in the interest of monument preservation` `[38,157)`
- `estg_000106`:
  - `only` `[33,37)`
- `estg_000108`:
  - `only` `[48,52)`
  - `to the extent that they directly serve the business purpose or are intended for residential purposes of employees of the business` `[64,193)`
- `estg_000112`:
  - `For low-value assets written off pursuant to Section 13` `[44,99)`
  - `For used assets which are intended, directly or indirectly, for transfer for consideration to the seller (sale and lease back) or for resale to the seller (sale and sale back)` `[241,416)`
  - `For used assets acquired by a group company within a group as defined by Section 15 of the Stock Corporation Act 1965` `[420,537)`
- `estg_000113`:
  - `in accordance with its designated purpose` `[79,120)`
- `estg_000118`:
  - `only` `[94,98)`
- `estg_000128`:
  - `only` `[18,22)`
  - `for at least seven years` `[137,161)`
  - `in a domestic permanent establishment` `[234,271)`
- `estg_000130`:
  - `only` `[40,44)`
- `estg_000146`:
  - `only` `[16,20)`
- `estg_000161`:
  - `only under the following conditions` `[33,68)`
- `estg_000164`:
  - `For a one-way distance between the residence and the place of work of up to 20 km` `[67,148)`
- `estg_000209`:
  - `within two years after the registration of the resolution on the reduction of the share capital` `[183,278)`
  - `for the purpose of repaying parts of the share capital` `[279,333)`
  - `(Sections 219 and 245 of the Stock Corporation Act 1965, Section 2 of the Federal Act on the Transformation of Commercial Companies, Federal Law Gazette)` `[527,680)`
- `estg_000210`:
  - `for which guarantees regarding value or dividend claims are provided` `[7,75)`
  - `within the meaning of paragraph 1 item 4` `[116,156)`
  - `which belong to the "Trade" or "Industry" sections of a chamber of commerce` `[253,328)`
  - `whose main business focus, according to the articles of association and the preparatory acts or the actual management, is demonstrably the industrial manufacture of tangible assets in the country` `[333,528)`
  - `for which no general deficiency guarantees for the event of insolvency have been assumed` `[598,686)`
- `estg_000218`:
  - `In the case of a reduction in deductible insurance premiums (Section 1(2), last sentence)` `[0,89)`
- `estg_000245`:
  - `to the extent that they are directly economically connected with non-taxable receipts` `[88,173)`
- `estg_000347`:
  - `of up to and including 50 S` `[56,83)`
  - `exceeding 50 S` `[120,134)`
- `estg_000393`:
  - `in total does not exceed the amount of 10,000 S` `[24,71)`
- `estg_000457`:
  - `apart from cases of an assessment` `[130,163)`
- `estg_000507`:
  - `regardless of whether they are based on judicial or extrajudicial settlements, and also in cases where they are not granted alongside current wages from the same employer` `[664,834)`
- `estg_000546`:
  - `pursuant to Section 41` `[133,155)`
- `estg_000569`:
  - `pursuant to Section 3` `[92,113)`
  - `referred to in Section 26` `[129,154)`
- `estg_000659`:
  - `from which no withholding of tax on wages, on capital yield, or under Sections 99 to 101 is to be made` `[88,190)`
- `estg_000716`:
  - `to the competent Regional Finance Directorate` `[139,184)`
  - `in the cases of paragraph (6)` `[189,218)`
  - `within the meaning of Section 18(1) item 3` `[288,330)`
  - `by or for the persons referred to in paragraph (2)` `[413,463)`
- `estg_000773`:
  - `exclusively, directly or indirectly, by corporations under public law` `[46,115)`
- `estg_000786`:
  - `that are unrelated to the purpose of the bank` `[24,69)`
  - `do not benefit any board member, managing director, or supervisory board member through disproportionately high remuneration` `[74,198)`
- `estg_000854`:
  - `in exceptional cases` `[202,222)`

### 7.7 模拟后仍存在的 actor 问题

- Actor 未匹配预测（FP）：**28 个**，分布于 24 个样本；与原 D 相同。
- Actor 漏检 Gold：**3 个**；与原 D 相同。

Actor FP 完整清单：

- `estg_000004`:
  - `the tax office` `[126,140)`
- `estg_000021`:
  - `employees in tobacco processing establishments` `[49,95)`
- `estg_000037`:
  - `business expenses` `[14,31)`
- `estg_000039`:
  - `The agreement` `[0,13)`
- `estg_000071`:
  - `registered traders` `[4,22)`
- `estg_000075`:
  - `the business assets transferred abroad` `[148,186)`
- `estg_000077`:
  - `The funds` `[227,236)`
- `estg_000092`:
  - `The register` `[0,12)`
- `estg_000094`:
  - `Acquisition or production costs incurred for the rehabilitation of business buildings` `[4,89)`
- `estg_000105`:
  - `the investment allowances` `[89,114)`
- `estg_000115`:
  - `the investment allowance` `[60,84)`
- `estg_000119`:
  - `This list` `[0,9)`
- `estg_000134`:
  - `Hidden reserves` `[4,19)`
- `estg_000135`:
  - `The reserve (the tax-free amount)` `[4,37)`
- `estg_000208`:
  - `Subsection (1)(3)` `[193,210)`
- `estg_000209`:
  - `Shares issued as a result of a capital increase` `[0,47)`
  - `capital reductions by a stock corporation or a limited liability company as the legal predecessor of the stock corporation` `[404,526)`
- `estg_000271`:
  - `The building` `[0,12)`
  - `the building` `[98,110)`
  - `the taxpayer themselves` `[279,302)`
- `estg_000285`:
  - `that rule` `[152,161)`
  - `The daily allowance for domestic business trips` `[292,339)`
- `estg_000293`:
  - `The following income` `[4,24)`
- `estg_000302`:
  - `The following income` `[4,24)`
- `estg_000414`:
  - `the taxpayer` `[176,188)`
- `estg_000505`:
  - `such other emoluments` `[73,94)`
- `estg_000659`:
  - `Persons with limited tax liability` `[4,38)`
- `estg_000720`:
  - `the building savings contract` `[45,74)`

Actor 漏检 Gold 完整清单：

- `estg_000037`:
  - `the fund must be subject to state supervision;\nbb) the fund` `[456,515)`
- `estg_000103`:
  - `the tax office` `[183,197)`
- `estg_000776`:
  - `the recipient` `[115,128)`

### 7.8 解释边界与未执行事项

> 这项计算只描述一种指定的假设性输出变化。它没有证明新句会让模型产生这种变化；真实运行也可能新增 condition FP、改变其他字段，或没有任何收益。

- `D_condition_retention_simulation` 不是 R_C v2 的预测或实验结果；本计算不构成候选修复数量、Prompt 增分、验证通过或自动进入实验的证据。
- 本轮真实 LLM/API 调用 = 0；只做内存计算和报告。
- 未覆盖原预测、未写入真实实验输出目录、未创建实验运行 manifest；未修改活动 Prompt、Gold、评价器或默认配置；未新增活动脚本或配置；未运行项目审计或代码测试。
- 是否值得进一步验证由用户根据结果决定；本节不设定验收阈值，也不提出后续调用数量。


---

## 8. 运行前接口问题定位（source_text 追加 E 示例）

### 8.1 固定结论

四条固定对象的异常首次均出现在 **原始模型响应层**：模型返回的 JSON 顶层 `source_text` 不是冻结目标正文，而是 `冻结目标正文 + "\n\n" + examples_E.md`。实际请求中的 `source_text` 位置只有冻结正文；E 示例是同一 user message 中位于 `source_text` 之后的独立段落。现有证据支持归类为「原始响应已经把示例复制进 source_text」，不支持后处理追加。解析结果和 canonical record 均逐字保留原始响应中的 `source_text`。

### 8.2 请求重建与边界

- 实际请求 body 没有单独落盘，只保存了 `request_body_sha256` 和 `rendered_prompt_user_sha256`。本轮用冻结输入 `approved_text_en` 加对应 arm 的冻结 generated prompt 重建请求；重建后的 user/body SHA-256 与每条 `raw_responses.jsonl` 保存值完全一致，因此下列请求层边界可按重建结果核对；未调用 API。
- E 模块来源：`formal_experiment/prompts/sun_compat/modular_v1/examples_E.md`，规范化后 2349 字符，SHA-256 `8f7ab57d337966eedf0f2955d5592c57d668623591d6d7720a1bd2169a6a61db`；追加到 user prompt 时由 `modular_prompt.py:170-174` 以 `"\n\n".join(...)` 放入，位于 `source_text` 之后。
- 相关代码位置：
  - 请求构造：`scripts/run_sep_c3_targeted_refinement_v1.py:110-132`、`:146-150`；落盘 request body hash：`:196`。
  - user prompt 渲染：`src/bpc_hybrid/modular_refinement_prompt.py:106-113`；E 模块组合：`src/bpc_hybrid/modular_prompt.py:170-174`。
  - 原始响应落盘：`scripts/run_sep_c3_targeted_refinement_v1.py:201-204`。
  - 解析链：`scripts/run_sep_c3_targeted_refinement_v1.py:389-413`；`scripts/run_barrientos_ablation_suite_v2.py:675-746`；adapter `src/bpc_hybrid/d1_schema_adapter.py:120-170`；span canonicalizer `src/bpc_hybrid/d1_span_canonicalizer.py:86-205`。

### 8.3 逐条证据链

#### A / estg_000044

- 冻结目标正文：`formal_experiment/data/input/estg150_formal_inference_input_v2.json:297`（`approved_text_en`；`sample_id` 在第 306 行）。161 字符，SHA-256 `5d4a0dd8ad47c776d56fc950364e56e34cbd3b33909080da231dd1746b7556ee`；不含 E。
- 实际请求：`formal_experiment/outputs/development/sep_c3_targeted_refinement_v1/A/repeat-01/raw_responses.jsonl:18` 保存 `request_body_sha256=ef0ae062a5ba77d36e1f741a83a229e690220b3189c30373f55e5cb0135cdbef`、`rendered_prompt_user_sha256=e7a2f42bfc4144d85ceeee1e19bfb5227acc69520d8eb09dffc74b750b0843d9`。重建 user prompt 中 `source_text` 范围为 `[88,249)`，只含冻结正文；E 标题从 `251` 开始。
- 原始模型响应：`A/repeat-01/raw_responses.jsonl:18` 的 `raw_response_content` 内 JSON `source_text`。长度 2512，SHA-256 `4edca77d64b078d5745cc2b163ba538cc6cb473776c7226f17e0e94fdd606795`，`response_sha256=da72951630fe9ceed1d2e2712bfa95102fec52461992da9f8434bc7dbdca8464`。与冻结正文不完全一致；包含 E；精确等于 `冻结正文 + "\n\n" + examples_E.md`。**异常首次出现层。**
- 解析结果：`formal_experiment/outputs/development/sep_c3_targeted_refinement_v1/A/repeat-01/canonical_predictions.jsonl:18` 的 `parsed_output.source_text`，长度 2512、SHA-256 `4edca77d...`，与原始响应相同；包含 E。
- canonical record：同文件 `record.source_text`，长度 2512、SHA-256 `4edca77d...`，与原始响应相同；包含 E。`parser_audit` 未记录 source_text 改写，`canonicalizer_audit` 也未记录 source_text 改写。

#### A / estg_000720

- 冻结目标正文：`formal_experiment/data/input/estg150_formal_inference_input_v2.json:2388`（`sample_id` 在第 2397 行）。215 字符，SHA-256 `cdfacc8ff49a5bab7850458bc88f6e4174e1a1bcbeaf085fe6b2e88bd9b6abb5`；不含 E。
- 实际请求：`formal_experiment/outputs/development/sep_c3_targeted_refinement_v1/A/repeat-01/raw_responses.jsonl:141` 保存 `request_body_sha256=ede4071fc5f989d072b734b05177229790d15d60f119f7e6a724557110a2adc1`、`rendered_prompt_user_sha256=3527f3b5baf3a95f4ec4e0841715262ba825dacc714429a5006df1d114f1a71e`。重建 user prompt 中 `source_text` 范围为 `[88,303)`，只含冻结正文；E 标题从 `305` 开始。
- 原始模型响应：`A/repeat-01/raw_responses.jsonl:141`。JSON `source_text` 长度 2566，SHA-256 `3284b4c528550b3e8771fe959dc96859e8c85f9ecc332b84d6a9c913997ce58f`，`response_sha256=a67aaf0fe87608c15315f3b78c3632b4522388b4f9dd27d5bea48a3630c59f84`。与冻结正文不完全一致；包含 E；精确等于 `冻结正文 + "\n\n" + examples_E.md`。**异常首次出现层。**
- 解析结果：`formal_experiment/outputs/development/sep_c3_targeted_refinement_v1/A/repeat-01/canonical_predictions.jsonl:141` 的 `parsed_output.source_text`，长度 2566、SHA-256 `3284b4c5...`，与原始响应相同；包含 E。
- canonical record：同文件 `record.source_text`，长度 2566、SHA-256 `3284b4c5...`，与原始响应相同；包含 E。解析与 canonicalizer 审计均未记录 `source_text` 改写。

#### C / estg_000035

- 冻结目标正文：`formal_experiment/data/input/estg150_formal_inference_input_v2.json:178`（`sample_id` 在第 187 行）。172 字符，SHA-256 `94906e35bea12352e3809e57ae95c16c8b18a832034e7d127685d679c4d8ef52`；不含 E。
- 实际请求：`formal_experiment/outputs/development/sep_c3_targeted_refinement_v1/C/repeat-01/raw_responses.jsonl:11` 保存 `request_body_sha256=1917bc4adacc07bff2df23c6b3d958e3d2f14d679596240ec2e300b3701f7611`、`rendered_prompt_user_sha256=bcb745fc95a147d430839aa08e6248a1c9937856e50a03c65a92fdb815b1c346`。重建 user prompt 中 `source_text` 范围为 `[88,260)`，只含冻结正文；E 标题从 `262` 开始。
- 原始模型响应：`C/repeat-01/raw_responses.jsonl:11`。JSON `source_text` 长度 2523，SHA-256 `e07d40fe58a5ee3bdf7fbec2a5fb3efb9033ffeec1aa0d71f5a2ade427f6a4f6`，`response_sha256=ce8358e9927aba2845caf19f7e2bfef8ffa2d3afe220708c63d8fa92b876a1d0`。与冻结正文不完全一致；包含 E；精确等于 `冻结正文 + "\n\n" + examples_E.md`。**异常首次出现层。**
- 解析结果：`formal_experiment/outputs/development/sep_c3_targeted_refinement_v1/C/repeat-01/canonical_predictions.jsonl:11` 的 `parsed_output.source_text`，长度 2523、SHA-256 `e07d40fe...`，与原始响应相同；包含 E。
- canonical record：同文件 `record.source_text`，长度 2523、SHA-256 `e07d40fe...`，与原始响应相同；包含 E。解析与 canonicalizer 审计均未记录 `source_text` 改写。

#### C / estg_000044

- 冻结目标正文：`formal_experiment/data/input/estg150_formal_inference_input_v2.json:297`（`sample_id` 在第 306 行）。161 字符，SHA-256 `5d4a0dd8ad47c776d56fc950364e56e34cbd3b33909080da231dd1746b7556ee`；不含 E。
- 实际请求：`formal_experiment/outputs/development/sep_c3_targeted_refinement_v1/C/repeat-01/raw_responses.jsonl:18` 保存 `request_body_sha256=c09f37cec957859e444213f49c641ceaedee1f4ae26ef45925786323d001aa8a`、`rendered_prompt_user_sha256=e7a2f42bfc4144d85ceeee1e19bfb5227acc69520d8eb09dffc74b750b0843d9`。重建 user prompt 中 `source_text` 范围为 `[88,249)`，只含冻结正文；E 标题从 `251` 开始。
- 原始模型响应：`C/repeat-01/raw_responses.jsonl:18`。JSON `source_text` 长度 2512，SHA-256 `4edca77d64b078d5745cc2b163ba538cc6cb473776c7226f17e0e94fdd606795`，`response_sha256=2f95d2505f2d8a2172c6b03c5f944b1004e35a8b556ab076d7c5143da5b95e44`。与冻结正文不完全一致；包含 E；精确等于 `冻结正文 + "\n\n" + examples_E.md`。**异常首次出现层。**
- 解析结果：`formal_experiment/outputs/development/sep_c3_targeted_refinement_v1/C/repeat-01/canonical_predictions.jsonl:18` 的 `parsed_output.source_text`，长度 2512、SHA-256 `4edca77d...`，与原始响应相同；包含 E。
- canonical record：同文件 `record.source_text`，长度 2512、SHA-256 `4edca77d...`，与原始响应相同；包含 E。解析与 canonicalizer 审计均未记录 `source_text` 改写。

### 8.4 validation=true 的来源与覆盖范围

- 四条原始模型响应中的顶层 `validation` 均为：`{"schema_valid": true, "cross_field_valid": true, "errors": []}`。canonical record 保存的同一对象来自模型，不是运行时校验生成。
- 实际执行路径没有执行逐 record 的 schema/cross-field 校验，也没有用 runtime validation 覆盖模型 validation 的调用：`scripts/run_sep_c3_targeted_refinement_v1.py:389-413` 只调用 `base.parse_same_response` 并保存 `parsed_output`/`canonical_output`；`scripts/run_barrientos_ablation_suite_v2.py:675-746` 只做 `adapt_relay_record` 和 `canonicalize_record_coordinates`；两者均深拷贝原始 payload，未修改顶层 `validation`。
- 现有 adapter/canonicalizer 只检查 span 文本是否出现在传入的 `source_text` 中（`d1_schema_adapter.py:106`）或重锚定 span 坐标（`d1_span_canonicalizer.py:66-84`），不校验顶层 `record.source_text` 是否等于输入正文。运行入口附近的 `validate_contracts`（`run_sep_c3_targeted_refinement_v1.py:537-594`）只检查预算、schedule、prompt 绑定、input/Gold 文件哈希等运行契约，不检查每条输出记录。
- Prompt 中「runtime validator overwrites validation and is authoritative」的说明位于 `formal_experiment/prompts/sun_compat/modular_v1/common_system.md:16`；在本次 A/C 实际执行路径中没有对应实现。因此现有校验无法拦住该异常，`validation=true` 不能视为运行时校验通过。

### 8.5 缺失证据与边界

- 实际 HTTP request body 原文没有单独落盘，只有 `request_body_sha256` 和 `rendered_prompt_user_sha256`；本轮通过冻结输入与冻结 prompt 重建后哈希完全匹配，但没有独立原始 body 文件。
- 没有保存任何 per-record 运行时校验结果或校验器调用日志；因此只能确认该路径未执行逐记录校验，不能把模型字段当作校验证据。
- 原始响应之前的 transport 解码中间产物未单独保存；但异常已经在最早的已保存模型输出层出现，且请求中的 `source_text` 字段边界可由冻结输入和 prompt 确定，后处理追加的假设与原始响应证据冲突。
- 四条对象为什么促使模型把 E 段落并入 `source_text`，不属于本轮证据可判定的问题；本轮不提出措辞、代码或实验修复。
- 新增 API=0；未修改活动 Prompt、代码、Gold、评价器或历史预测；未运行项目审计或代码测试。
