# Stage 2 运行与结果索引

**盘点日期**：2026-07-29
**用途**：只索引已有产物及其可解释边界；不是新 Pipeline 或最终结果表。机器可读
版本位于 `outputs/reports/stage2_run_inventory_20260729.json`。

## 1. 用户目标

当前目标是让 DeepSeek V4 Pro 按统一六要素语义合同生成 D1 与 H1 fallback 输出，
再与同一输入、Gold、schema 和 evaluator 下的 B0 比较 P/R/F1。H1 当前只考虑一种
主方案：先运行 B0，仅对预注册失败/不确定字段 fallback 到 LLM，调用或 merge 失败时
保留 B0 并计入错误/成本分母。

## 2. 当前可用结果

| 资产 | 状态 | 输出范围 | 可否进入六要素 B0/H1/D1 主表 |
|---|---|---|---:|
| B0 v10a | `succeeded-development` | 150 canonical attempts；modality、五字段 span、结构、coverage | 仅作 development B0 候选；可以作为未来同合同比较的 B0 输入，但不是 paper-faithful final B0 |
| canonical H1 S2.8 v6 | `verified-offline` | trigger、field patch/merge、B0 fallback、预算；synthetic only | 否，尚无真实 DeepSeek 预测/P/R |
| canonical D1 S2.9 v5 | `verified-offline` | 完整 prompt、schema、attempt envelope、预算；synthetic only | 否，尚无真实 DeepSeek 预测/P/R |
| 旧 DeepSeek paper pilot | `succeeded-paper-level` | clause text + modality；部分 D1 文本 actor/action 未计分 | 否，modality-only 且绕过 canonical 协议 |
| Paper Validation R1 | `partial-paper-level` | 8 个有效 repeat；clause text + modality | 否，modality-only；D1 repeat 02 invalid |
| internal Sol candidate 150 | `validated-development-candidate` | 150/150、232 clauses、完整六要素 exact spans | 否，它是人工审核候选；可见性与正式 D1/H1 不同，未适配为方法 attempt |

## 3. 当前唯一完整六要素性能产物

`outputs/development/s27_estg150_b0_enhanced_v10a/` 是当前最完整、可直接读取的
development 六要素性能产物：

- 150/150 attempts，schema valid rate = 1.0，LLM calls = 0；
- modality micro P/R/F1 = 0.597656 / 0.662338 / 0.628337；
- clause alignment P/R/F1 = 0.761719 / 0.844156 / 0.800821；
- actor token-overlap micro P/R/F1 = 0.510159 / 0.361362 / 0.423058；
- action token-overlap micro P/R/F1 = 0.201493 / 0.199861 / 0.200674；
- condition token-overlap micro P/R/F1 = 0.433646 / 0.496464 / 0.462934；
- constraint token-overlap micro P/R/F1 = 0.281987 / 0.312800 / 0.296596；
- exception token-overlap micro P/R/F1 = 0.437534 / 0.471190 / 0.453739；
- complete record rate = 0.36；hallucinated field rate = 0.342781。

边界：`paper_faithful_b0=false`、`is_formal_performance_result=false`，RWI-0001/RWI-0007
仍开放。该结果不能冒充 Sun 原始实现或最终 B0。

## 4. Modality-only 结果隔离区

`paper_validation_r1_20260728` 的已聚合有效结果：

| 方法 | 有效 repeats | P | R | F1 |
|---|---:|---:|---:|---:|
| D1-unprimed | 2 | 0.8815 | 0.8182 | 0.8486 |
| H1-selective-primed | 3 | 0.8263 | 0.8052 | 0.8156 |
| H1-selective-empty | 3 | 0.8642 | 0.8442 | 0.8540 |

这些数字只评价 token-IoU 0.3 clause alignment 后的 modality，不是六要素 P/R。
`H1-selective-primed` 是整条 keep/correct/remove/add，不是预注册 field-level fallback；
`H1-selective-empty` 是锚定对照，不是目标三方法之一。

## 5. 无效、未完成和诊断产物

| 产物 | 分类 | 处置 |
|---|---|---|
| `paper_validation_r1/.../d1_unprimed/repeat_02` | invalid | 缺 30/150；不得进入均值、bootstrap 或 threshold summary |
| `paper_validation_r1/.../d1_unprimed/repeat_04` | partial/unregistered-at-generation | 5 batch 调用成功、138,510 tokens、0 parse failure，但没有合并 prediction/metrics；provider host 又与根 manifest 不一致；不评价、不替换 repeat 02 |
| Paper Validation threshold/bootstrap 中的 D1 repeat 02 | contaminated secondary analysis | 现有文件保留为 provenance；引用时必须剔除 invalid repeat 后重算 |
| B0 v6 Phase A `Minimax` | invalid diagnostic naming/methodology | `Minimax` 是诊断名，不是 MiniMax provider；correction 已证明原归因无效，不进入主表 |
| B0 B2a2/B3a/B3b/B5 | negative/diagnostic | 保留负结果；未晋级 active B0，不与主表方法混合 |
| DeepSeek canonical C1 HTTP 400 | failed transport pilot | 0 candidate、P/R=null；不是六要素运行结果 |

没有证据表明名为 MiniMax 的外部模型覆盖了 Gold、canonical prompt 或 B0 attempts。
当前风险是结果口径混用和缺失日志，不是核心数据被破坏。

## 6. 下一次真实运行前的冻结清单

1. 新建唯一 run ID，不复用 `paper_validation_r1` 或旧 pilot 目录。
2. 明确标记 `development`，直到 formal Gold/publication gate 解锁。
3. 绑定 150 sample IDs、Layer E hash、extraction-contract、schema、evaluator 和 B0 attempts hash。
4. 固定 DeepSeek provider、exact model ID、transport profile、temperature、token/call/cost ceiling。
5. D1 不得看 B0、H1、Gold、Layer C；H1 只看 B0、trigger 和授权修复字段。
6. 每条 sample 独立 attempt；网络错误只允许 identical-byte retry，内容/schema 错误保留分母。
7. 保存 request/response hash、canonical validation、prediction、metrics、cost 和 manifest。
8. 先跑 1-5 条 pilot，经人工检查 schema/span/语义后再单独授权全量。

在这些条件满足前，不再补跑或重解释现有 modality-only 输出。
