# 实验日志（人类可读）

本文件是项目当前的人类可读实验日志。它回答“什么时候、为了什么、用什么状态和
测试证据做了什么”。机器可读的完整事件记录在 `EXPERIMENT_EVENTS.jsonl`。

## 怎样阅读

- `变更`：代码、配置、文档、数据协议或治理结构发生了经过验证的修改。
- `实验运行`：实际执行了某个方法；必须同时记录 run ID、Stage、方法、命令、
  manifest 和结果摘要。
- `里程碑`：数据冻结、阶段完成或投稿前复核等关键节点。
- “完整性通过”只表示项目结构和不变量没有被破坏，不等于正式实验已经完成。
- blocker 是尚未完成的研究条件，不是本次变更失败。

## 历史迁移说明

2026-07-15 整理项目前，事件 1—29 的机器记录已经追加在旧文件中。整理时没有
重写任何 JSONL 行，只把文件改名为 `EXPERIMENT_EVENTS.jsonl`。旧版人类日志原文
冻结在 `_retired/logs/AUDIT_LOG_legacy_through_event_29.md`，用于追溯早期细节。
从事件 30 起，`record_change.py` 统一在本文件追加中文条目。

## 当前摘要

- 研究主线：先完整完成 Stage 2，再补 Stage 1，最后复现并扩展 Stage 3。
- 人工审核：Layer E 输入门已就绪，仍为 0/150 adjudicated。
- 正式结果：尚未冻结，没有可用于最终论文结论的正式结果。
- LLM/API：未经用户明确授权，不进行真实调用。

<!-- 新事件只允许由 scripts/record_change.py 追加到本行之后。 -->


## 2026-07-15T05:23:02.146059+00:00 - 彻底整理 formal_experiment 目录并建立中文实验日志与可维护文件目录

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：738 passed, 22 skipped in 72.50s (0:01:12)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`469f840bd23e86f6be699f83698d84ef85fcf4ac`；相关未提交路径：215 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_alignment_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、formal_capsule_not_versioned、sun_stage2_baseline_not_paper_faithful
- 备注：建立 _retired 专属只读归档并迁移 22 个已替代文件；机器事件 1-29 原样保留并更名；新增中文目录地图、216 文件目录和中文日志入口；清除可再生缓存；未修改 Gold、用户审核内容、references 或根 archive。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-15T06:24:47.843567+00:00 - 建立按 Pipeline 分阶段派工与论文并行写作轨道

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：742 passed, 22 skipped in 89.85s (0:01:29)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`469f840bd23e86f6be699f83698d84ef85fcf4ac`；相关未提交路径：219 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_alignment_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、formal_capsule_not_versioned、sun_stage2_baseline_not_paper_faithful
- 备注：新增中文 Agent 分阶段执行手册、可复制 Prompt、论文目录、主论文草稿和主张证据矩阵；更新项目入口、实时派工、主 Pipeline、活动数据路线说明与完整性检查。首个实验任务锁定为 S2.1-A，论文先推进 PW1-PW6 非结果章节；未调用真实 LLM/API，未修改 Gold、人工审核记录、references 或 archive。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-15T06:53:20.759748+00:00 - S2.1-A 官方 Stage 2 modality 来源/许可/原始文件证据:落档 source_manifest + ingestion 文档 + 28 个回归测试;raw/ 字节未取得,许可 unknown_pending_confirmation,S2.1-A 保持 in_progress,不解锁 S2.1-B

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：770 passed, 22 skipped in 71.21s (0:01:11)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`469f840bd23e86f6be699f83698d84ef85fcf4ac`；相关未提交路径：222 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_alignment_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、formal_capsule_not_versioned、sun_stage2_baseline_not_paper_faithful
- 备注：本地核对:无 Decision_Logic_data.zip / EStG_sent_vec.csv / EStG_raw.txt / estg.html / input 2.zip 任何字节;archive.org 入口在本会话 web_fetch 不可达、web_search 未返回项目页直证;官方 SHA-1=0346f84a246b7049d5aef58bcb33471435bee106 已在 source_manifest.json 落档,作为 S2.1-B 取得 raw 后的核验基准;raw/ 目录为空、formal/references 路径未被污染;新增 28 个 pytest 用例(28 passed)、重建 FILE_CATALOG.md,audit_project.py --with-tests 770 passed 22 skipped 退出码 0;integrity_pass=true,所有 gate 状态与本批次前完全一致;S2.1-A 明确停在 in_progress,B1(raw 字节取得与 hash 核验)+B2(archive.org license 元数据核实)未解决,不解锁 S2.1-B
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-15T08:14:57.680717+00:00 - S2.1-A 字节级核验:官方 ZIP 191,874,718 字节 byte-match archive.org metadata,SHA-1 0346f84a246b7049d5aef58bcb33471435bee106 一致,3 成员全部存在且路径安全,EStG_raw.txt SHA-256 与 2026-07-11 审计记录一致;raw/ 加目录级 + 根级 .gitignore 双层保护;许可 unknown_pending_confirmation (B2 仍 open),B1 resolved;S2.1-A verified,S2.1-B 可派发但本轮不实际进入

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：786 passed, 22 skipped in 77.91s (0:01:17)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`469f840bd23e86f6be699f83698d84ef85fcf4ac`；相关未提交路径：224 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_alignment_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、formal_capsule_not_versioned、sun_stage2_baseline_not_paper_faithful
- 备注：本地核验:size=191874718、SHA-1=0346f84a246b7049d5aef58bcb33471435bee106 一致,新增本地计算 ZIP SHA-256=ada231f092927813ba9f1cd32a44a3d30d96b57fc463d042dfd76c652b6d58f2、CSV SHA-256=1e53eb1b7f88f57c63029385eafe5e6f269bb7878328c0c409c5e708250ad5c3、HTML SHA-256=bc385ce9acee1fd9289d5c0dc9c273bf0c7392e11783b6043032066c7ce80eb0;新增 scripts/verify_sun_modality_zip.py(离线 byte 级核验脚本,流式 hash 不写解压文件,拒绝绝对路径/盘符/NUL/.. 段/反斜杠);新增 raw/.gitignore 目录级 ignore + 根 .gitignore 兜底条目;tests 从 28 增至 44 个用例,audit_project.py --with-tests 786 passed 22 skipped 退出码 0;所有 gate 状态与本批次前完全一致(10 blockers、5 warnings、16 passes);S2.1-A 标 verified,许可仍 unknown_pending_confirmation;不解锁 final_gold/final_experiment,routes/stage3/freeze_policy 仍由 B2/B3 等独立 blocker 锁定
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-15T08:42:43.981476+00:00 - S2.1-B:数据集合同(sun_modality_dataset@1.0.0)+manifest schema(dataset_manifest.schema@1.0.0)+stdlib-only streaming importer+12 个 synthetic fixtures+47 个测试全过;inspect-only 零写入/默认拒绝覆盖/stable ID 可复现/同 seed 输出 byte-identical/不同 seed split membership 不同/train-dev-test 两两无交集并集完整/cross-split leakage raise/manifest hash 与实际文件一致/importer 不读 .env 不调 LLM/API 不写 formal 目录/S2.1-A artifacts 不变;真实 CSV 列结构与合同 4 列 one-hot 假设不一致,合同保持 csv_inspect_pending_unlock: pending,S2.1-C 精确 blocker 已记录;S2.1-B verified,S2.1-C ready,本轮不实际进入

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：833 passed, 22 skipped in 87.31s (0:01:27)
- 测试证据：本次新运行（`fresh_run`）
- Git：`469f840bd23e86f6be699f83698d84ef85fcf4ac`；相关未提交路径：244 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_alignment_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、formal_capsule_not_versioned、sun_stage2_baseline_not_paper_faithful
- 备注：新增:configs/datasets/sun_modality_dataset.json(7.0KB)、configs/schemas/dataset_manifest.schema.json(7.0KB)、src/bpc_hybrid/datasets/__init__.py(0.5KB)、src/bpc_hybrid/datasets/sun_modality_importer.py(45KB)、scripts/ingest_sun_modality.py(8.7KB)、tests/fixtures/sun_modality/_fixture_builder.py(8.5KB)+README.md(2.5KB)+11 个 csv fixture+1 个 large_normal fixture、tests/test_sun_modality_ingestion.py(36KB);追加 docs/research/SUN_MODALITY_DATASET_INGESTION.md §3.5 真实 CSV 列结构发现(无传统 header、整数 0-3 modality 编码、含 768 维 BERT 向量);更新 docs/PROJECT_AUDIT.md §4 + §5 把 S2.1-B 标 verified、S2.1-C 标 ready;S2.1-A 不变、许可仍 unknown_pending_confirmation、本轮不进入 S2.1-C;audit_project.py --with-tests 833 passed 22 skipped exit 0;generate_file_catalog.py 收录 257 个文件;git diff --check 退出码 0;stdlib only 0 第三方依赖新增,无 LLM/API/网络调用,未读 .env,Gold / EStG-150 / route / Stage 3 / 任何 readiness gate 全部未触动
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-15T09:27:06.186146+00:00 - S2.1-B-R1：修正 source ID、group-aware split、小类别阈值、双哈希与确定性 manifest 合同/实现

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：840 passed, 22 skipped in 76.84s (0:01:16)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`469f840bd23e86f6be699f83698d84ef85fcf4ac`；相关未提交路径：247 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：已授权覆盖（`authorized_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_alignment_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、formal_capsule_not_versioned、sun_stage2_baseline_not_paper_faithful
- 备注：协调 Agent 复核后先把 S2.1-B 降为 in_progress、S2.1-C 阻塞；本批次完成显式 source_id 重复 fail closed、无 ID row_index fallback manifest 留痕、normalized_text 同标签分组切分、label_conflict fail closed、唯一阈值 active_nonzero_splits*min_per_class_in_smallest_split=3、ZIP SHA-1/SHA-256 独立核验、records/train/dev/test/manifest 五文件 byte-identical、移除 manifest self-child 与 placeholder、synthetic strict_one_hot 与 official pending_s2_1_c schema/mapping 分离。定向 54 passed；最终全量 840 passed、22 skipped、0 integrity errors；catalog 249 文件有效；git diff --check=0。未读取完整真实 CSV，未进入 S2.1-C，未生成官方 split，未训练，未调用网络或 LLM/API，未修改 Gold、Layer E、references、archive 或仓库根 .gitignore。S2.1-B verified，S2.1-C ready。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-15T10:36:30.260152+00:00 - S2.1-C：完成官方 CSV 全量流式 schema 核验并对源标签冲突 fail closed

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：869 passed, 22 skipped in 67.77s (0:01:07)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`469f840bd23e86f6be699f83698d84ef85fcf4ac`；相关未提交路径：254 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：已授权覆盖（`authorized_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_alignment_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、formal_capsule_not_versioned、sun_stage2_baseline_not_paper_faithful
- 备注：重新核验 ZIP/CSV 身份后完整扫描 2833 行；锁定无 header 的 10 列 positional schema、四列 one-hot、300 维词向量序列与 row_index fallback。论文计数支持 one-hot 列到四类的精确分布推断，但不是作者 codebook；不存在整数 modality code。发现 1 个 normalized-text group 在 permission/obligation 间冲突，真实 import 在写出 records/splits/manifest 前关闭失败，S2.1-C 保持 in_progress，S2.1-D 保持 blocked。定向测试 83 passed；项目审计 869 passed、22 skipped、0 errors。未联网、未调用 LLM/API、未修改 Gold、未训练、未进入 S2.1-D，写入仅限 formal_experiment/。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-15T16:42:59.187918+00:00 - S2.1-C-R1：按预结果治理决定精确隔离唯一冲突组并完成 2831 行 development import

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：878 passed, 22 skipped in 112.14s (0:01:52)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`469f840bd23e86f6be699f83698d84ef85fcf4ac`；相关未提交路径：257 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：已授权覆盖（`authorized_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_alignment_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、formal_capsule_not_versioned、sun_stage2_baseline_not_paper_faithful
- 备注：用户在任何训练或结果前选择 pre_result_conflicting_label_group_quarantine。raw 2833 行、ZIP/CSV 字节和 permission/obligation 原标签均未修改；只有 source/normalized/raw-text hash、row 616/1221、逐行标签与 section hash 全部精确匹配的唯一 group 整体隔离，任意未授权冲突或 hash/行号/标签/数量不匹配仍 fail closed。主数据 2831 行，分布 definition=1190/obligation=1273/permission=264/prohibition=104；train/dev/test=1985/420/426，seed=20260715，group-aware、两两无交集、并集完整、泄漏 0，隔离行不在 records/splits。records/splits/quarantine/manifest/summary 七产物独立重放 byte-identical；manifest=33db82259123064602d58ea815dba08ae256d1d9cdd88e12b8c6c2d066d28f34，summary=75f57fdd398d1d6a816fe87324e4d43721694b8b312b5a7b64a2acb9e412bf4e，quarantine=1e5543029a72513e2803e1001fc0cc1bcffb5a803704e99ca2cb556a9d97957c。full-source sensitivity 仅预注册 planned_not_run。定向 92 passed；全量 878 passed、22 skipped、0 errors。未训练、未评价、未联网、未调用 LLM/API、未修改 Gold、未进入 S2.1-D、未写 formal_experiment/ 外。S2.1-C verified，S2.1-D ready。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-16T04:39:45.307092+00:00 - S2.1-D：修复 Sun modality manifest 可移植路径并锁定独立 development 数据机器门禁

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：917 passed, 22 skipped in 132.19s (0:02:12)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`469f840bd23e86f6be699f83698d84ef85fcf4ac`；相关未提交路径：259 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：已授权覆盖（`authorized_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、formal_capsule_not_versioned、sun_stage2_baseline_not_paper_faithful
- 备注：official importer 与 schema 升级为 patch 版本，contract_path 和 source_asset.local_path 改为项目相对路径；受控重建后 records/train/dev/test 的行数、membership 与 SHA-256 保持不变，manifest=21a3390c8356053832041d626563910328952097f0c011ece0ec07a229dba534，split_summary=a5b0a828d95eae21fb3ba57d9c59bc34f44a4e997cbb455a7d08ea4be4b08bbc。新增独立 fail-closed machine gate，交叉验证 ZIP 身份、合同、schema、quarantine、records/splits、membership/artifact hash、ignore、相对路径与许可边界；38 个 gate 测试覆盖真实正例和全部要求的负例，最终 S2.1-D 定向 148 passed。全量审计 917 passed、22 skipped、0 errors；sun_modality_development_data_verified=true，旧 stage2_dataset_alignment_pending 已替换为 stage2_dataset_route_relock_pending；human review input=true、freeze=false、formal Gold=false、final=false。S2.1 整体 verified；未训练、未评价、未联网、未调用 LLM/API、未修改 Gold、未写 formal_experiment/ 外、未进入 S2.3/S2.4。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-16T06:24:27.888969+00:00 - S2.3 public marker lexicon 离线重建与版本化机器门禁

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：929 passed, 22 skipped in 96.22s (0:01:36)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`469f840bd23e86f6be699f83698d84ef85fcf4ac`；相关未提交路径：272 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、formal_capsule_not_versioned、sun_stage2_baseline_not_paper_faithful
- 备注：锁定 public_marker_lexicon_en_v1：来源快照 SHA-256=e40c85cf572c68278d8fa2db00a57f193c0c9352aee889096731b6e87e31e369，manifest SHA-256=5b9bafb268469acb33c3779ad4e0d8ce6a9984c4cf900855aeeafc0f332e2bf7，combined payload SHA-256=8c3a27b2aa62025ff266b4cb19a1c89984e967539188ccf96820836c2eef7b91；英文显式 public seed 7/25/19/5/8 共64个，dev extension=0。定向测试在项目 .tmp basetemp 下 51 passed；全量 929 passed、22 skipped。未联网、未训练、未评价、未修改 Gold、未调用 LLM/API、未进入 S2.4/S2.5；上游 license 未在本离线任务重核，资源保持 development-only 且禁止再分发/formal use；许可与 S2.4 ready 的现有矛盾留待后续单独收口。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-16T07:06:52.668996+00:00 - 建立 ChatGPT GitHub 论文协作入口与版本新鲜度协议

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：930 passed, 22 skipped in 100.33s (0:01:40)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`469f840bd23e86f6be699f83698d84ef85fcf4ac`；相关未提交路径：272 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：已授权覆盖（`authorized_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、formal_capsule_not_versioned、sun_stage2_baseline_not_paper_faithful
- 备注：沿用 MASTER_PIPELINE、PROJECT_AUDIT、EXPERIMENT_LOG 与 CLAIM_EVIDENCE_MATRIX 作为唯一事实源；未新建平行 handoff/status。paper/README 固定外部 ChatGPT 读取顺序、commit/状态/最新事件回报、冲突优先级和写作门禁；formal README 增加入口；新增回归测试。定向 10 passed；全量 930 passed、22 skipped；未修改 Gold、未调用 LLM/API、未读取 .env。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`
