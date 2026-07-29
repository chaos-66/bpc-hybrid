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

## 3. Sun Table 8 同口径六要素视图

用户在看到严格 token-overlap 结果后，明确要求 B0/H1/D1 与 Sun Table 8 使用同一
phrase matching 口径。为避免只对 B0 放宽，现冻结共同的
`sun_table8_compatible_v1`：以整条 statement 为单位，同一语义字段的预测 span 与
Gold span 只要存在非空字符交集即可匹配；用最大一对一匹配同时保持
`Extracted = Matched + Misclassified` 和 `Ground Truth = Matched + Missed`；不再先做
clause alignment。Modality 本行只评价 evidence span 是否抽到，四分类标签正确性继续
由独立 modality 指标评价。

当前 B0 v10a 的离线只读重算位于
`outputs/development/s27_estg150_b0_sun_table8_compatible_v1/`：

| 语义要素 | Ground Truth | Extracted | Matched | Misclassified | Missed | P | R |
|---|---:|---:|---:|---:|---:|---:|---:|
| Modality | 231 | 256 | 211 | 45 | 20 | 0.824219 | 0.913420 |
| Actor | 48 | 34 | 25 | 9 | 23 | 0.735294 | 0.520833 |
| Action | 247 | 245 | 203 | 42 | 44 | 0.828571 | 0.821862 |
| Condition | 214 | 245 | 147 | 98 | 67 | 0.600000 | 0.686916 |
| Constraint | 302 | 335 | 144 | 191 | 158 | 0.429851 | 0.476821 |
| Exception | 13 | 14 | 11 | 3 | 2 | 0.785714 | 0.846154 |
| Overall | 1055 | 1129 | 741 | 388 | 314 | 0.656333 | 0.702370 |

这套视图是后见到 B0 严格分数后、由用户选择的 Sun-paper comparison view，不伪装成
结果前预注册指标；但 H1/D1 尚未运行，因此它已在两者生成结果前固定，未来三方法必须
共享同一实现和配置。Gold 中 231 个 modality 中有 3 个没有显式 trigger span，canonical
adapter 使用 clause-span fallback，故 modality phrase P/R 的直接可比性略弱于其余五项。

## 4. 严格边界质量视图

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

这些严格 token-overlap 与 clause-aligned 指标继续保留为边界质量和结构诊断，不再用来
冒充 Sun Table 8 的 phrase P/R。

## 5. Modality-only 结果隔离区

`paper_validation_r1_20260728` 的已聚合有效结果：

| 方法 | 有效 repeats | P | R | F1 |
|---|---:|---:|---:|---:|
| D1-unprimed | 2 | 0.8815 | 0.8182 | 0.8486 |
| H1-selective-primed | 3 | 0.8263 | 0.8052 | 0.8156 |
| H1-selective-empty | 3 | 0.8642 | 0.8442 | 0.8540 |

这些数字只评价 token-IoU 0.3 clause alignment 后的 modality，不是六要素 P/R。
`H1-selective-primed` 是整条 keep/correct/remove/add，不是预注册 field-level fallback；
`H1-selective-empty` 是锚定对照，不是目标三方法之一。

## 6. 无效、未完成和诊断产物

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

## 7. 下一次真实运行前的冻结清单

1. 新建唯一 run ID，不复用 `paper_validation_r1` 或旧 pilot 目录。
2. 明确标记 `development`，直到 formal Gold/publication gate 解锁。
3. 绑定 150 sample IDs、Layer E hash、extraction-contract、schema、严格 evaluator、
   `sun_table8_compatible_v1` 和 B0 attempts hash。
4. 固定 DeepSeek provider、exact model ID、transport profile、temperature、token/call/cost ceiling。
5. D1 不得看 B0、H1、Gold、Layer C；H1 只看 B0、trigger 和授权修复字段。
6. 每条 sample 独立 attempt；网络错误只允许 identical-byte retry，内容/schema 错误保留分母。
7. 保存 request/response hash、canonical validation、prediction、metrics、cost 和 manifest。
8. 先跑 1-5 条 pilot，经人工检查 schema/span/语义后再单独授权全量。

在这些条件满足前，不再补跑或重解释现有 modality-only 输出。
