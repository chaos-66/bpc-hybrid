# Stage 3 三类检查的成对受控机制实验（development / synthetic）

本报告是开发阶段的受控机制实验，不是正式 GDPR Oracle，不是人工规则与自动规则的优劣比较，也没有评价法条与流程图之间的语义映射难度。

## 1. 实验问题

在目标要求已经明确、动作名称直接取自 BPMN 标签的受控条件下，检查器能否区分“原图局部要求满足”与“单一目标错误”？

## 2. 设计

- 固定面板：30 个冻结变体（missing_action 10 / incorrect_actor 10 / out_of_order 10），未重新选样、未删除失败项。
- 有效契约：28；未解决：2；有效配对：28；检查实例：56（每条有效契约 = 1 个原图对照 + 1 个错误变体）。
- 来源流程：冻结 GDPR-7 语料 7 个流程，其中 6 个被实际变异；这些实例不是 60 个独立流程。
- 两个检查器：`sun_2024_frozen`（冻结 Sun 重建）与 `evidence_checks_v1`（已提交开发检查器），使用完全相同的局部合成要求、原图／变体、Stage 1 解析、NLP 模型、tau/gamma/theta 与评价口径。
- 局部合成规范由原图结构与冻结目标元数据确定，在推断前生成并锁定；动作名称直接取自原图，因此本实验基本排除了法条与流程图之间的语义映射难度，只验证检查机制。

## 3. 指标口径

- 正例 = 有效契约的变体侧（预期违规）；对照 = 有效契约的原图侧（预期满足）。
- 正例 unknown 计入漏检（FN）；对照 unknown 不计为正确拒报（TN），也不计为误报（FP）。
- 冻结 Sun 的“数值 0 + 分母 0”由只读适配层转为 unknown，并保留原始返回值。
- 全部数字由 `predictions.jsonl` 的逐项状态重算，不做手工汇总。

## 4. 结果

### 4.1 `sun_2024_frozen`

| 检查类型 | 有效对 | TP | FP | FN | TN | 正例unknown | 对照unknown | Precision | Recall | F1 | 对照满足/有效对照 | 成对成功/有效对 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| missing_action | 10 | 5 | 0 | 5 | 10 | 0 | 0 | 1.0000 | 0.5000 | 0.6667 | 10/10 | 5/10 |
| incorrect_actor | 8 | 8 | 7 | 0 | 1 | 0 | 0 | 0.5333 | 1.0000 | 0.6957 | 1/8 | 1/8 |
| out_of_order | 10 | 10 | 0 | 0 | 10 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 10/10 | 10/10 |

- macro-F1 = 0.7874；总 unknown = 0；有效契约覆盖 = 28/30（0.9333）。

### 4.2 `evidence_checks_v1`

| 检查类型 | 有效对 | TP | FP | FN | TN | 正例unknown | 对照unknown | Precision | Recall | F1 | 对照满足/有效对照 | 成对成功/有效对 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| missing_action | 10 | 5 | 0 | 5 | 5 | 2 | 5 | 1.0000 | 0.5000 | 0.6667 | 5/10 | 5/10 |
| incorrect_actor | 8 | 6 | 0 | 2 | 6 | 2 | 2 | 1.0000 | 0.7500 | 0.8571 | 6/8 | 6/8 |
| out_of_order | 10 | 6 | 0 | 4 | 6 | 4 | 4 | 1.0000 | 0.6000 | 0.7500 | 6/10 | 6/10 |

- macro-F1 = 0.7579；总 unknown = 19；有效契约覆盖 = 28/30（0.9333）。

## 5. 案例（固定规则：每类按 variant_id 排序取第一个契约有效者）

### 5.1 `syn_missing_action_01`（missing_action）

- 原图局部要求：必须执行的动作 = “Retrieve breached subjects”
- 变体改动：从流程中删除活动 'Retrieve breached subjects'（sid-20C5FDD3-8014-432D-8595-CD780D866E38）并用 bypass 边接通前后节点
- `sun_2024_frozen`：原图 → satisfied（—）；变体 → satisfied（—）
- `evidence_checks_v1`：原图 → unknown（ambiguous_action_mapping）；变体 → satisfied（—）
- 解释：两个检查器在该对照上未同时给出“原图满足 + 变体违规”：sun_2024_frozen 原图=satisfied 变体=satisfied；evidence_checks_v1 原图=unknown 变体=satisfied。

### 5.2 `syn_incorrect_actor_01`（incorrect_actor）

- 原图局部要求：动作 “Retrieve breached subjects” 的执行者必须是 “Data Controller”
- 变体改动：为目标活动注入 lane 'Data subject'（syn_lane_sid-20C5FDD3-8014-432D-8595-CD780D866E38_0D866E38），只改该活动归属
- `sun_2024_frozen`：原图 → violation（—）；变体 → violation（—）
- `evidence_checks_v1`：原图 → unknown（ambiguous_action_mapping）；变体 → unknown（ambiguous_action_mapping）
- 解释：两个检查器在该对照上未同时给出“原图满足 + 变体违规”：sun_2024_frozen 原图=violation 变体=violation；evidence_checks_v1 原图=unknown 变体=unknown。

### 5.3 `syn_out_of_order_01`（out_of_order）

- 原图局部要求：“Retrieve breached subjects” 必须早于 “Notify national authority”
- 变体改动：反转 ['sid-20C5FDD3-8014-432D-8595-CD780D866E38', 'sid-0F3D7191-F96A-45A1-B616-EC78A870BACF'] 这对活动的先后关系（原路径 ['sid-20C5FDD3-8014-432D-8595-CD780D866E38', 'sid-9FECC45C-033C-4750-9436-4DA0648C4B43', 'sid-0F3D7191-F96A-45A1-B616-EC78A870BACF']）
- `sun_2024_frozen`：原图 → satisfied（—）；变体 → violation（—）
- `evidence_checks_v1`：原图 → unknown（order_endpoint_unmapped）；变体 → unknown（order_endpoint_unmapped）
- 解释：两个检查器在该对照上未同时给出“原图满足 + 变体违规”：sun_2024_frozen 原图=satisfied 变体=violation；evidence_checks_v1 原图=unknown 变体=unknown。

## 6. 边界与未解决项

- 局部合成规范由原图定义，不是人工 GDPR 法律规则、不是法律 Gold、不是法条抽取结果。
- 对照“满足”只表示本次指定的局部合成要求满足，不表示整个流程合法。
- 动作名称直接取自原图，本实验未评价真实法条到流程的语义映射难度。
- 旧 33 条人工标签的检查范围问题仍未解决，本实验不替代也不修改该评价面。
- 零 LLM/API 调用；未修改人工 Gold、旧标签、原图、冻结变体、旧预测与旧报告。

