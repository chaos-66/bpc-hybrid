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
6. `AGENTS.md`：强制操作边界；
7. `docs/AI_CHANGE_PROTOCOL.md`：实验日志、自动检查和记录协议；
8. `paper/README.md`：外部 ChatGPT 通过 GitHub 协作写作的固定入口；
9. `paper/THESIS_DRAFT.md`：已启动的论文工作稿；
10. `docs/INDEX.md`：其余文档地图；
11. `docs/FILE_CATALOG.md`：自动生成的逐文件目录。

不要新建平行 pipeline、日期版 status 或 handoff。实验中出现新证据时，原位更新
主 Pipeline 的版本号、任务状态、依赖、完成定义和 changelog。

外部 ChatGPT 不会自动看到本地未推送的改动。每次 GitHub checkpoint 更新后，让
它从 `paper/README.md` 重新读取权威文件并报告实际 commit/状态日期/最新事件；聊天
记忆不能替代仓库事实。

## 当前事实

- EStG-150 人工审核输入门已就绪，但仍是 0/150 adjudicated；
- 现有 `sun_rule_only` 是 development heuristic，不是完整 Sun baseline；
- S2.3 `public_marker_lexicon_en_v1` 已离线 verified，但仍是 development-only，
  未激活 extractor、训练或评价；
- B0、H1、正式 D1、Stage 1 和 Stage 3 均未完成；
- 未经用户明确授权，不运行真实 LLM/API；
- 没有 formal Gold，也没有可用于最终论文结论的正式结果。

最新状态以自动完整性检查为准（脚本保留历史兼容名 `audit_project.py`）：

```powershell
python formal_experiment/scripts/audit_project.py
python formal_experiment/scripts/audit_project.py --with-tests
```

启动已授权的人工审核工具：

```powershell
python formal_experiment/scripts/estg150_review_tool.py
```

## 目录边界

```text
configs/       机器可读合同、方法与 schema
data/          development 与未来冻结的 input/gold/predictions/results
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
