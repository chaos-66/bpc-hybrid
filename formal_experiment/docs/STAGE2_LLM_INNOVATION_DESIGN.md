# Sun Stage 2 + LLM 实验设计与创新点

**日期**：2026-07-12  
**研究目标**：只改变 Sun Stage 2；Stage 3 在三组实验中冻结一致。

> **统一语义源**：人工、B0、H1 与 D1 的六要素操作语义以
> `STAGE2_EXTRACTION_CONTRACT_V1.md` / `stage2_extraction_contract@1.0.0` 为准。
> 本文负责方法比较设计；遇到最小 span、代词、隐含 actor、missing/uncertain、
> scope 或 clause/coordination 冲突时，不在本文另建一套规则。

## 1. 必须比较的三组方法

| 组 | 输入 | Stage 2 | 输出 | 研究问题 |
|---|---|---|---|---|
| B0 | 同一法规句子 | Sun final-paper-faithful reconstruction | Sun 六要素 spans + rule record | 公开资产能否重建 Sun 方法 |
| H1 | 同一法规句子 | B0，只有预注册失败条件触发 LLM 修复 | 同一 Sun schema，保留规则/LLM provenance | 选择性 LLM 是否优于全规则并降低调用成本 |
| D1 | 同一法规句子 | 纯 LLM，不读取 B0 预测 | 同一 Sun schema | LLM 能否直接替代整个 Stage 2 |

B0、H1、D1 使用相同 split、相同六字段定义、相同 span evaluator、相同 Stage 3
adapter 和阈值。D1 不能先看 B0 结果；H1 的 trigger 不能读取 Gold。

## 2. Barrientos 到 Sun 的准确借鉴关系

Barrientos/RC4PC **不是**直接提取 Sun 的六个 span。其实际结构是：

- `precondition`：由 `and/or/not` 连接的 action；
- `norms[]`：`modality` + action；
- `temporal_validity`：start/end；
- action 分成 control-flow、data、resource、time 四个 dimension，并从受控
  compliance patterns 中选择模式和参数。

因此不能写“Barrientos 已经给出了 Sun 六要素抽取方法”。正确借鉴是其工程和
评价纪律，并做显式适配：

| Sun 字段 | Barrientos 中最接近的位置 | 必须增加的约束 |
|---|---|---|
| modality | `norms[].modality` | 必须返回原文 evidence span |
| actor | resource action / `resources` | participant 与物理资源分开；返回 span |
| action | `activities` | 保留动词短语而不只给规范化活动名 |
| condition | `precondition` | 保留连接词、作用域和原文 span |
| constraint | compliance pattern + data/time args | 同时给 pattern 与原文限定 span |
| exception | 无一等字段；有时被编码为 `not` precondition | 新增 first-class `exception`，禁止静默并入 condition |

可借鉴项目是：逐条处理、strict JSON schema、controlled vocabulary、temperature
0、多次运行测稳定性、schema validation、deterministic normalization、专家语义
核验。Barrientos 的主要错误来源是同义表示不一致，因此本实验必须同时保存
`evidence_span` 与 normalized value。

## 3. 推荐的主创新：证据约束的双视图选择性混合抽取

创新不应写成笼统的“在 Sun 后面加一个 LLM”。推荐的完整表述是：

> 构建一个 public-lexicon-grounded Sun Stage 2，并以推理时可观察的不确定性作为
> 门控，仅让 LLM 修复失败字段；LLM 同时输出 Sun 六要素证据 spans 与
> Barrientos-style 规范化 compliance pattern，两个视图经确定性一致性检查后才
> 进入 Stage 3。

它包含四个可分别验证的贡献：

1. **资源贡献**：把散落在 Sleimi、LexNLP、Wiktionary 的 marker 生成过程变成
   有来源、版本和哈希的可复现 lexicon，而不是隐藏人工词表。
2. **方法贡献**：field-level selective fallback，而不是整句 all-or-nothing
   fallback。规则擅长 modality/condition/constraint，LLM/SRL 更适合长距离
   actor/action 和隐式 exception，按字段修复能保留可解释证据。
3. **表示贡献**：一个输出同时包含 source-faithful span view 和 downstream
   normalized pattern view，解决纯 LLM 容易语义正确但表示不一致的问题。
4. **评价贡献**：同时报告 span 正确性、稳定性、覆盖率、风险-覆盖曲线、调用成本
   和 Stage 3 错误传播，而不是只比较最终 compliance accuracy。

## 4. H1 的预注册 trigger

只能使用推理时可见条件：

- parser 超时/失败或 Tregex 产生结构冲突；
- schema invalid；
- 非 definition 规则没有 action；
- modality classifier 低于冻结置信阈值或 top-1/top-2 margin 低于阈值；
- 同一 span 被赋给互斥字段；
- condition/exception marker 命中但找不到完整作用域；
- actor 候选多于一个且 dependency 关系不能消歧；
- rule record 无法通过固定 Stage 3 adapter。

不得使用“该样本在 Gold 上错了”“该类别测试集表现差”或 test distribution 来触发
LLM。阈值只在 development split 确定并冻结。

S2.8 已于 2026-07-17 把该设计冻结为可执行合同。模态 top-1 confidence 严格低于
0.60 或 top1-top2 margin 严格低于 0.15 才触发；parser timeout/failure、已命名的
Tregex 字段冲突、canonical invalid 字段、非 definition 缺 action、marker 命中但
scope 缺失、多 actor 候选未解和固定 Stage 3 adapter 拒绝也可触发。修复 `actors`
必须同时授权 `actor_action_map`，修复 `actions` 必须同时授权 `actor_action_map` 与
`order_relations`。patch 只能整字段替换，未授权字段保持 JSON 值不变；envelope、span、
ID 引用或合并后 canonical validation 任一失败时，返回原 B0。正式 150 条输入的上限为
45 次请求、每条最多 1 次、0 重试、temperature=0、max output=2048。该冻结由 synthetic
mock dry-run 验证，不构成真实 LLM 调用授权或性能证据。

## 5. D1 纯 LLM 的 Sun-compatible schema

每个字段至少包含：

```json
{
  "label": "actor",
  "text": "the data controller",
  "start": 12,
  "end": 31,
  "normalized": "data controller",
  "confidence": 0.0
}
```

顶层必须包含 sentence modality、六类 span 数组、Barrientos-style pattern view、
`unsupported_or_ambiguous` 和 schema version。强制规则：

- `text == source[start:end]`，不允许凭空改写证据；
- 缺失信息输出空数组，不得猜测隐含 actor；
- exception 与 condition 分开；
- action 必须是原文动作短语，normalization 另存；
- controlled vocabulary 只约束 normalized view，不覆盖原文 span；
- 每句独立、temperature 0；正式稳定性实验对同一输入运行 5 次。

## 6. 关键消融

### Lexicon 消融

- B0-a：只用 Sun/Sleimi 论文示例；
- B0-b：+ LexNLP condition/constraint；
- B0-c：+ Wiktionary 自动 actor；
- B0-d：+ development-only exception expansion。

### LLM 消融

- H1-field：按字段选择性修复（主方法）；
- H1-sentence：触发后重做整句；
- H1-all：每句都调用 LLM；
- D1-span：只输出 Sun spans；
- D1-dual：Sun spans + normalized pattern 双视图；
- D1-free：无 controlled vocabulary，用于证明规范化约束的作用。

## 7. 数据与评价

### 正式主数据的选择顺序

用户已锁定 reconstructed route：使用公开 marker 和独立实现，德文 EStG 通过
固定流程翻译为英文，由用户审核英文六要素 spans。原作者 150 句和 443 phrase
Gold 若以后获得，只用于额外对齐/验证，不再作为继续实验的前置条件。

必须保存德文原文、冻结英文译文和翻译 provenance；译文修改会使字符 span Gold
失效。EStG 四分类和英文六要素抽取应分表报告，避免把语言适配影响隐藏在总体指标
中。

可作为辅助、不能冒充六要素主 Gold 的公开数据：LEXDEMOD（modality+agent）、
PET（actor/activity/condition）、MGTC（action/SRL）、AI Act obligations repo
（Addressee/Predicate/Target/Specifications/Pre-conditions/Beneficiaries）。

### 指标

- sentence modality：macro-F1、每类 P/R/F1、confusion matrix；
- 六要素：exact span 与 token-overlap P/R/F1，逐字段和 macro/micro；
- structure：schema-valid rate、unsupported rate、完整 record coverage；
- stability：5 次运行的 field/span agreement；
- selective prediction：risk-coverage curve、触发率、被修复/被破坏比例；
- efficiency：每句 token、延迟、估算费用；
- Stage 3：相同冻结输入下的 matching AP/MAP 和 violation P/R/F1；
- error propagation：Stage 2 各字段错误对 Stage 3 的条件错误率。

缺失、invalid、terminal API error 与 recovered provider error 必须分别计入 coverage，
不能从分母删除。H1 的 recovered provider error 保留 canonical B0 fallback，并以 H1
method identity 继续计分；不能伪装成成功调用，也不能把样本丢掉。真实 LLM 调用前必须
获得用户明确授权。

## 8. 创新点优先级

| 优先级 | 创新点 | 新颖性 | 可实施性 | 建议 |
|---:|---|---|---|---|
| 1 | evidence-constrained dual-view selective hybrid | 高 | 高 | 主创新 |
| 2 | 可复现自动 marker 构建与 provenance | 中高 | 高 | 资源/方法贡献 |
| 3 | field-level fallback + risk/coverage/cost | 高 | 高 | 与主创新绑定 |
| 4 | rare exception/condition/constraint 最小对照测试 | 中高 | 中 | 鲁棒性扩展 |
| 5 | 德英跨语言一致性审计 | 高 | 中低 | 时间足够再做 |
| 6 | 单纯“全规则 vs 全 LLM” | 低 | 高 | 只作必要对照，不当创新 |

## 9. 最小可发表实验包

若时间和标注能力有限，最低限度仍应包含：

1. B0 公共词典重建；
2. H1 field-level selective fallback；
3. D1 direct LLM；
4. 同一小型、独立冻结 Gold；
5. 一次 lexicon 消融和一次 dual-view 消融；
6. 六要素 span F1 + stability + coverage/cost + 冻结 Stage 3 结果；
7. 完整报告 Sun 原资产缺失和语言不一致。

这套设计既保留“方法尽量和 Sun 一样”，又让 LLM 的贡献具体可检验；即使最终拿
不到 Sun 原 marker 和 150 句 Gold，也不会把不可复现部分伪装成 exact baseline。

## 10. Stage 3 端到端验证

不修改 Stage 3 不等于不评价 Stage 3。B0、H1、D1 必须进入相同冻结的 Sun Stage
3，以回答 Stage 2 的 P/R 提升是否改善 AP/MAP、missing-action、incorrect-actor
和 out-of-order P/R/F1。

Sun 作者稿 Table 12 将其 violation checking 与 Winter 比较，报告 Winter
P/R/F1=0.58/0.89/0.70、Sun=0.77/0.83/0.80。本研究若使用不同数据，不直接与
这些绝对值争胜；主结论来自同一数据下 H1/D1 相对 B0 的 downstream 增量。
Winter 可在公平可运行时作为第四个增强 baseline。
