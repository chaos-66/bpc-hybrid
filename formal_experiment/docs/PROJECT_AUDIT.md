# 项目实时状态（兼容文件名 PROJECT_AUDIT.md）

**更新时间**：2026-07-16  
**唯一活动目录**：`formal_experiment/`  
**完整路线**：`docs/MASTER_PIPELINE.md`  
**机器事实源**：`python formal_experiment/scripts/audit_project.py`（自动完整性检查）  
**执行制度**：实验日志为主、自动检查为辅、正式复核只在阶段冻结/最终运行/投稿前

本文是唯一实时状态页，只记录“现在做到哪里、下一步做什么”。研究目标、完整
Stage 1/2/3 工作分解、依赖和完成定义不在这里重复，统一见主 Pipeline。

## 1. 当前结论

项目目标是完整重建并改进 Sun 的三阶段流程，而不是只做一个 Stage 2 小实验：

1. 完成 Stage 1 流程模型结构与标签语义解析；
2. 在 Stage 2 完成 Sun、传统方法、直接 LLM 和 Hybrid 的同条件比较；
3. 用主数据和更复杂法律语料验证复杂度退化与 LLM 优势边界；
4. 在 Stage 3 完成多 baseline 的规则—流程匹配、违规检测和错误类型分类；
5. 分开报告 Oracle Stage 3 与端到端误差传播，并做 Stage 2/3 交叉消融。

实施顺序锁定为：**先完成 Stage 2，再补齐 Stage 1，最后复现并扩展 Stage 3**。
当前机器合同仍是 Stage 2 优先、Stage 3 固定的阶段性合同；启动 Stage 3 改进前
必须另行修改并审计合同。

根据导师最新要求，论文非结果章节从现在与实验并行：先写引言、相关工作、方法、
数据/标注流程和实验设计；结果、摘要结论和“LLM 优势”只保留显式 TODO，直到正式
manifest 解锁。论文工作稿位于 `paper/`，不能反向定义实验状态。

## 2. 当前门禁

| 门禁 | 当前值 | 含义 |
|---|---:|---|
| `integrity_pass` | true | 可以继续受控开发，不代表实验完成 |
| `formal_capsule_versioned` | true | `formal_experiment/` 已进入 Git checkpoint `bfb0b8a`；不代表 input/Gold/结果已冻结 |
| `sun_modality_development_data_verified` | true | 2,833→2,831 development 数据、quarantine 与重建 split 已通过独立机器门禁；不是 formal Gold |
| `public_marker_lexicon_verified` | true | S2.3 英文 public-source v1 的 64 个 marker、来源/生成/hash/空扩展表通过离线机器门禁；development-only，未激活 S2.4+ |
| `human_review_input_ready` | true | 用户可以审核 Layer E |
| `human_review_freeze_ready` | false | EStG-150 仍是 0/150 adjudicated |
| `formal_gold_publication_ready` | false | route/data/stage3/Gold 尚未共同重锁 |
| `final_experiment_ready` | false | 正式方法、冻结数据与最终实验均未就绪 |

每次修改后的最新值以机器检查输出为准；若本表与机器检查冲突，以机器检查为准并
立即修正本页。

## 3. 已有资产与真实边界

| 资产 | 当前状态 | 允许的表述 |
|---|---|---|
| EStG-150 五层审核工作流 | input-ready，0/150 | LLM-assisted、human-adjudicated 候选 Gold 工作流 |
| 现有 `sun_rule_only` | development heuristic | 不是完整或 exact Sun Stage 2 |
| B0（BERT-TextCNN + CoreNLP/Tregex/Tsurgeon） | blocked | 论文级独立重建尚未完成 |
| H1（Sun + LLM fallback） | blocked on B0 | 真实 LLM 未授权 |
| D1（direct LLM） | prompt/fixture development only | 真实 LLM 未授权，不能报告正式指标 |
| Stage 1 | 部分解析代码/历史资产 | 尚无冻结的正式组件结果 |
| Stage 3 | fixture/scaffold only | 尚无完整 Sun/Winter 多 baseline 比较 |
| 正式结果目录 | 未冻结 | 当前不得声称最终实验结果 |
| Sun modality development 数据 | verified；2,831 analysis rows | 只允许本地 development 使用；许可未知、禁止再分发，不是 Sun original split |
| public marker lexicon v1 | verified；7/25/19/5/8，共 64 个 | 英文 public-source reconstruction、development-only；不是 Sun original/full lexicon，不能据此训练或评价 |

Sun 最终版、公开数据、引用链和代码来源证据统一放在 `docs/research/`；历史路线和
过期交接统一放在 `_retired/docs/2026-07/`，不得再作为实时指令。

## 4. 当前工作队列

| 顺序 | Pipeline 任务 | 当前动作 | 完成信号 |
|---:|---|---|---|
| 1 | P0 / G0.6 | **已完成**：主 Pipeline、日志/检查制度与 Git checkpoint 有回归测试保护 | Agent 入口、目录、日志字段和自动检查已固定；checkpoint `bfb0b8a` 可追踪 |
| 2 | S2.1-A | **verified**（2026-07-15 字节核验通过）| raw 字节已 byte-match：size 191,874,718、SHA-1 `0346f84a246b7049d5aef58bcb33471435bee106`、ZIP integrity testzip 通过、3 个预期成员全部存在且路径安全、EStG_raw.txt SHA-256 与 2026-07-11 审计记录一致；许可仍 `unknown_pending_confirmation`（B2 仍 open），B1 已 resolved。S2.1-B 可派发但本轮不实际进入 |
| 2.1 | S2.1-B | **verified**（2026-07-15；R1 contract repair） | 合同/schema/importer/CLI/15 个 synthetic fixtures 已修正：显式 source ID 重复 fail closed；无 ID 时显式 row-index fallback 并入 manifest；normalized-text group-aware split；标签冲突 `label_conflict` fail closed；唯一小类别阈值为 3 个 group；ZIP SHA-1/SHA-256 独立核验；5 个确定性文件含 manifest byte-identical；manifest 不含运行时、self-child 或 placeholder；synthetic one-hot 与 official pending schema 分离。R1 定向测试 54 passed；首次全量检查 840 passed, 22 skipped，0 integrity errors |
| 2.2 | S2.1-C | **verified — R1 pre-result conflict quarantine + development import**（2026-07-16） | raw 2,833 行、CSV 字节和原标签均未修改；只有精确匹配 source/normalized/raw-text hash、row 616/1221、逐行 permission/obligation 标签与 section hash 的唯一 group 被整体 quarantine。主 analysis population=2,831，分布 1190/1273/264/104；train/dev/test=1985/420/426，group-aware、无泄漏、并集完整；七个产物独立重放 byte-identical；sensitivity full-source variant 仅预注册未运行 |
| 3 | S2.1-B-R1 | **verified** | R1 合同与实现缺陷已修复并由后续真实数据与机器门禁回归保护 |
| 4 | S2.1-D / S2.1 | **verified / overall verified** | manifest 路径已项目相对化；独立 gate 交叉验证 ZIP、合同、schema、quarantine、records/splits、membership/artifact hash、ignore 与许可。records/split hash 未变；B2/B3 许可边界仍 open，formal Gold 与 final experiment 不解锁 |
| 5 | S2.2 | 用户并行完成人工裁决；Agent 只验证 | 150/150 adjudicated，freeze validator 通过 |
| 6 | S2.3 | **verified**：`public_marker_lexicon_en_v1` 已离线锁定；64 个 marker、source/manifest/payload hash、空扩展表和机器门禁通过 | 来源、规则、语言、hash 与 dev-only 扩展策略固定 |
| 6.1 | S2.4-S2.6 | 本轮严格未启动；许可未知与 S2.4 ready 的现有矛盾不在 S2.3 绕过，留待 S2.4 单独派发前收口 | 非 LLM canonical Rule Record 可复现 |
| 7 | S2.7-S2.12 | 多 baseline、H1/D1、复杂语料和错误分析 | 同 IDs/Gold/evaluator 的完整比较 |
| 8 | S2.13 | 冻结 Stage 2 | 数据、方法、指标、成本、manifest 完整 |
| 9 | PW1 | **下一论文任务**：引言与 RQ0–RQ4 | 无结果性过度主张；主张矩阵同步 |

Stage 1 和 Stage 3 的后续任务已经在主 Pipeline 中排好依赖，不在当前阶段抢跑。

## 5. 当前派工

| 角色 | 任务 | 状态 | 写入范围 | Prompt |
|---|---|---|---|---|
| 协调 Agent | 维护门禁、验收和日志 | in_progress | shared docs/log only | `docs/AGENT_RUNBOOK.md` §§1–3 |
| Agent-E1 | S2.1-A 官方数据来源证据 | **verified** (2026-07-15 字节级核验通过；许可仍 unknown_pending_confirmation；B2 仍 open) | `data/development/sun_modality/`、`docs/research/SUN_MODALITY_DATASET_INGESTION.md`、manifest、`scripts/verify_sun_modality_zip.py`、tests | §4.1 |
| 当前执行 Agent | S2.3 public marker lexicon 重建 | **verified；严格停止在 S2.3** | `resources/lexicon/`、生成/加载/门禁代码、fixtures/tests、合同与状态文档；未改 Gold，未联网/调用 API，未训练/评价，未进入 S2.4/S2.5 | source=`e40c85…e369`；manifest=`5b9baf…2bf7`；combined payload=`8c3a27…7b91` |
| Agent-P1 | PW1 引言与研究问题 | ready | `paper/THESIS_DRAFT.md`、主张矩阵 | §4.2 |
| Agent-R1 | 论文科学主张只读复核 | blocked on PW1 draft | 无写入 | §4.3 |
| 用户 | S2.2 Layer E 人工裁决 | in_progress 0/150 | 仅 Layer E | 审核工具/人工决定 |

实验 Agent 默认串行；论文 Agent 可以与一个实验 Agent 并行，但不得编辑 shared
状态页。协调 Agent 在工作 Agent 交接后统一更新本页、Pipeline、catalog 和日志。

## 6. 当前禁止

- 不把现有 heuristic 叫作 Sun 完整复现或 Sun 原始代码；
- 不自动填写、修改或通过预测反推人工 Gold；
- 不运行真实 LLM/API，除非用户再次明确授权且预算、模型、prompt 已锁定；
- 不把 development 结果复制成 formal 结果；
- 不用不同 test IDs、Gold、schema 或 evaluator 制造 baseline 比较；
- 不新增第二份 pipeline、日期版 status 或 handoff；
- 不改动 `references/` 或根 `archive/`，也不恢复其中代码为活动实现。

## 7. 证据入口

- 文档地图：`docs/INDEX.md`
- 目录职责与逐文件清单：`docs/DIRECTORY_GUIDE.md`、`docs/FILE_CATALOG.md`
- Sun 数据与最终版审计：`docs/research/SUN_FINAL_VERSION_AND_DATA_AUDIT.md`
- S2.3 public marker 重建：`docs/research/PUBLIC_MARKER_LEXICON_RECONSTRUCTION.md`
- Sun baseline 边界：`docs/research/SUN_BASELINE_AUDIT.md`
- Winter/Sun 代码分离：`docs/research/SUN_WINTER_CODE_SEPARATION_AUDIT.md`
- Barrientos 借用边界：`docs/research/BARRIENTOS_BORROWING_AUDIT_2026-07-12.md`
- 历史交接：`_retired/docs/2026-07/CURRENT_HANDOFF_2026-07-12.md`
- 追加式实验日志：`docs/EXPERIMENT_LOG.md`、`docs/EXPERIMENT_EVENTS.jsonl`
- Agent 派工与 Prompt：`docs/AGENT_RUNBOOK.md`
- 论文工作稿与主张矩阵：`paper/THESIS_DRAFT.md`、`paper/CLAIM_EVIDENCE_MATRIX.md`
