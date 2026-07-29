# Paper Validation R1 - modality-only 范围说明

> **文件性质**：本文件只限定 `paper_validation_r1_20260728` 的可解释范围，不是
> 新状态页或路线图。它以本轮冻结 prompt、实际预测 JSON 和 evaluator 为准，并补正
> `09_SIX_FIELD_BLOCKER.md` 中把合法空字段误当成 Gold 缺失的论证。

## 1. 一句话结论

**Paper Validation R1 实际是 clause detection + modality classification 实验。**
主指标是 token-IoU 0.3 文本对齐后的 clause-level modality micro P/R/F1；它不是
canonical 六要素抽取评价，也不能进入未来 B0/H1/D1 六要素主表。

## 2. 本轮实际输出合同

本轮必须以冻结到运行目录的 prompt 为准，而不是以另一条 canonical 方法路线的
`prompts/sun_compat/` prompt 为准：

| 方法 | 冻结 prompt 实际要求 | 聚合预测保留字段 | 完整六要素？ |
|---|---|---|---:|
| D1-unprimed | `clause_text`、`modality`、`evidence`、`actor`、`action` | `clause_text`、`modality` | 否 |
| H1-selective-primed | 对 B0 clause 执行 keep/correct/remove/add；每项只有 clause text 与 modality | `clause_text`、`modality` | 否 |
| H1-selective-empty | 与 primed 相同，但 B0 block 为空 | `clause_text`、`modality` | 否 |

证据：

- `outputs/paper_validation_r1_20260728/prompts/d1_prompt.txt`
- `outputs/paper_validation_r1_20260728/prompts/h1_selective_primed_prompt_template.txt`
- `outputs/paper_validation_r1_20260728/prompts/h1_selective_empty_prompt_template.txt`
- `outputs/paper_validation_r1_20260728/runs/*/repeat_*/all_predictions.json`

因此，本轮不能评价完整六要素并不只是因为缺少 char spans。更直接的原因是 H1
输出本身没有 actor/action/condition/constraint/exception，D1 也没有 condition、
constraint、exception；最终聚合预测又只保留 clause text 和 modality。

## 3. 与 canonical 六要素路线的区别

项目另有一条尚未完成真实 DeepSeek 全量比较的 canonical 路线：

- 统一语义合同：`stage2_extraction_contract@1.0.0`
- 统一输出：`stage2_prediction.schema.json@1.0.0`
- 完整字段：modality、actor、action、condition、constraint、exception、exact spans、
  actor-action map、order relations
- 统一 evaluator：S2.10-E v1.2
- B0：已有 150/150 development canonical attempts 和六要素指标
- H1：仅完成离线 fallback trigger/patch/merge 预注册，没有真实 DeepSeek 六要素 batch
- D1：仅完成离线 prompt/attempt 预注册，没有真实 DeepSeek 六要素 batch

`paper_validation_r1` 的简化 prompt/hash、30-record batch 输出和 token-IoU evaluator
均不等于上述 canonical 路线。两条路线不得合并计算均值、显著性或方法排名。

## 4. Gold 空字段的正确解释

Gold 中的 actor、condition、constraint、exception 是数组。空数组可以表示源 clause
确实没有该语义要素，不应自动解释为漏标。非空覆盖率是语料分布描述，不是 Gold
完整性的充分判据。

同时，span extraction 的常规 micro P/R/F1 也不会把“Gold 空、prediction 空”计为
一个 TP：

- Gold 空、prediction 空：没有 TP/FP/FN，可另报正确 abstention/presence accuracy；
- Gold 空、prediction 非空：FP；
- Gold 非空、prediction 空：FN；
- 预测 span 与 Gold span 按冻结规则匹配成功：TP。

因此 `09_SIX_FIELD_BLOCKER.md` 的非空覆盖率数字可以保留为数据描述，但“空数组说明
尚待补标”和“双方为空算 TP”都不能作为当前评价合同。

## 5. 真正的六要素解锁条件

要比较用户目标中的 B0、H1 fallback、D1，最小一致条件是：

1. 三种方法使用相同 150 IDs、相同冻结英文输入和同一 annotation snapshot；
2. D1 只见输入文本，输出完整 canonical Rule Record；
3. H1 以同一 B0 为底座，只对预注册 trigger/字段调用 LLM，失败保留 B0；
4. D1/H1 都输出 exact clause/field spans 和关系字段，并通过同一 canonical validator；
5. 三种方法统一进入 S2.10-E v1.2，分别报告 modality、五字段 span、结构、coverage、
   invalid/API 和 cost；
6. 在 formal publication gate 解锁前，结果只能标为 development comparison。

历史 LLM candidate prompt 可以作为语义定义来源，但不能不加适配地直接当 D1/H1
prompt：candidate protocol 对部分样本可见 Layer C，而正式 D1 禁止看到 Layer C；H1
又必须是字段级 fallback，不是整条 full extraction。

## 6. 本轮结果的允许表述

允许：

- `paper-level modality-only validation`
- `token-IoU 0.3 clause alignment 下的 modality P/R/F1`
- `H1-primed 的 B0 false-positive inheritance 更高，与 B0 草稿锚定效应一致`

禁止：

- “完成了六要素 B0/H1/D1 对比”
- “DeepSeek V4 Pro 已按 canonical candidate protocol 跑完 150 条”
- “H1 fallback 已按预注册字段 trigger 跑完”
- “这些数字是正式 Stage 2 主表或 formal Gold 结果”

完整运行分类见 `docs/experiments/STAGE2_RUN_INVENTORY.md` 和
`outputs/reports/stage2_run_inventory_20260729.json`。
