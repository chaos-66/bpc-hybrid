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
