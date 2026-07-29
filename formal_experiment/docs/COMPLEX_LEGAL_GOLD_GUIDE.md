# S2.11 复杂法律语料与人工 Gold 协议

## 1. 数据身份

活动复杂法律集是 `gdpr_2016_679_articles_5_50_seeded50_v1`。原文来自 EU
Publications Office 的 CELEX `32016R0679` 英语 Official Journal Formex XML。
范围固定为 GDPR Articles 5–50；单位是条文的顶层编号 paragraph，未编号条文使用
唯一直接 `ALINEA`。

成员选择不读取任何方法预测、错误或评价结果：先在每个 Article 内按固定 seed 的
SHA-256 rank 取一条，保证 46 个 Article 全覆盖；再从其余单位中取 rank 最小的 4 条；
最后按原文顺序排列。成员一旦锁定，不能因模型表现、标注难度或复杂度分层结果换样。

旧 `data/development/gdpr50/` 只保留开发溯源。它混入 recital、外部条约 Article
引用和 PDF 抽取伪影，且所谓 Gold 是 `auto_annotated_rule_based_pending_review`。
旧文本、`design_tags` 和自动六字段都不导入本数据集或人工 Gold。

## 2. 人工审核面

空白模板为
`data/development/complex_legal/gdpr_2016_679_oj_en/gdpr_articles_5_50_seeded50_human_gold_v1.json`。
Agent 只能创建空白模板、验证结构和导入用户明确给出的决定；不得把
`needs_review`、`unreviewed` 自动改为 `reviewed`、`adjudicated` 或任何语义标签。

每条记录必须先确认 source，再逐项决定：clause segmentation、modality、actors、
actions、conditions、constraints、exceptions、actor-action map 和 order relations。
modality 只能由人工在 `obligation`、`prohibition`、`permission`、`definition` 中选择，
没有默认 obligation。一个 paragraph 可有多个 clause；所有 span 使用 Python slice
语义的 0-based `[start, end)`，并且 `text == source_text[start:end]`。

`record_decision` 有三种可裁决终态：

- `canonical_rule_present`：填写 `canonical_gold.clauses`；结构必须与
  `stage2_prediction.schema.json@1.0.0` 的 clause 完全相同。
- `no_canonical_rule`：成员保留为负例，`canonical_gold=null`，不得删样。
- `source_error`：只记录真实来源损坏；成员仍保留并单独报告，不能因困难删除。

`needs_adjudication` 只能存在于 reviewed 阶段；冻结要求 50/50 全部
`review_state=adjudicated`，所有字段 decision 均为 accepted/edited/rejected，且
reviewer、reviewed_at 完整。

## 3. Gold 到统一评价合同的映射

Gold 顶层不含预测方法身份。评价时按以下一一映射：

| Human Gold | Canonical Stage 2 |
|---|---|
| `sample_id` | `sample_id` |
| 冻结 `source_id` | `source_id` |
| 冻结 `source_text` | `source_text` |
| `canonical_gold.clauses` | `clauses` |
| clause modality + evidence | `clauses[].modality` |
| actors/actions/conditions/constraints/exceptions | 同名 span arrays |
| actor-action map / order relations | 同名 edge arrays |

结构校验会在内存中加一个仅供 validator 使用的预测 envelope；该占位 envelope
不写入 Gold，也不表示 Gold 由任何方法生成。正式 evaluator 必须把 Gold 和各方法
预测分开读取，并按 frozen sample IDs 配对。

## 4. 复杂度与评价边界

S2.11 只冻结来源、许可证据、membership 和人工协议，不产生性能结果。G0.5 的文本
复杂度 profile 只有在相应记录成为 `human_approved_gold` 后才能生成；模型预测、方法
错误、test metric 和 post-result 手工改 bin 均不可作为复杂度输入。

S2.11 的“输入与协议通过”不等于复杂 Gold 已冻结。S2.12 的正式退化曲线仍必须等待：

1. 复杂集 50/50 人工裁决；
2. S2.10 统一 evaluator 与主数据评价门禁；
3. B0/H1/D1 使用相同复杂集 IDs、Gold、schema 和 normalization；
4. 如需真实 LLM，另有用户明确授权与硬调用预算。
