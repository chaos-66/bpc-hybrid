# Public Marker Lexicon v3 Paired B0 Evaluation

**日期**：2026-07-30

**范围**：EStG-150 development；Gold 只读；0 LLM/API

**决定**：`reject_candidate_keep_active_v2`

## 1. 冻结与唯一变量

候选 v3 在读取任何评测指标前生成并冻结：Modality/Actor/Action/Condition/
Constraint/Exception=7/8/0/26/41/5，总计 87，B0 运行时实际绑定后四个 marker
字段中的 Actor/Condition/Constraint/Exception 共 80。combined payload SHA-256：

`4c6b7737f6d11b6405e5b5375fa35f452a81920782a789507b7756d3fa881846`

两臂使用同一 150 records、同一内存 Gold 和输入对象、同一
`run_b0_batch_sun_paper`、CPU、CoreNLP 4.5.10 JAR、S2.6 classifier、paper rule
registry、Java bridge 与 `sun_table8_literal_overlap_v2` evaluator。唯一传入差异是
四个运行时 marker category 文件。v2 baseline 指标与既有
`s27_estg150_b0_sun_paper_v1` 完全一致。

## 2. 六字段 P/R

| 字段 | v2 P | v3 P | ΔP | v2 R | v3 R | ΔR | 门禁 |
|---|---:|---:|---:|---:|---:|---:|---|
| Modality | 0.729323 | 0.729323 | 0.000000 | 0.848485 | 0.848485 | 0.000000 | 通过 |
| Actor | 0.318681 | 0.000000 | -0.318681 | 0.500000 | 0.000000 | -0.500000 | P/R 回归 |
| Action | 0.673282 | 0.578563 | -0.094720 | 0.862348 | 0.910931 | +0.048583 | P 回归 |
| Condition | 0.699482 | 0.762963 | +0.063481 | 0.700935 | 0.565421 | -0.135514 | R 回归 |
| Constraint | 0.683544 | 0.600000 | -0.083544 | 0.258278 | 0.102649 | -0.155629 | P/R 回归 |
| Exception | 1.000000 | 0.000000 | -1.000000 | 0.230769 | 0.000000 | -0.230769 | P/R 回归 |

精确门禁由 counts 构成有理数；上表小数仅用于展示。Condition precision 是预注册
目标改善项，但 12 项 P/R 中有 8 项下降，零回归门禁失败。Action 没有 marker 文件；
其变化来自更换 Condition/Constraint/Exception marker 后的顺序 Tsurgeon 剪枝，是
该唯一参数的下游效应。

## 3. 结果与保留边界

- 不更新活动 v2 指针；
- 不修改或覆盖 v2、既有 B0 结果、Gold、evaluator、parser、规则、分类器或训练产物；
- 保留 v3 source snapshot、六类 category、manifest、逐 marker provenance report；
- 保留完整两臂 attempts、metrics、exact comparison 与 run manifest 作为负结果；
- 不把 v3 称为更优参数，也不把活动 v2 的 provenance 称为已完全验证。

机器证据位于
`outputs/development/s27_estg150_b0_marker_lexicon_v3_paired_v1/`；其中
`comparison.json` SHA-256 为
`62cb42c60eba5802261adaddb3b4b6b0cfafd623670db35a72d0faf4975c13a4`，
`manifest.json` SHA-256 为
`53f23ca9fbf13bad7d4871995616d5390562e7e3dbea18bb45b2ace260d9baf5`。
