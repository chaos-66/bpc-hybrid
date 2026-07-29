# Stage 1 人工 Gold 协议

本协议只定义 S1.5 的人工核对格式与冻结条件。当前机器验证使用 synthetic BPMN，
没有正式 BPMN membership，也没有人工 Gold。

## 1. 输入与盲区

- 每条记录绑定 BPMN 路径、源文件 SHA-256 和 canonical Process Record SHA-256。
- 标注界面可以显示原 activity label 与 lane-label context；不得把 P0/P1 输出自动写入 Gold。
- `gold_process_record` 初始必须为 `null`；actor/action/business-object 三个字段的初始
  `status` 必须为 `unreviewed`、`value` 必须为 `null`。
- 只有人可以把记录改为 `reviewed` 或 `adjudicated`，Agent 只能验证格式和汇总状态。

## 2. 字段决定

每个 actor/action/business-object 字段使用同一状态机：

- `unreviewed`：尚未判断，value 必须为 null；
- `present`：Gold 中存在，value 必须是非空字符串；
- `absent`：Gold 中不存在，value 必须为 null；
- `needs_adjudication`：存在分歧，不能冻结。

结构决定为 `unreviewed`、`accepted_candidate`、`corrected` 或
`needs_adjudication`。即使解析器候选完全正确，也必须由人明确选择
`accepted_candidate`，机器不得代填。

## 3. 冻结条件

`freeze_ready=true` 必须同时满足：数据 scope 是 `formal`；membership 已 frozen；
所有记录均 `adjudicated`；所有结构决定为 `accepted_candidate`/`corrected` 且存在
schema-valid Gold Process Record；所有标签字段均为 `present`/`absent` 且 value 与状态
一致。synthetic protocol pack 永远不能冻结为正式 Gold。

## 4. 当前阻塞

活动目录当前没有正式 BPMN。项目记录了 57 个 provenance 候选文件，但从
`references/` 或 `archive/` 提升为活动数据必须得到用户明确批准并追加事件；在此之前，
只能验证空白协议，不能开始正式标注或 S1.6 性能评价。
