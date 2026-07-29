# 实验日志与自动检查协议

> **名称说明**：本项目不把日常论文实验称为“正式项目审计”。检查脚本继续保留
> 兼容名 `audit_project.py`，含义是“自动完整性检查”。活动日志已经改成语义清楚的
> `EXPERIMENT_LOG.md`（中文人类日志）和 `EXPERIMENT_EVENTS.jsonl`（机器事件）。
> 事件 1—29 没有重写，旧人类日志冻结在 `_retired/logs/`。

## 1. 我们实际采用的制度

| 层级 | 作用 | 什么时候使用 |
|---|---|---|
| 实验日志（主制度） | 记录运行目的、代码/数据/参数、结果、错误和产物 | 每次真实实验运行；影响结果的设计/代码变更 |
| 自动完整性检查（护栏） | 防止误改 Gold、数据漂移、schema 破坏、方法越权和测试回归 | 连贯修改批次开始与结束 |
| 正式里程碑复核 | 冻结数据/Gold、最终实验、论文提交前的系统检查 | 阶段冻结、导师复核、投稿前 |

自动检查不是第三方正式审计，也不应成为每天反复生成报告的工作。它只负责快速
告诉 Agent 当前能做什么、哪些结果还不能声称，以及改动有没有破坏项目不变量。

## 2. 修改前

按统一顺序阅读：

1. `docs/MASTER_PIPELINE.md`
2. `docs/PROJECT_AUDIT.md`（兼容文件名；内容是实时状态）
3. `docs/AGENT_RUNBOOK.md`
4. `docs/DIRECTORY_GUIDE.md`
5. `docs/EXPERIMENT_LOG.md` 的最新事件
6. 本协议
7. `docs/ROUTE_LOCK.md`
8. `configs/experiment_contract.json`
9. `configs/methods.json`

开始一个会修改代码、配置、数据协议、prompt 或评价器的连贯批次时只跑快速检查：

```powershell
python formal_experiment/scripts/audit_project.py
```

纯阅读、论文分析和讨论不需要重复检查。快速检查通常只需数秒，且不跑测试。

## 3. 检查与记录频率

| 情况 | 要做什么 |
|---|---|
| 只读分析、回答问题 | 不跑全量检查，不追加日志 |
| 连贯开发批次开始 | 快速完整性检查一次 |
| 开发过程中 | 只跑相关测试，不反复全测 |
| 连贯批次结束/交接 | 完整性检查 + 全量测试一次，然后追加日志事件 |
| 真实实验运行 | 运行前检查门禁；运行后记录 experiment_run 和 manifest |
| Gold/数据/结果冻结、最终运行、投稿 | 使用正式里程碑复核与 `--require-final-ready` |

“material change”指会影响实验路线、代码、配置、schema、prompt、数据、Gold、
evaluator、指标或正式产物的修改。纯错别字、排版和不改变含义的链接修复不需要单独
建立事件，可以合并进同一连贯批次。

### 3.1 实际问题必须持续登记

真实数据、人工标注、方法行为、工具、运行环境、模型/provider 输出或评价中暴露的
问题，统一登记到 `docs/REAL_WORLD_ISSUE_REGISTER.md`。实验日志回答“本批次做了
什么”，问题登记册回答“出现过什么实际问题、是否仍存在、怎样解决”，二者不能互相
替代。

- 发现即登记；同一批次解决也必须保留问题原貌；
- 未解决问题保持 `open`，临时绕行但根因未消除为 `mitigated`；
- 只有解决方法已经实施并有测试/manifest/人工复核等证据才可标 `resolved`；
- `resolved` 条目必须补齐解决方法、验证证据和实验事件编号；
- 问题重现时追加 `reopened` 历史，不删除旧记录；
- 每次批次结束检查新问题和状态更新，再运行全量检查并记录事件。

## 4. 真实实验日志必须记录什么

每次实际运行至少记录：

- `run_id`、时间、Stage、方法和实验目的；
- Git commit 与 dirty 状态；
- 输入数据/Gold/split 的版本或 hash；
- 模型、prompt/rule 版本、超参数、seed、threshold；
- LLM 模型版本、temperature、调用预算、实际调用数、成本和失败数（如适用）；
- 完整运行命令；
- manifest 与输出路径；
- 主指标、运行状态、报错和异常处置；
- 该结果属于 development、pilot 还是 formal。

参数和 hash 的详细值应写入运行 manifest；机器日志负责索引 manifest，而不是把
所有字段复制进 Markdown。示例：

```powershell
python formal_experiment/scripts/record_change.py `
  --event-type experiment_run `
  --purpose "Stage 2 B0 development run" `
  --run-id "s2-b0-seed13" `
  --stage "stage2" `
  --method "sun_rule_only" `
  --run-status succeeded `
  --run-command "python scripts/run_sun_rule_only.py --seed 13" `
  --manifest "data/results/s2-b0-seed13/manifest.json" `
  --result-summary "development only; metrics in manifest" `
  --gold audit_read_only `
  --llm-api not_called `
  --artifacts created_no_overwrite
```

## 5. 修改批次结束

先执行一次完整验证：

```powershell
python formal_experiment/scripts/audit_project.py --with-tests
python formal_experiment/scripts/generate_file_catalog.py --check
git diff --check
git status --short
```

运行前先检查 `REAL_WORLD_ISSUE_REGISTER.md`：本批次发现的问题是否全部登记，已解决
问题是否有方法/证据/事件，未解决问题是否仍明确为 open/mitigated。

再追加变更日志：

```powershell
python formal_experiment/scripts/record_change.py `
  --event-type change `
  --purpose "本次连贯修改目的" `
  --gold audit_read_only `
  --llm-api not_called `
  --artifacts not_created_or_overwritten `
  --notes "可选说明"
```

`--with-tests` 会写入一个绑定当前活动文件内容 SHA-256 的临时验证凭证。
`record_change.py` 只有在活动状态完全未变时才复用它，因此正常流程只跑一遍全量
测试；状态变动、凭证缺失或不匹配时才重新跑测试。`.env` 和生成缓存既不读取也不
进入状态指纹。

日志追加到以下活动路径：

- `docs/EXPERIMENT_LOG.md`：中文人类可读实验日志；
- `docs/EXPERIMENT_EVENTS.jsonl`：机器可读事件、测试证据、commit、dirty paths、
  blocker、安全声明和可选实验运行字段。

既有事件只能追加，不能重写。事件 1—29 的机器记录在更名时原样保留；迁移前的
旧人类日志位于 `_retired/logs/AUDIT_LOG_legacy_through_event_29.md`。

## 6. 不可放松的安全边界

- Agent 不得根据预测、多数票或论文聚合数字自动生成/修改 Gold；
- 用户可以继续编辑已 input-ready 的 Layer E，但只有 150/150 人工裁决后才可能冻结；
- 不得为提高指标调整 Gold、test threshold 或删除困难样本；
- 未经用户明确授权和硬调用预算，不得运行真实 LLM/API；
- `sun_rule_only` 不得调用 LLM；
- predictions、results、manifest 和正式产物默认不得覆盖；
- `references/` 与根 `archive/` 保持只读；
- 不得把 development heuristic 写成 Sun exact reproduction。

## 7. 正式里程碑复核

只有以下命令返回 0，才允许启动最终正式实验：

```powershell
python formal_experiment/scripts/audit_project.py --require-final-ready
```

最终还要人工确认三组方法共享 frozen IDs、Gold、schema、normalization、evaluator
和 Stage 3 配置。Stage 2 与 Stage 3 指标必须分开报告。这一步才接近论文语境下的
正式复核；日常开发不使用“正式审计”表述。
