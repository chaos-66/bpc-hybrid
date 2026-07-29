# EStG-150 人工 Gold 审核指南（v2，**LLM-assisted, human-adjudicated Gold**）

> **重大更新（2026-07-13 11:30）**：
> - **启动门禁 vs 冻结门禁**已显式分开。`human_review_input_ready` 在 0/150 时即可
>   为 true（输入已就绪，可以开始人工审核）；`human_review_freeze_ready` 必须等到
>   150/150 全部裁决完成才能声明正式 Gold。
> - **2026-07-12 21:30**：v1 工作流（`estg_150_canonical_review_v1.json`）已
>   **退役为 workflow draft**，仅作 provenance。新工作流 v2 把数据拆成 5 层，
>   唯一可编辑文件是 **`data/development/human_review/estg_150_human_correction_v1.json`**。
>   LLM 候选作为只读 `llm_candidate` 复制进 Layer E；可编辑的
>   `human_correction` 初始为空。只有人工点击逐字段“已接受”或
>   “接受本条全部 LLM 候选”后，候选值和精确 span 才会复制到人工结果。
>   **复制动作不等于自动批准**——它必须由人工在核对后点击触发；所有字段初始
>   decision=`unreviewed`。
>   最终 Gold 称为 **LLM-assisted, human-adjudicated Gold**；论文不得称"完全从零人工标注"。

## 1. 5 层数据模型

| 层 | 文件路径 | 角色 | 可写？ |
|---|---|---|---|
| **A. 德文原文** | `data/development/estg/estg_selected_150_de.jsonl` | 原始 EStG 法规句子（150 条 legacy record_id） | **永久只读**（工具绝不写） |
| **B. 英文翻译候选** | `data/development/human_review/estg_150_translation_en_v1.jsonl` | LLM 翻译的英文 + provenance | **永久只读**（immutable:true） |
| **C. LLM 六要素候选** | `data/development/human_review/estg_150_llm_six_element_candidates_v1.jsonl` | 从旧 `estg_gold_150_llm_draft.jsonl` 重建的六要素候选 | **永久只读**（immutable:true, human_approved:false） |
| **D. 中文核对辅助** | 活动路径由 `configs/estg150_layer_d.json` 指定；v1 是全 null 占位，当前 v2 为 150/150 中文 + 回译 | 中文 gloss + 英文回译，辅助阅读 | **永久只读**（不得写入人工答案） |
| **E. 人工修正** | `data/development/human_review/estg_150_human_correction_v1.json` | LLM candidate 复制为 `llm_candidate`（不可写）；用户编辑 `human_correction`、`decisions`、`review_state` | **唯一可编辑文件** |

5 层生成器：

```powershell
python formal_experiment/scripts/build_estg150_review_layers.py
```

每次都会重建 4 个新文件（layer A 永远不动）。Layer E 始终初始化为
150/150 needs_review，0 approved_en，0 clauses 决策，0 review 决策。

## 2. 工具启动

当前推荐入口是极简 Sol 修改工具：

```powershell
python formal_experiment/scripts/estg150_simple_review_tool.py
```

界面只显示法规英文、每个 clause 的六要素和 4 个导航按钮。Sol 已经把全部
clause 和六要素预填好：没问题时点一次“保存并下一条”；有问题时直接修改对应
文本框再保存。actor/action/condition/constraint/exception 每行一个原文片段；工具
在后台自动生成并校验 span、offset、ID 和关系引用，界面不要求用户手填字符位置。

“稍后再看”只导航，不写文件；“保存并下一条”是用户对当前显示结果的明确最终确认，
一次完成旧数据结构内部所需的状态推进、备份、原子写入和格式校验。Sol 候选本身不会
自动写入 Layer E。已有人工完成记录优先从 Layer E 回显，不会被后台候选静默覆盖。

如需处理非常规 clause 边界、显式关系或疑难上下文，原高级工具仍保留：

```powershell
python formal_experiment/scripts/estg150_review_tool.py
```

默认打开 Layer E 文件（`estg_150_human_correction_v1.json`）。可用
`--path <other>` 指定其他文件，但 Layer A/B/C/D 是只读的不应作为编辑目标。

## 3. 高级工具的两个标签页（一般不需要）

### 标签页一：翻译核对

5 列并排显示：

1. **德文原文**（只读，浅灰）
2. **英文候选**（只读，浅灰）—— 来自 Layer B
3. **中文翻译**（只读，浅灰）—— 来自活动 Layer D
4. **英文回译**（只读，浅灰）—— 来自活动 Layer D；用于发现译义漂移
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

左侧只读显示 `llm_candidate` JSON；右侧只读预览 `human_correction` JSON。
实际修改必须使用下方的字段、span 和条款控件，避免出现“看似修改 JSON、实际未保存”。

每个 clause 有 6 行六要素（modality / actor / action / condition / constraint / exception），
每行 3 列：LLM 候选值、人工值（可编辑）、决策（5 选 1 按钮）。
LLM 候选单元格会自动换行并保持只读；特别长的候选最多在表格中显示 3 行，
双击任意候选单元格会弹出可选中复制、可滚动的完整候选全文。

高频操作：
- **接受本条全部 LLM 候选**：人工确认后，一次复制本条 6 个候选字段、精确字符
  offset 和 clause；只把记录推进到 `in_progress`，不会自动标 `reviewed` 或
  `adjudicated`。
- **逐字段“已接受”**：只复制当前字段。非空候选若没有可核验的精确 span，工具
  会拒绝“接受为空”，要求使用人工值或 span 编辑器修正。
- **逐字段“已修改”**：使用人工值；文本在当前 clause 中唯一出现时工具自动计算
  `[start,end)`，不唯一时必须在 span 编辑器明确填写位置。
- **逐字段“已拒绝”**：清空人工结果中的该候选字段，但左侧不可变候选仍保留作
  provenance。
- **待裁决**：保留问题，允许先标 `reviewed`，但最终 `adjudicated` 前必须改成
  `accepted` / `edited` / `rejected`。
- `actor_action_map` 与 `order_relations` 使用下方 JSON 框编辑；离开输入框或点击
  “保存草稿”时会解析并校验引用 ID，未知 actor/action ID 会拒绝保存。

特别规则：
- **modality 必须是 4 选 1**：`obligation` / `prohibition` / `permission` / `definition`。**无默认 obligation**。
- 添加新条款是**空白** clause：modality.value=null, decision=unreviewed。
- 添加 span 必须落在 clause_span 内，否则工具拒绝。
- 添加 span 必须唯一：id 计数器跨字段在 clause 内去重。
- 删除/添加条款/span/actor_action_map/order_relations 全部显式按钮。

底部按钮：
- 本条已复核：要求 translation + 6 个六要素 decision 都已决策，且 validator 通过
- 本条已裁决：要求 review_state.status=reviewed，validator 通过（要求 freeze 级别）

### 3.1 当前句缺少上下文时怎么办

如果当前句出现 `it/es/this/that/the former`、`shorter/other/such` 或法条引用，而
主体、比较基准、被指对象必须看上一句或同一款其他句才能确定，不要凭印象把当前句
强行补成一条“完全独立”的规则：

1. 在“翻译核对”把翻译标为“待裁决”（如果英文表面翻译本身明确，也可以接受翻译，
   但受上下文影响的六要素仍要待裁决）；
2. 在“六要素核对”把受影响字段选为“待裁决”，不受影响的字段仍可正常接受/修改；
3. 在备注写明缺少什么，例如“`It` 的先行词在上一句，当前样本未提供”；
4. 点击“保存草稿”，然后用“下一条待审核”继续，不要把本条标为“已裁决”；
5. 确认该类问题已登记到 `docs/REAL_WORLD_ISSUE_REGISTER.md`；同一根因更新原 RWI，
   不重复创建新问题。

当前已登记的实例是 RWI-0001。它在上下文输入和公平评价合同锁定前保持 `open`；
这不妨碍审核其他记录。

### 3.2 不懂德文时，人工审核到底负责什么

Sun 的数据来源与英语方法之间存在未披露的语言转换缺口，见 RWI-0007。不会德语的
审核者**不负责证明德文原句与英文候选完全等价**，也不要在德文中人工找 span。
本项目当前可执行的人工职责是：

1. 把“接受英文候选”理解为“采用这段英文作为冻结工作文本”，不是德译英认证；
2. clause、modality、actor、action、condition、constraint、exception 以及所有
   `[start,end)` span 都只以右侧最终英文为边界；
3. 中文和英文回译用于理解、发现英文内部不通顺或语义漂移，不是德文翻译证明；
4. 英文意思清楚时正常接受或修改六要素；明显不完整、疑似错译、必须依赖德文才能
   判断时选“待裁决”、写备注并继续下一条；
5. 在 RWI-0007 关闭前，不把该数据称为“人工验证的德译英”，只称
   `LLM-translated English working text with human-adjudicated English spans`。

### 3.3 统一六要素合同 v1（人工裁决必须遵守）

人工、D1 和 H1 现共同绑定 `stage2_extraction_contract@1.0.0`；机器文件为
`configs/stage2_extraction_contract_v1.json`，SHA-256 为
`7f17ecba78cfa1acf1bbc488942f1c85c37d08ece7662c622bab4226bd2dbd46`，完整人读规则见
`docs/STAGE2_EXTRACTION_CONTRACT_V1.md`。审核时特别注意：

1. 只按右侧冻结英文当前句裁决，不用上一句、章节、法律知识或方法预测补值；
2. 非空字段必须保存当前句中的精确 `[start,end)`；normalized 不能代替原文 span；
3. 句内可消解代词仍以代词本身为 actor span；句内不可消解的 `It` 也保留 `It`
   span，同时标记受控的 `unresolved_coreference/context_required`，并保持待裁决；
4. 被动句没有显式主体时 actor 为空，action 的 actor mapping 使用 `null`，不能猜主体；
5. 原文没有字段时保存空值；有候选但边界/功能不可靠时用“待裁决”，不能用空值掩盖
   不确定性；
6. condition 决定规则是否触发，constraint 限制已触发行为，exception 从一般规则中
   排除范围；无法稳定区分时留待裁决；
7. 独立情态/主体/适用范围拆 clause；共享情态和主体的并列动作可留在同一 clause，
   但每个 action 都必须有明确 actor mapping；
8. 12 条合同 pilot 只是规则覆盖与 schema 检查，不是 Gold、few-shot 或方法优劣测试。

RWI-0001 与 RWI-0007 继续保持 open；句级合同冻结不等于 context sidecar 或语言 QA
已经完成。

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
（高级工具使用 `mark_reviewed` / `mark_adjudicated`；极简工具由用户一次点击
触发 `apply_simple_review_candidate`，该方法在内存中依次通过两个相同门禁）。

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
| `python scripts/estg150_simple_review_tool.py` | 启动推荐的极简 Sol 六要素修改工具 |
| `python scripts/estg150_simple_review_tool.py --check` | 只检查 150 条 Sol 候选和当前进度，不打开窗口、不写文件 |
| `python scripts/estg150_review_tool.py` | 启动旧高级人工修正工具（疑难情况备用） |
| `python scripts/estg150_review_tool.py --path <file>` | 编辑其他 human_correction 副本 |
| `python scripts/validate_human_correction.py` | 校验 layer E 状态 |
| `python scripts/validate_human_correction.py --json` | 机器可读输出 |
| `python scripts/validate_canonical_review.py` | 校验旧 v1 canonical review（仅 sanity check） |

## 12. 工具架构（v2）

数据操作**全部**在 `src/formal_experiment/estg150_service.py` 的
`HumanCorrectionService` 纯逻辑层。极简 Tk 薄壳是
`scripts/estg150_simple_review_tool.py`，其 span/导航适配层是
`src/formal_experiment/estg150_simple_review.py`；旧高级薄壳仍在
`scripts/estg150_review_tool.py`。两个界面都只通过 service 写 Layer E。
校验在 `src/formal_experiment/estg150_validator.py`：

- `validate_record_format(record, ctx)` — 单条结构校验
- `validate_record_for_review(record, ctx)` — 单条资格校验
  (`eligible_for_reviewed` / `eligible_for_adjudicated`)
- `validate_global(path)` — 全局聚合校验(读盘)

**没有**任何 LLM / API / 网络调用。**没有** `.env` 读取。`scripts/`
下的脚本是离线 CLI 入口。
