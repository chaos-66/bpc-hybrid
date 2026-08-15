# 项目实时状态（兼容文件名 PROJECT_AUDIT.md）

**更新时间**：2026-08-15
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

用户于 2026-08-01 确认：B0（Rules-Only）采用 `method-level independent
reconstruction` 口径，满足 Sun 核心组件、处理顺序、统一输入输出和统一 evaluator
后可进入正式结论；不再要求作者原代码、原权重、完整私有词典或论文绝对数值一致。
B0-R0–R5 已全部完成（各批次 verified，R5 正式结论包 2026-08-11 交付；Rules-Only 正式 arm 已发布并独立验证）。当前真实主线为：**S2.11/G0.5 外部复杂语料资格与映射 → S2.12 full DoD → S2.13 freeze → 用户裁决并冻结 9 个 GDPR Gold Rule Records → S3.4–S3.6 formal promotion → S3.7 单独授权**；S3.7 授权句仍未生成。

**2026-08-08 导师汇报确认（详见 `MASTER_PIPELINE.md` §8.8）**：
1. **Rules+LLM-Repair（旧代号 H1）不再深究，仅作对照**——全量 150 运行主口径
   F1 0.7621 vs Rules-Only 0.7986（净负），机制正常但 trigger+repair 配方加 FP
   不加召回；S2.8 正式 trigger 预注册取消；
2. **Rules-Only / Direct-LLM 局限性**已列表+举例写入 §8.8.2（含 B0 字段归属错误、
   词典缺口、Sun-marker 口径差异；D1 constraint 召回弱、actor 泛化误抽、保守漏抽）；
3. **命名直观化**：B0→**Rules-Only**（纯规则法）、H1→**Rules+LLM-Repair**（规则+
   LLM 修复）、D1→**Direct-LLM**（直接 LLM）；机器 ID 不变；
4. **与 Barrientos et al. (2026) 严格对比 + 贡献细模块化**：Direct-LLM 拆 8 模块、
   Rules-Only 拆 7 模块；消融矩阵 AB-1..AB-10 待跑（我的模块 vs 换 Barrientos
   模块 vs 去掉模块）；论文方法章节目标 4–5 页。

根据导师最新要求，论文非结果章节从现在与实验并行：先写引言、相关工作、方法、
数据/标注流程和实验设计；结果、摘要结论和“LLM 优势”只保留显式 TODO，直到正式
manifest 解锁。论文工作稿位于 `paper/`，不能反向定义实验状态。

## 2. 当前门禁

| 门禁 | 当前值 | 含义 |
|---|---:|---|
| `integrity_pass` | true | 2026-07-31 G0-EOL-HASH-PORTABILITY 后机器检查通过：合同显式声明 `source_manifest.hash_mode=canonical_lf_utf8_text`，gate 对该受控文本按 CRLF→LF 归一化验证，LF/CRLF 工作树均可验证同一受控内容；未声明资产仍按原始字节 |
| `formal_capsule_versioned` | true | `formal_experiment/` 已进入 Git checkpoint `bfb0b8a`；不代表 input/Gold/结果已冻结 |
| `sun_modality_development_data_verified` | true | S2.1-D 门禁恢复通过；2,831 行 analysis population、quarantine、split 与许可边界均未变 |
| `public_marker_lexicon_verified` | true | S2.3 英文 public-source v1 的 64 个 marker、来源/生成/hash/空扩展表通过离线机器门禁；development-only，未激活 S2.4+ |
| `human_review_input_ready` | true | Layer E 输入门禁已满足；历史 "0/150 可开始"语义不等于当前审核进度 |
| `human_review_freeze_ready` | true | 150/150 adjudicated（2026-08-06 经授权恢复）；freeze validator 通过，仍不足以发布 formal Gold |
| `formal_gold_publication_ready` | **true** | 用户 2026-08-10 按 formal_gold_authorization_packet_v2 授权：stage3.status=locked、publication gate=ready_for_formal_gold_publication（白名单精确匹配）、freeze_policy 重锁（治理/许可/禁止约束保留）；formal Gold 已发布（尚不代表 S1.7/S2.13/Gold Rule-Process Records/Oracle/最终实验完成） |
| `final_experiment_ready` | **true（仅机器门禁）** | 正式方法、冻结输入/Gold 与三方法正式 capsule 机器门禁就绪；**仅代表 Stage 2 三方法正式评价/最终指标机器门禁就绪，不代表 S2.13、S3.7 或完整 MASTER_PIPELINE 完成**（2026-08-15 过渡核账：S2.13 仍 blocked、正式 Oracle 未启动未授权，见 `outputs/reports/s2_13_s3_7_transition_readiness_v1.json`） |

每次修改后的最新值以机器检查输出为准；若本表与机器检查冲突，以机器检查为准并
立即修正本页。

## 3. 已有资产与真实边界

| 资产 | 当前状态 | 允许的表述 |
|---|---|---|
| EStG-150 五层审核工作流 | annotation frozen，150/150 adjudicated；formal Gold 已发布（2026-08-10，Gold publication subtask） | LLM-assisted、human-adjudicated Gold；不得在 publication gate 前称 formal Gold |
| 现有 `sun_rule_only` | **B0-R0–R5 全部 verified（2026-08-11）**：`method_conformance_status=verified_method_level_independent_reconstruction`（2026-08-04 用户授权）；`formal_status=ready`、`command_status=formal_ready_candidate_authorized`（2026-08-10 用户授权）；正式 arm 已发布 （`data/predictions/b0_formal_arm_v1`，claim_scope=formal，独立 verifier VERIFIED）；正式三方法比较报告 与正式结论包已交付；`sun_stage2_baseline_not_paper_faithful` blocker 已按设计解除 | 历史 provenance：B0-R0 组件集成 → R1 七子批次实测（ACTION/ALIGN/ACTOR 等）→ R2 method crosswalk → R3 快照（细 Gold F1 0.71865 / 粗 0.7986）→ R4 formal candidate + 方法门禁授权 → R5 正式结论；runner 仍是 development reconstruction，禁止声称 Sun original/exact reproduction |
| Rules-Only（旧代号 B0；BERT-TextCNN + CoreNLP/Tregex/Tsurgeon） | B0-R0–R5 verified（R1 七子批次闭环 2026-08-04；R2 method-level conformance 用户授权 2026-08-04；R3 56d2b03 快照细 Gold F1 0.71865、句子级粗 Gold 主口径 F1 0.7986（2026-08-07 用户决策口径对齐 Sun）） | 允许方法级独立复现（非 exact）；B0 v10 code/config/CoreNLP bridge/runner 已纳入 main，旧 heuristic 不再冒充 B0 入口；audit 区分 component presence（pass: `b0_paper_faithful_components_present`）与 method conformance（pass: `verified_method_level_independent_reconstruction`，2026-08-04 用户授权，见 `configs/methods.json` 与 docs/B0_R2_METHOD_CROSSWALK.md）；441MB checkpoint / CoreNLP jar / Legal-BERT cache 仍为 external runtime prerequisites（未提交、未下载） |
| Rules+LLM-Repair（旧代号 H1；Sun + LLM fallback） | **对照方法（2026-08-08 用户确认，不再深究，§8.8.1）**；development 机制与全量 150 运行（commit 74614e3）：主口径 F1 0.7621 vs Rules-Only 0.7986（净负）、LLM 修复过度抽取 actor（P 0.7077→0.2754、spans 65→167） | runner 强制读取并 SHA 绑定落盘 B0，不再内部重跑；field-level patch 原子应用并记录 accepted/rejected/no-op（103 accepted / 89 changed / gate=True / 0 incidents）；机制正常但 trigger+repair 配方加 FP 不加召回 → 论文中仅作对照臂，不作贡献 |
| Direct-LLM（旧代号 D1；direct LLM） | 历史分支 development run 已登记 P/R；D1-R0 整合 verified、D1-R1 四子批次 verified（150 全量 F1 0.7735、constraint R 0.4172、0 事故）、**D1-R2 锁定 verified（2026-08-06）**（v6 prompt sha 3aa64877 固定、deepseek-v4-pro/temp0/top_p1/4096、预算合同，见 `configs/models/estg150_d1_active_registry_v1.json`）、**D1-R3 快照重跑 verified（2026-08-06）**（细 Gold F1 0.7756 / P 0.8793 / R 0.6938，0 事故）、**句子级粗 Gold 归因 verified（2026-08-07，用户决策口径对齐 Sun，粗 Gold 为主口径）**（F1 0.8726，与 B0 同 Gold 同口径）；**主方法（2026-08-08 导师汇报后确认，§8.8.4）**；**formal arm 已正式发布（2026-08-11，`direct_llm_formal_arm_v1`，zero-API 绑定 D1-R3 snapshot，独立 verifier VERIFIED）；正式三方法比较覆盖 D1** | 可引用为历史开发证据与 D1-R1/R2/R3 development 结果及归因实验；不得冒充当前冻结 capsule 的正式指标；贡献细模块化（8 模块）与消融矩阵 AB-1..AB-10 见 §8.8.4 |
| Stage 1 | S1.1-S1.6 合同/解析/标注协议/评价器资产已从 56d2b03 checkpoint 恢复并重新绑定（2026-08-08）；37 项 stage1 测试全绿；audit pass：`stage1_structural_process_record_verified`/`stage1_label_semantics_p0_p1_verified`/`stage1_annotation_protocol_verified`/`stage1_evaluator_contract_verified`。**S1.5 人工裁决 7/7 批全部完成并正式冻结发布（2026-08-13）**：7/7 records adjudicated、135/135 label fields resolved、7/7 structures accepted_candidate、142/142 human decisions resolved、0 unresolved；七批链式 verifier（blank→b1..b7→磁盘逐位）VERIFIED；用户明确授权冻结（授权 manifest `s1_5_process_gold_freeze_authorization_v1.manifest.json`）；**正式 Stage 1 Process Gold 已发布**（`data/gold/stage1/process_records/stage1_process_gold_v1.json`，独立 verifier `verify_stage1_process_gold.py` VERIFIED）。**S1.3 P2 + S1.6 正式评价（2026-08-13）**：P2=Sun/Leopold-style 方法级重建（跨walk+锁定 config/实现/runtime），P0/P1/P2 正式评价完成（P2 语义 micro F1 0.8185）；**claim 已纠正（2026-08-13 纠错）**：target-overlap 审计（历史 3 条重合、当前 0）+ claim correction v2（target-aware、strict_test_blind=false、held-out 泛化禁止、fixed-GDPR7 描述性组件评价）+ 正式 v2 路径（`data/predictions/stage1_formal_v1/`、`data/results/stage1_formal_v1/`）；audit pass `stage1_formal_evaluation_verified`/`stage1_claim_correction_verified`；**S1.7 正式冻结已完成（2026-08-13 用户明确授权）**：授权 manifest `s1_7_freezer_authorization_v1.manifest.json`（P2 锁定方法/P0-P1-P2 预测/原始指标/Stage 1 Process Gold/评价 capsule 全部冻结；未改 P2、未选择性重算、零 LLM-API、未授权 Stage 3 Oracle）；audit pass `stage1_s7_freeze_authorized`；S3.7 Oracle 仍须经 Stage 3 独立门禁 | 合成 BPMN 上验证的 development 合同与机制；S1.5 正式 Process Gold 已冻结发布（2026-08-13）；S1.3/S1.6 verified（target-aware claim）；S1.7 frozen（2026-08-13 用户授权）；S3.7 Oracle 待 Stage 3 独立门禁 |
| Stage 3 | **S3.1 verified（2026-08-08）**：7 个 Winter-provenance GDPR BPMN 以 byte-exact（LF）恢复至 `data/input/stage1_stage3/gdpr7/`；合同 `stage1_stage3_gdpr7_v1.json` hash 全匹配；`verify_stage1_stage3_gdpr7.py` 通过（7 byte-exact、45 activities、135 blank label fields）；audit pass `stage1_formal_bpmn_membership_locked`（claim=all-seven extension，非 Sun 原 4）。**S3.2/S3.3 decision Gold 已发布（2026-08-10，随 formal Gold publication）**：matching 25 条 + violation 33 条（`data/gold/stage3/stage3_matching_gold_v1.json` / `stage3_violation_gold_v1.json`，与 frozen correction `3310d624…` 一致，冻结 manifest `s32_s33_gold_annotation_freeze_v1.manifest.json`）；**这些 matching/violation decisions ≠ Gold Rule Records**。**S3.4/S3.5/S3.6 development verified（2026-08-08，DEV_ONLY，evidence capsule 已版本化）**：Winter wrapper / Sun Def 4-7 重建 / BM25 v3 + TF-IDF-SVD baseline；**S1.7 依赖已满足（2026-08-13 frozen），formal completion 仍 blocked on S2.13**。**S3.7 formal Oracle 未启动、未授权**（2026-08-15 过渡核账：`formal_oracle_started=false`、`formal_oracle_authorized=false`、`ready_for_oracle_authorization=false`、`authorization_sentence=null`、`no_pseudo_oracle=true`；9 个 GDPR rule IDs article6/7/15/16/17/20/22/33/34 的正式 Gold Rule Records 不存在，本轮未创建/未推断） | S3.1 文件名/hash/claim 已固定；S3.2/S3.3 decision Gold 已发布（非 Gold Rule Records）；S3.4-S3.6 为 development baseline，尚未进入 formal Oracle 主表；正式 Oracle 待 S2.13 + 人工 Gold Rule Records + S3.4-S3.6 formal promotion + 用户单独授权 |
| 正式结果目录 | **Stage 2 三方法正式 capsule 已冻结发布**（`data/predictions`、`data/results` 下 `*_formal_arm_v1`，claim_scope=formal，独立 verifier 全过）；**Stage 3 formal 结果未冻结** | 禁止把 development Stage 3 数字写成 formal；不得声称 Stage 3/端到端最终实验结果 |
| Sun modality development 数据 | verified；2,831 analysis rows | 只允许本地 development 使用；许可未知、禁止再分发，不是 Sun original split |
| public marker lexicon v1 | verified；7/25/19/5/8，共 64 个 | 英文 public-source reconstruction、development-only；不是 Sun original/full lexicon，不能据此训练或评价 |

Sun 最终版、公开数据、引用链和代码来源证据统一放在 `docs/research/`；历史路线和
过期交接统一放在 `_retired/docs/2026-07/`，不得再作为实时指令。

### 3.1 历史分支 D1 Precision/Recall 登记

来源：`experiment/paper-validation-r1` 的 commit `b5f05b8`，run
`s28_s29_deepseek_v4pro_sun_literal_v1`，150 samples，repeat=1。指标文件 canonical-LF
SHA-256 为 `25628188f17eae054b2537aa1f1bef562bcd6a35995b7b03f263e0a1836ab4bc`。

| 字段 | Precision | Recall |
|---|---:|---:|
| Overall | 90.68% | 66.45% |
| Action | 95.02% | 85.02% |
| Actor | 59.42% | 87.50% |
| Condition | 91.11% | 69.16% |
| Constraint | 84.54% | 28.81% |
| Exception | 100.00% | 38.46% |
| Modality evidence span | 97.27% | 90.48% |

口径是 `sun_table8_literal_overlap_evaluation@2.0.0`：statement 级、同字段任意非空
字符交叠、无 clause alignment、无一对一 assignment；`modality` 忽略类别标签，只看
evidence span。Overall F1=76.69%，`invalid_attempt_count=1`。manifest 状态仍是
`succeeded_development_not_formal`；本登记未重跑模型、未调用 API，也未将该结果提升为
当前 formal capsule。

## 4. 当前工作队列

当前真实下一路径（2026-08-15 核账，唯一执行顺序；S3.7 授权句仍未生成）：

1. **S2.11/G0.5**：外部复杂语料资格、3→4 标签映射与人工 Gold 门禁（需用户决策/授权）；
2. **S2.12 full DoD**（预注册分层与错误类型）；
3. **S2.13 Stage 2 冻结**（DoD 不变）；
4. **用户裁决并冻结 9 个 GDPR Gold Rule Records**（article6/7/15/16/17/20/22/33/34；Agent 不得创建/推断）；
5. **S3.4–S3.6 formal readiness/promotion**（S1.7 已满足）；
6. **S3.7 formal Oracle 单独授权**（authorization_sentence 仍为 null）。

下表为历史完成记录（provenance）。

| 顺序 | Pipeline 任务 | 当前动作 | 完成信号 |
|---:|---|---|---|
| 1 | P0 / G0.6 | **已完成**：主 Pipeline、日志/检查制度与 Git checkpoint 有回归测试保护；G0-TEST-REAL-BACKUP-SNAPSHOT 后全量测试 0 failed（1048 passed, 24 skipped） | Agent 入口、目录、日志字段和自动检查已固定；checkpoint `bfb0b8a` 可追踪；真实用户备份由 session 级只读快照守卫保护（允许预先非空，要求 session 前后 byte-identical） |
| 2 | S2.1-A | **verified**（2026-07-15 字节核验通过）| raw 字节已 byte-match：size 191,874,718、SHA-1 `0346f84a246b7049d5aef58bcb33471435bee106`、ZIP integrity testzip 通过、3 个预期成员全部存在且路径安全、EStG_raw.txt SHA-256 与 2026-07-11 审计记录一致；许可仍 `unknown_pending_confirmation`（B2 仍 open），B1 已 resolved。S2.1-B 可派发但本轮不实际进入 |
| 2.1 | S2.1-B | **verified**（2026-07-15；R1 contract repair） | 合同/schema/importer/CLI/15 个 synthetic fixtures 已修正：显式 source ID 重复 fail closed；无 ID 时显式 row-index fallback 并入 manifest；normalized-text group-aware split；标签冲突 `label_conflict` fail closed；唯一小类别阈值为 3 个 group；ZIP SHA-1/SHA-256 独立核验；5 个确定性文件含 manifest byte-identical；manifest 不含运行时、self-child 或 placeholder；synthetic one-hot 与 official pending schema 分离。R1 定向测试 54 passed；首次全量检查 840 passed, 22 skipped，0 integrity errors |
| 2.2 | S2.1-C | **verified — R1 pre-result conflict quarantine + development import**（2026-07-16） | raw 2,833 行、CSV 字节和原标签均未修改；只有精确匹配 source/normalized/raw-text hash、row 616/1221、逐行 permission/obligation 标签与 section hash 的唯一 group 被整体 quarantine。主 analysis population=2,831，分布 1190/1273/264/104；train/dev/test=1985/420/426，group-aware、无泄漏、并集完整；七个产物独立重放 byte-identical；sensitivity full-source variant 仅预注册未运行 |
| 3 | S2.1-B-R1 | **verified** | R1 合同与实现缺陷已修复并由后续真实数据与机器门禁回归保护 |
| 4 | S2.1-D / S2.1 | **verified / overall verified** | manifest 路径已项目相对化；独立 gate 交叉验证 ZIP、合同、schema、quarantine、records/splits、membership/artifact hash、ignore 与许可。records/split hash 未变；B2/B3 许可边界仍 open，formal Gold 与 final experiment 不解锁 |
| 5 | S2.2 | **verified（2026-08-06）**：150/150 adjudicated（用户 2026-07-18 裁决经授权从 56d2b03 恢复至活动 v2 文件，freeze validator 通过） | 150/150 adjudicated，freeze validator 通过 |
| 6 | S2.3 | **verified**：`public_marker_lexicon_en_v1` 已离线锁定；64 个 marker、source/manifest/payload hash、空扩展表和机器门禁通过 | 来源、规则、语言、hash 与 dev-only 扩展策略固定 |
| 6.1 | S2.4-S2.6 | **已覆盖（2026-08-11 核账）**：BERT-TextCNN 模态分类、CoreNLP/Tregex/Tsurgeon 抽取与完整 B0 流水线由正式 Rules-Only 方法（MASTER_PIPELINE §8.6）实现并验证；无独立剩余任务 | 正式三方法 capsule 与正式比较报告为证 |
| 6.2 | B0-R0–B0-R5 | **B0-R0 verified**（2026-08-02 commit 之后）：actor_action.py + 12 个 b0_v10 模块 + sun_style/lexicon_v2_runtime + estg150_b0_development v1/v2/v3/v10 + corenlp_runtime/sun_b0/bert_textcnn + stage2_evaluation v1/v3 + 7 个 v2 lexicon 资源 + SunPhraseRuleBatchBridgeMulti.java + sun_corenlp_runtime.json + sun_b0_s26_candidate_B_v1.json + sun_bert_textcnn_s24.json + estg150_b0_enhanced_s27_v10a.json + estg150_b0_v10_preregistration_v2.json + stage2_evaluator_s210_v3.json + stage2_prediction.schema.json + scripts/run_estg150_b0_enhanced_v10_development.py + test_b0_v10_integration_contract.py（15 验收点） 已纳入 main；audit 区分 component presence（pass）与 method-conformance（blocker，必须由 B0-R2 才能解除）；B0-R1 ready（后续 R2/R3/R4/R5 逐批 verified，2026-08-04 → 2026-08-11）；未运行 CoreNLP、未读 Gold/Layer E、未调 API、未改 D1/H1（历史批次当时状态）；先前 6341136 的 B0-R0-C0 仅依赖闭包，状态从误报 COMPLETE 修正为 verified，correction event 已追加。**B0-R1 五批已完成并实测**（2026-08-04，全部在隔离 worktree + 56d2b03 历史输入 + 真实 CoreNLP 下验证，主口径 sun_literal_overlap_evaluation@2.0.0）：R1-A..C3（token-safe span）→ E1/E2（主口径 evaluator + v10a/C3 重评：F1 0.71019/0.71024，旧 0.5398→0.5326 推翻）→ ERR（错误分析文档，docs/B0_ERROR_ANALYSIS.md）→ **ACTION**（F1 持平，质量收益：主语吞并 8→0、strict-exact 3×）→ **SCOPE-DISAMBIG**（候选实测 −0.0005 拒绝回退，记方法局限）→ **ALIGN**（伪 validated 消除 DoD 达成，主口径不变，label 面板 −0.48pp 记录代价）→ **BRIDGE**（`<`/`<<` 语义测试 + operated 多命中 fail-closed 守卫）→ **ACTOR**（clause 内全 nsubj 弧 + obl/by-to + 中心词词典校验；**主口径 F1 +0.0018，系列首个正向**，actor F1 0.616→0.670，8/8 词典内漏抽找回）。当前 B0-R3 快照细 Gold F1=**0.71865**（P 0.6845 / R 0.7564，用户条件授权为论文依据候选）；**2026-08-07 用户决策：评价口径对齐 Sun 句子级粒度，句子级粗 Gold（609 spans）为主口径，B0 粗口径 F1=0.7986（P 0.7309 / R 0.8801）、D1 粗口径 F1=0.8726（P 0.9012 / R 0.8456），细 Gold 降为对照口径**。B0-R2 method-conformance 已由用户授权解除（2026-08-04，`method_conformance_status`=`verified_method_level_independent_reconstruction`）；LEXICON-DECISION 已实施（2026-08-04 用户授权路径 b，13 名词入词典）；CLAUSE-REVIEW 已复核不改动；C7 过短边界留待正式 Gold 后按需再议。**S2.13 Gold publication subtask 已发布（2026-08-10，发布 manifest outputs/reports/formal_gold_publication_v1.manifest.json，确定性重放 + 34 项验证全通过）**；B0-R4 ready 核账：冻结输入/Gold/共享 evaluator/schema/normalization 齐备（zero-API 满足），剩余 blocker=缺 formal claim_scope 运行入口（现有 runner 硬编码 development）→ 本轮不执行重评；B0-R4 formal candidate **verified**（2026-08-10：Gold-blind runner 只读 formal input v2，150 条全量 + 双跑语义 byte-identical，主口径 F1 0.71865 与 B0-R3 快照逐位一致，promotion 已授权应用（2026-08-10 用户明确授权：methods.json sun_rule_only formal_status→ready、command_status→formal_ready_candidate_authorized，其余未动，零 API））；**B0-R5 verified（2026-08-11，正式结论包 stage2_formal_conclusion_v1）** | B0 方法级实现可重放、B0-R1 确定性缺陷逐批实测（正/负结果均记录）、变更均有日志和 Git checkpoint；修复后低分可作为正式负结果 |
| 6.3 | D1-R0–D1-R5 | **D1-R0 verified**（runner/prompt loader/canonical schema/s28_s29 产物 tracked 可重评）→ **D1-R1 verified**（2026-08-05，四子批次 FIELD-TYPING/PROMPT-CONTRACT/VERIFY-PASS/CLEAN-RERUN 闭环：v6= v5+规则25-27+示例5-6 KEEP；150 全量 0 事故，主口径 F1 0.7669→**0.7735**、constraint R 0.2881→**0.4172**，P 0.8799（−0.0269 披露 trade-off）；空不为错语义，坏 span/clause/边丢弃+审计）→ **D1-R2 锁定 verified**（2026-08-06）：`configs/models/estg150_d1_active_registry_v1.json` 固定 v6 prompt hash 3aa64877（磁盘/loader/manifest 三方一致）、模型钉死 deepseek-v4-pro、sampling temp0/top_p1/max_tokens4096、seed 策略 unsupported_or_omitted、transport 配方（thinking-disabled 无 json_object）、共享输入/evaluator hash、预算合同（逐批授权+`--max-calls` 硬上限 150）；12 项 lock-config 测试含 S2.9 Gold 不可见核查（6 个合成 fixture 与 150 测试句零交叠）；§8.5 S2.9 DoD（D1 侧）达成、整行仍 partial。**D1-R3 快照重跑 verified**（2026-08-06，用户授权 150 calls）：锁定配方逐项一致干净重跑，150/150 有效、0 事故；同一进程双评 R1/R3（sun_literal_overlap@2.0.0）R3 F1 **0.7756**（P 0.8793/R 0.6938）vs R1 0.7735（+0.0021，复现成功）；失败类型分析（1055 gold span：wrong_field 169 其中 constraint 100、not_extracted 154）见 docs/D1_ERROR_ANALYSIS.md §8；产物 outputs/development/s27_d1_v6_r3_clean_rerun_150_hist56d_v1/；**句子级粗 Gold 归因 verified**（2026-08-07，与 B0 同粗 Gold 同口径：F1 0.8726 / P 0.9012 / R 0.8456，见 outputs/development/s27_d1_coarse_gold_sentence_granularity_v1/）。**S2.13 Gold publication subtask 已发布（2026-08-10）**；D1-R4 ready 核账：冻结输入/Gold/共享组件齐备，剩余 blocker=LLM 调用授权与预算（本轮 zero-API 核账不调用 API、不伪造）→ 不执行；D1-R4 历史预测绑定核账（2026-08-10）：D1-R3 与 H1 的 150 条 predictions 与 formal input v2 逐项绑定（IDs/文本 hash/prompt/model/sampling/schema-valid 全过）→ zero-API candidate 重评允许；D1/H1 zero-API candidate 重评完成（2026-08-10，同 Gold/双口径视图/evaluators，comparison capsule outputs/evidence/d1_h1_zero_api_reeval_v1；D1 coarse 五字段与历史逐位一致；D1/H1 均 candidate/formal-gate-blocked，未写入正式目录）；2026-08-11 用户授权：D1/H1 门禁 ready（H1 为 comparison_arm_only），D1-R3/H1 snapshot 零 API 正式发布（direct_llm_formal_arm_v1 / sun_llm_fallback_formal_arm_v1，verifier 全过）；正式三方法比较报告完成（stage2_formal_three_method_comparison_v1），S2.10 verified（授权后 DoD），S2.12 描述性分析（retrospective），S2.11 dry-run + S2.13 gap capsule 已备；final_experiment_ready=true（fail-closed 条件真实满足，三方法 ready ≠ 全 Pipeline 完成）；D1-R5 verified（2026-08-11 正式结论包 stage2_formal_conclusion_v1） | D1-R3 experiment_run 事件 + 双评 evaluation JSON + audit --with-tests；150 次调用由用户逐批授权，manifest 记录 llm_calls/max_calls |
| 7 | S2.7-S2.12 | H1 development wiring 已修复；S2.8A/B/C development verified；S2.8D-R1 transport 离线修复 verified；S2.8D-R1 单次 v4-flash canary（硬上限 1、0 retry）因 span reference mismatch 被原子拒绝（valid=1、accepted=0、effective=0、gate=false、H1==B0），历史真实调用累计 41 次。**S2.8D-R2 离线取证**（0 real API calls）：3/3 被拒 span 为正确文本+错误坐标（clause 内唯一 exact match），结论=情况 A。**S2.8D-R3 已实现**（0 real API calls）：fail-closed unique exact-text coordinate canonicalization（`bpc_hybrid/h1_span_canonicalizer.py`，单一共享路径接入四模式；zero/ambiguous/contract 整 patch 拒绝；只改 start/end；仍过现有 validator 与 atomic merge）；同一 R1 capture 的 R3 离线 transport replay：reanchored 3/3、validator 通过、merge accepted、effective_patch=true、changed=1、**gate=true、H1!=B0**、identity 不变；R1 历史 strict 结果未改。**S2.8D-R4 真实 canary 成功**（1 real API call、retry 0，用户明确授权）：requested/resolved/returned=deepseek-v4-flash；HTTP 200、ok_message_content、reasoning=false、tool_calls=0、usage=1305/405/1710；非空 patch→canonicalizer reanchored 3/3（zero/ambiguous/contract=0）→canonical validator 通过→merge accepted→effective_patch=true、changed=1、**gate=true、H1!=B0**、identity 不变；离线 replay（s28d_r4_h1_canary_replay_v1）H1 sha 与真实运行一致、byte-identical；R1/R3 历史结果未改。**S2.8D-R5 已冻结**（0 real API calls、retry 0、未运行 pilot）：历史真实调用集合恢复=42 calls / 20 唯一 plan keys（sha c813a384…）；Gold-blind 确定性选样 10 个不同 sample plan（排除全部历史已调用 keys，复用现有 risk 排序）；frozen plan 配置 `configs/s28d_r5_h1_small_pilot_plan_v1.json`（sha 35dc6a75…，cap=10/retry=0/early-stop 合同）；runner `--frozen-plan` 严格绑定 fail closed + early-stop 实现（provider model / capture / count / plan key / 连续 3 次失败 abort；patch 级拒绝 continue）；plan-only 验证：selected=10/10、llm_calls=0、gate=false、H1==B0、execution order 与 keys hash 一致、历史交集空、byte-identical；新增 29 项测试（30 验收点），H1 focused 106 passed；默认行为不变。**S2.8D-R6 已执行**（用户明确授权，主真实命令仅一次）：实际 API calls=5（冻结 order 1–5：estg_000118/000133/000164/000206/000207），每 plan 1 次、retry=0、模型/capture 全对、无未冻结 plan；proposed=5、accepted=3、rejected=2、effective=3、changed=3、gate=true、H1!=B0=3、identity violation=0；canonicalizer reanchored 4/failed 1；usage 总 8976。**early stop 于 order 5 后误报 plan_key_mismatch**（R5 runner 计数缺陷，已修复+回归测试；真实调用无违规）；未调用 order 6–10 保留 not-called、不补跑。离线 replay（s28d_r6_h1_small_pilot_replay_v1，0 API calls）与真实运行逐项一致、byte-identical；机制最低可用门 passed=true。**S2.8D-R6C1 已补完**（用户授权只补 order 6–10；新增 actual API calls=5、retry=0、order 1–5 新调用=0、无 early stop）：estg_000232/000285/000302/000414 被拒（canonical_invalid+reference_mismatch）、estg_000716 accepted/effective；proposed=5、accepted=1、rejected=4、effective=1、changed=1、gate=true、identity violation=0；continuation replay 一致且 byte-identical；合并 R6+R6C1 为完整 10-plan capsule（s28d_r6_complete_h1_small_pilot_v1）：**10/10 覆盖 complete**、keys sha=bb8d73b2…、每 plan 一次、10 不同 sample；合并指标 calls=10、accepted=4、rejected=6、effective=4、changed=4、H1!=B0=4、identity=0、usage 总 18628。**formal S2.8 仍 blocked on S2.6；不得自动重试或进入完整 pilot** | 具备申请 S2.8D-R7（完整 10-plan Gold-blind 结果审计与受控 P/R 评价解锁准备）；P/R 仍 not_computed。**2026-08-08 H1 降级为对照（§8.8.1）**：全量 150 运行（commit 74614e3，用户授权 150 calls，deepseek-v4-pro）主口径粗 Gold F1 **0.7621 vs Rules-Only 0.7986（净负 −0.0365）**、细 Gold 0.6875 vs 0.7186；LLM 修复过度抽取 actor（P 0.7077→0.2754、spans 65→167），其余 5 字段持平或微升；机制正常（103 accepted / 89 changed / gate=True / 0 incidents）但 trigger+repair 配方加 FP 不加召回；证据支持决策 A（Direct-LLM 为主方法）；**H1 不再深究，仅作论文对照臂**；S2.8 正式 trigger 预注册取消 |
| 8 | S3.1 | **verified（2026-08-08）**：S1/S3.1 资产从 56d2b03 checkpoint 恢复（configs/schemas/data/docs/outputs/scripts/src/tests + 5 个 s1 gate 模块）；7 个 GDPR BPMN byte-exact（LF）落地并加入 `.gitattributes` eol=lf；修复 56d2b03 快照先存的跨任务 binding 过期（s13/s15/s16 合同 upstream hash、5 个 gate 期望、合同 stage1 块），manifest 按当前合同重新生成并全链更新；`verify_stage1_stage3_gdpr7.py` 通过；audit pass `stage1_formal_bpmn_membership_locked`；37 项 stage1 测试全绿 | 文件名、hash、claim 固定（合同 `stage1_stage3_gdpr7_v1.json` user-approved 2026-07-18 + 验证 manifest `s15_s31_gdpr7_membership_v1.manifest.json`） |
| 9 | S3.2/S3.3 | **annotation frozen（2026-08-08）**：58 条候选全部由用户裁决（matching 25=11 相关/14 不相关；violation 33=三类各 11）；裁决存 `data/development/human_review/stage3_gold_annotation_human_correction_v1.json`（decision 与 candidate 分离）；冻结 manifest `s32_s33_gold_annotation_freeze_v1.manifest.json`；工具：`review_stage3_gold_annotation.py`（交互/批量出题+导入）、`build/verify_stage3_gold_annotation.py`；**decision Gold 已发布（2026-08-10 随 formal Gold publication：matching 25 + violation 33，与 frozen correction 一致，≠ Gold Rule Records）** | 用户裁决完成；decision Gold 已发布；Gold Rule Records 另行人工裁决 |
| 10 | S3.4 | **development wrapper verified + 收口（2026-08-08）**：Winter baseline 转写 + 可移植重放（reachability 双模式、manifest 1.1.0、export index）；修复后重放 v3_clean/v3_prototype_literal（inference pack check_type 路由）；DEV_ONLY：MAP 0.6429、binary F1 0.6111、violation macro 0.373；evidence capsule `outputs/evidence/s34_winter_stage3_development_v3_clean|prototype_literal/`；S1.7 依赖已满足（2026-08-13 frozen）；formal completion blocked on S2.13 | 正式 canonical I/O + reproducible command（DoD 正式完成仍 blocked on S2.13；S1.7 已满足） |
| 11 | S3.5 | **development implementation verified（2026-08-08）**：Sun Def 4-7 重建 + 证据修复（inference pack/check_type/Def 6 存在性语义/unobservable 口径/sensitivity 真实重算）；run v2（不覆盖 v1，before/after 对照：unobs 33→10、macro 0.333→0.389、exact 0.333→0.364）；DEV_ONLY：MAP 0.8175、binary F1 0.0 如实；evidence capsule `outputs/evidence/s35_sun_stage3_development_v2/`（含 5 方法 comparison）；S1.7 依赖已满足（2026-08-13 frozen）；formal completion blocked on S2.13 | 不再是 fixture approximation；formal Oracle 主表待 formal Gold 门禁 |
| 12 | S3.6 | **development baseline verified（2026-08-08）**：BM25 + TF-IDF/SVD 双 arm；sensitivity 修复（gamma/theta 重实例化 scorer 重算，v2 runs 主指标与 v1 byte-identical）；DEV_ONLY：BM25 MAP 0.6833/macro 0.333；TF-IDF MAP 0.5881/macro 0.542；evidence capsule v2；阈值 0.5=fixed development setting（非 blind preregistration）；S1.7 依赖已满足（2026-08-13 frozen）；formal completion blocked on S2.13 | 相同 Gold/evaluator；正式 baseline 待 formal Oracle 门禁 |
| 12.1 | S2.13→S3.7 过渡核账 | **完成（2026-08-15，过渡控制 capsule v1）**：`outputs/reports/s2_13_s3_7_transition_readiness_v1.{json,md,manifest.json,export_index.json}` + schema + builder + 独立 verifier + 14 项聚焦测试——依赖矩阵从磁盘资产/manifest/hash/实际执行的 7 个独立 verifier 逐项重推导（S1.7=frozen、S2.10=verified、S2.11=blocked、S2.12=partial/retrospective、S2.13=blocked、S3.4-S3.6=development_only）；Stage 1 Process Gold 与 Stage 3 matching/violation decision Gold 均存在且 verifier 通过；9 个 GDPR Gold Rule Records 不存在；Oracle 控制全 false；旧报告（s2_13 gap capsule、s3_7_oracle_readiness_v2、s37_oracle_readiness_v1、release v2 历史 exclusions、两个旧 builder）声明 supersede 但文件逐字节保留；audit.py 陈旧尾部改为动态措辞并消除真假矛盾；零 gate 翻转 | 独立 verifier VERIFIED；14 项聚焦测试通过；全量 audit --with-tests 通过 |
| 13 | S2.13 | **blocked（2026-08-15 核账）**：Stage 2 冻结 DoD（S2.1–S2.12 完整）未达成；精确 blockers：S2.11 blocked（外部复杂语料许可 unknown_pending_confirmation、数据激活授权未授予、3→4 标签映射未裁决、人工 Gold 未开始、G0.5 复杂度规则未冻结、Barrientos adapter 未实现）+ S2.12 full DoD 未达成（仅 retrospective 描述性部分）；`final_experiment_ready=true` 不代表 S2.13 完成；DoD 未改、未拆新任务 | 数据、方法、Gold、指标、成本、manifest 完整（全部达成前保持 blocked） |
| 14 | PW1 | **下一论文任务**：引言与 RQ0–RQ4 | 无结果性过度主张；主张矩阵同步 |

Stage 1 和 Stage 3 的后续任务见主 Pipeline §8.9：S3.1-S3.3 数据治理及明确标注的
development 准备可受控并行；Stage 3 LLM/Hybrid、正式 Oracle、端到端均不得抢跑。

## 5. 当前派工

| 角色 | 任务 | 状态 | 写入范围 | Prompt |
|---|---|---|---|---|
| 协调 Agent | 维护门禁、验收和日志 | in_progress | shared docs/log only | `docs/AGENT_RUNBOOK.md` §§1–3 |
| Agent-E1 | S2.1-A 官方数据来源证据 | **verified** (2026-07-15 字节级核验通过；许可仍 unknown_pending_confirmation；B2 仍 open) | `data/development/sun_modality/`、`docs/research/SUN_MODALITY_DATASET_INGESTION.md`、manifest、`scripts/verify_sun_modality_zip.py`、tests | §4.1 |
| 当前执行 Agent | S2.13→S3.7 过渡核账与 readiness 维护（2026-08-15） | **完成**：v1 capsule 已提交 （5d57430）；v2 capsule 收敛 verifier-completeness / fail-closed 保证（三态 GRR 探测、manifest/export 精确重建、严格 verifier 判定），v1 文件逐字节保留 | 只写 `formal_experiment/` 内 capsule/docs/scripts/tests；未改 Gold/合同/门禁，零 LLM/API | 下一真实路径：S2.11/G0.5 → S2.12 → S2.13 → Gold Rule Records （用户）→ S3.4–S3.6 → S3.7 单独授权 |
| Agent-P1 | PW1 引言与研究问题 | ready | `paper/THESIS_DRAFT.md`、主张矩阵 | §4.2 |
| Agent-R1 | 论文科学主张只读复核 | blocked on PW1 draft | 无写入 | §4.3 |
| 用户 | S2.2 Layer E 人工裁决 | verified，150/150 adjudicated | 仅 Layer E | freeze validator 通过；formal Gold 已于 2026-08-10 发布（用户授权）；Gold Rule Records 另行裁决 |

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
- S2.8D-R2 canary span/offset 取证：`docs/research/S28D_R2_CANARY_OFFSET_FORENSICS.md`、`docs/research/S28D_R2_CANARY_OFFSET_FORENSICS.json`
- S2.8D-R3 coordinate canonicalization：`docs/research/S28D_R3_COORDINATE_CANONICALIZATION.md`、`docs/research/S28D_R3_COORDINATE_CANONICALIZATION.json`
- Sun baseline 边界：`docs/research/SUN_BASELINE_AUDIT.md`
- Winter/Sun 代码分离：`docs/research/SUN_WINTER_CODE_SEPARATION_AUDIT.md`
- Barrientos 借用边界：`docs/research/BARRIENTOS_BORROWING_AUDIT_2026-07-12.md`
- 历史交接：`_retired/docs/2026-07/CURRENT_HANDOFF_2026-07-12.md`
- 追加式实验日志：`docs/EXPERIMENT_LOG.md`、`docs/EXPERIMENT_EVENTS.jsonl`
- Agent 派工与 Prompt：`docs/AGENT_RUNBOOK.md`
- S2.13→S3.7 过渡核账（2026-08-15）：`outputs/reports/s2_13_s3_7_transition_readiness_v1.json`（+ `.md` / `.manifest.json` / `_export_index.json`；schema `configs/schemas/s2_13_s3_7_transition_readiness.schema.json`；builder `scripts/build_s2_13_s3_7_transition_readiness_v1.py`；verifier `scripts/verify_s2_13_s3_7_transition_readiness_v1.py`；测试 `tests/test_s2_13_s3_7_transition_readiness_v1.py`）
- 历史（superseded 当前状态判断，文件保留）：`outputs/reports/s2_13_stage2_freeze_gap_capsule.{json,md}`、`outputs/reports/s3_7_oracle_readiness_v2.json`、`outputs/reports/s37_oracle_readiness_v1.json`
- 论文工作稿与主张矩阵：`paper/THESIS_DRAFT.md`、`paper/CLAIM_EVIDENCE_MATRIX.md`
