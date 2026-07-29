# Formal Experiment

这是 `bpc-hybrid` 唯一的活动实验目录。项目完整目标是重建并改进 Sun 的
Stage 1/2/3：先完成 Stage 2 多 baseline 与复杂法律语料比较，再补齐 Stage 1，
最后完成 Stage 3 多 baseline、错误类型分类和端到端消融。

## 唯一入口

Agent 和人类都按以下顺序进入：

1. `docs/MASTER_PIPELINE.md`：唯一完整路线、任务树、依赖和完成定义；
2. `docs/PROJECT_AUDIT.md`：唯一实时状态与当前任务；
3. `docs/AGENT_RUNBOOK.md`：分阶段派工规则和可复制 Prompt；
4. `docs/DIRECTORY_GUIDE.md`：每个目录的职责和文件去向；
5. `docs/EXPERIMENT_LOG.md`：中文实验日志和最新已验证变更；
6. `docs/REAL_WORLD_ISSUE_REGISTER.md`：实际问题、开放状态、解决方法和验证证据；
7. `AGENTS.md`：强制操作边界；
8. `docs/AI_CHANGE_PROTOCOL.md`：实验日志、自动检查和记录协议；
9. `paper/README.md`：外部 ChatGPT 通过 GitHub 协作写作的固定入口；
10. `paper/THESIS_DRAFT.md`：已启动的论文工作稿；
11. `docs/INDEX.md`：其余文档地图；
12. `docs/FILE_CATALOG.md`：自动生成的逐文件目录。

不要新建平行 pipeline、日期版 status 或 handoff。实验中出现新证据时，原位更新
主 Pipeline 的版本号、任务状态、依赖、完成定义和 changelog。

外部 ChatGPT 不会自动看到本地未推送的改动。每次 GitHub checkpoint 更新后，让
它从 `paper/README.md` 重新读取权威文件并报告实际 commit/状态日期/最新事件；聊天
记忆不能替代仓库事实。

## 当前事实

- EStG-150 人工审核已完成 150/150，并由 S2.2 deterministic receipt 冻结为
  sentence-only English annotation snapshot；RWI-0001/RWI-0007 仍阻塞 formal Gold publication；
- 经用户授权，Codex 内置 `gpt-5.6-sol` 已生成并严格校验 150/150 条候选、共 232
  clauses；外部 API/费用为 0，候选不会自动写 Layer E；
- 候选协议 C0 已冻结唯一 external canonical serializer/runner：八项历史资产、Layer-A
  顺序、0–2 双轮/3–149 单轮、四 provider adapters 和 strict validation 均 hash 锁定；
  历史隐藏 Codex transport 未存档，C1–C4 与真实 API 尚未运行；
- `sun_rule_only` 已完成 150/150 development attempts；S2.10-E v1.2 复用 immutable
  attempts 重算得到 modality micro P/R/F1=0.394737/0.454545/0.422535，旧 exact-ID/span
  低分已标为 superseded。该结果不是 formal performance；
- Stage 2 六要素 extraction-contract v1 已统一人工、H1 v5 与 D1 v5；12 条 pilot 只作
  静态/schema 覆盖；H1、D1、v1.2 evaluator 与统计协议已完成真实运行前的离线预注册，
  尚无正式结果；
- Stage 1 的结构、P0/P1、blank protocol、evaluator 已验证；7 个 GDPR BPMN 已冻结为
  Stage 1/Stage 3 共享的 all-seven extension，人工 Stage 1 Gold 仍为 0/7；
- Stage 3 只完成 all-seven membership 子任务，原 4 模型、matching/violation Gold 和
  多 baseline 尚未锁定；
- 未经用户明确授权，不运行真实 LLM/API；
- 没有 formal Gold，也没有可用于最终论文结论的正式结果。

最新状态以自动完整性检查为准（脚本保留历史兼容名 `audit_project.py`）：

```powershell
python formal_experiment/scripts/audit_project.py
python formal_experiment/scripts/audit_project.py --with-tests
```

启动推荐的极简法规六要素修改工具：

```powershell
python formal_experiment/scripts/estg150_simple_review_tool.py
```

Sol 已预填全部 clause 和六要素；没问题点“保存并下一条”，有问题直接改对应框。
span/offset 在后台自动定位。旧 `estg150_review_tool.py` 仅保留为疑难情况的高级入口。

## 目录边界

```text
configs/       机器可读合同、方法与 schema
data/          development 与冻结的 input、未来 gold/predictions/results
docs/          主路线、实时状态、规范、日志与研究证据
outputs/       报告；正式报告必须可追溯
paper/         论文工作稿与科学主张证据矩阵
prompts/       受版本控制的 prompt 与 fixtures
resources/     词表等静态资源
scripts/       自动检查、日志、构建、验证与运行入口
src/           活动实现
tests/         离线测试与 fixtures
_retired/      已退出活动流程但需追溯的专属只读归档
```

`references/` 和根 `archive/` 是只读 provenance；所有活动修改留在本目录。
`.env` 不得读取或进入日志；`.tmp`、`.pytest_cache`、`__pycache__` 是可再生缓存。
