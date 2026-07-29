# Stage 2 统一六要素提取合同 v1

<!--
contract_id: stage2_extraction_contract@1.0.0
contract_sha256: 7f17ecba78cfa1acf1bbc488942f1c85c37d08ece7662c622bab4226bd2dbd46
status: frozen_for_sentence_only_pilot
-->

**合同 ID**：`stage2_extraction_contract@1.0.0`  
**状态**：`frozen_for_sentence_only_pilot`  
**机器合同**：`configs/stage2_extraction_contract_v1.json`  
**机器合同 SHA-256**：`7f17ecba78cfa1acf1bbc488942f1c85c37d08ece7662c622bab4226bd2dbd46`  
**Canonical Schema**：`stage2_prediction.schema.json@1.0.0`  
**适用对象**：人工 Gold、B0 / `sun_rule_only`、H1 / `sun_llm_fallback`、
D1 / `direct_llm`

本合同冻结的是四种生产方式必须共同回答的**同一个语义任务**。它不宣布
EStG-150 Gold 已冻结，不授权真实 LLM/API，也不关闭 RWI-0001（上下文 sidecar）或
RWI-0007（德文—英文 QA）。当前冻结轨道是 `target_text_only`：从同一条批准英文
目标文本抽取 exact spans；缺少的上下文不得由任何一方用常识补全。

## 1. 证据、借鉴与项目决定

| 层级 | 已确定内容 | 边界 |
|---|---|---|
| Sun 公开方法证据 | 四类 modality；modality/actor/action/condition/constraint/exception 六目标；源文本短语抽取；action 在其它标记范围识别后抽取 | Sun 的不可得源码、完整 marker、原始 150 phrase Gold 仍不能声称已复现 |
| Barrientos 公开 artifact | 仅 JSON 输出、固定结构、受控枚举、禁止自造标签、Schema 验证、版本间标签一致、语义覆盖/结构编码/deontic correctness 与 style-equivalent 评价思想 | RC4PC 是 3 类 modality、precondition/norms/temporal-validity；不能替代 Sun 六要素，也不能决定 `It` 是否是 actor |
| 本项目操作性决定 | 最小充分跨度、代词 mention、被动隐含 actor、指代状态、condition/constraint/exception 测试、并列和多子句、missing/uncertain、Stage 3 准入 | 这些决定用于可操作、公平和可复现；不伪称 Sun 原文逐字规定 |
| 尚需用户在正式 Gold 前决定 | sentence-only 是否为主轨道；context sidecar 的来源/hash/可见范围；德英 QA 或原生英文主轨道 | 不阻止本合同的 sentence-only pilot，但阻止正式 Gold/正式结果冻结 |

Barrientos 的 `compliance_pattern` 44 标签、三类 modality 默认规则、temporal validity
和 change-impact schema 均**未**并入本合同。它们属于可能的 Stage 3/消融扩展，不是
六要素 Gold 字段。

## 2. 修改前差异表

| 主题 | 人工协议（修改前） | D1 Prompt v4（修改前） | H1 Prompt v4（修改前） | 冲突/缺口 | v1 决定 |
|---|---|---|---|---|---|
| 输入范围 | 遇到缺上下文记录 `needs_adjudication`，但未定义仍可抽哪些 mention | 明确单句；无 context 字段 | 单句 + B0 clause | 人工与模型对缺上下文的可答部分不清楚 | 当前全部按目标文本；可见代词照抽，未决语义另记状态 |
| `It` | 没有统一 actor 规则 | 只说不 invent | 只说不能确定则 absent | 可能出现人工抽 `It`、模型删 `It` | `It` 是显式 actor mention；exact=`It`、normalized=`it`、状态 unresolved/context-required |
| 被动隐含 actor | “没有显式 span 不补造” | 可用 `actor_id:null`，未明说何时 | absent marker | 可能把法律常识 actor 填入 | actors=[]；每个 action 映射 actor_id=null；不推断 |
| missing vs uncertain | 空数组和待裁决并存，语义未统一 | empty array + optional unsupported | `absent:true`，且禁止改 unsupported | 三种表示无法对齐 | missing→空数组；uncertain→保留可辩护 span + controlled unsupported entry |
| normalized | 未说明能否把代词改先行词 | 仅说 normalized 与 raw 分离 | 同 Schema | 可能把 `It` 偷换成 business year | 先行词不在正式输入时禁止替换；normalized 保留表面词 |
| condition/constraint/exception | 只有简短定义 | 只有字段名 | 只有字段名 | marker 重叠时可任意分类 | 用 applicability / performance limit / carve-out 三个 scope test |
| 多子句 | 不为模型输出改 clause 数 | 支持多子句，但 few-shot 无真正多子句 | 不得改 clause 边界 | 分句判据未冻结 | 独立 normative force/actor/modality/consequence 才分 clause |
| Hybrid 歧义状态 | Gold 可留待裁决 | D1 可写 unsupported | H1 明令不得写 unsupported | `It` 状态无法进入 H1 final record | H1 envelope 返回完整 `unsupported_or_ambiguous` replacement，merge 后统一验证 |
| 版本绑定 | 未绑定合同 hash | 仅 prompt/schema hash | 仅 prompt/schema hash | Prompt 改后 Gold 规则可继续漂移 | 合同 hash 写入两 Prompt；bundle 锁定合同/Schema/协议/Prompt/pilot |

## 3. 输入合同

1. 一个输入单位是一个稳定 `sample_id` 对应的批准英文 `source_text`。
2. `source_text` 是 exact-span 的唯一坐标系：0-based `start`、exclusive `end`，且
   `text == source_text[start:end]`。
3. 当前 `context_mode=target_text_only`。人工、D1 和 H1 不得使用未进入正式输入的
   上一句、法条全文、法律评论或网页来补 actor/condition/constraint/exception。
4. B0 为复现方法可用锁定德文作 modality 分类，并用对齐批准英文作 phrase 抽取；
   这是显式方法差异。六个 phrase 字段的 Gold 和 span 坐标仍统一落在英文目标文本。
5. 将来若加入 context，必须先锁定 sidecar 来源和 payload hash，并给所有比较方法
   相同可见 context。context 不能贡献目标 span；它只能支持受控的指代消解/状态更新。
6. 中文 gloss、回译和德文源是审核辅助，不得偷偷成为模型不可见的新法律事实来源。

## 4. 六要素的操作性定义

| 字段 | 操作性定义 | 最小跨度原则 |
|---|---|---|
| `modality` | 每个 clause 一个 `obligation/prohibition/permission/definition` 标签，并保存触发表面证据 | 取足以决定类别的最小 trigger；否定改变类别时包含否定证据 |
| `actor` | 执行或承担规范的最小显式名词短语或代词 mention | 保留身份必要修饰；并列 actor 分开；不添加隐含 actor |
| `action` | 足以区分受规制行为的最小动词中心短语 | 排除 modality/condition/constraint/exception；保留必要宾语、补语、particle |
| `condition` | 使规则开始适用或决定是否适用的前置状态/事件 | 包含 marker 与完整受辖命题；删除后会改变规则是否/何时适用 |
| `constraint` | 规则已适用后，对如何、多少、何地、何时完成行为的限制 | 包含限制 marker 与最小完整限制 |
| `exception` | 从本来适用的规则中排除或缩小某类情形的 carve-out | 包含 exception marker 与完整受辖命题 |

`definition` clause 可以没有 action。非 definition clause 若目标文本确实没有明确
action，应使用空数组并通过状态/验证说明，而不是制造动词。

## 5. Exact span 与 normalized value

- exact span 是评价证据；大小写、冠词和原文代词均原样保存。
- `normalized` 仅供下游匹配，可做大小写/空白折叠、无新增论元的 lemmatization、
  删除非识别性冠词。
- `normalized` 不能改变 raw `text`，不能增加输入中不存在的 actor/object/条件。
- 当前输入只有 `It` 时，actor 为 `text="It"`、`normalized="it"`；不得写成
  `business year`。只有 antecedent 已进入正式、同等可见的输入，normalized 才可
  消解，而 exact span 仍是 `It`。

## 6. 代词、被动与隐含主体

### 6.1 `it / they / this / these / such`

| 用法 | 正例 | 反例 | 输出规则 |
|---|---|---|---|
| 代词是显式主语 | `It may cover ...`; `They must file ...`; `This shall be assessed ...` | 因 antecedent 不明而删掉 actor | 抽代词 exact actor span；若 antecedent 不在输入，记录 unresolved/context-required |
| demonstrative determiner + noun | `these expenses shall be deducted`; `such a notice has been issued` | 只抽 `these` 或 `such` | 抽完整最小 NP：`these expenses`、`such a notice` |
| 代词只在从句内指回已表达名词 | `Prepayments ... unless they relate ...` | 把 `they` 再建成主 clause 的第二 actor | 依据 clause scope 决定；主 actor 仍取明确 NP，exception 内的代词不自动新增主 actor |

未消解状态在 canonical record 中统一写为：

```json
{
  "field": "actor",
  "reason": "reference_status=unresolved_coreference;independence_status=context_required"
}
```

### 6.2 `It may cover a shorter period if ...`

正例（canonical 关键片段）：

```json
{
  "actors": [
    {"id": "a01", "text": "It", "start": 0, "end": 2, "normalized": "it"}
  ],
  "actions": [
    {"id": "p01", "text": "cover a shorter period", "start": 7, "end": 29, "normalized": "cover a shorter period"}
  ],
  "unsupported_or_ambiguous": [
    {
      "field": "actor",
      "reason": "reference_status=unresolved_coreference;independence_status=context_required"
    }
  ]
}
```

反例：actor 设为空；或 exact span 写成 `business year`；或 normalized 在 sentence-only
输入下写成 `business year`。前者丢失真实 mention，后两者使用了输入外先行词。

Stage 2 exact-span 仍可正常计分 `It`。该记录在 reference 未消解前不能进入 Stage 3
actor-to-participant matching。

### 6.3 被动句

正例：`The report must be filed within 72 hours.`

```json
{
  "actors": [],
  "actions": [
    {"id": "p01", "text": "filed", "start": 19, "end": 24, "normalized": "file"}
  ],
  "constraints": [
    {"id": "c01", "text": "within 72 hours", "start": 25, "end": 40, "normalized": "within 72 hours"}
  ],
  "actor_action_map": [{"actor_id": null, "action_id": "p01"}]
}
```

反例：凭 GDPR 常识添加 `controller`。若句中出现 `by the controller` 且它确实是
performer，才抽该显式 by-phrase actor。

## 7. 并列与多规范子句

- 同一 modality 同时支配 `record and report` 时，可保留一个 clause、两个 action。
- `The controller and processor shall report` 保留两个 actor。只有语法明确两者都对应
  同一 action 时才建立两条 edge；禁止无依据做 actor×action 全笛卡尔积。
- `The controller shall assess ...; the processor must notify ...` 有各自 actor、modal
  和 consequence，应拆成两个 clause。
- H1 只能修复既有 clause 的字段，不能新增/删除 clause、改 `clause_id` 或
  `clause_span`。若 clause 边界本身不明，保留 B0 并报告 `clause_boundary_ambiguous`。
- `order_relations` 只在 `first/then/before/after` 等 exact evidence 或明确结构建立
  顺序时输出；普通 `and` 不自动表示顺序。

## 8. Condition、constraint 与 exception 的三步测试

按顺序判断：

1. **Carve-out test**：该短语是否撤销一个本来适用的规范？是 → `exception`。
2. **Applicability test**：是否决定规则是否或何时开始适用？是 → `condition`。
3. **Performance-limit test**：规则已适用后，是否限制如何、多少、何地或何时完成？
   是 → `constraint`。

示例：

| 文本 | 正确 | 常见反例 |
|---|---|---|
| `if a business is opened` | condition | 仅因有时间含义就标 constraint |
| `within 72 hours` | constraint | 标 condition |
| `unless the authority grants an extension` | exception | 标普通 condition，丢失 carve-out 语义 |
| `in accordance with Annex A` | constraint | 用外部 Annex 内容扩写 span |

一个短语原则上只属于最能解释其规范作用的字段。真正存在嵌套时可以分别抽不同
non-overlapping 或有清晰作用层级的 spans；不得仅因 marker 列表重叠重复标注。

## 9. Missing 与 uncertain

| 状态 | 表示 | 示例 |
|---|---|---|
| 字段确实不存在 | 空数组；H1 patch 可用 `{"absent": true}`，merge 后变空数组 | 清楚的主动句没有 exception |
| mention 存在但 reference 不明 | 保留 exact span + controlled unsupported entry | `It` 无可见 antecedent |
| 可能存在但 target 被截断 | 空数组 + `context_required` 或 `semantic_scope_ambiguous_in_target` | 只有列表项、缺主句 |
| clause 边界不明 | 保留可验证字段，报告 `clause_boundary_ambiguous` | 多页/编号截断 |

空数组不能兼作“不知道”。不确定也不能用 fabricated span 伪装“已找到”。

## 10. 禁止推断

人工、D1、H1 均不得使用：

- 法律常识、法律评论或未提供的法规全文；
- Web 搜索或世界知识；
- Gold、测试分布、其它方法错误统计；
- 输入外 antecedent、actor、object、condition、constraint 或 exception；
- 未在输入中出现的 canonical span。

H1 唯一额外可见信息是 B0 clause 和预注册的 inference-time repair reason；这不是
Gold，也不能用于修改未请求字段。

## 11. 三方法共同语义与可见信息

| 生产方式 | 可见输入 | 输出职责 | 不允许 |
|---|---|---|---|
| 人工 Gold | 批准英文、不可变审核辅助；当前无外部 context | 按本合同裁决六字段和状态 | 用辅助材料补模型不可见的新事实；Agent 代审 |
| B0 | 锁定德文 modality 输入 + 对齐英文 phrase 输入 | Sun-compatible baseline，接受同一 Gold 评价 | LLM、Gold、输入外推断 |
| H1 | B0 clause、同一英文 target、repair fields/reasons | 仅替换授权字段和完整 ambiguity metadata，merge 后验证 | 改 clause/ID/source、全记录重写、Gold |
| D1 | 英文 target + identifiers | 从头输出完整 canonical record | B0/H1/Gold/external context/legal knowledge |

共同语义不要求 D1 与 H1 Prompt 字面相同；要求字段定义、span、代词、missing/
uncertain、禁止推断和状态编码相同。

## 12. 评价合同

- modality：clause-level 四类 macro-F1，并报告逐类 P/R/F1。
- actor/action/condition/constraint/exception：strict exact-span P/R/F1 为主；
  safe-normalized 与 token overlap 仅作次要/诊断指标。
- structure：clause segmentation、actor-action edge、order relation 分开报告。
- validity/coverage：schema invalid、cross-field invalid、missing、hallucination、
  `unsupported_or_ambiguous`、unresolved coreference、context-required 均留在分母。
- 所有方法必须共享 frozen IDs、Gold、target/context visibility、Schema、normalization
  和 evaluator。
- `It` 的 exact span 得分与 reference 是否已消解分开；不得因 Stage 3 暂不可用而删掉
  Stage 2 actor mention。

## 13. Stage 3 准入

一个 Stage 2 record 进入 Stage 3 前至少满足：

1. canonical Schema 和 cross-field validation 均通过；
2. 每个 span 精确绑定冻结 target text；
3. 用于 participant matching 的 actor 不带 `unresolved_coreference`；
4. Stage 3 所需 clause 边界不存在 unresolved ambiguity；
5. 输入/context 版本与 formal manifest 一致。

因此 `It` 记录可以是合格的 Stage 2 评价记录，但在先行词未由正式输入消解时，不能
直接和 BPMN participant 匹配。

## 14. Prompt、Schema、Gold 与版本绑定

1. 两个 Prompt 必须写入本合同 ID 与机器合同 SHA-256。
2. `configs/stage2_extraction_bundle_v1.json` 记录机器合同、canonical Schema、人工
   协议、两 Prompt 和 12 条 pilot 的 SHA-256。
3. Prompt、合同、Schema 或人工规则任一语义变化都必须产生新 bundle；旧 Gold 不得
   在未迁移/复核时继续冒充兼容。
4. Layer E 不由本任务自动迁移或修改。正式 Gold 发布事件必须记录所用 bundle ID/hash。
5. B0 的 Sun 规则实现本任务不改；若未来发现它与本合同 exact-span 定义冲突，先登记
   真实问题并报告影响，再决定 adapter 或规则版本，不静默修正。

## 15. Pilot 边界

`configs/stage2_extraction_pilot_v1.json` 锁定 12 条现有 EStG 输入，只用于静态覆盖：
明确/并列 actor、`It/They/This/these/such`、被动、隐含 actor、condition、constraint、
`unless/except`、缺主句/缺 modality、嵌套列表和多 clause。

Pilot 只保存 sample ID、输入文本 hash 和覆盖标签；不保存预测答案，不是 Gold，不做
性能评价，也不会进入 D1/H1 few-shot。Prompt 中的例子全部是人工编写的 synthetic
句子。

## 16. 仍未冻结的事项

本合同语义已冻结；以下外部输入/路线事项仍阻止正式 150 条冻结：

- RWI-0001：context sidecar、来源 hash 和 sentence-only/context-assisted 轨道决定；
- RWI-0007：德英翻译 QA 或原生英文主轨道决定；
- 150/150 人工 adjudication；
- route/data/Stage 3/formal-Gold publication gate 共同重锁。

这些事项不会把 `It` 的 sentence-only 处理重新变成未定义：在当前轨道它固定为
exact actor mention + unresolved/context-required 状态。
