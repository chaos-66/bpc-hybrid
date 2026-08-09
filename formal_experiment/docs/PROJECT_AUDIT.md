# 项目实时状态（兼容文件名 PROJECT_AUDIT.md）

**更新时间**：2026-08-08
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
当前仍先执行 `MASTER_PIPELINE.md` §8.6 的 B0-R0–B0-R5，排除确定性代码错误后才
重跑并解释低分。

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
| `formal_gold_publication_ready` | false | route/data/stage3/Gold 尚未共同重锁 |
| `final_experiment_ready` | false | 正式方法、冻结数据与最终实验均未就绪 |

每次修改后的最新值以机器检查输出为准；若本表与机器检查冲突，以机器检查为准并
立即修正本页。

## 3. 已有资产与真实边界

| 资产 | 当前状态 | 允许的表述 |
|---|---|---|
| EStG-150 五层审核工作流 | annotation frozen，150/150 adjudicated；formal publication 仍 blocked | LLM-assisted、human-adjudicated Gold；不得在 publication gate 前称 formal Gold |
| 现有 `sun_rule_only` | B0-R0 集成（component presence verified）；B0-R1 ready；方法级一致性仍 blocked_until_b0_r2 | 旧 heuristic 不再冒充 B0 入口；`run_b0_batch_v10` + 完整 v10 runner script + S2.6 candidate B + CoreNLP bridge + 离线 contract 与 pattern registry 已纳入 main；未跑 ESTG-150 正式实验；`sun_stage2_baseline_not_paper_faithful` 仍为 blocker，仅 B0-R2 完成方法对照表后才能解除 |
| Rules-Only（旧代号 B0；BERT-TextCNN + CoreNLP/Tregex/Tsurgeon） | B0-R0–R3 verified（R1 七子批次闭环 2026-08-04；R2 method-level conformance 用户授权 2026-08-04；R3 56d2b03 快照细 Gold F1 0.71865、句子级粗 Gold 主口径 F1 0.7986（2026-08-07 用户决策口径对齐 Sun）） | 允许方法级独立复现（非 exact）；B0 v10 code/config/CoreNLP bridge/runner 已纳入 main，旧 heuristic 不再冒充 B0 入口；audit 区分 component presence（pass: `b0_paper_faithful_components_present`）与 method conformance（pass: `verified_method_level_independent_reconstruction`，2026-08-04 用户授权，见 `configs/methods.json` 与 docs/B0_R2_METHOD_CROSSWALK.md）；441MB checkpoint / CoreNLP jar / Legal-BERT cache 仍为 external runtime prerequisites（未提交、未下载） |
| Rules+LLM-Repair（旧代号 H1；Sun + LLM fallback） | **对照方法（2026-08-08 用户确认，不再深究，§8.8.1）**；development 机制与全量 150 运行（commit 74614e3）：主口径 F1 0.7621 vs Rules-Only 0.7986（净负）、LLM 修复过度抽取 actor（P 0.7077→0.2754、spans 65→167） | runner 强制读取并 SHA 绑定落盘 B0，不再内部重跑；field-level patch 原子应用并记录 accepted/rejected/no-op（103 accepted / 89 changed / gate=True / 0 incidents）；机制正常但 trigger+repair 配方加 FP 不加召回 → 论文中仅作对照臂，不作贡献 |
| Direct-LLM（旧代号 D1；direct LLM） | 历史分支 development run 已登记 P/R；D1-R0 整合 verified、D1-R1 四子批次 verified（150 全量 F1 0.7735、constraint R 0.4172、0 事故）、**D1-R2 锁定 verified（2026-08-06）**（v6 prompt sha 3aa64877 固定、deepseek-v4-pro/temp0/top_p1/4096、预算合同，见 `configs/models/estg150_d1_active_registry_v1.json`）、**D1-R3 快照重跑 verified（2026-08-06）**（细 Gold F1 0.7756 / P 0.8793 / R 0.6938，0 事故）、**句子级粗 Gold 归因 verified（2026-08-07，用户决策口径对齐 Sun，粗 Gold 为主口径）**（F1 0.8726，与 B0 同 Gold 同口径）；**主方法（2026-08-08 导师汇报后确认，§8.8.4）**；当前 formal 仍 blocked | 可引用为历史开发证据与 D1-R1/R2/R3 development 结果及归因实验；不得冒充当前冻结 capsule 的正式指标；贡献细模块化（8 模块）与消融矩阵 AB-1..AB-10 见 §8.8.4 |
| Stage 1 | S1.1-S1.6 合同/解析/标注协议/评价器资产已从 56d2b03 checkpoint 恢复并重新绑定（2026-08-08）；37 项 stage1 测试全绿；audit pass：`stage1_structural_process_record_verified`/`stage1_label_semantics_p0_p1_verified`/`stage1_annotation_protocol_verified`/`stage1_evaluator_contract_verified` | 合成 BPMN 上验证的 development 合同与机制；尚无冻结的正式组件结果（formal BPMN/Gold 未评价） |
| Stage 3 | **S3.1 verified（2026-08-08）**：7 个 Winter-provenance GDPR BPMN 以 byte-exact（LF）恢复至 `data/input/stage1_stage3/gdpr7/`（原 CRLF 变体内容一致，备份于 `.tmp/untracked_gdpr7_backup_2026_08_08/`）；合同 `stage1_stage3_gdpr7_v1.json`（user-approved 2026-07-18）hash 全匹配；`verify_stage1_stage3_gdpr7.py` 通过（7 byte-exact、45 activities、135 blank label fields）；audit pass `stage1_formal_bpmn_membership_locked`（claim=all-seven extension，非 Sun 原 4）。**S3.2/S3.3 annotation frozen**：58 条候选用户裁决完成（冻结 manifest `s32_s33_gold_annotation_freeze_v1.manifest.json`）。**S3.4 Winter wrapper development verified**：Winter 2020 baseline 转写（`src/bpc_hybrid/winter_stage3/`）全量 58 条运行（`outputs/development/s34_winter_stage3_development_v1/`，DEV_ONLY），formal 完成 blocked on S1.7/S2.13 | S3.1 文件名/hash/claim 已固定；S3.2/S3.3 Gold 标注已冻结（正式发布随 §8.9 门禁）；S3.4 为 development baseline，尚未进入 formal Oracle 主表 |
| 正式结果目录 | 未冻结 | 当前不得声称最终实验结果 |
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
| 6.1 | S2.4-S2.6 | 本轮严格未启动；许可未知与 S2.4 ready 的现有矛盾不在 S2.3 绕过，留待 S2.4 单独派发前收口 | 非 LLM canonical Rule Record 可复现 |
| 6.2 | B0-R0–B0-R5 | **B0-R0 verified**（2026-08-02 commit 之后）：actor_action.py + 12 个 b0_v10 模块 + sun_style/lexicon_v2_runtime + estg150_b0_development v1/v2/v3/v10 + corenlp_runtime/sun_b0/bert_textcnn + stage2_evaluation v1/v3 + 7 个 v2 lexicon 资源 + SunPhraseRuleBatchBridgeMulti.java + sun_corenlp_runtime.json + sun_b0_s26_candidate_B_v1.json + sun_bert_textcnn_s24.json + estg150_b0_enhanced_s27_v10a.json + estg150_b0_v10_preregistration_v2.json + stage2_evaluator_s210_v3.json + stage2_prediction.schema.json + scripts/run_estg150_b0_enhanced_v10_development.py + test_b0_v10_integration_contract.py（15 验收点） 已纳入 main；audit 区分 component presence（pass）与 method-conformance（blocker，必须由 B0-R2 才能解除）；B0-R1 ready；B0-R2–B0-R5 仍按依赖 blocked；未运行 CoreNLP、未读 Gold/Layer E、未调 API、未改 D1/H1；先前 6341136 的 B0-R0-C0 仅依赖闭包，状态从误报 COMPLETE 修正为 verified，correction event 已追加。**B0-R1 五批已完成并实测**（2026-08-04，全部在隔离 worktree + 56d2b03 历史输入 + 真实 CoreNLP 下验证，主口径 sun_literal_overlap_evaluation@2.0.0）：R1-A..C3（token-safe span）→ E1/E2（主口径 evaluator + v10a/C3 重评：F1 0.71019/0.71024，旧 0.5398→0.5326 推翻）→ ERR（错误分析文档，docs/B0_ERROR_ANALYSIS.md）→ **ACTION**（F1 持平，质量收益：主语吞并 8→0、strict-exact 3×）→ **SCOPE-DISAMBIG**（候选实测 −0.0005 拒绝回退，记方法局限）→ **ALIGN**（伪 validated 消除 DoD 达成，主口径不变，label 面板 −0.48pp 记录代价）→ **BRIDGE**（`<`/`<<` 语义测试 + operated 多命中 fail-closed 守卫）→ **ACTOR**（clause 内全 nsubj 弧 + obl/by-to + 中心词词典校验；**主口径 F1 +0.0018，系列首个正向**，actor F1 0.616→0.670，8/8 词典内漏抽找回）。当前 B0-R3 快照细 Gold F1=**0.71865**（P 0.6845 / R 0.7564，用户条件授权为论文依据候选）；**2026-08-07 用户决策：评价口径对齐 Sun 句子级粒度，句子级粗 Gold（609 spans）为主口径，B0 粗口径 F1=0.7986（P 0.7309 / R 0.8801）、D1 粗口径 F1=0.8726（P 0.9012 / R 0.8456），细 Gold 降为对照口径**。B0-R2 method-conformance 已由用户授权解除（2026-08-04，`method_conformance_status`=`verified_method_level_independent_reconstruction`）；LEXICON-DECISION 已实施（2026-08-04 用户授权路径 b，13 名词入词典）；CLAUSE-REVIEW 已复核不改动；C7 过短边界留待正式 Gold 后按需再议。B0-R4/R5 仍 blocked on formal Gold/shared capsule | B0 方法级实现可重放、B0-R1 确定性缺陷逐批实测（正/负结果均记录）、变更均有日志和 Git checkpoint；修复后低分可作为正式负结果 |
| 6.3 | D1-R0–D1-R5 | **D1-R0 verified**（runner/prompt loader/canonical schema/s28_s29 产物 tracked 可重评）→ **D1-R1 verified**（2026-08-05，四子批次 FIELD-TYPING/PROMPT-CONTRACT/VERIFY-PASS/CLEAN-RERUN 闭环：v6= v5+规则25-27+示例5-6 KEEP；150 全量 0 事故，主口径 F1 0.7669→**0.7735**、constraint R 0.2881→**0.4172**，P 0.8799（−0.0269 披露 trade-off）；空不为错语义，坏 span/clause/边丢弃+审计）→ **D1-R2 锁定 verified**（2026-08-06）：`configs/models/estg150_d1_active_registry_v1.json` 固定 v6 prompt hash 3aa64877（磁盘/loader/manifest 三方一致）、模型钉死 deepseek-v4-pro、sampling temp0/top_p1/max_tokens4096、seed 策略 unsupported_or_omitted、transport 配方（thinking-disabled 无 json_object）、共享输入/evaluator hash、预算合同（逐批授权+`--max-calls` 硬上限 150）；12 项 lock-config 测试含 S2.9 Gold 不可见核查（6 个合成 fixture 与 150 测试句零交叠）；§8.5 S2.9 DoD（D1 侧）达成、整行仍 partial。**D1-R3 快照重跑 verified**（2026-08-06，用户授权 150 calls）：锁定配方逐项一致干净重跑，150/150 有效、0 事故；同一进程双评 R1/R3（sun_literal_overlap@2.0.0）R3 F1 **0.7756**（P 0.8793/R 0.6938）vs R1 0.7735（+0.0021，复现成功）；失败类型分析（1055 gold span：wrong_field 169 其中 constraint 100、not_extracted 154）见 docs/D1_ERROR_ANALYSIS.md §8；产物 outputs/development/s27_d1_v6_r3_clean_rerun_150_hist56d_v1/；**句子级粗 Gold 归因 verified**（2026-08-07，与 B0 同粗 Gold 同口径：F1 0.8726 / P 0.9012 / R 0.8456，见 outputs/development/s27_d1_coarse_gold_sentence_granularity_v1/）。D1-R4/R5 仍 blocked on formal Gold 发布（annotation freeze 已达成 2026-08-06，route/data/stage3 重锁 + publication gate 未过） | D1-R3 experiment_run 事件 + 双评 evaluation JSON + audit --with-tests；150 次调用由用户逐批授权，manifest 记录 llm_calls/max_calls |
| 7 | S2.7-S2.12 | H1 development wiring 已修复；S2.8A/B/C development verified；S2.8D-R1 transport 离线修复 verified；S2.8D-R1 单次 v4-flash canary（硬上限 1、0 retry）因 span reference mismatch 被原子拒绝（valid=1、accepted=0、effective=0、gate=false、H1==B0），历史真实调用累计 41 次。**S2.8D-R2 离线取证**（0 real API calls）：3/3 被拒 span 为正确文本+错误坐标（clause 内唯一 exact match），结论=情况 A。**S2.8D-R3 已实现**（0 real API calls）：fail-closed unique exact-text coordinate canonicalization（`bpc_hybrid/h1_span_canonicalizer.py`，单一共享路径接入四模式；zero/ambiguous/contract 整 patch 拒绝；只改 start/end；仍过现有 validator 与 atomic merge）；同一 R1 capture 的 R3 离线 transport replay：reanchored 3/3、validator 通过、merge accepted、effective_patch=true、changed=1、**gate=true、H1!=B0**、identity 不变；R1 历史 strict 结果未改。**S2.8D-R4 真实 canary 成功**（1 real API call、retry 0，用户明确授权）：requested/resolved/returned=deepseek-v4-flash；HTTP 200、ok_message_content、reasoning=false、tool_calls=0、usage=1305/405/1710；非空 patch→canonicalizer reanchored 3/3（zero/ambiguous/contract=0）→canonical validator 通过→merge accepted→effective_patch=true、changed=1、**gate=true、H1!=B0**、identity 不变；离线 replay（s28d_r4_h1_canary_replay_v1）H1 sha 与真实运行一致、byte-identical；R1/R3 历史结果未改。**S2.8D-R5 已冻结**（0 real API calls、retry 0、未运行 pilot）：历史真实调用集合恢复=42 calls / 20 唯一 plan keys（sha c813a384…）；Gold-blind 确定性选样 10 个不同 sample plan（排除全部历史已调用 keys，复用现有 risk 排序）；frozen plan 配置 `configs/s28d_r5_h1_small_pilot_plan_v1.json`（sha 35dc6a75…，cap=10/retry=0/early-stop 合同）；runner `--frozen-plan` 严格绑定 fail closed + early-stop 实现（provider model / capture / count / plan key / 连续 3 次失败 abort；patch 级拒绝 continue）；plan-only 验证：selected=10/10、llm_calls=0、gate=false、H1==B0、execution order 与 keys hash 一致、历史交集空、byte-identical；新增 29 项测试（30 验收点），H1 focused 106 passed；默认行为不变。**S2.8D-R6 已执行**（用户明确授权，主真实命令仅一次）：实际 API calls=5（冻结 order 1–5：estg_000118/000133/000164/000206/000207），每 plan 1 次、retry=0、模型/capture 全对、无未冻结 plan；proposed=5、accepted=3、rejected=2、effective=3、changed=3、gate=true、H1!=B0=3、identity violation=0；canonicalizer reanchored 4/failed 1；usage 总 8976。**early stop 于 order 5 后误报 plan_key_mismatch**（R5 runner 计数缺陷，已修复+回归测试；真实调用无违规）；未调用 order 6–10 保留 not-called、不补跑。离线 replay（s28d_r6_h1_small_pilot_replay_v1，0 API calls）与真实运行逐项一致、byte-identical；机制最低可用门 passed=true。**S2.8D-R6C1 已补完**（用户授权只补 order 6–10；新增 actual API calls=5、retry=0、order 1–5 新调用=0、无 early stop）：estg_000232/000285/000302/000414 被拒（canonical_invalid+reference_mismatch）、estg_000716 accepted/effective；proposed=5、accepted=1、rejected=4、effective=1、changed=1、gate=true、identity violation=0；continuation replay 一致且 byte-identical；合并 R6+R6C1 为完整 10-plan capsule（s28d_r6_complete_h1_small_pilot_v1）：**10/10 覆盖 complete**、keys sha=bb8d73b2…、每 plan 一次、10 不同 sample；合并指标 calls=10、accepted=4、rejected=6、effective=4、changed=4、H1!=B0=4、identity=0、usage 总 18628。**formal S2.8 仍 blocked on S2.6；不得自动重试或进入完整 pilot** | 具备申请 S2.8D-R7（完整 10-plan Gold-blind 结果审计与受控 P/R 评价解锁准备）；P/R 仍 not_computed。**2026-08-08 H1 降级为对照（§8.8.1）**：全量 150 运行（commit 74614e3，用户授权 150 calls，deepseek-v4-pro）主口径粗 Gold F1 **0.7621 vs Rules-Only 0.7986（净负 −0.0365）**、细 Gold 0.6875 vs 0.7186；LLM 修复过度抽取 actor（P 0.7077→0.2754、spans 65→167），其余 5 字段持平或微升；机制正常（103 accepted / 89 changed / gate=True / 0 incidents）但 trigger+repair 配方加 FP 不加召回；证据支持决策 A（Direct-LLM 为主方法）；**H1 不再深究，仅作论文对照臂**；S2.8 正式 trigger 预注册取消 |
| 8 | S3.1 | **verified（2026-08-08）**：S1/S3.1 资产从 56d2b03 checkpoint 恢复（configs/schemas/data/docs/outputs/scripts/src/tests + 5 个 s1 gate 模块）；7 个 GDPR BPMN byte-exact（LF）落地并加入 `.gitattributes` eol=lf；修复 56d2b03 快照先存的跨任务 binding 过期（s13/s15/s16 合同 upstream hash、5 个 gate 期望、合同 stage1 块），manifest 按当前合同重新生成并全链更新；`verify_stage1_stage3_gdpr7.py` 通过；audit pass `stage1_formal_bpmn_membership_locked`；37 项 stage1 测试全绿 | 文件名、hash、claim 固定（合同 `stage1_stage3_gdpr7_v1.json` user-approved 2026-07-18 + 验证 manifest `s15_s31_gdpr7_membership_v1.manifest.json`） |
| 9 | S3.2/S3.3 | **annotation frozen（2026-08-08）**：58 条候选全部由用户裁决（matching 25=11 相关/14 不相关；violation 33=三类各 11）；裁决存 `data/development/human_review/stage3_gold_annotation_human_correction_v1.json`（decision 与 candidate 分离）；冻结 manifest `s32_s33_gold_annotation_freeze_v1.manifest.json`；工具：`review_stage3_gold_annotation.py`（交互/批量出题+导入）、`build/verify_stage3_gold_annotation.py`；formal Gold 发布仍待 stage3.status 合同门禁 | 用户裁决完成；正式 Gold 发布随 §8.9 门禁链 |
| 10 | S3.4 | **development wrapper verified（2026-08-08）**：Winter 2020 Stage 3 baseline 转写（`src/bpc_hybrid/winter_stage3/`，spaCy 语义匹配 + gamma 0.4/delta 0.8 + fitness/cost 三分量，配置 `configs/winter_stage3_development_v1.json`）；唯一入口 `scripts/run_winter_stage3_development.py` + 评价器 `scripts/evaluate_winter_stage3_development.py`；58 条冻结候选全量运行，产物 `outputs/development/s34_winter_stage3_development_v1/`（DEV_ONLY：matching F1 0.61、mean AP 0.64；violation macro F1 0.37、exact type acc 0.33）；gold-blind、确定性、无 LLM/网络；原型 is_reachable_from bug 修正 + participant 空导致 resource cost vacuous 已披露；12 项聚焦测试；formal completion blocked on S1.7 and S2.13 | 正式 canonical I/O + reproducible command（S3.4 DoD 正式完成仍 blocked on S1.7/S2.13） |
| 11 | S2.13 | 冻结 Stage 2 | 数据、方法、指标、成本、manifest 完整 |
| 12 | PW1 | **下一论文任务**：引言与 RQ0–RQ4 | 无结果性过度主张；主张矩阵同步 |

Stage 1 和 Stage 3 的后续任务见主 Pipeline §8.9：S3.1-S3.3 数据治理及明确标注的
development 准备可受控并行；Stage 3 LLM/Hybrid、正式 Oracle、端到端均不得抢跑。

## 5. 当前派工

| 角色 | 任务 | 状态 | 写入范围 | Prompt |
|---|---|---|---|---|
| 协调 Agent | 维护门禁、验收和日志 | in_progress | shared docs/log only | `docs/AGENT_RUNBOOK.md` §§1–3 |
| Agent-E1 | S2.1-A 官方数据来源证据 | **verified** (2026-07-15 字节级核验通过；许可仍 unknown_pending_confirmation；B2 仍 open) | `data/development/sun_modality/`、`docs/research/SUN_MODALITY_DATASET_INGESTION.md`、manifest、`scripts/verify_sun_modality_zip.py`、tests | §4.1 |
| 当前执行 Agent | S2.3 public marker lexicon 重建 | **verified；严格停止在 S2.3** | `resources/lexicon/`、生成/加载/门禁代码、fixtures/tests、合同与状态文档；未改 Gold，未联网/调用 API，未训练/评价，未进入 S2.4/S2.5 | source=`e40c85…e369`；manifest=`5b9baf…2bf7`；combined payload=`8c3a27…7b91` |
| Agent-P1 | PW1 引言与研究问题 | ready | `paper/THESIS_DRAFT.md`、主张矩阵 | §4.2 |
| Agent-R1 | 论文科学主张只读复核 | blocked on PW1 draft | 无写入 | §4.3 |
| 用户 | S2.2 Layer E 人工裁决 | verified，150/150 adjudicated | 仅 Layer E | freeze validator 通过；后续 formal Gold 仍由 stage3/publication gate 控制 |

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
- 论文工作稿与主张矩阵：`paper/THESIS_DRAFT.md`、`paper/CLAIM_EVIDENCE_MATRIX.md`
