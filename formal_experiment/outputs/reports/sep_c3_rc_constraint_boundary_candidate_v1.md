停止推进：该候选包含尚未得到充分解释的 predicate/threshold、distinct head 和短限定语分类规则，不进入活动 Prompt 或实验。

# SEP-C3 R_C 边界候选设计报告

- 状态：未验证、未冻结
- 新增 API：0

- 日期：2026-09-19
- 分支：`codex/b0-r1-a-span-boundaries`；读取基线：`ced677a9ff6672a5303b8dd2a268e20ba6f732d9`
- 候选状态：**offline_candidate / 未验证 / 未冻结**
- 新增真实 LLM/API：**0**
- 活动 Prompt / Gold / 评价器 / 历史预测 / 默认配置：**未修改**
- 本轮结论：**A. 存在值得进一步审查的离线候选；它不是已验证修复，也不可直接冻结。**
本报告只做离线设计与既有证据核验，不运行项目审计、代码测试或 API。结论 A 的依据是：本轮能够用「先判适用条件，再取已适用 action 的局部参数，两数组允许 overlap」组织 8 条 condition-only 迁移、4 条范围合并和 3 条合法嵌套；但仍保留样本级语义不确定性，必须明确标为未验证。

## 0. 执行摘要

旧 R_C 把 `when / how / how much / purpose / legal reference / exclusivity` 直接列为 constraint 抽取触发条件，没有先区分「条件命题」和「已适用行为的局部限制」。这导致模型把整个适用条件搬进 constraints，并在合法嵌套、范围合并和短限定语上产生冲突行为。
候选只替换 `R_C_constraint_recall.md`，不追加 T/G/TG 模块，不改 R_A，不改默认 v6。核心是三点：

1. 先保留适用条件：决定规范是否适用的完整条件命题留在 `conditions`，不得因其中出现数量、时间、法律引用、目的或排他表达而整段迁移。
2. 允许双向重叠：condition 内可含局部 constraint；constraint 内也可含完整 applicability condition；两数组可保留同段文字。
3. 禁止拆条件谓词和跨字段合并：不要把 condition 自身的 predicate/threshold 拆成 constraint，也不要把 condition 与其后的 constraint 合并成一个 span。

候选仅写入本报告，状态为未验证、未冻结，不进入活动 Prompt。

## 1. 继承事实与证据范围

- B = common + E + R_A 仍为研究参照；R_A 不改；正式默认仍为 v6。
- 19 条 condition 覆盖丢失：8 条/5 样本为 condition-only 整段迁移；3 条 Gold 已有嵌套覆盖；4 条 condition/constraint 范围合并；4 条没有新增重叠 constraint。两方向重复样本不重复计独立证据。
- 52 条 coarse recovery：49 条命中真实细粒度 Gold constraint；37 条至少精确恢复一个细粒度 constraint；3 条仅命中合并空隙（`estg_000247` 双向、`estg_000293` A→C）。
- temporal-only 无充分依据；字段绝对互斥、扩大到整个 coarse 区间、笼统禁止短词均不合格。
- E5 已说明 condition 内可嵌套 constraint；旧 R_C 已要求完整短语、不要孤立 `only`。重复旧要求不是新增有效干预。
- 六个 B→D actor regression 内部机制未知；不得声称 condition 边界修补必然解决 actor 副作用。

核心来源：`sep_c3_rc_boundary_attribution_v1.json`、`sep_c3_constraint_refinement_v2_semantic_review.json`、`data/gold/stage2/estg150_formal_gold_v1.json`、A/B/C/D canonical predictions、`common_system.md`、`examples_E.md`、`semantic_rules_S.md`、`R_C_constraint_recall.md`。关键 hash：semantic review `bd938671...753964`，Gold `c31a514a...db57100`，旧 R_C `CFCBBC45...571FCAE`。本轮只回查这些证据，不重做全量 taxonomy。
## 2. 语义边界：适用条件 vs 局部限制

### 2.1 判定问题

「决定规范是否适用的条件命题」和「对行为的局部限制」可以用一个操作性提问区分：

> 如果删掉这个短语，规范是否还保留一个仍可适用于某些对象的完整行为规则，只是该行为缺少一个参数？若是，它更像 constraint；若删除后规范不再有足够的适用条件或适用范围，它更像 condition。

该提问不是形式 evaluator，也不是新 Gold；它只用于解释冻结 Gold 和既有失败案例。关键是：不能按时间、数量、目的、法律引用等语义主题分类，因为同一主题在 Gold 中既可归 condition，也可归 constraint。

### 2.2 判定步骤

1. 先确定 clause 的 action、modality 和规范何时/对谁适用。
2. 若短语提供使规范适用到案件上的 state / event / qualification，且删除后规范失去适用命题，则归 `conditions`，保留完整 governed proposition。
3. 若 action 已可适用，短语只给出方式、金额、时间、地点、法律依据、目的、排他性、范围或类似参数，则归 `constraints`，保留完整限制短语。
4. 若 condition 内有独立修饰 distinct head 的完整局部参数，则同一文字同时进入两数组；若 constraint 内含完整 applicability condition，也同时进入两数组。两数组允许 overlap。
5. 不要把 condition 自身的 predicate / threshold 拆成 constraint；不要把 condition 与其后的 constraint 合并成一个跨字段 span。
### 2.3 关键案例

#### 2.3.1 `estg_000052` vs `estg_000104`：同样有数量，字段归属为何不同

冻结 Gold：

- `estg_000052` condition：`insofar as they, together with contributions within the meaning of item 6, do not exceed a total of 10% of the profit of the immediately preceding business year` `[38,198)`；constraint 为空。
- `estg_000104` condition：`Upon the acquisition or production of depreciable fixed assets` `[4,66)`；constraint：`up to 20% of the acquisition or production costs` `[118,166)` 和 `as a profit-reducing deduction` `[167,197)`。

解释：

- `000052` 的 `10%` 是 `insofar as ... do not exceed ...` 整个条件命题的 predicate/threshold。它决定 contributions 在什么程度上可扣除；删去数量后，剩下的文本不是完整可适用的扣除规则。因此整段视为 condition，数量、法律引用和时间线索都只是条件内部成分。
- `000104` 的 `Upon the acquisition...` 是触发 allowance 适用的 condition；`up to 20%...` 则是在 action `claim an investment allowance` 已可适用后，限制 claim 的金额参数，属于 constraint。`as a profit-reducing deduction` 进一步限定行为性质，也属于 constraint。
- 区别不是「数量一定归 condition」或「数量一定归 constraint」，而是该数量是适用命题的 truth condition，还是已适用行为的局部参数。
冻结 Gold 事实：`000052` 数量明确属 condition；`000104` 数量明确属 constraints。对 `000104` 的语义解释较稳定；对 `000052` 的「条件 predicate 不拆分」解释具有一定判断性，是本轮候选的显式约束，也是需要未来模型行为验证的点。

#### 2.3.2 `estg_000028`、`estg_000106`：怎样保留合法嵌套

`estg_000028`：Gold condition `when taking into account the converted income` `[55,100)`；Gold constraint `at the tax rate that results when taking into account the converted income` `[26,100)` 包含该 condition。A/B 没有 constraint；C/D 有 constraint 但丢掉 condition。正确行为是两数组都保留。这提供了 E5 未覆盖的反方向：constraint phrase 内可含完整 applicability condition。候选新增：constraint 内含完整 condition 时也记 condition。

`estg_000106`：Gold conditions 为 `[77,141)` 和 `[149,274)`；Gold constraints 为 `[49,68)`、`[122,141)`、`[227,274)`，其中后两者分别嵌套在两个 condition 内。C/D 把整段 `[49,275)` 搬进 constraint，丢掉 conditions，并额外产生 `only` `[33,37)`。正确行为是保留两个 conditions，同时保留其内部局部 constraints，不把 condition 与后续局部限制合并。
#### 2.3.3 `000039`、`000108`、`000161`、`000210`：整段迁移应如何避免

- `estg_000039`：D 把第二 condition `to the extent that they are required under the articles of association for benefit entitlements ...` `[234,389)` 整段移入 constraint，同时保留第一 clause 的两个真实 constraints。候选要求完整 applicability qualification 留在 condition；第一 clause 的 `for compelling economic reasons` 和 `only after consultation with the works council` 仍为 constraints。
- `estg_000108`：D 把 `to the extent that they directly serve the business purpose or are intended for residential purposes ...` `[64,193)` 整段移入 constraint；Gold condition 正是该段，Gold constraint 仅有独立 `For buildings` `[4,17)`。候选要求 condition 留在 conditions，不因其中出现 purpose 而迁移。
- `estg_000161`：D 把 `only under the following conditions` `[33,68)` 移入 constraint；Gold 中它是 condition。`in accordance with their statutes and actual management`、`exclusively or predominantly`、`in a reasonable amount as fixed in the statutes` 是真实 constraints。候选要求保留 condition 引导语，并保留列表项内的独立局部限制。
- `estg_000210`：D 将多个 relative clauses 移入 constraints，丢掉 Gold conditions；Gold 同时有真实 constraint `having their registered seat and place of management in the country` `[180,247)`。候选要求 substantive applicability/relative qualifications 留 conditions，reduced participial/action parameter `having ...` 留 constraint。此案最难：relative clause 与 participial modifier 的区分仍可能受句法和上下文影响，模型稳定性必须实验验证。
#### 2.3.4 `estg_000776`：怎样兼容 Gold 已标注的 `in particular`

Gold condition：`where services are involved the acceptance of which the recipient is obliged to accept by virtue of a statutory or official order` `[63,192)`。Gold constraints：`in particular` `[49,62)` 和嵌套在 condition 内的 `by virtue of a statutory or official order` `[150,192)`。

解释：`in particular` 是短限定语，但 Gold 将其标为 constraint，因此候选不能写成短词/功能词一律删除，也不能只保留旧 R_C 的 `only` 禁令而不给短限定语留出口。`by virtue of ...` 是 condition 内修饰 `obliged to accept` 的 legal-basis parameter，应作为 nested constraint 保留。候选保留「完整短语而非孤立 cue」原则，同时说明短短语在它是完整 scope/exemplification qualifier 时仍可成立，避免直接要求删除 `in particular`。

#### 2.3.5 真实 recovery 的反向控制

- `estg_000103`：命中 `two weeks` `[239,248)`，是 action `set ... a grace period` 的时间参数，候选应保留。
- `estg_000222`：命中 `Section 1, no. 3, lit. d` `[127,151)`，是法律引用参数，候选应保留。
- `estg_000104`：`up to 20%...` 是数量参数，候选应保留。
- 因此候选不能写「time / legal / quantity 都不得进 constraint」，只禁止整段适用条件迁移。
- `estg_000569` 的 Gold constraint `upon application` `[29,45)` 和 `estg_000816` 的 `when determining income for the calendar year in which the business year ends` `[257,334)` 说明 `upon/when` 不自动是 condition；它们分别可解释为 procedural circumstance 或 method/time parameter。候选没有写「遇 upon/when 即判 condition」，但这一边界存在真实不确定性，需要人工判断，不能靠关键词列表。
### 2.4 冻结 Gold、语义解释与不确定性

必须区分：

- 冻结 Gold 实际标注：`000052` quantity 属 condition；`000104` quantity 属 constraints；`000028` constraint 包含 condition；`000106` condition 内嵌 constraints；`000039`/`000108`/`000161`/`000210` 的 extent/relative 条件属 conditions；`000776` 的 `in particular` 属 constraint。
- 本报告的语义解释：上述案例支持先判适用范围、再在已适用行为上取局部限制，并支持两数组 overlap。但 `upon application`、`when determining income`、`000210` 的 relative vs participial modifier、以及 `000052` 中条件 predicate 是否拆分仍有解释不确定性。

本报告不修改 Gold，不把 AI 意见写成人工裁决。候选尽量让不确定性以可审查规则出现，而不是以 sample_id 特判处理。
## 3. 旧 R_C 完整原文

文件：`formal_experiment/prompts/sun_compat/modular_refinement_v1/R_C_constraint_recall.md`

```text
Constraint: extract an explicit phrase when it directly restricts when, how, how much, for what purpose, under what legal reference, or with what exclusivity the regulated action applies. Extract the complete restrictive phrase rather than an isolated cue word such as ‘only’.
```

## 4. 候选完整原文（未验证、未冻结）

```text
Constraint boundary: extract a constraint only for a complete phrase that specifies a manner, amount, time, place, legal basis, purpose, exclusivity, scope, or comparable parameter of an action that is already applicable. Keep in conditions every phrase that supplies the state, event, or qualification that determines whether the norm applies, including its complete governed proposition; do not move that condition into constraints merely because it contains a quantity, time, legal citation, purpose, or exclusivity expression. If a condition contains a separate complete phrase that modifies a distinct head, record that phrase in constraints as well, but do not split the condition's own predicate or threshold into a constraint. If a constraint phrase contains a complete applicability condition, record that condition in conditions as well. Condition and constraint spans may overlap. Extract complete phrases rather than isolated cue words such as 'only'; a short phrase may still be complete when it is itself the full scope or exemplification qualifier.
```
## 5. 具体改动与对应 failure

| 改动 | 旧 R_C / 现有问题 | 对应真实 failure |
|---|---|---|
| 前置 `only for ... an action that is already applicable` | 旧 R_C 写 `when ... the regulated action applies`，把适用条件与已适用行为混在一起 | `000039`、`000052`、`000108`、`000161`、`000210` 的 condition-only 整段迁移 |
| 新增 `do not move that condition into constraints merely because ...` | 旧 R_C 直接列 quantity/time/legal/purpose/exclusivity，未给 condition 优先规则 | 同上；`000052` 中 quantity/legal/time 同时出现却被整段移入 constraint |
| 新增 condition 内独立 local phrase 可继续记为 constraint | E5 有单向嵌套，但旧 R_C 未要求在 condition 内保留局部限制 | `000106`、`000776` 的 nested constraints |
| 新增 `do not split the condition's own predicate or threshold` | 旧 R_C 未说明嵌套 constraint 的边界，baseline 会拆分条件谓词 | `000052` 的 quantity 片段 FP 风险 |
| 新增 constraint 内含 condition 时也记 condition | E5 未覆盖反方向 | `000028`：C/D 保留 constraint 但丢 condition |
| 新增两数组可 overlap | 旧 R_C 无 overlap 语句；S8 只覆盖单向 | `000028`、`000106`、`000776` |
| 保留完整短语要求，并允许完整短限定语 | 旧 R_C 的 `only` 禁令不能解释 Gold 的 `in particular` | `000776`；`000106`/`000108`/`000161` 的 isolated `only` FP 仍需模型行为验证 |

## 6. 相比 E5、S5/S6、旧 R_C 新增或澄清了什么

- 相比 E5：新增反方向 constraint 内含 condition、双向 overlap、condition 优先和 condition 内局部参数的边界。
- 相比 S5/S6：替换旧 R_C 中与 S5/S6 冲突的触发句，并明确 condition 优先、不拆 predicate、不跨字段合并、完整短限定语可成立。
- 相比旧 R_C：删除 `when ... action applies` 歧义；新增 condition 不迁移；新增双向嵌套；新增不拆 predicate；保留完整短语要求并容许可审查的短 scope/exemplification 限定语。
- 仍不构成已验证效果：模型是否遵守、是否增加 constraint FP 或 actor 副作用，离线无法回答。
## 7. 正反例审查表

说明：「是否兼容 Gold」指候选指令语义是否与冻结 Gold 相容；模型实际是否遵守本轮没有新运行，不能写成已修复。尚存疑点保留真实语义或行为不确定性。

| sample_id | 原始问题 / 正例 | 候选要求的行为 | 是否兼容 Gold | 尚存疑点 |
|---|---|---|---|---|
| `estg_000052` | condition-only 整段迁移；Gold 只有 condition | 保留完整 `insofar as...` condition；不拆 predicate/threshold | 是 | 模型可能把内部 quantity 片段抽成 nested constraint，产生 FP |
| `estg_000104` | 正例：quantity 是真实 constraint；R_C 有 recovery | 金额参数属已适用 action，保留 constraint | 是 | C/D 预测从 `[115,166)` 开始，未精确覆盖 Gold `[118,166)`；候选不修 span 边界 |
| `estg_000028` | 反方向嵌套：constraint 内含 condition；C/D 丢 condition | constraint 与 condition 同时保留，允许 overlap | 是 | 模型可能把整个 NP 误判为 condition 并丢掉 constraint |
| `estg_000106` | 范围合并；condition 内有 nested constraints；C/D 整段迁移并添加 `only` | 保留两个 conditions 与 nested constraints；不跨字段合并；不拆 predicate | 要求层面是 | isolated `only` FP 可能仍存在；distinct head 判断不确定 |
| `estg_000060` | condition+constraint 范围合并；Gold 要求 condition `[134,250)` 和 constraint `[251,335)` 分开 | 不跨字段合并；condition 与后续 constraint 分开保留 | 是 | 模型仍可能把两者视为一个整体 span |
| `estg_000039` | 第二 condition 整段迁移；第一 clause 有真实 constraints | condition 留 conditions；第一 clause 局部限制留 constraints | 是 | 模型仍可能把 purpose/legal qualification 看成局部限制 |
| `estg_000108` | `to the extent...` 整段迁移；Gold 仅有该 condition 与独立 constraint | 保留 condition；`For buildings` 等独立 constraint 保留 | 是 | isolated `only` FP 可能仍存在 |
| `estg_000161` | `only under the following conditions` 被 D 移入 constraint；列表内有真实 constraints | 条件引导语留 conditions；列表内独立限制保留 | 是 | `only` 单独成为 constraint 的行为仍可能发生 |
| `estg_000210` | 多个 relative conditions 被 D 移入 constraints；同时有真实 `having...` constraint | relative/applicability qualifications 留 conditions；participial/action parameter 留 constraint | 要求层面是，Gold 边界风险最高 | relative clause vs participial modifier 仍需人工/运行验证 |
| `estg_000776` | Gold `in particular` 是 constraint；condition 内还有 nested legal constraint；B 全丢、C/D 仅保留 `in particular` | 不笼统禁止短限定语；condition 内 legal parameter 也作为 nested constraint 保留 | 是 | 模型是否保留 `in particular` 不确定；候选只避免要求删除它 |
| `estg_000103`、`estg_000104`、`estg_000222` | 真实 time / quantity / legal-reference recovery | 已适用 action 的参数保留为 constraint | 是 | 不能把 time/quantity/legal 一律判 condition；候选没这样写 |
| `estg_000569`、`estg_000816` | 真实 `upon application`、`when determining income...` 是 Gold constraint | procedural circumstance / method-time parameter 留 constraint，不因 upon/when 自动判 condition | 语义上兼容，但边界不确定 | procedural precondition vs applicability condition 仍需人工判断 |
| `estg_000247`、`estg_000293` | coarse 合并空隙造成的表面 recovery | 候选不改变 evaluator，不把 coarse hull 当目标 | 不适用 | 这是冻结 evaluator 口径问题，Prompt 候选不能修 |
| isolated `only`：`000106`、`000108`、`000161` | constraint FP | 保留完整短语而非孤立 cue 的要求 | 要求兼容，但不等于已修复 | 旧 R_C 已有相近要求；新增短限定语例外后行为未验证 |
| actor regression：`000004`、`000021`、`000105`、`000209`、`000302`、`000505` | B→D empty-Gold actor 新增，机制未知 | 候选不涉及 actor 字段 | 不针对 | 不能声称 condition 边界候选会解决 actor 副作用 |
| `estg_000121`、`estg_000231`、`estg_000509`、`estg_000124` | condition 丢失但没有新增重叠 constraint | 候选不是专门修复 condition omission 的模块 | 未覆盖 | 需单独审查机制，不应硬塞进本候选 |
## 8. 覆盖、不可覆盖与边界

### 8.1 候选设计上覆盖的目标

- condition-only 整段迁移：`000039`、`000052`、`000108`、`000161`、`000210`。
- condition/constraint 范围合并：`000060`、`000106`。
- 合法嵌套双向保留：`000028`、`000106`、`000776`。
- 真实时间、数量、法律引用 recovery：`000103`、`000104`、`000222` 等不能被删除。
- 短限定语兼容：`000776` 的 `in particular`。
- 不拆 condition predicate：`000052`。

### 8.2 明确不能覆盖 / 不能声称的问题

- `estg_000121`、`estg_000231`、`estg_000509`、`estg_000124` 没有新增重叠 constraint；本轮没有证明由 R_C 字段边界造成，候选不承诺修复。
- `estg_000037` 等长 Gold 的局部 recovery / 多标签混合，候选只能提供 boundary rule，不能保证完整恢复。
- coarse 合并空隙造成的表面 recovery（`000247`、`000293`）是评价器口径问题，不是 Prompt wording 能修的。
- isolated `only`、其他短词 FP、span 起止边界、actor regression、运行方差均无本轮验证。
- 候选不修改活动 Prompt，不修改 Gold、评价器、历史预测或默认配置。
- `source_text` 追加 E 示例的四条异常（A/000044、A/000720、C/000035、C/000044）仍保留为未来调用前必须处理的问题；本轮不扩展成工程重构。
## 9. 结论 A：保留候选供审查，不启动 API

**决策：A. 存在值得进一步审查的离线候选。**

依据：19 条 condition 丢失中的 8 条 condition-only 迁移、4 条范围合并和 3 条合法嵌套，能够用一个通用解释组织起来；`000052` vs `000104` 说明数量/时间/法律线索不能单独决定字段；`000028`/`000106` 说明双向 overlap 必要；`000776` 说明不能笼统禁止短限定语。候选完整替换旧 R_C，不改变 R_A、B 研究参照或 v6 默认。

**候选状态**：未验证、未冻结；不得写入活动 Prompt、生成文件或默认配置。

**未来实验要回答、但离线无法回答的问题**：模型实际是否会遵守该边界——减少 condition-only 整段迁移和范围合并，同时不删除 `000103`/`000104`/`000222`/`000569`/`000816` 等真实 constraint，不增加 isolated `only` / 短限定语 FP，并且不恶化 actor regression？

**保留/删除判据（未来实验前冻结，不在本轮安排调用数量或预算）**：

- 若候选仍把 `000039`/`000052`/`000108`/`000161`/`000210` 的 condition 整段搬入 constraint，或删除嵌套 constraint，则判候选失败，回到 B。
- 若候选保持/改善 condition 覆盖但新增 constraint FP、actor 副作用或删除真实 recovery，则判净收益不足，回到 B。
- 只有在一个明确预注册、同口径且离线/小运行可回答的范围内，候选同时满足 condition 迁移减少、真实 constraint 保留、FP 与 actor 未恶化，才进入下一轮人工审查或更大验证。

本轮不安排调用数量，不启动 API，不恢复 750-call 方案，也不自动改成 300/450 calls。

## 10. 来源、核验与限制

- Gold 使用 `estg150_formal_gold_v1.json`；预测使用 `outputs/development/sep_c3_targeted_refinement_v1` 的 A/B/C/D canonical 文件；prompt 使用 `common_system.md`、`examples_E.md`、`semantic_rules_S.md`、`R_C_constraint_recall.md`。
- 本轮只做内容与来源核验；没有运行项目审计、代码测试或 API。
- 表中「候选要求的行为」是指令语义，不是模型实际行为；没有新运行，因此不写修复多少条、提高多少分、通过模型验证。
- 人工裁决尚未完成；候选状态明确为 AI 离线候选。