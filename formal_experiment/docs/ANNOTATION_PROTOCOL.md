# Gold Annotation Protocol

**状态：v2 Layer E 输入门已就绪；Stage 2 句级统一六要素提取合同 v1 已冻结用于
静态 pilot；人工 Gold 尚未
完成 150/150 裁决，因此不得冻结或发布正式 Gold。唯一活动编辑面仍是
`data/development/human_review/estg_150_human_correction_v1.json`。**

本协议与 `STAGE2_EXTRACTION_CONTRACT_V1.md` 和
`configs/stage2_extraction_contract_v1.json` 共同定义人工标注、D1 与 H1 的统一语义。
机器合同身份为 `stage2_extraction_contract@1.0.0`，SHA-256 为
`7f17ecba78cfa1acf1bbc488942f1c85c37d08ece7662c622bab4226bd2dbd46`。

## 1. 输入与标注单位

- 主轨输入是当前记录的冻结英文 `target_text`，不借助上一句、下一句、章节正文、
  法律常识、Gold 候选或任何方法预测补值。
- 每条记录保留稳定 `sample_id`。一句含多个独立规范命题时建立多个稳定
  `clause_id`；不得为适配某个模型输出而改变 clause 数量。
- clause span 是该命题在 target text 中的最小连续范围；并列但共享主体或情态的动作
  可保留在同一 clause，以多个 action 和明确映射表示。
- RWI-0001 的 context sidecar 与 context-assisted 轨道尚未锁定；RWI-0007 的语言 QA
  尚未锁定。这两项不改变本合同已冻结的 sentence-only 行为，也不得被写成已解决。

## 2. 六要素与 span

所有非空表面证据都保存精确的半开区间 `[start,end)`，并满足
`target_text[start:end] == text/value`。`normalized` 仅用于安全等价比较，不能替代原文
span，也不能凭常识补写原文没有的词。

| 字段 | 统一定义 | 最小 span 原则 |
|---|---|---|
| `modality` | `obligation`、`prohibition`、`permission`、`definition` 四选一 | 保存触发类别的原文证据；类别值不是原文 span |
| `actor` | 执行、获准、被禁止或被定义命题所指的显式主体 | 保留能独立指代主体的最小名词短语或代词 |
| `action` | 受情态支配的行为或定义性谓词 | 保留最小可执行/可匹配的 verb + 必要 object/complement |
| `condition` | 决定规则何时、何地或在何种事件下适用的触发前提 | 包含必要的 `if/when/where` 引导范围 |
| `constraint` | 在规则已适用后限制时间、数量、范围、方式或法律界限的限定 | 只取实际限制 action 的最小短语 |
| `exception` | 从一般规则中排除情形、对象或效力的 carve-out | 包含 `unless/except/without prejudice` 等必要引导范围 |

区分测试：删去 condition 会改变“规则是否触发”；删去 constraint 会改变“已触发行为
怎样/何时/在何范围完成”；删去 exception 会扩大一般规则的覆盖面。一个短语只能按其
在当前 clause 中的主要功能进入一个字段；无法可靠区分时不猜，转入受控待裁决状态。

## 3. 代词、隐含主体与不确定性

- `it/they/this/that/these/those/such/the former/the latter` 若在当前句内可消解，actor
  span 仍取代词本身，`normalized` 可保存句内先行词；不得把先行词的非连续文本伪装成
  代词位置。
- 若当前句内不能消解，例如单独的 `It may ...`，仍保存原文 `It` actor span，且在
  `unsupported_or_ambiguous` 写入唯一受控状态：

```json
{
  "field": "actor",
  "reason": "reference_status=unresolved_coreference;independence_status=context_required"
}
```

- 被动句没有显式执行者时使用 `actors: []`；若 action 仍存在，
  `actor_action_map` 对该 action 使用 `actor_id: null`。不得补出“authority”、
  “controller”等常识主体。
- 原文确实没有某字段时使用空数组；原文有候选但边界或功能不可靠时使用
  `needs_adjudication`/`unsupported_or_ambiguous`，两者不得混同。
- 只有机器合同列出的受控 reason 可进入可比较记录；自由说明放 reviewer notes。

## 4. 多命题、并列与关系

- 独立情态、独立主体或独立适用范围形成新的 clause；共享情态/主体且仅并列动作时，
  在同一 clause 中保存多个 action。
- `actor_action_map` 必须覆盖每个 action；显式 actor 用 actor ID，无显式 actor 用
  `null`。不得因多个 actor/action 存在就默认生成笛卡尔积。
- `order_relations` 只保存原文明确的先后关系；并列顺序或常识流程不构成顺序证据。
- modality、actor、action、condition、constraint、exception 以外的背景事实不得为
  填满 schema 而改造成六要素。

## 5. 人工审核与派生 Rule Record

人工可见 Layer C 的不可变 LLM 候选，但每一字段必须由人显式
`accepted/edited/rejected/needs_adjudication`；候选不是 Gold，工具也不得自动接受。
最终 Gold 应称 **LLM-assisted, human-adjudicated Gold**。

审核后的 clauses deterministic 地派生 Sun rule record
`r=(tr,Ar,Pr,Cr,Or,Er,Ur,fr)`。人工确认六要素、clause、actor-action 和显式顺序关系，
不再手填另一份可能矛盾的 Rule Record。

每条最终记录必须包含 reviewer、reviewed_at、confidence、notes 和 status。建议至少
10% 由第二审核者独立复核；分歧按书面 adjudication 规则解决。遇到跨句依赖或语言
不确定性时按 `HUMAN_GOLD_GUIDE.md` 保存草稿和备注，不得标为已裁决。

## 6. 方法可见性与评价

- Human：冻结英文 target text、不可变辅助候选与审核界面；人必须显式裁决。
- D1：只见 sample/source identity 与 target text；不见 Gold、B0、H1、上下文或外部
  法律材料。
- H1：只见 target text、当前 B0 canonical record、触发原因与授权修复字段；不见 Gold、
  test metrics 或外部法律材料。未授权字段保持不变；修复失败保留 B0。
- Rule-only：本任务不改变其逻辑或输出，只要求其未来结果接受同一 canonical validator
  与 evaluator。

主要评价使用 strict exact span；safe-normalized 与人工 style-equivalent 只能作为明确
分离的辅助视图。任何 `needs_adjudication`、未消解引用、schema-invalid 或关系不完整
记录都不得进入 Stage 3 正式输入。

## 7. 冻结校验

最终 validator 必须检查：全量且唯一的 ID、四类合法 modality、clause/span 边界、
span 文本一致、六字段结构、actor-action 引用、显式顺序关系、受控不确定性、review
metadata，以及未审核/待裁决行数量为 0。合同 pilot 只做 12 条静态/schema/local
验证，不产生 Gold、few-shot、方法预测或性能主张。
