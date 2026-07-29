# 文档索引

本文只负责导航。研究主线以 `MASTER_PIPELINE.md` 为准，实时状态以
`PROJECT_AUDIT.md` 和机器完整性检查为准。

## Agent 必读

1. `MASTER_PIPELINE.md` — 三阶段目标、流程图、任务树、依赖和完成标准；
2. `PROJECT_AUDIT.md` — 当前实时状态、当前焦点和 blocker；
3. `AGENT_RUNBOOK.md` — 分阶段派工规则、当前任务 Prompt 模板；
4. `DIRECTORY_GUIDE.md` — 每个目录和文件类别的职责；
5. `EXPERIMENT_LOG.md` — 中文人类可读实验日志；
6. `REAL_WORLD_ISSUE_REGISTER.md` — 实际问题、开放状态、解决方法与验证证据；
7. `AI_CHANGE_PROTOCOL.md` — 实验日志、自动检查和记录要求；
8. `ROUTE_LOCK.md` — 当前 EStG-150、Gold 和门禁不变量；
9. `../configs/experiment_contract.json` — 当前阶段机器合同；
10. `../configs/methods.json` — 当前 Stage 2 方法注册表。

编辑人工审核数据前还必须读 `HUMAN_GOLD_GUIDE.md`。

## 论文写作

- `../paper/THESIS_DRAFT.md` — 已启动的中文连续工作稿与结果空表；
- `../paper/CLAIM_EVIDENCE_MATRIX.md` — 主张状态、证据、允许时态和解锁任务；
- `../paper/README.md` — TODO、回填和只读主张复核规则。

## 活动设计规范

- `B0_RECONSTRUCTION_DESIGN.md` — Sun Stage 2 独立重建；
- `STAGE2_CANONICAL_SCHEMA_SPEC.md` — Rule Record 合同；
- `STAGE2_EXTRACTION_CONTRACT_V1.md`、`../configs/stage2_extraction_contract_v1.json`、
  `../configs/stage2_extraction_bundle_v1.json` — 人工、D1、H1 共用的句级六要素语义与
  hash bundle；12 条 pilot 仅作静态/schema 覆盖；
- `STAGE2_EXTRACTION_CONTRACT_V1.md`、`../configs/stage2_extraction_contract_v1.json`、
  `../configs/stage2_extraction_bundle_v1.json` — 人工、D1、H1 共用的句级六要素语义与
  hash bundle；12 条 pilot 仅作静态/schema 覆盖；
- `STAGE2_LLM_INNOVATION_DESIGN.md` — H1/D1 设计；
- `EVAL_3DIM_SPEC.md`、`STYLE_EQUIVALENT_SPEC.md` — 语义与结构评价；
- `ANNOTATION_PROTOCOL.md`、`HUMAN_GOLD_GUIDE.md`、
  `HUMAN_GOLD_REVIEW_PACK_SCHEMA_v2.md` — 人工 Gold；
- `ESTG150_DATA_MAP.md` — 唯一 EStG-150 数据地图；
- `ESTG150_CANDIDATE_PROTOCOL_V1.md` — EStG-150 历史可见候选协议的唯一 external
  serializer、0–2/3–149 分流、provider adapters、prereg、validation、C0 hash，以及
  canonical 不变的 C1 strict transport v1.1 派生 schema/递归 preflight/七模型 capability
  fail-closed；
- `LLM_BUDGET_PROPOSAL_2026-07-12.md` — 预算设计，不代表已授权调用；
- `REPRODUCTION_PROTOCOL.md` — 可复现运行要求；
- `USER_DECISION_LOCK_2026-07-12.md` — 具体用户决定和权限边界。

## 研究证据

`research/` 保存 Sun、Winter、Barrientos 的方法、数据和代码身份核查。它们是证据，
不是活动任务入口。

- `research/SUN_MODALITY_DATASET_INGESTION.md` — Sun modality 来源、schema、quarantine、
  development split、许可边界与 S2.1-D 机器门禁证据；
- `research/SUN_OFFICIAL_LICENSE_RECORD.md` — S2.4-L 官方许可证据实时核对、阻塞结论与
  重新打开训练/评价门禁所需的最小证据；
- `../src/formal_experiment/s2_4_license_gate.py` — 把“许可证据已复核”与“S2.4 可执行”
  分离的 exact-hash fail-closed 门禁；
- `../src/formal_experiment/sun_modality_gate.py` — audit/status 共用的独立 fail-closed
  development 数据门禁实现。
- `research/PUBLIC_MARKER_LEXICON_RECONSTRUCTION.md` — S2.3 public marker 来源表、
  生成规则、语言/扩展边界、版本化文件与 hash；
- `../src/bpc_hybrid/sun_style/public_marker_lexicon.py` — S2.3 离线确定性生成、加载与
  fail-closed 机器门禁实现。
- `research/SUN_CORENLP_RUNTIME_ALIGNMENT.md` — S2.5 CoreNLP 4.5.10 外部运行时
  身份、软件许可边界、六字段顺序、Java bridge 和 synthetic live 证据；
- `../src/formal_experiment/corenlp_gate.py` — S2.5 exact-hash 合同/live manifest
  fail-closed 状态实现。

## 目录与逐文件导航

- `DIRECTORY_GUIDE.md` — 中文目录地图和新文件放置规则；
- `FILE_CATALOG.md` — 脚本生成的完整逐文件清单；
- `../_retired/` — 已替代路线、日期快照、旧输出和旧脚本的专属只读归档。

未来 Agent 可以追溯 `_retired/`，但不得依据其中材料启动任务、导入代码或覆盖
当前 Pipeline。迁移和恢复规则见 `../_retired/README.md`。

## 实验来源日志与检查历史

- `EXPERIMENT_LOG.md` — 追加式中文人类日志；
- `EXPERIMENT_EVENTS.jsonl` — 追加式机器 change/run/milestone 事件；
- `REAL_WORLD_ISSUE_REGISTER.md` — 不删除历史的问题/解决方法登记册；
- `_retired/logs/AUDIT_LOG_legacy_through_event_29.md` — 事件 1—29 的旧版人类日志；
- `_retired/changes/2026-07/` — 已退出活动流程的历史变更集。
