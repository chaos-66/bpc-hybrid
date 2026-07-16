# EStG-150 人工 Gold 审核指南（v2，**LLM-assisted, human-adjudicated Gold**）

> **重大更新（2026-07-13 11:30）**：
> - **启动门禁 vs 冻结门禁**已显式分开。`human_review_input_ready` 在 0/150 时即可
>   为 true（输入已就绪，可以开始人工审核）；`human_review_freeze_ready` 必须等到
>   150/150 全部裁决完成才能声明正式 Gold。
> - **2026-07-12 21:30**：v1 工作流（`estg_150_canonical_review_v1.json`）已
>   **退役为 workflow draft**，仅作 provenance。新工作流 v2 把数据拆成 5 层，
>   唯一可编辑文件是 **`data/development/human_review/estg_150_human_correction_v1.json`**。
>   LLM 候选会复制进 human_correction，但**复制不等于批准**——所有字段初始
>   decision=`unreviewed`，必须由人显式选择 `accepted`/`edited`/`rejected`/`needs_adjudication`。
>   最终 Gold 称为 **LLM-assisted, human-adjudicated Gold**；论文不得称"完全从零人工标注"。

## 1. 5 层数据模型

| 层 | 文件路径 | 角色 | 可写？ |
|---|---|---|---|
| **A. 德文原文** | `data/development/estg/estg_selected_150_de.jsonl` | 原始 EStG 法规句子（150 条 legacy record_id） | **永久只读**（工具绝不写） |
| **B. 英文翻译候选** | `data/development/human_review/estg_150_translation_en_v1.jsonl` | LLM 翻译的英文 + provenance | **永久只读**（immutable:true） |
| **C. LLM 六要素候选** | `data/development/human_review/estg_150_llm_six_element_candidates_v1.jsonl` | 从旧 `estg_gold_150_llm_draft.jsonl` 重建的六要素候选 | **永久只读**（immutable:true, human_approved:false） |
| **D. 中文核对辅助** | `data/development/human_review/estg_150_review_aids_zh_v1.jsonl` | 中文 gloss + 英文回译，辅助阅读 | **永久只读**（字段全 null，直到用户单独授权真实 LLM） |
| **E. 人工修正** | `data/development/human_review/estg_150_human_correction_v1.json` | LLM candidate 复制为 `llm_candidate`（不可写）；用户编辑 `human_correction`、`decisions`、`review_state` | **唯一可编辑文件** |

5 层生成器：

```powershell
python formal_experiment/scripts/build_estg150_review_layers.py
```

每次都会重建 4 个新文件（layer A 永远不动）。Layer E 始终初始化为
150/150 needs_review，0 approved_en，0 clauses 决策，0 review 决策。

## 2. 工具启动

```powershell
python formal_experiment/scripts/estg150_review_tool.py
```

默认打开 Layer E 文件（`estg_150_human_correction_v1.json`）。可用
`--path <other>` 指定其他文件，但 Layer A/B/C/D 是只读的不应作为编辑目标。

## 3. 两个标签页

### 标签页一：翻译核对

5 列并排显示：

1. **德文原文**（只读，浅灰）
2. **英文候选**（只读，浅灰）—— 来自 Layer B
3. **中文翻译**（只读，浅灰）—— 来自 Layer D（暂为 "未生成" 提示）
4. **英文回译**（只读，浅灰）—— 来自 Layer D（暂为 "未生成" 提示）
5. **人工最终英文**（可编辑，淡黄）—— 唯一可编辑英文区域

按钮：
- 接受英文候选 → 把 `approved_text_en` 设为当前英文；旧的会进 history
- 保存人工修改英文 → 把 `approved_text_en` 设为当前编辑；**所有现有 span 标记 stale**，review_state 重置为 needs_review
- 拒绝英文候选 → translation decision = rejected
- 标记为待裁决 → translation decision = needs_adjudication

每次点击都会：
- 写一个 JSONL 条目到 `outputs/development/human_review/estg_150_review_actions_v1.jsonl`
- 写一个 .json 备份到 `outputs/development/human_review/review_backups/`
- 跑 `validate_human_correction.py` 并把结果显示在状态栏
- 原子替换主文件（tmp → rename）

### 标签页二：六要素核对

左侧只读显示 `llm_candidate` JSON；右侧可编辑显示 `human_correction` JSON。

每个 clause 有 6 行六要素（modality / actor / action / condition / constraint / exception），
每行 3 列：LLM 候选值、人工值（可编辑）、决策（5 选 1 按钮）。

特别规则：
- **modality 必须是 4 选 1**：`obligation` / `prohibition` / `permission` / `definition`。**无默认 obligation**。
- 添加新条款是**空白** clause：modality.value=null, decision=unreviewed。
- 添加 span 必须落在 clause_span 内，否则工具拒绝。
- 添加 span 必须唯一：id 计数器跨字段在 clause 内去重。
- 删除/添加条款/span/actor_action_map/order_relations 全部显式按钮。

底部按钮：
- 本条已复核：要求 translation + 6 个六要素 decision 都已决策，且 validator 通过
- 本条已裁决：要求 review_state.status=reviewed，validator 通过（要求 freeze 级别）

## 4. 关键不变量（运行 `python formal_experiment/scripts/validate_human_correction.py` 自动检查）

### 4.1 全局聚合校验（仅用于状态栏 / audit）

- `format_valid: true`：每条 record 满足 schema；每条 span 文本 ==
  `approved_text_en[start:end]`；每条 span 在 clause_span 内；actor_action_map
  和 order_relations 引用合法 id；modality 是 4 类之一；span id 在 clause
  内跨字段唯一；raw_text_de_sha256 与原德文一致
- `review_ready: true`：**全部 150 条**都满足：
  - 每条 record 都有 `approved_text_en` 或 translation decision=rejected
  - `review_state.status ∈ {reviewed, adjudicated}`
  - 7 个 decision（translation + 6 fields）∈ `{accepted, edited,
    rejected, needs_adjudication}`
- `freeze_ready: true`：**全部 150 条**满足：
  - `review_state.status = adjudicated`
  - 所有 decision ∈ `{accepted, edited, rejected}`（**不含** `needs_adjudication`）
  - 所有 clause modality + 所有 span decision ∈ `{accepted, edited, rejected}`

> **4.1.1 四门禁（与 §4.1 不同维度，2026-07-13 拆分）**
> §4.1 的 `review_ready` / `freeze_ready` 是**逐条累计**的统计——
> 它们只在用户完成 150/150 之后才能为 true。audit 同时报告四个
> **正交**的"门"：
>
> | # | 字段 | 含义 | 0/150 | 何时 true |
> |---|---|---|---|---|
> | 1 | `audit.human_review_input_ready` | 启动门禁（可以开始人工审核） | **true** | authoritative contract `human_review_gate.status` 允许 + 数据 / 工具 / schema / membership 全部就位 |
> | 2 | `audit.human_review_freeze_ready` | 注释冻结门禁（150/150 adjudicated） | false | 等价于 v2 `freeze_ready` |
> | 3 | `audit.formal_gold_publication_ready` | 正式 Gold 可发布门禁 | false | gate 2 + route/dataset/stage3/freeze_policy **同时**重新锁定 |
> | 4 | `audit.final_experiment_ready` | 最终实验可运行门禁 | false | gate 3 + 三方法就绪 + 冻结 input/gold |
>
> 命令 `python scripts/audit_project.py --require-human-review-ready`
> 检查的是**启动门禁**（gate 1），0/150 时已经通过。命令
> `python scripts/audit_project.py --require-final-ready` 检查的是
> **最终实验可运行门禁**（gate 4），0/150 时返回非零。命令
> `python scripts/validate_human_correction.py` 输出的
> `review_ready` / `freeze_ready` 仍然是 §4.1 的累计统计。
>
> `audit.human_review_ready` 是 gate 1 的 **DEPRECATED 别名**；新代码
> 需要 "ready to publish Gold" 时请使用 `human_review_freeze_ready` /
> `formal_gold_publication_ready` / `final_experiment_ready`，不要依赖
> `human_review_ready` 这个别名。
>
> **Event 23 publication whitelist (2026-07-13)**：gate 3
> `formal_gold_publication_ready` 现在还要求
> `formal_gold_publication_gate.status` 与 contract 的
> `allowed_publication_statuses` **精确**匹配（默认
> `["ready_for_formal_gold_publication"]`）。Event 23 移除了之前的
> "不是 blocked_* 也不是 unknown" 启发式 fail-open；任何拼写错误 /
> pending / 空值 / 未登记值都让 gate 3 保持 false。详见
> `formal_experiment/AGENTS.md` 4-gate 表。

### 4.2 单条资格校验（"本条已复核" / "本条已裁决" 按钮使用）

工具上的 "本条已复核" 和 "本条已裁决" 按钮**只检查当前 record**,
**不**检查其他 149 条。这是 v2 工作流的关键修正 —— 否则第一条永远
无法标 reviewed（鸡生蛋死锁）。具体规则：

**eligible_for_reviewed**:
1. 当前 record 自己的 per-record 结构检查通过
2. `decisions.translation ≠ unreviewed`
3. `approved_text_en` 已填,或 `decisions.translation == rejected`
4. 6 个 element decision (`modality/actor/action/condition/constraint/exception`)
   **都不是** `unreviewed`
5. 当前 `review_state.status` 不是 `reviewed` 或 `adjudicated`
6. **不**检查其他 149 条

**eligible_for_adjudicated**:
1. 当前 record 自己的 per-record 结构检查通过
2. 当前 `review_state.status == reviewed`（必须先 reviewed）
3. 所有 7 个 decision ∈ `{accepted, edited, rejected}`（**不**含 `needs_adjudication`）
4. 所有 clause 的 modality.decision ∈ `{accepted, edited, rejected}`
5. 所有 span decision ∈ `{accepted, edited, rejected}`
6. **不**检查其他 149 条

### 4.3 状态机

```text
needs_review --(accept translation + decide all 6 fields + save)--> in_progress
in_progress --(per-record eligible_for_reviewed)--> reviewed
reviewed --(per-record eligible_for_adjudicated)--> adjudicated
```

**任何**标 `reviewed` / `adjudicated` 的操作都需要 service-level
`_snapshot_for_undo` + `append_action_log`,且**只能由人点击**触发
（service 的 `mark_reviewed` / `mark_adjudicated` 是入口）。

工具启动时如果 `approved_text_en` 与 `candidate_text_en` 不同，会**强制
把 review_state 重置为 needs_review** 并标记所有 clause 为 `_stale`，
避免用户用旧 span 假装"已审核"。

### 4.4 on_save 流程

"保存草稿" 按钮是工具**唯一**的写盘入口。流程:

1. 收集当前界面所有未保存的修改（编辑框的 `<<FocusOut>>` 已自动收集）
2. `service.save_draft()`:
   - `create_backup()`: 用 UTC 微秒 + 单调计数器生成**唯一**备份名
   - 原子写入(per-process unique tmp → rename)
3. `service.validate_global()`: 对刚保存的文件做全局聚合校验(只读)
4. 状态栏显示:
   - 格式是否有效
   - 已批准英文: `X/150`
   - 已复核: `X/150` / 已裁决: `X/150`
   - 六要素决策已决: `X/900` (6 字段 × 150 记录, **不**是 150 记录)
   - 全部要素已决策记录: `X/150`
   - 本条可标记已复核/已裁决
   - 全局 `review_ready` / `freeze_ready`

**草稿不完整**也允许保存（`format_valid=true, review_ready=false`）
—— 状态栏会显示 "草稿已保存，但尚未完成审核"。

## 5. 不要做的事

- 不要把 `needs_review` 自动改成 `accepted` / `reviewed` / `adjudicated`
- 不要让 modality 默认成 `obligation`
- 不要伪造中文/英文回译（Layer D 字段全 null 时不假装有内容）
- 不要修改 layer A/B/C/D 文件
- 不要在 tool 之外直接写 `estg_150_human_correction_v1.json`（所有写入
  都应走 tool 的 atomic save → backup → validator 流程）
- 不要在 `outputs/development/human_review/estg_150_review_actions_v1.jsonl`
  中放 API key 或 `.env` 内容（tool 不写，validator 不读）

## 6. Action log + backup

每次操作会写两份持久化记录：

- `outputs/development/human_review/estg_150_review_actions_v1.jsonl`：每条
  操作一行 JSON：`{timestamp, sample_id, field, action, old_sha256,
  new_sha256, reviewer}`
- `outputs/development/human_review/review_backups/estg_150_human_correction_v1_<UTC微秒>_n<单调序号>.json`：
  覆盖前一刻的整文件副本。**格式**为 `estg_150_human_correction_v1_<YYYYMMDDTHHMMSSffffffZ>_n<NNNN>.json`,
  微秒精度 + 单调计数器,保证**同一秒内连续两次保存**产生**两个**不同
  备份文件名(不会互相覆盖)

关掉 tool 之前如有未保存修改，会弹窗询问是否保存。

## 7. 与 v1 canonical review file 的关系

`estg_150_canonical_review_v1.json` 是 v1 工作流（single editing surface,
three-pane UI）的输出。它已被 v2 替代，**但保留**：
- 旧用户工作不会被覆盖
- 作为 provenance 仍然可读
- 不会进入正式 Gold
- 旧 `validate_canonical_review.py` 仍能读它做 development sanity check
- 论文不再引用它作为人工 Gold 来源

## 8. 唯一 EStG-150 数据集声明

- 唯一 membership = `estg_selected_150_de.jsonl` 的 150 个 legacy record_id
- 5 层是同一 150 的不同处理层，**不是不同数据集**
- 不重新抽样；不并行 old 150 / new 150
- 英文翻译 = 现有 `estg_selected_150_en_llm_translated.jsonl`
- LLM 候选 = 现有 `estg_gold_150_llm_draft.jsonl`（仅这一份，不混入 v1_backup / v2）
- membership hash 见 `data/development/estg/estg_150_membership_hashes.json`

## 9. 论文中如何称呼

- **必须**称为 `LLM-assisted, human-adjudicated Gold`
- **不得**称为"完全从零人工标注"或"纯人工 Gold"
- 如果未来真用 D1 同一模型产生 LLM 候选，**必须**披露，并增加盲审样本
  和报告锚定偏差

## 10. 故障恢复

- 备份目录 `outputs/development/human_review/review_backups/` 保留所有
  保存前的整文件快照，按 UTC 时间戳命名
- 撤销最近一次操作：UI 上的"撤销最近一次操作"按钮恢复上一条操作前的
  当前 record 状态
- 完全重置：删除 layer E 文件并重跑 `build_estg150_review_layers.py`
  （会重新生成 150/150 needs_review 的初始状态；layer A/B/C/D 不会被
  重新生成因为它们是只读的；如果修改了它们的源就重跑整 builder）

## 11. 工具命令速查

| 命令 | 用途 |
|---|---|
| `python scripts/build_estg150_review_layers.py` | 重建 B/C/D/E 四层 |
| `python scripts/estg150_review_tool.py` | 启动人工修正工具 |
| `python scripts/estg150_review_tool.py --path <file>` | 编辑其他 human_correction 副本 |
| `python scripts/validate_human_correction.py` | 校验 layer E 状态 |
| `python scripts/validate_human_correction.py --json` | 机器可读输出 |
| `python scripts/validate_canonical_review.py` | 校验旧 v1 canonical review（仅 sanity check） |

## 12. 工具架构（v2）

数据操作**全部**在 `src/formal_experiment/estg150_service.py` 的
`HumanCorrectionService` 纯逻辑层。Tk GUI 在
`scripts/estg150_review_tool.py` 是薄壳,所有数据操作都调
service 方法。校验在 `src/formal_experiment/estg150_validator.py`：

- `validate_record_format(record, ctx)` — 单条结构校验
- `validate_record_for_review(record, ctx)` — 单条资格校验
  (`eligible_for_reviewed` / `eligible_for_adjudicated`)
- `validate_global(path)` — 全局聚合校验(读盘)

**没有**任何 LLM / API / 网络调用。**没有** `.env` 读取。`scripts/`
下的脚本是离线 CLI 入口。
