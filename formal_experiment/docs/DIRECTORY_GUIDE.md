# 项目目录地图

本文同时面向人和 Agent，说明每个目录“放什么、当前能否使用、去哪里找”。逐文件
清单见 `FILE_CATALOG.md`；研究任务顺序见 `MASTER_PIPELINE.md`；实时进度见
`PROJECT_AUDIT.md`。

## 1. 进入项目的固定顺序

1. `MASTER_PIPELINE.md`：完整三阶段路线和任务树；
2. `PROJECT_AUDIT.md`：现在做到哪里、下一项是什么；
3. 本文：目录和文件职责；
4. `EXPERIMENT_LOG.md`：最近做过什么；
5. `../AGENTS.md` 与 `AI_CHANGE_PROTOCOL.md`：操作边界和记录方法；
6. `ROUTE_LOCK.md`、`../configs/experiment_contract.json`、
   `../configs/methods.json`：机器门禁和方法状态。

## 2. 顶层结构

| 路径 | 内容 | 使用规则 |
|---|---|---|
| `AGENTS.md` | Agent 必读合同、安全边界、检查命令 | 修改前必读 |
| `README.md` | 人类入口和当前事实摘要 | 快速入门 |
| `MANIFEST.md` | 控制面、数据面和目录职责总表 | 结构核对 |
| `configs/` | 实验合同、方法注册、路径、schema、Layer D 配置 | 活动；修改会影响门禁 |
| `data/` | 开发数据与未来冻结数据 | 按 development/formal 严格分区 |
| `docs/` | 活动路线、状态、规范、日志和研究证据 | 活动入口只留当前版本 |
| `outputs/` | 可重建报告和诊断 | 正式报告必须绑定 manifest |
| `paper/` | 论文工作稿、TODO 和主张证据矩阵 | 可并行写作；结果必须来自正式 manifest |
| `prompts/` | 版本化 prompt、少样本 fixture、dry-run 产物 | 活动；真实调用仍需授权 |
| `resources/` | marker 词表等静态资源 | 活动、版本化 |
| `scripts/` | 检查、记录、构建、验证和 runner 入口 | 活动命令入口 |
| `src/` | Python 实现 | 活动代码 |
| `tests/` | 离线回归测试和 fixture | 活动验证 |
| `_retired/` | 已退出活动流程但需追溯的材料 | 只读，不得导入或直接运行 |

`.pytest_cache/`、`__pycache__/` 和 `.tmp/` 是可再生缓存，不属于研究资产；可以
清除，也不会写入逐文件目录。`.env` 可能含密钥，任何 Agent、目录脚本和日志都
不得读取或打印。

## 3. 数据目录

| 路径 | 内容 | 当前地位 |
|---|---|---|
| `data/development/estg/` | EStG-150 德文源、候选翻译、旧自动标注和成员 hash | 开发/溯源；成员不可重抽 |
| `data/development/human_review/` | EStG-150 五层审核工作流，以及 GDPR7 Stage 1 的不可变 Process Record/blank 模板和唯一 human_correction 副本 | 活动审核区；各工作流只编辑其明确标注的 correction 文件 |
| `data/development/gdpr50/` | GDPR 50 条开发候选和旧 Gold | 开发数据，不是正式 Gold |
| `data/development/complex_legal/` | S2.11 官方 GDPR Formex source、确定性 50 条 membership 与空白复杂集 Gold 协议 | 输入/协议已锁定；语义 Gold 0/50，不进正式结果 |
| `data/development/gold_review/` | Sun Stage 2 Gold 审核候选/模板 | 开发审核材料 |
| `data/development/metadata/` | 旧开发 runner 的 manifest | 开发溯源 |
| `data/development/predictions/` | 旧开发预测 | 不进正式表格 |
| `data/input/` | 冻结并由所有方法共享的输入 | `stage1_stage3/gdpr7/` 已含 7 个 byte-exact GDPR BPMN，明确为 all-seven extension |
| `data/gold/` | 未来冻结的人工 Gold | 当前保持空壳 |
| `data/predictions/` | 未来正式预测 | 只由受控 runner 写入 |
| `data/results/` | 未来正式指标和明细 | 默认禁止覆盖 |

被替代的熟悉用审核副本和 R15.0 历史输出已经迁入 `_retired/data/`；它们不能
重新成为活动审核面或正式结果。

## 4. 文档目录

`docs/` 顶层只放仍然生效的路线、状态、规范、日志和索引。重要类别如下：

| 类别 | 文件 / 目录 | 说明 |
|---|---|---|
| 主线 | `MASTER_PIPELINE.md` | 唯一完整 Pipeline，可在实验中原位升级版本 |
| 状态 | `PROJECT_AUDIT.md` | 兼容文件名；内容是唯一实时状态页 |
| 导航 | `INDEX.md`、`DIRECTORY_GUIDE.md`、`FILE_CATALOG.md` | 文档地图、目录职责、逐文件清单 |
| 日志 | `EXPERIMENT_LOG.md`、`EXPERIMENT_EVENTS.jsonl` | 中文人类日志 + 原始机器事件 |
| 实际问题 | `REAL_WORLD_ISSUE_REGISTER.md` | 唯一问题登记册；保留 open/resolved 状态、解决方法和验证证据，不是平行状态页 |
| 治理 | `AI_CHANGE_PROTOCOL.md`、`ROUTE_LOCK.md`、`REPRODUCTION_PROTOCOL.md` | 修改、门禁、复现规则 |
| Stage 2 | `B0_RECONSTRUCTION_DESIGN.md`、`STAGE2_*`、`EVAL_3DIM_SPEC.md` 等 | baseline、schema、LLM 和评价设计 |
| Stage 2 六要素合同 | `STAGE2_EXTRACTION_CONTRACT_V1.md`、`configs/stage2_extraction_contract_v1.json`、`configs/stage2_extraction_bundle_v1.json`、`configs/stage2_extraction_pilot_v1.json` | 人工/D1/H1 的 sentence-only 统一语义、hash bundle 与 12 条非 Gold 静态 pilot；context/language QA 仍开放 |
| S2.10 evaluator | `EVAL_3DIM_SPEC.md`、`STYLE_EQUIVALENT_SPEC.md`、`configs/stage2_evaluator_s210_v3.json`（未来 development）、`configs/stage2_evaluator_s210.json`（旧结果 provenance） | v1.2 method-independent alignment、safe normalization 与人工 style 复核边界；旧 v1.1 不再用于新结果 |
| S2.12 analysis | `configs/s212_analysis_protocol.json`、`outputs/reports/s212_analysis_protocol_synthetic_v2.manifest.json` | 结果前统计推断、复杂度分层、错误 taxonomy 与质性样本选择合同；绑定 S2.10-E v2，synthetic 验证不代表正式比较 |
| S2.9 D1 | `configs/models/sun_d1_s29.json`、`prompts/sun_compat/direct_llm_sun_record_prompt.md`、`outputs/reports/s29_sun_d1_offline_prereg_v5.manifest.json` | v5 direct-LLM prompt 与统一六要素合同、模型/采样/重复/预算及失败保留合同；离线 verified，不代表真实调用 |
| S2.7-M baseline | `configs/models/s27_non_llm_baselines.json`、`outputs/reports/s27_non_llm_modality_baselines_seed20260717_v1.manifest.json` | 同一 S2.1 split 的多数类/固定关键词/Multinomial NB 聚合 component 结果；phrase/full Stage 2 未完成 |
| S2.2 annotation freeze | `outputs/reports/s22_estg150_human_annotation_freeze_v1.manifest.json` | exact-hash 绑定 Layer E 150/150、900/900 与 231 clauses；只表示 sentence-only English annotation frozen，不是 formal Gold publication |
| EStG-150 candidate protocol | `ESTG150_CANDIDATE_PROTOCOL_V1.md`、`configs/estg150_candidate_protocol_v1.json`、`.lock.json`、`configs/estg150_openai_strict_transport_schema_adapter_v1_1.json`、`data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_strict_v1_1_pilot_v1/`、`c1_relay_gpt54_nano_strict_v1_1_pilot_v1/`、`c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/` | canonical external serializer/分流/validation/C0 hash 保持 v1；gpt-5.6-luna C1 为 canonical-valid，gpt-5.4-nano C1 因 exact-span 越界 fail closed；C2 六请求 offline prep 已冻结但未启动；P/R=null，不声称独立验证 relay 模型身份 |
| Gold | `HUMAN_GOLD_*`、`ANNOTATION_PROTOCOL.md`、`ESTG150_DATA_MAP.md` | 审核规则和数据映射 |
| 研究证据 | `research/` | Sun、Winter、Barrientos 的来源核查；不是任务入口 |
| Agent 派工 | `AGENT_RUNBOOK.md` | 静态任务卡与 Prompt；实时派工仍在 `PROJECT_AUDIT.md` |

旧状态、旧交接、旧路线和旧 changeset 统一在 `_retired/docs/` 与
`_retired/changes/`，不再在 `docs/` 建 `history/` 或 `changes/` 平行入口。

## 5. 脚本目录

| 类别 | 典型脚本 | 作用 |
|---|---|---|
| 完整性与日志 | `audit_project.py`、`record_change.py`、`status.py` | 快速检查、全测凭证、追加事件 |
| 目录维护 | `generate_file_catalog.py` | 重建中文逐文件目录，不读取 `.env` |
| 人工 Gold | `build_*review*`、`validate_*review*`、`estg150_simple_review_tool.py`、`estg150_review_tool.py`、`verify_estg150_s22_freeze.py` | 构建、极简 Sol 修改、疑难高级审核、验证五层数据与生成 no-overwrite S2.2 annotation-freeze receipt |
| Stage 1 | `run_stage1_structural.py`、`run_stage1_label_semantics.py`、`build_stage1_annotation_protocol.py`、`evaluate_stage1_s16.py` 及对应 `verify_*`；`build_stage1_gdpr7.py`、`verify_stage1_stage3_gdpr7.py` | 前四类入口保持 synthetic 合同验证；GDPR7 专用入口在用户批准的独立 membership gate 下读取 7 个正式 BPMN、生成空白审核材料，不生成 Gold/性能结果 |
| Stage 2 | `check_sun_baseline.py`、`run_sun_rule_only.py`、`run_sun_llm_fallback.py`、`run_direct_llm.py`、`evaluate_stage2_s210.py` | baseline/LLM 方法入口与统一离线 evaluator；formal scope 受总门禁保护 |
| Stage 3 | `audit_stage2_to_stage3.py`、`run_stage3_fixture_harness.py` | 适配与离线 fixture 验证 |
| Layer D | `run_llm_zh_aid.py`、`validate_layer_d_v2.py`、`promote_layer_d_v2.py` | 中文辅助层；真实调用必须先获授权 |
| EStG-150 canonical AI 候选 | `run_estg150_candidate_protocol.py` | C0–C4 唯一活动入口；canonical serializer/分流/本地 validation 共享，C1 transport 可使用明确版本化派生 schema；默认 dry-run，capability/schema 在 key/network 前 fail closed，真实调用另授权 |
| EStG-150 历史 relay runner | `run_estg150_ai_review.py` | 仅保留历史 helper/回归；真实执行已 fail closed 退役，不能作为第二套 provider pipeline |
| EStG-150 内置 Sol 汇总 | `build_estg150_internal_sol_bundle.py` | 离线合并并严格校验内置 Sol 子代理的 150 条候选；检查 sample 顺序、exact span、关系和明显规范性 cue 覆盖；不读写 Layer E |

`_retired/scripts/` 中的脚本只服务于已退役文件，不属于活动命令集合。

## 6. 代码与测试

- `src/bpc_hybrid/`：Stage 1/2/3 业务实现、Sun 风格规则、LLM 接口、评价和 schema；S1.1/S1.2/S1.4 是 `stage1_process.py`，S1.3 P0/P1 是 `stage1_label_semantics.py`，S1.5 blank human protocol 是 `stage1_human_annotation.py`，共享 GDPR7 membership/正式解析激活是 `stage1_formal_dataset.py`，S1.6 evaluator 是 `stage1_evaluation.py`；S2.7-M component baseline 是 `sun_style/non_llm_modality_baselines.py`，S2.9 D1 离线合同是 `sun_style/d1_direct.py`，S2.10 evaluator 是 `stage2_evaluation.py`，S2.12-P 统计/错误分析是 `s212_analysis.py`，旧 `evaluator.py` 仅为历史 synthetic 原型。
- `src/formal_experiment/`：项目路径、合同状态、完整性检查和 EStG-150 审核服务；
  `estg150_candidate_protocol.py` 保持 canonical serializer/response validation，
  `estg150_c1_transport.py` 负责独立版本化 strict transport derivation、递归 preflight 与
  七模型 capability fail-closed；
  `s2_2_freeze_gate.py` 对 Layer E、membership、schema、validator、verifier、receipt 与
  contract 做 fail-closed exact-hash 复核，但不解锁 formal Gold 或正式方法运行。
- `paper/`：论文连续工作稿和主张证据矩阵；不能反向定义实验状态。
- `tests/fixtures/`：离线 BPMN、Sun-compatible、few-shot 等固定样例。
- `tests/test_*.py`：所有活动回归测试；归档材料若仍承担历史防回归证据，测试必须
  明确从 `_retired/` 读取并标注“历史证据”。

修改文件集合后运行 `python scripts/generate_file_catalog.py` 重建目录；只检查是否
过期可运行 `python scripts/generate_file_catalog.py --check`。

## 7. 新文件应该放哪里

- 新活动实现进 `src/`，命令入口进 `scripts/`，测试进 `tests/`。
- 论文正文、TODO 和主张矩阵进 `paper/`；正式结果只从 manifest 定向回填。
- 新研究证据进 `docs/research/`；新的当前规范直接更新已有活动文档。
- 临时输出进 `.tmp/` 或 `outputs/development/`，不得混进 formal 数据目录。
- 被替代但需要追溯的文件迁入 `_retired/`，同步更新 `_retired/MANIFEST.md`、
  `FILE_CATALOG.md` 和实验日志；恢复时需要用户批准。
- 不确定去向时先查本文和 `MANIFEST.md`，不要新建平行 status、handoff、pipeline、
  history 或 changes 目录。
