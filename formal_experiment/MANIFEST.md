# Formal Experiment Manifest

## 控制平面

| 文件 | 唯一职责 |
|---|---|
| `AGENTS.md` | Agent 强制入口与安全边界 |
| `docs/MASTER_PIPELINE.md` | 唯一完整三阶段路线与 WBS |
| `docs/PROJECT_AUDIT.md` | 唯一实时状态、blocker 和下一任务 |
| `docs/REAL_WORLD_ISSUE_REGISTER.md` | 全实验实际问题、状态、解决方法和验证证据的唯一登记册 |
| `docs/AGENT_RUNBOOK.md` | Agent 分阶段派工、并发边界和可复制 Prompt |
| `docs/DIRECTORY_GUIDE.md` | 人和 Agent 共用的中文目录职责地图 |
| `docs/FILE_CATALOG.md` | 自动生成的逐文件目录 |
| `docs/INDEX.md` | 文档分类地图 |
| `docs/AI_CHANGE_PROTOCOL.md` | 实验日志、自动检查与 change/run event 协议 |
| `docs/ROUTE_LOCK.md` | EStG-150、Gold 和阶段性执行门禁 |
| `configs/experiment_contract.json` | 当前机器可读实验合同 |
| `configs/methods.json` | 当前方法状态 |
| `configs/stage2_extraction_contract_v1.json` / `configs/stage2_extraction_bundle_v1.json` | Stage 2 人工、D1、H1 共用的六要素语义合同 / hash bundle |
| `configs/estg150_candidate_protocol_v1.json` / `.lock.json` | EStG-150 原始候选协议的唯一 external serializer、历史资产、分流、adapter 与 fixture hash |
| `configs/estg150_openai_strict_transport_schema_adapter_v1_1.json` | canonical v1 不变前提下的 OpenAI strict transport schema 派生、六项允许差异与七模型 capability allowlist |
| `scripts/run_estg150_candidate_protocol.py` | C0–C4 唯一候选 runner；默认离线，schema/capability 在 key/network 前 fail closed，真实 API 需 provider/call/token/cost 四重授权 |
| `scripts/audit_project.py` | 自动完整性检查（保留历史兼容文件名） |
| `src/formal_experiment/sun_modality_gate.py` | Sun modality development 数据的独立、离线、fail-closed 机器门禁 |
| `resources/lexicon/public_marker_sources_en_v1.json` / `public_marker_lexicon_en_v1.manifest.json` | S2.3 公开来源快照 / 版本化词表总 manifest |
| `src/bpc_hybrid/sun_style/public_marker_lexicon.py` | S2.3 确定性生成、加载、hash 与 fail-closed 机器门禁 |
| `docs/EXPERIMENT_LOG.md` / `docs/EXPERIMENT_EVENTS.jsonl` | 中文人类日志 / 追加式机器事件 |
| `_retired/MANIFEST.md` | 退役文件的原路径、现路径和理由 |
| `paper/THESIS_DRAFT.md` / `paper/CLAIM_EVIDENCE_MATRIX.md` | 论文工作稿 / 科学主张证据与解锁条件 |

## 文档分层

```text
docs/                         活动路线、实时状态和执行规范
docs/research/                论文、数据、代码来源和 baseline 证据审计
_retired/docs/2026-07/        已过期但保留的路线、快照和交接
_retired/changes/2026-07/     历史结构化变更说明
```

历史文档不是当前指令。任何冲突依次服从 `AGENTS.md`、机器合同、
`MASTER_PIPELINE.md`、`PROJECT_AUDIT.md` 和机器完整性检查。

## 数据分层

```text
data/development/             非正式工作数据与 provenance
data/input/                   共享冻结输入；stage1_stage3/gdpr7 为 7 个 all-seven extension BPMN
data/gold/                    未来冻结人工 Gold
data/predictions/             未来正式预测
data/results/                 未来正式指标
outputs/reports/              可追溯报告
paper/                        论文工作稿；不作为实验事实源
```

EStG-150 的 Layer E 是当前唯一可由用户编辑的审核面。正式 Gold 只能是
LLM-assisted、human-adjudicated Gold，且必须通过路线、数据、Stage 3 与发布门禁。

## 清理与冻结规则

- `__pycache__`、`.pytest_cache`、`.tmp`、临时提取脚本和可再生中间物可删除；
- 被正式版本取代的材料迁入 `_retired/` 并更新其清单，研究证据迁入 `docs/research/`；
- 用户数据、Gold、predictions、results、实验来源日志不得为整理目录而删除；
- `_retired/` 不得被活动代码导入或作为实验输入；恢复材料需要用户批准和日志事件；
- `references/` 与根 `archive/` 不得修改或恢复为活动代码；
- 正式产物必须记录 input IDs、hash、命令、commit、环境、模型/prompt、seed 和时间，
  默认禁止覆盖。
