# s3_semantic_grounding_v3 (development-only, zero API)

本 revision 重用 v2 的逐项确定性预测（hash 校验后 byte-identical），只修复评价口径、
输入匿名化和 fallback 候选包；不覆盖 v1/v2 证据，不调用真实 API。

## 目标字段配对评价（primary）

| 类型 | variant TP / observed-wrong / unknown | control TN / FP / unknown | P | R | F1 | pair success |
|---|---|---|---|---|---|---|
| prohibited_action_present | 10 / 0 / 0 | 8 / 0 / 2 | 1.0000 | 1.0000 | 1.0000 | 8/10 |
| required_condition_not_enforced | 9 / 0 / 1 | 9 / 1 / 0 | 0.9000 | 0.9000 | 0.9000 | 8/10 |
| constraint_violated | 2 / 0 / 8 | 2 / 0 / 8 | 1.0000 | 0.2000 | 0.3333 | 2/10 |
| exception_not_handled | 3 / 0 / 7 | 9 / 0 / 1 | 1.0000 | 0.3000 | 0.4615 | 3/10 |

- Target-paired Macro-F1: **0.6737**
- Pair success: **21/40 = 0.5250**
- Variant outcomes (mutually exclusive): positive **24**, observed negative/wrong **0**, unknown **16**; coverage **0.6**.
- Control outcomes (mutually exclusive): negative **28**, false alarm **1**, unknown **11**; coverage **0.725**.
- Control target FP rate over all pairs: **0.0250**; over decided controls: **0.0345**.
- Unknown rate over all target-field side checks: **0.3375**.

Unknown 处理：variant unknown 计入 FN 但单独列出；control unknown 单独计数，不进入 decided TNR 分母；
不把 unknown 当作合规或违规；pair success 以全体 pair 为分母，只有 variant positive 且 control negative 才算成功。

## 匿名化修复

- Fallback items: **20**
- Semantic field preservation mismatches: **0**
- Forbidden/generated leaks in model-visible payload: **0**
- Anonymisation audit passed: **True**

## Control 自洽诊断（不是独立验证）

- Control 状态由同一批待评价 checker 产生，只能称为模型诊断；没有独立全局合规标签，不报告 clean-unified 全局性能，也不按方法自身输出改变测试子集。所有 40 个 control 均保留在固定评价分母中。

## C36 可比性缺口

- Status: **GAP_DOCUMENTED_NOT_COMPUTED**
- Reason: C36 predictions contain variant-side unified outputs and some control scores, but not the v3 per-side target-field determination/coverage structure. Recomputing or splicing C36 old metrics into the v3 table would be an incomparable combination; the gap is recorded instead.

## Boundary

Development-only synthetic controlled panel. Not formal Oracle and not human Gold. Predictions are byte-identical to the frozen v2 deterministic artifacts; v3 changes only the input pack and evaluation accounting. No real LLM result is claimed.
