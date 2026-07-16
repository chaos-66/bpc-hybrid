# 论文写作区

这里保存论文工作稿，不保存实验结果源文件。事实和任务状态仍以
`../docs/MASTER_PIPELINE.md`、`../docs/PROJECT_AUDIT.md` 和机器合同为准。

## 外部 ChatGPT 的 GitHub 入口

当 ChatGPT 通过 GitHub 协助论文写作时，本文件是唯一的论文协作入口，但不是新的
状态页。每次开始写作或收到“本地实验已更新”的消息后，必须重新读取当前 GitHub
分支上的下列文件，不得把历史对话记忆当作项目现状：

1. `formal_experiment/AGENTS.md`：安全边界与必读规则；
2. `formal_experiment/configs/experiment_contract.json`：机器门禁；
3. `formal_experiment/docs/MASTER_PIPELINE.md`：唯一完整路线与任务依赖；
4. `formal_experiment/docs/PROJECT_AUDIT.md`：唯一实时状态页；
5. `formal_experiment/docs/EXPERIMENT_LOG.md`：最新已验证变更；
6. `formal_experiment/paper/CLAIM_EVIDENCE_MATRIX.md`：论文主张的证据与解锁条件；
7. `formal_experiment/paper/THESIS_DRAFT.md`：当前论文工作稿。

开始指导前，ChatGPT 应先向用户报告：实际读取的仓库/分支与 commit SHA（若连接器
可提供）、`PROJECT_AUDIT.md` 的更新时间、`EXPERIMENT_LOG.md` 的最新事件，以及
`human_review_input_ready`、`human_review_freeze_ready`、
`formal_gold_publication_ready`、`final_experiment_ready` 四个门禁。无法访问文件或
无法确认版本时，必须明确说“尚未完成仓库同步”，不能根据旧对话继续推断进度。

发生冲突时，按 `AGENTS.md` → 机器合同 → `MASTER_PIPELINE.md` →
`PROJECT_AUDIT.md` → `CLAIM_EVIDENCE_MATRIX.md` → 论文草稿的顺序取值。只读取
`formal_experiment/` 的活动文件；`_retired/`、根 `references/` 和根 `archive/`
只用于溯源，不得作为当前状态或可直接写入论文的结果。

GitHub 同步是“每次 push 后可刷新”，不是秒级实时共享。本地未提交或未推送的改动
对 ChatGPT 不可见；用户告知有新进度时，ChatGPT 必须重新读取上述文件。

## 推荐协作节奏

1. 先完成上述版本与门禁回报；
2. 从 `MASTER_PIPELINE.md` 的 PW1–PW9 中选择当前已解锁的一个最小写作任务；
3. 一次只教学和处理一个小节，先解释论证目标、证据边界和段落结构；
4. 用户写作后再逐段修改，并把缺失证据保留为标准 TODO；
5. 新增结果性句子前先检查 `CLAIM_EVIDENCE_MATRIX.md`；
6. 没有 `experiment_run` 事件和 formal manifest 时，不得把 development 数字写成
   正式结果，也不得提前撰写性能优劣、摘要结论或最终贡献。

## 文件

- `THESIS_DRAFT.md`：中文论文连续工作稿、章节骨架和结果空表。
- `CLAIM_EVIDENCE_MATRIX.md`：每项科学主张的证据、时态、解锁任务和禁止表述。

## 写作规则

1. 一次只有一个 Agent 编辑正文；另一个 Agent 可以只读复核。
2. 内部 `docs/research/` 只作证据导航，正式引用必须回到可核验的原论文。
3. 无法核验页码、表号或数字时保留 `TODO-SOURCE`，禁止猜测。
4. 没有正式 manifest 的结果不得写入论文；development 数字只能标 `DEV_ONLY`。
5. Stage 2 与 Stage 3 分表，Oracle 与 end-to-end 分表，C1–C4 证据等级不得混写。
6. Gold 只能称 `LLM-assisted, human-adjudicated Gold`；Sun 方法只能称
   `paper-faithful independent reconstruction`。

## 占位符

- `[[TODO-RESULT:任务ID：说明]]`
- `[[TODO-SOURCE:文献键：说明]]`
- `[[TODO-STATUS:任务ID：说明]]`
- `[[TODO-DECISION:任务ID：说明]]`

结果回填时必须同时更新正文和 `CLAIM_EVIDENCE_MATRIX.md`，并由只读 Agent 对照
对应 `experiment_run` 与 manifest 复核。
