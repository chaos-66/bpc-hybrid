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

## 2026-07-16T07:22:01.311179+00:00 - 收口 formal_experiment Git checkpoint 与 G0.6 状态

- 事件类型：里程碑（`milestone`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：930 passed, 22 skipped in 96.39s (0:01:36)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`bfb0b8a99dbe753f52ffe41fa6c7034fabb2ca94`；相关未提交路径：3 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：已授权覆盖（`authorized_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、sun_stage2_baseline_not_paper_faithful
- 备注：checkpoint bfb0b8a 已将 formal_experiment 纳入版本控制；提交后机器检查由 formal_capsule_not_versioned blocker 转为 formal_capsule_versioned pass，blocker 10→9。MASTER_PIPELINE 升级至 3.4.3 并将 G0.6 标 verified，PROJECT_AUDIT 同步 checkpoint 事实；定向 7 passed，全量 930 passed、22 skipped；未修改 Gold、未调用 LLM/API、未读取 .env。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-16T08:07:34.919265+00:00 - S2.4 license fail-closed closure and S2.5-A CoreNLP/Tregex offline contract

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：941 passed, 22 skipped in 82.30s (0:01:22)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：16 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、s2_4_license_gate_blocked、s2_5_corenlp_runtime_missing、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、sun_stage2_baseline_not_paper_faithful
- 备注：Pinned CoreNLP 4.5.10 runtime contract, six-field extraction order, candidate Tregex/Tsurgeon registry, synthetic CoreNLP JSON fixture, read-only runtime probe/command builder, exact-hash gate, status/docs/tests. S2.4 remains blocked on unknown_pending_confirmation; S2.5 runtime/overall remain false. No CoreNLP distribution acquired or executed; no Java/Tregex/Tsurgeon live run; no training or evaluation. Verified 941 passed, 22 skipped.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-16T08:11:55.497838+00:00 - Clarify S2.5-A network evidence boundary

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：941 passed, 22 skipped in 81.31s (0:01:21)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：18 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、s2_4_license_gate_blocked、s2_5_corenlp_runtime_missing、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、sun_stage2_baseline_not_paper_faithful
- 备注：Corrected research documentation: implementation/tests/audit/runtime probe were offline; the Agent only consulted official Stanford pages for version/license verification and did not download the CoreNLP distribution. S2.4/S2.5 gates unchanged. Verified 941 passed, 22 skipped.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-16T09:28:08.488021+00:00 - Verify S2.5 CoreNLP Tregex Tsurgeon extractor runtime

- 事件类型：里程碑（`milestone`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：942 passed, 22 skipped in 100.23s (0:01:40)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：23 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、s2_4_license_gate_blocked、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、sun_stage2_baseline_not_paper_faithful
- 备注：S2.5-A and S2.5-B are verified with official CoreNLP 4.5.10 held outside formal_experiment: archive sha256 76a04089069dad21176c02881f46e07c19ca148b71c8581de2b5b2e2855e042e; exact code/model JAR hashes locked; 12 Tregex patterns compiled; 2 synthetic sentences produced 28 tokens, 11 field matches, and 7 Tsurgeon surgeries. Offline audit: 942 passed, 22 skipped, 0 errors. No training, evaluation, Gold mutation, formal use, redistribution, or real LLM/API call. S2.4 remains blocked by unknown_pending_confirmation license and S2.6 was not entered.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-16T12:37:21.852080+00:00 - S2.4-L Sun modality license evidence closure

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：950 passed, 22 skipped in 94.60s (0:01:34)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：30 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、s2_4_license_gate_blocked、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、sun_stage2_baseline_not_paper_faithful
- 备注：Live read-only checks of the official Archive.org metadata endpoint and Springer article page found licenseurl=null, rights=null, a reasonable-request data-availability statement, and no explicit dataset training/evaluation permission; the local official ZIP has no license member. Added exact-hash evidence record sha256=5a4d6ee78007cbc81c611b4ad1164328589ed6bb323394342d6808a15e11df7e, human record, fail-closed S2.4-L gate, status/audit integration, and negative tests. Evidence review is verified, but rights remain unknown_pending_confirmation; training/evaluation/formal use/publication/redistribution remain false, S2.4 stays blocked, and S2.6 was not entered. Full offline audit: 950 passed, 22 skipped, 0 errors. No Gold mutation or real LLM/API call.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T04:29:58.664550+00:00 - 收口现有文件目录并完成 PW1 引言、RQ0-RQ4 与主张矩阵初稿

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：950 passed, 22 skipped in 96.89s (0:01:36)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：32 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：已授权覆盖（`authorized_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、s2_4_license_gate_blocked、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、sun_stage2_baseline_not_paper_faithful
- 备注：按 Sun 原文 Section 4/Figure 1 将三部分与项目 Stage 1/2/3 映射明确分开；新增的 RQ、预期贡献、Oracle/端到端与负结果表述全部保持计划或待检验时态；PROJECT_AUDIT 已将 PW1 标为 verified、PW2 标为下一论文任务；FILE_CATALOG 共 294 个文件且检查有效；未修改 Gold，未运行真实实验或 LLM/API。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T04:59:58.112832+00:00 - 完成 PW2 一手文献核验、相关工作与方法边界，并同步主张矩阵和实时状态

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：950 passed, 22 skipped in 92.66s (0:01:32)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：32 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、s2_4_license_gate_blocked、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、sun_stage2_baseline_not_paper_faithful
- 备注：Sun/Winter/Sleimi/Michel/Agostinelli/Barrientos 的任务、schema、代码身份与证据等级已分开；无正式结果主张。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T05:05:11.280719+00:00 - 完成 PW3 三阶段合同与 B0/H1/D1 方法设计稿，并同步 Pipeline、主张矩阵和实时状态

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：950 passed, 22 skipped in 106.61s (0:01:46)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：32 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、s2_4_license_gate_blocked、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、sun_stage2_baseline_not_paper_faithful
- 备注：区分 canonical schema/S2.5 verified、B0 blocked、H1/D1 planned；未产生或引用正式结果。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T05:09:35.209392+00:00 - 完成 PW4 modality 数据治理、五层 Gold 与人工标注协议当前稿，并同步 Pipeline、主张矩阵和实时状态

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：950 passed, 22 skipped in 98.72s (0:01:38)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：32 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、s2_4_license_gate_blocked、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、sun_stage2_baseline_not_paper_faithful
- 备注：只读运行 human_correction validator；Layer E 仍为 0/150 adjudicated、0/900 字段决定，未写入任何 Gold。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T05:14:04.070265+00:00 - 完成 PW5 baseline、指标、统计与复现设计，并同步 Pipeline、主张矩阵和实时状态

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：950 passed, 22 skipped in 99.58s (0:01:39)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：32 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、s2_4_license_gate_blocked、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、sun_stage2_baseline_not_paper_faithful
- 备注：正式 evaluator、阈值、bootstrap 参数与 LLM 重复次数仍保持 TODO-DECISION；未运行任何实验。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T05:24:12.131216+00:00 - 完成 PW6 Stage 2、复杂度、Oracle、端到端结果空表与作图/provenance 模板，并将论文轨道推进到 PW7 门禁

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：950 passed, 22 skipped in 100.62s (0:01:40)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：32 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、s2_4_license_gate_blocked、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、sun_stage2_baseline_not_paper_faithful
- 备注：所有待测数值保持空白；恢复测试锁定的 TEMPLATE 安全标记；未生成任何结果或图像。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T06:02:33.626281+00:00 - 根据用户明确决定，将 S2.4 重锁为仅本地非商业训练、开发集选择与评价可用；许可证据仍 unknown，数据再分发继续禁止

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：952 passed, 22 skipped in 98.90s (0:01:38)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：33 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、sun_stage2_baseline_not_paper_faithful
- 备注：新增 exact-hash 本地研究使用决定；experiment contract 2.0.6、机器门禁、负测试、Pipeline、项目审计和论文主张同步。952 passed, 22 skipped；未训练、未评价、未进入 S2.6。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T06:30:22.661045+00:00 - 实现并预注册 S2.4 Legal-BERT + TextCNN 本地训练、dev 选择和单次 test 评价流程

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：960 passed, 22 skipped in 87.75s (0:01:27)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：37 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、sun_stage2_baseline_not_paper_faithful
- 备注：固定 Legal-BERT commit 与文件 hash、2/3/4 TextCNN、无超参搜索、dev macro-F1 早停、test 只评一次；真实模型离线 smoke 通过。960 passed, 22 skipped；尚未正式训练或评价。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T07:49:33.139596+00:00 - 完成 S2.4 Legal-BERT + TextCNN 可重放训练、development 选择与唯一一次 test 评价

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s24_legal_bert_textcnn_seed20260717_v1；阶段=S2.4；方法=sun_bert_textcnn；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/train_sun_bert_textcnn.py --mode train --device cpu --run-id s24_legal_bert_textcnn_seed20260717_v1 --output-dir outputs/development/s24_legal_bert_textcnn_seed20260717_v1 --manifest-out outputs/reports/s24_legal_bert_textcnn_seed20260717_v1.manifest.json`
- manifest：outputs/reports/s24_legal_bert_textcnn_seed20260717_v1.manifest.json
- 结果摘要：development component run; 7 epochs; best epoch 5; dev macro-F1=0.856263; test n=426, accuracy=0.924883, macro-F1=0.851071; test evaluated exactly once
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：960 passed, 22 skipped in 99.48s (0:01:39)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：38 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked、sun_stage2_baseline_not_paper_faithful
- 备注：Local noncommercial thesis use only; rightsholder license remains unknown; no raw or row-level derived redistribution; no row-level predictions persisted.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T08:31:52.881578+00:00 - 完成 S2.6 no-LLM classifier-extractor-canonical B0 技术组合并锁定双语路由

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s26_sun_b0_canonical_composition_v3；阶段=S2.6；方法=sun_rule_only；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/verify_sun_b0_s26.py --device cpu --manifest-out formal_experiment/outputs/reports/s26_sun_b0_canonical_composition_v3.manifest.json`
- manifest：outputs/reports/s26_sun_b0_canonical_composition_v3.manifest.json
- 结果摘要：synthetic component verification only; exact S2.4 checkpoint + attested S2.5 live observations; de classifier / aligned en phrase+canonical routing; 1 record, 1 clause, schema_invalid=0, cross_field_invalid=0; no performance evaluation
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：968 passed, 22 skipped in 113.21s (0:01:53)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：51 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Only v3 is accepted by the exact-hash gate. Earlier v1/v2 exploratory smoke manifests are superseded and are not evidence or paper results. Test split was not read or re-evaluated; no real-data row predictions were persisted.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T08:56:06.857735+00:00 - 完成 S2.8 H1 离线预注册、B0 重基和 fail-closed dry-run 验证

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s28_sun_h1_selective_dry_run_v3；阶段=stage2；方法=sun_llm_fallback；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/verify_sun_h1_s28.py --manifest-out outputs/reports/s28_sun_h1_selective_dry_run_v3.manifest.json`
- manifest：outputs/reports/s28_sun_h1_selective_dry_run_v3.manifest.json
- 结果摘要：verified S2.6 B0 binding; inference-visible trigger and field dependency closure; accepted mock patch canonical-valid; unauthorized patch returned original B0; hard budget 45/150, one request per sample, zero retries; no performance evaluation
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：981 passed, 22 skipped in 100.08s (0:01:40)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：63 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：仅 synthetic dry-run；v1/v2 为本批迭代中被 v3 明确取代的非门禁产物；未读取或修改 Gold，未读取 test split，未调用网络或真实 LLM/API，未写 formal predictions。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T08:56:59.307050+00:00 - 参考 Sun 的综述结构重写相关工作并补充形式化方法、流程文本 NLP、选择性预测与 LLM 路由文献边界

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：981 passed, 22 skipped in 100.98s (0:01:40)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：63 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：已授权覆盖（`authorized_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：仅修改 THESIS_DRAFT 相关工作和 CLAIM_EVIDENCE_MATRIX；未改 Gold、实验数据、结果或方法实现；全量离线验证 981 passed, 22 skipped。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T09:08:57.511335+00:00 - 完成 G0.5 预结果文本与 BPMN 复杂度合同及泄漏防护验证

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=g05_complexity_contract_synthetic_v1；阶段=governance；方法=not_applicable；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/verify_complexity_contract_g05.py --manifest-out outputs/reports/g05_complexity_contract_synthetic_v1.manifest.json`
- manifest：outputs/reports/g05_complexity_contract_synthetic_v1.manifest.json
- 结果摘要：text 11 indicators and BPMN 12 indicators frozen into low/medium/high strata; text fixture score 4 medium; cyclic BPMN fixture score 1 low; method outputs/results forbidden; no complex dataset selected and no performance evaluation
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：995 passed, 22 skipped in 94.72s (0:01:34)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：72 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：仅 synthetic fixtures；未选择或读取复杂法律数据集，未读取/修改 Gold，未读取 test 结果，未调用网络或 LLM/API，未生成 formal complexity profiles。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T09:35:47.236831+00:00 - 完成 S2.11 官方 GDPR 复杂法律输入 membership 与人工 Gold/映射协议冻结

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s211_gdpr_complex_dataset_freeze_v1；阶段=stage2；方法=not_applicable；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/verify_complex_legal_s211.py --manifest-out outputs/reports/s211_gdpr_complex_dataset_freeze_v1.manifest.json`
- manifest：outputs/reports/s211_gdpr_complex_dataset_freeze_v1.manifest.json
- 结果摘要：official CELEX 32016R0679 Formex source; 200 units; deterministic 50 records covering Articles 5-50; membership 9a6a2c892e6e9ef86877066fb3c88ad03d06ca999c41ecbd91c6df35d09c28b9; blank human Gold input-ready 0/50, not frozen; no method/performance results
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1006 passed, 22 skipped in 95.28s (0:01:35)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：90 个
- Gold：仅按授权调整格式（`authorized_format_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：source acquisition used official EU Publications Office endpoint; verifier is offline; old heuristic gdpr50 excluded; no method outputs, test results, or complexity profiles
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T09:56:27.239349+00:00 - 按Sun相关工作篇幅与连续段落格式压缩论文相关工作

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：否；正式实验就绪：否
- 测试：1 failed, 1020 passed, 22 skipped in 108.01s (0:01:48)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：102 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：已授权覆盖（`authorized_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：将Section 2压缩为1022个汉字、7个连续段落，保留形式化方法、NLP、Sun、LLM与选择性回退脉络；修复文献主张ID冲突。完整离线套件两次均为1005通过、22跳过，唯一失败为测试期间并发新增S2.10文件导致目录索引过期；重建354项目录后该失败项通过，完整性审计0 errors。未修改Gold、数据、结果或方法实现。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T10:04:48.766900+00:00 - 完成 S2.10-E Stage 2 统一离线 evaluator 合同与 fail-closed 门禁

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s210_stage2_evaluator_contract_synthetic_v1；阶段=stage2；方法=shared_evaluator；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/verify_stage2_evaluator_s210.py --manifest-out outputs/reports/s210_stage2_evaluator_contract_synthetic_v1.manifest.json`
- manifest：outputs/reports/s210_stage2_evaluator_contract_synthetic_v1.manifest.json
- 结果摘要：five synthetic attempts; exact membership; clause-level four-class modality; strict/safe/token field metrics; coverage/hallucination; structural edges; invalid/API and cost accounting; formal scope fail closed; no formal method performance
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1021 passed, 22 skipped in 108.52s (0:01:48)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：102 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：synthetic fixture only; formal Gold/predictions not read or modified; no real LLM/network; synthetic metric values are contract constants, not B0/H1/D1 results; 1021 passed, 22 skipped
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T10:34:15.445078+00:00 - 完成S2.9 D1离线预注册并锁定实际prompt、模型、重复、预算与失败分母

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s29_sun_d1_offline_prereg_v3；阶段=S2.9；方法=direct_llm；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/verify_sun_d1_s29.py --manifest-out outputs/reports/s29_sun_d1_offline_prereg_v3.manifest.json`
- manifest：outputs/reports/s29_sun_d1_offline_prereg_v3.manifest.json
- 结果摘要：synthetic input=3; planned requests=15 (5 repeats); four few-shots/request; primary valid=1 invalid=1 api_error=1; dropped=0; exact-hash gate ready; no performance result
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1034 passed, 22 skipped in 125.31s (0:02:05)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：113 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：修复v3 nested-fence实际prompt截断；v4显式插入4个few-shot；模型gpt-4.1-2025-04-14，temperature=0，0重试，formal 150x5最多750次、9216000 tokens、37 USD ceiling。runner离线且拒绝--allow-llm；未读.env/Gold/B0/H1预测，未联网或调用LLM。全量1034 passed, 22 skipped。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T10:52:06.382724+00:00 - 完成S2.7-M非LLM模态baseline聚合运行与exact-hash门禁

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_non_llm_modality_baselines_seed20260717_v1；阶段=S2.7-M；方法=non_llm_modality_baselines；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/run_s27_modality_baselines.py --allow-test-evaluation --run-id s27_non_llm_modality_baselines_seed20260717_v1 --manifest-out outputs/reports/s27_non_llm_modality_baselines_seed20260717_v1.manifest.json`
- manifest：outputs/reports/s27_non_llm_modality_baselines_seed20260717_v1.manifest.json
- 结果摘要：same reconstructed split train/dev/test=1985/420/426; test majority accuracy/macro-F1=0.457746/0.157005; keyword=0.483568/0.414154; NB=0.784038/0.568849; aggregate-only; phrase/full S2.7 blocked
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1043 passed, 22 skipped in 122.84s (0:02:02)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：119 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Pure-standard-library word 1-2 gram Multinomial NB, no hyperparameter search. Disclosed one identical-config unversioned test-label smoke before the versioned run; no alternative config/model selected on test. No row-level predictions, no LLM/network/.env/Gold changes. Full suite 1043 passed, 22 skipped.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T11:12:39.385494+00:00 - 完成S2.12-P结果前复杂度分层、统计推断与错误分析协议冻结

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1049 passed, 22 skipped in 137.12s (0:02:17)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：126 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：No formal Gold/predictions/results read or created. Six synthetic count rows only; no LLM/network/formal complexity profile or method-performance claim. Full suite 1049 passed, 22 skipped.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T12:24:44.402356+00:00 - 闭合S2.10 recovered-error语义并重锁D1、S2.12与H1真实运行前合同

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s210_h1_recovered_fallback_relock_v1；阶段=stage2_offline_contracts；方法=shared_evaluator_and_sun_llm_fallback；状态=成功（`succeeded`）
- 实际运行命令：`verify_stage2_evaluator_s210.py v2; verify_sun_d1_s29.py v4; verify_s212_analysis_protocol.py v2; verify_sun_h1_s28.py v5`
- manifest：outputs/reports/s210_stage2_evaluator_contract_synthetic_v2.manifest.json, outputs/reports/s29_sun_d1_offline_prereg_v4.manifest.json, outputs/reports/s212_analysis_protocol_synthetic_v2.manifest.json, outputs/reports/s28_sun_h1_selective_dry_run_v5.manifest.json
- 结果摘要：S2.10 separates terminal/recovered provider errors; H1 provider-error B0 fallback remains canonical and scorable with H1 identity; exact Chat Completions request, deterministic 45-call allocation, 460800-token and 1.5-USD ceilings locked; D1/S2.12 rebound to evaluator v2; 1053 passed, 22 skipped
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1053 passed, 22 skipped in 131.37s (0:02:11)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：131 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Synthetic/offline contracts only. H1 v4 was an intermediate no-overwrite artifact superseded by canonical v5. No formal Gold/predictions/results, network, .env, or real LLM/API access.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T12:52:37.478913+00:00 - Verify the S1.1/S1.2/S1.4 deterministic BPMN structural Process Record contract on synthetic fixtures

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s11_s14_stage1_structural_synthetic_v1；阶段=stage1_offline_structural；方法=stage1_bpmn_xml_structural；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/verify_stage1_structural_s11_s14.py`
- manifest：outputs/reports/s11_s14_stage1_structural_synthetic_v1.manifest.json
- 结果摘要：Synthetic structural verification passed: 2 BPMN fixtures; deterministic entities and flows; 53 reachable pairs on the branching fixture; cycle and unreachable-node detection verified; no performance evaluation.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1064 passed, 22 skipped in 134.47s (0:02:14)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：141 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Full integrity audit passed with 1064 tests passed and 22 skipped; exact-hash Stage 1 structural gate is ready.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T13:11:45.328334+00:00 - Verify the S1.3 deterministic P0/P1 label-semantics sidecar contract on synthetic BPMN

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s13_stage1_label_semantics_synthetic_v1；阶段=stage1_offline_label_semantics；方法=stage1_label_p0_raw_and_p1_surface_split；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/verify_stage1_label_semantics_s13.py`
- manifest：outputs/reports/s13_stage1_label_semantics_synthetic_v1.manifest.json
- 结果摘要：Synthetic label verification passed: 6 activities; P0 semantic inference count 0; P1 actor statuses single/no/ambiguous=4/1/1 and label statuses empty/unparsed/action-only/action-object=1/1/1/3; no performance evaluation.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1073 passed, 22 skipped in 137.15s (0:02:17)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：150 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Full integrity audit passed with 1073 tests passed and 22 skipped; exact-hash S1.3 gate is ready; formal BPMN, P2, human Gold, and accuracy remain unrun.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T13:30:11.562409+00:00 - Verify the S1.5 blank human-annotation protocol and fail-closed freeze semantics on synthetic BPMN

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s15_stage1_annotation_protocol_synthetic_v1；阶段=stage1_offline_annotation_protocol；方法=stage1_blank_human_annotation_protocol；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/verify_stage1_annotation_protocol_s15.py`
- manifest：outputs/reports/s15_stage1_annotation_protocol_synthetic_v1.manifest.json
- 结果摘要：Protocol-only verification passed: 1 synthetic process, 6 activities, 18 label fields, 0 resolved, 0 adjudicated, 0 Gold Process Records, freeze_ready=false; formal BPMN membership remains 0.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1079 passed, 22 skipped in 132.34s (0:02:12)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：159 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、stage1_formal_bpmn_membership_not_promoted、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Full integrity audit passed with 1079 tests passed and 22 skipped. Protocol gate is ready; formal membership requires user-approved promotion of provenance BPMN candidates and human annotation.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-17T13:45:59.718659+00:00 - Verify the S1.6 unified structural and label-semantics evaluator contract on synthetic constants

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s16_stage1_evaluator_contract_synthetic_v1；阶段=stage1_offline_evaluator_contract；方法=stage1_unified_evaluator；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/verify_stage1_evaluator_s16.py`
- manifest：outputs/reports/s16_stage1_evaluator_contract_synthetic_v1.manifest.json
- 结果摘要：Evaluator contract passed: exact P0/P1 membership; 8 structural set components; actor/action/business-object exact metrics; triple accuracy; terminal/invalid denominators. Synthetic constants only, not formal performance.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1085 passed, 22 skipped in 129.43s (0:02:09)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：168 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、stage1_formal_bpmn_membership_not_promoted、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Full integrity audit passed with 1085 tests passed and 22 skipped. Formal evaluator scope remains blocked on active BPMN membership and adjudicated Stage 1 Gold.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-18T05:55:43.361822+00:00 - 经用户批准冻结共享Stage 1/Stage 3 GDPR7扩展membership并生成空白Stage 1审核输入

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s15_s31_gdpr7_membership_v1；阶段=stage1_stage3_membership；方法=stage1_bpmn_xml_structural_with_formal_input_id_adapter；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/verify_stage1_stage3_gdpr7.py`
- manifest：outputs/reports/s15_s31_gdpr7_membership_v1.manifest.json
- 结果摘要：7/7 byte-exact BPMN copies verified; 7 unique Process Records; 45 activities; 135 blank label fields; formal membership ready; human Gold 0/7; no performance result
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1090 passed, 22 skipped in 125.49s (0:02:05)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：187 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：用户于2026-07-18明确批准使用7个模型。来源references/winter_2020_model_check/model_check/input/models/gdpr保持只读；活动副本位于data/input/stage1_stage3/gdpr7。明确标注all-seven extension，不称Sun original four。文件3/4复用raw process id，使用membership input_id作为项目级唯一process_id且保留raw id。全量1090 passed, 22 skipped；未读取.env、未调用网络/LLM、未自动填Gold。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-18T08:50:42.918977+00:00 - 生成并激活 EStG-150 Layer D 中文辅助与盲回译，并保留用户已作出的首条翻译决定

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=run_20260718_layerd_deepseek_v4_flash_v2_nonthinking；阶段=S2.2-Layer-D；方法=deepseek-v4-flash-layer-d-review-aid；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/run_llm_zh_aid.py --allow-llm --provider openai_compatible --model deepseek-v4-flash --base-url https://api.deepseek.com --max-calls 300 --start-index 0 --end-index 150 --api-key-env-name DEEPSEEK_API_KEY --run-id run_20260718_layerd_deepseek_v4_flash_v2_nonthinking --temperature 0 --max-tokens 2048 --thinking-mode disabled`
- manifest：data/development/estg/llm_candidate_runs/run_20260718_layerd_deepseek_v4_flash_v2_nonthinking/manifest.jsonl
- 结果摘要：DeepSeek V4 Flash 非思考模式生成成功并激活 Layer D v2：中文 150/150、盲回译 150/150；主运行清单 150 条成功、1 条失败尝试后按同一锁定配置重试成功；严格校验 25/25；全量测试 1094 passed、22 skipped。当前 Layer E 已批准英文 1/150、人工裁决 0/150。
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1094 passed, 22 skipped in 96.93s (0:01:36)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：204 个
- Gold：按授权导入人工审核（`authorized_human_review_import`）；LLM/API：已授权调用（`authorized_called`）；产物：已授权覆盖（`authorized_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：用户已明确授权自动推进及本次真实 DeepSeek API 调用。API 密钥仅从用户级 DEEPSEEK_API_KEY 环境变量加载，未读取或记录 .env，日志中不含密钥。保留失败溯源运行 run_20260718_layerd_deepseek_v4_flash_v1（2 成功、1 失败）以及成功运行 v2（150 成功、1 失败尝试）。两次运行合计实际 HTTP 调用 306 次，prompt tokens=183680，completion tokens=114109；按全部输入均视为缓存未命中的官方单价估算上限约 0.057666 美元。用户此前对 sample_id=estg_000002 的 translation=accepted 决定通过审核服务原样重放，未由 Agent 推断或新增任何人工 Gold。v1 全 null 占位文件保留，v2 已原子激活。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-18T09:42:04.443164+00:00 - 修复 EStG-150 审核工具的 LLM 候选物化与人工修正流程

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1101 passed, 22 skipped in 134.95s (0:02:14)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：208 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：依据用户要求将流程落实为“LLM先提取、人工再核对修正”。修复逐字段 accepted 只改状态却不复制候选值/span 的断链；新增由用户显式点击的整条六字段接受按钮；非空候选缺少精确 span 时 fail closed；人工编辑唯一文本时自动计算 start/end；rejected 清空旧人工值；needs_adjudication 不再制造空 span；actor_action_map/order_relations JSON 现会保存并校验引用。右侧伪可编辑 JSON 改为只读预览，Layer D 150/150 显示绿色真实状态，缩短面板以显示完整控件。所有接受/复核/裁决仍只能由用户点击；未修改 Layer E 的任何现有人工决定。聚焦测试44 passed；全量1101 passed、22 skipped。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-18T10:19:16.127826+00:00 - 修复 EStG-150 审核工具中六要素长候选被裁切的问题

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1102 passed, 22 skipped in 156.05s (0:02:36)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：208 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：六要素候选单元格改为只读自动换行，普通长值显示1至3行；双击任意候选可打开可滚动、可复制的全文窗口；仅修改显示层，未自动改变任何人工决定。聚焦测试45 passed；全量1102 passed、22 skipped。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-18T12:17:36.054835+00:00 - 建立全实验实际问题持续登记与解决状态制度

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1103 passed, 22 skipped in 105.90s (0:01:45)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：212 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：新增唯一 REAL_WORLD_ISSUE_REGISTER；RWI-0001 上下文缺失保持 open；RWI-0002 至 RWI-0004 回填解决方法与既有事件；验证中发现并解决 RWI-0005（测试错误写死 Layer E 0/150），保留用户 1/150 adjudicated；全量 1103 passed、22 skipped、integrity errors=0。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-18T12:24:01.284420+00:00 - 补记终端显示乱码核验并完成问题登记制度收口

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1103 passed, 22 skipped in 154.17s (0:02:34)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：212 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Event 74 持久化中文正常；超长 PowerShell 输出仅显示乱码，登记为 RWI-0006 resolved。最终状态：RWI-0001 open，RWI-0002 至 RWI-0006 resolved；全量 1103 passed、22 skipped、integrity errors=0。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-18T12:36:36.063470+00:00 - 登记Sun语言转换缺口并限定非德语人工审核职责

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1103 passed, 22 skipped in 172.51s (0:02:52)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：212 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：新增 RWI-0007 open：Sun 的德文 EStG 来源与英语 phrase 方法之间未披露转换；用户只裁决冻结英文工作文本上的六要素/span，不承担德译英认证；疑似翻译问题待裁决，正式冻结前选择原生英文主轨道或独立翻译加德语复核 QA。全量 1103 passed、22 skipped、integrity errors=0。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-18T12:51:37.538443+00:00 - 完成 EStG-150 句子级独立性逐条盘点并生成审核辅助表

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1103 passed, 22 skipped in 164.11s (0:02:44)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：212 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：150/150；独立82、需上下文核实26、不独立42；生成XLSX、JSONL和manifest；RWI-0001保持open；未修改Layer E。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-19T12:42:25.762119+00:00 - 冻结 Stage 2 统一六要素提取合同并同步人工、D1 与 H1

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1110 passed, 22 skipped in 135.47s (0:02:15)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：221 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：冻结 stage2_extraction_contract@1.0.0 与 hash bundle；现有 canonical schema 保持 byte-identical；同步人工协议、D1/H1 v5、H1 ambiguity metadata merge、方法注册和 exact-hash gates；选取 12 条既有 EStG ID/hash 作为非 Gold/非 few-shot/非性能静态 pilot；S2.8 v6 与 S2.9 v5 离线 manifest 已生成。全量 1110 passed、22 skipped、integrity errors=0；未改 Layer E Gold 或 Rule-only，未调用真实 LLM/API；RWI-0001/RWI-0007 继续 open。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-20T04:32:34.815953+00:00 - 修复 EStG-150 审核工具人工值导航回显与提交断链

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1113 passed, 22 skipped in 158.47s (0:02:38)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：221 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：RWI-0009 resolved：复数 span 数组正确回显；上一条、下一条、下一条待审、保存、复核和裁决统一先提交当前英文、六要素、关系与备注；无 exact span 或关系错误时停留当前记录。审核工具48项聚焦测试通过；全量1113 passed、22 skipped；未修改用户 Layer E 决定。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-20T09:12:43.823482+00:00 - 准备 EStG-150 GPT-5.6 Sol 双轮 AI 裁决候选与中转安全闸门

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1133 passed, 22 skipped in 138.41s (0:02:18)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：227 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：固定 gpt-5.6-sol/high/strict JSON Schema；支持 ChatAnywhere 基础或完整端点；密钥隐藏输入；实时币种单价、预算、调用上限、pilot≤5 与全量二次授权 fail-closed；不读 DeepSeek Layer D，不读写 Layer E。全量测试 1133 passed、22 skipped；真实 API 未调用。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-20T09:40:06.749845+00:00 - 记录 ChatAnywhere pilot 被托管数据外发策略拒绝

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1133 passed, 22 skipped in 153.40s (0:02:33)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：227 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：用户已确认第三方风险、CNY 单价、3条/15 CNY预算，并在获知具体外发内容后再次授权；托管策略仍在读取密钥、创建run目录和HTTP调用前拒绝向不受信任中转外发。未绕过；RWI-0010保持mitigated。安全替代为等待用户明确授权Codex内置gpt-5.6-sol子代理委派。全量测试1133 passed、22 skipped。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-20T10:20:15.320279+00:00 - 完成内置 GPT-5.6 Sol 三条双轮 AI 裁决候选 pilot

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=codex_internal_gpt56sol_pilot3_v1；阶段=stage2_annotation_candidate；方法=gpt-5.6-sol_two_pass_internal_candidate；状态=成功（`succeeded`）
- 实际运行命令：`Codex internal subagents: /root/estg_pilot_pass_a then /root/estg_pilot_pass_b`
- manifest：data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_pilot3_v1/manifest.jsonl
- 结果摘要：development-only first-3 pilot; Pass A/Pass B/root validation 3/3; translation accepted=1 edited=2; context insufficient=1 uncertain=2; confidence medium=3; no Layer D/E input, no external relay, no Gold promotion
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1134 passed, 22 skipped in 159.00s (0:02:38)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：232 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：用户明确授权 Codex 内置 gpt-5.6-sol 子代理。两个独立 high-reasoning 子代理完成双轮；外部 ChatAnywhere 未调用、密钥未读取、外部费用0 CNY。Layer E 保持 adjudicated=3/150，六要素已决21/900；全量150条未授权。全量测试1134 passed、22 skipped。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-20T12:45:01.494373+00:00 - 完成内置 GPT-5.6 Sol 全量六要素提取与极简用户修改工具

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=codex_internal_gpt56sol_full150_v1；阶段=stage2_annotation_candidate；方法=gpt-5.6-sol_internal_full_extract_simple_user_review；状态=成功（`succeeded`）
- 实际运行命令：`Codex internal gpt-5.6-sol subagents; python scripts/build_estg150_internal_sol_bundle.py --write`
- manifest：data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/manifest.json
- 结果摘要：150/150 regulations extracted into 232 clauses; simple review tool ready; existing Layer E preserved at approved_text_en=4/150, resolved six-element fields=21/900, adjudicated=3/150
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1141 passed, 22 skipped in 128.85s (0:02:08)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：268 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、annotation_freeze_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：User explicitly authorized Codex-internal gpt-5.6-sol subagents. No external API or ChatAnywhere was used; no API key was read; cost was zero. All candidates and spans validated. UI exposes only previous, later, German source, and save-next; span offsets and legacy review/adjudication mechanics remain hidden. Scientific label remains LLM-assisted, human-adjudicated after user edits.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-21T06:12:21.206529+00:00 - 验证并锁定 EStG-150 S2.2 人工注释冻结 receipt

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s22_estg150_human_annotation_freeze_v1；阶段=stage2_human_annotation_freeze；方法=human_adjudication_freeze_receipt；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/verify_estg150_s22_freeze.py --write`
- manifest：outputs/reports/s22_estg150_human_annotation_freeze_v1.manifest.json
- 结果摘要：Layer E: 150/150 approved English, 900/900 resolved field decisions, 150/150 adjudicated, 231 clauses; annotation frozen; formal Gold publication and formal B0/H1/D1 runs remain blocked on RWI-0001/RWI-0007 and route/data/Stage3 gates
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1145 passed, 22 skipped in 160.19s (0:02:40)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：273 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Deterministic no-overwrite receipt and fail-closed exact-hash gate added. No data/gold or data/input write, no prediction/result generation, no network/API call, and no human decision changed. Full offline audit: 1145 passed, 22 skipped.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-21T07:36:51.946236+00:00 - 运行并锁定 EStG-150 B0 development 评价及低额度 H1/D1 pilot 计划

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_development_v1；阶段=S2.7-B0-DEV/S2.10；方法=sun_rule_only；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/run_estg150_b0_development.py --runtime-home D:\environment\stanford-corenlp-4.5.10 --device cpu`
- manifest：outputs/development/s27_estg150_b0_development_v1/manifest.json
- 结果摘要：development only: 150/150 attempts; all150 modality clause accuracy/macro-F1=0.103896/0.090583; independent82=0.128440/0.119124; five-field precision/recall/F1 persisted; 0 LLM/API calls
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1153 passed, 22 skipped in 188.81s (0:03:08)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：281 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：首次真实批处理暴露 Tsurgeon 完整树删除并登记 RWI-0013；保留原 locked bridge/rules，以 batch bridge 显式记录 2/266 terminal removals 后成功重跑。exact-hash gate 通过；低额度 paired diagnostic pilot 锁为 7 IDs、H1<=7+D1<=7、0 retry，但精确 gpt-4.1 子代理/transport 当前不可用，未执行且未静默换模。全量离线审计 1153 passed、22 skipped、0 errors；formal Gold 与正式比较仍被既有门禁阻塞。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-21T08:24:07.306502+00:00 - 修复 S2.10-E 方法本地 ID/边界低计并重算 EStG-150 B0 development 指标

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_v3_evaluation_v1；阶段=S2.10-E-v1.2/S2.7-B0-DEV-REEVAL；方法=sun_rule_only_immutable_attempts_v3_evaluator；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/verify_stage2_evaluator_s210_v3.py; python scripts/reevaluate_estg150_b0_v3.py`
- manifest：outputs/development/s27_estg150_b0_v3_evaluation_v1/manifest.json
- 结果摘要：development only; all150 modality micro P/R/F1=0.394737/0.454545/0.422535, macro-F1=0.406801; clause alignment P/R/F1=0.680451/0.783550/0.728370; independent82 modality micro P/R/F1=0.433071/0.504587/0.466102; 0 model/API reruns
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1166 passed, 22 skipped in 203.07s (0:03:23)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：291 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：RWI-0014 resolved. v1.2 threshold 0.5 was frozen before result generation; method-local IDs are ignored, exact segmentation remains separate, and paper-score targeting/threshold search are forbidden. Old v1 development report is preserved as superseded provenance. Sun 0.77/0.83/0.80 is locally recorded Stage 3 evidence and is not a comparable Stage 2 acceptance target. Synthetic/adversarial receipt: outputs/reports/s210_stage2_evaluator_contract_synthetic_v3.manifest.json. Full offline audit: 1166 passed, 22 skipped, 0 errors.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-21T10:04:37.135987+00:00 - EStG-150 B0 enhanced v3 development: clause-level modality routing, segmentation merge, multi-match phrase extraction; no Gold/LLM

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_enhanced_v3；阶段=stage2；方法=b0_enhanced；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_b0_enhanced_development.py --config formal_experiment/configs/models/estg150_b0_enhanced_s27_v3.json --runtime-home D:\environment\stanford-corenlp-4.5.10 --device cpu`
- manifest：formal_experiment/outputs/development/s27_estg150_b0_enhanced_v3/manifest.json
- 结果摘要：development only; modality micro F1 0.423->0.612; alignment F1 0.728->0.771; complete-record 0.06->0.167; Table8 any-overlap overall F1=0.443; not formal
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1172 passed, 22 skipped in 138.80s (0:02:18)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：311 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：RWI-0015 mitigated; RWI-0001/0007 remain open; v1 artifacts preserved; Windows subprocess utf-8 test harness fixed
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-21T11:21:49.373670+00:00 - EStG-150 b0_enhanced v5 development after v4 regression; hybrid segmentation and definition-first modality

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_enhanced_v5；阶段=stage2；方法=b0_enhanced_v5；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_b0_enhanced_v4_development.py --config formal_experiment/configs/models/estg150_b0_enhanced_s27_v5.json --runtime-home D:\environment\stanford-corenlp-4.5.10 --device cpu`
- manifest：formal_experiment/outputs/development/s27_estg150_b0_enhanced_v5/manifest.json
- 结果摘要：v5 modality micro F1 0.624 align F1 0.801 complete-record 0.347 Table8 F1 0.492; vs v3 modest gains; not formal not Sun targets
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：否；正式实验就绪：否
- 测试：1 failed, 1177 passed, 22 skipped in 162.00s (0:02:41)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：310 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：RWI-0015 mitigated; RWI-0001/0007 open; v4 retained as negative evidence
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-21T11:28:52.788034+00:00 - Post-v5: regenerate catalog and confirm full offline suite green after b0_enhanced_v5 development batch

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1178 passed, 22 skipped in 172.67s (0:02:52)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：310 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Reconfirm integrity after catalog refresh; experiment run s27_estg150_b0_enhanced_v5 already appended; RWI-0001/0007 remain open
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-21T14:54:51.489267+00:00 - S2.7-B0-ENHANCED-DEV v6 development run (negative evidence vs v5)

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_enhanced_v6；阶段=S2.7-B0-ENHANCED-DEV；方法=b0_enhanced_v6；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_b0_enhanced_v6_development.py --runtime-home D:\environment\stanford-corenlp-4.5.10 --output-dir formal_experiment/outputs/development/s27_estg150_b0_enhanced_v6`
- manifest：outputs/development/s27_estg150_b0_enhanced_v6/manifest.json,outputs/development/s27_estg150_b0_enhanced_v6/evaluation_all150.json,outputs/development/s27_estg150_b0_enhanced_v6/evaluation_independent82.json,outputs/development/s27_estg150_b0_enhanced_v6/sun_table8_any_overlap_diagnostic.json
- 结果摘要：modality micro P=0.562 R=0.628 F1=0.593 (v5 0.594/0.658/0.624); clause alignment F1=0.769 (v5 0.801); regression vs v5; v5 remains current best; v6 retained as negative development evidence
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1225 passed, 22 skipped in 165.50s (0:02:45)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：324 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：无
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-21T15:00:59.901952+00:00 - RWI-0015 update: log v6 development run as negative evidence vs v5

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1225 passed, 22 skipped in 163.97s (0:02:43)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：324 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：v6 is a regression vs v5; v5 remains current best; v6 retained as negative development evidence; v6 manifest hash and metric diff recorded in RWI-0015
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-22T08:14:38.621990+00:00 - Correct invalid Minimax v6 Phase A diagnostics: real S2.4 classifier ablation, Gold segmentation oracle, DE-S2.4 overlap audit; RWI-0016

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1229 passed, 22 skipped in 126.90s (0:02:06)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：328 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：v6 full run retained as negative evidence; Phase A attribution invalid; correction at s27_estg150_b0_phase_a_correction_v2; v5 remains current best; no v7 started
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-22T12:16:47.276661+00:00 - S2.4 BERT candidates A/B/C preregistered; B invsqrt-weighted wins on dev and is promotable; C balanced sampler secondary; A bound to locked parent

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s24_candidate_selection_v1；阶段=S2.4-CAND；方法=legal_bert_textcnn_candidates；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/train_s24_bert_textcnn_candidates.py --candidate B_invsqrt_weighted_ce --device cpu; python formal_experiment/scripts/train_s24_bert_textcnn_candidates.py --candidate C_balanced_sampler --device cpu`
- manifest：formal_experiment/outputs/reports/s24_bert_textcnn_candidate_selection_v1.manifest.json
- 结果摘要：dev winner B macro-F1=0.8590 > parent 0.8563; test B macro-F1=0.8772 (not used for selection); C dev=0.8587 test=0.8642; A=parent
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1235 passed, 22 skipped in 161.33s (0:02:41)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：353 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：No ESTG/All-150 used for selection; test_used_for_selection=false
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-22T12:23:36.896794+00:00 - b0_enhanced_v7 development modest promote vs v5

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_enhanced_v7；阶段=S2.7-B0-ENHANCED-DEV；方法=b0_enhanced_v7；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_b0_enhanced_v7_development.py --config formal_experiment/configs/models/estg150_b0_enhanced_s27_v7.json --runtime-home D:\environment\stanford-corenlp-4.5.10 --device cpu`
- manifest：formal_experiment/outputs/development/s27_estg150_b0_enhanced_v7/manifest.json
- 结果摘要：modality micro P/R/F1 0.598/0.662/0.628 vs v5 0.594/0.658/0.624; align F1 0.801; Table8 F1 0.492; current best development; v6 negative
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：否；正式实验就绪：否
- 测试：1 failed, 1234 passed, 22 skipped in 144.59s (0:02:24)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：338 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：candidate B classifier; lexicon v2 161 active; tsurgeon_enabled=false; no edge fanout
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-22T13:22:34.518404+00:00 - Post-v7 catalog refresh; integrity green; current best b0_enhanced_v7

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1235 passed, 22 skipped in 170.07s (0:02:50)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：338 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：v7 experiment_run already logged; this confirms catalog+1235 tests green
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-22T14:00:19.074218+00:00 - Preregister b0_enhanced_v8 before any candidate run: residual Phase A fixes, production lexicon, ownership-only edges, max 3 candidates A/B/C

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1235 passed, 22 skipped in 181.38s (0:03:01)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：341 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：prereg=configs/models/estg150_b0_v8_preregistration_v1.json sha=7b8eadd20fd996d7025abcd3f9f54780b5417157865950cb7c57be2e40ddfa48; RWI-0016 mitigated residual; RWI-0017 open S2.4 test exposed; no v8 candidate run yet
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-22T14:56:42.991214+00:00 - v8 prereg + residual Phase A v3 + overlap v2 + v8-A/B/C candidates; none promoted; v7 remains provisional best

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_v8_batch；阶段=S2.7-B0-ENHANCED-DEV；方法=b0_enhanced_v8；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_b0_enhanced_v8_development.py --config formal_experiment/configs/models/estg150_b0_enhanced_s27_v8a.json --runtime-home D:\environment\stanford-corenlp-4.5.10 --device cpu (and v8b/v8c)`
- manifest：formal_experiment/outputs/reports/s27_estg150_b0_v8_selection_v1.manifest.json
- 结果摘要：v8a/b/c modality F1=0.63244 (+0.004 vs v7, +1 TP) fails +0.010 gate; v8b/c Table8 F1 0.506 hallu up; residual: align_cov=0.281 unsupported=184; no promotion
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：否；正式实验就绪：否
- 测试：1 failed, 1240 passed, 22 skipped in 145.84s (0:02:25)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：347 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：RWI-0016 mitigated residual v3; RWI-0017 open; prereg sha 7b8eadd2... before candidates; tsurgeon_enabled=false; edge FP still 185
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-22T15:01:35.258870+00:00 - Post-v8 batch: catalog refresh; integrity green; no v8 promotion; v7 provisional best

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1241 passed, 22 skipped in 155.69s (0:02:35)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：347 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Prior v8 experiment_run had integrity_pass=false only due to stale FILE_CATALOG; 1241 passed; selection report s27_estg150_b0_v8_selection_v1; RWI-0016 mitigated; RWI-0017 open
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-22T16:21:22.241036+00:00 - v8 status correction v2, active_registry_v1, b0_v9 package and v9 preregistration; no v9 experiment run

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：否；正式实验就绪：否
- 测试：1 failed, 1250 passed, 22 skipped in 164.88s (0:02:44)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：359 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：correction 363fdc28; registry 8c8395e0; v9 prereg 22ea52d6; v8a invalid placeholder; v8c no-op; v7 provisional best; 1251 tests green
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-22T16:27:13.355708+00:00 - Integrity green after v8 correction/registry/v9 prereg catalog refresh; no v9 run

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1251 passed, 22 skipped in 160.76s (0:02:40)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：359 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：v8a invalid; v8c no-op; v8b negative; active v5+v7; v9 prereg only; 1251 passed
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-22T17:28:44.438869+00:00 - v9a clean-core run not promoted; v9-B not_instantiated; provisional best remains v7

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_enhanced_v9a；阶段=S2.7-B0-ENHANCED-DEV；方法=b0_enhanced_v9a；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_b0_enhanced_v9_development.py --config formal_experiment/configs/models/estg150_b0_enhanced_s27_v9a.json --runtime-home D:\environment\stanford-corenlp-4.5.10 --device cpu`
- manifest：formal_experiment/outputs/development/s27_estg150_b0_enhanced_v9a/manifest.json
- 结果摘要：mod F1=0.62834 equal v7; placeholder=0; align 225/256; hallu 0.277; edgeFP 34; not promoted
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1253 passed, 22 skipped in 221.89s (0:03:41)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：364 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：selection 910f09d3; modular b0_v9; v9-B not_instantiated
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-22T18:45:19.246930+00:00 - v9 status correction; v10 modular scope fix; v10a All-150 accepted for scope gates; modality not promoted; v7 remains provisional best

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_enhanced_v10a；阶段=S2.7-B0-ENHANCED-DEV；方法=b0_enhanced_v10a；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_b0_enhanced_v10_development.py --config formal_experiment/configs/models/estg150_b0_enhanced_s27_v10a.json --runtime-home D:\environment\stanford-corenlp-4.5.10 --device cpu`
- manifest：formal_experiment/outputs/development/s27_estg150_b0_enhanced_v10a/manifest.json
- 结果摘要：Table8 F1 0.492->0.540; cons F1 0.096->0.396 vs v9a; presence 0.703; complete 0.36; hallu 0.343; modality F1 still 0.6283=v7; scope gates PASS; final promotion FAIL
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1261 passed, 22 skipped in 204.52s (0:03:24)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：394 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：prereg v2 9b074dd9; v9 scope prereg mismatch corrected; placeholder=0; tregex_final_affected=453; no S2.4 test; no BERT retrain
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-22T20:21:43.304695+00:00 - B1 deontic-nucleus segmentation; failed promotion; negative evidence

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_enhanced_b1；阶段=S2.7-B0-ENHANCED-DEV；方法=b0_enhanced_b1；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_b0_enhanced_b1_development.py --config formal_experiment/configs/models/estg150_b0_enhanced_s27_b1.json --runtime-home D:\environment\stanford-corenlp-4.5.10 --device cpu`
- manifest：formal_experiment/outputs/development/s27_estg150_b0_enhanced_b1/manifest.json
- 结果摘要：align F1 0.794 exact 0.140 mod P/R/F1 0.596/0.658/0.626 pred 255; gates FAIL; v10-A parent retained; v7 best
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1271 passed, 22 skipped in 187.86s (0:03:07)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：389 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：prereg 1d7e30c0; segmentation only; no B2/BERT; fixtures 10 passed
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-22T21:46:25.372037+00:00 - B2a definition disambiguation on v10-A; FP reduced but definition TP/FN gates fail; not promoted

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_enhanced_b2a；阶段=S2.7-B0-ENHANCED-DEV；方法=b0_enhanced_b2a；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_b0_enhanced_b2a_development.py --config formal_experiment/configs/models/estg150_b0_enhanced_s27_b2a.json --runtime-home D:\environment\stanford-corenlp-4.5.10 --device cpu`
- manifest：formal_experiment/outputs/development/s27_estg150_b0_enhanced_b2a/manifest.json
- 结果摘要：def TP/FP/FN 16/28/23 F1 0.386; overall TP 155 F1 0.6366; seg identical v10a 256/195; definition gates FAIL so not promote; v10-A parent
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1282 passed, 22 skipped in 213.10s (0:03:33)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：395 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：prereg 58ed8b51; conf=0.55 a priori; no B1; no second run; diagnostic 37d395c9
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-23T05:44:44.330485+00:00 - B2a2 clause-local constrained decoding removed supported record fallback but failed definition and overall promotion gates; retained as negative evidence

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_enhanced_b2a2；阶段=S2.7-B0-ENHANCED-DEV；方法=b0_enhanced_b2a2；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_b0_enhanced_b2a2_development.py --config formal_experiment/configs/models/estg150_b0_enhanced_s27_b2a2.json --runtime-home D:\environment\stanford-corenlp-4.5.10 --device cpu`
- manifest：formal_experiment/outputs/development/s27_estg150_b0_enhanced_b2a2/manifest.json
- 结果摘要：route A and exact-v10 E gates PASS; fallback 20, supported new fallback 0; definition TP/FP/FN 2/13/37 F1 0.0741; overall TP 142 F1 0.5832; B/C/D FAIL; not promoted
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1310 passed, 22 skipped in 136.76s (0:02:16)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：403 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：route diagnostic manifest cf5d8d86: 40/40 same-clause vectors valid; prereg edd69b9d; run manifest 58aacd50; exactly one All150; no rerun, no threshold/rule change, no Independent82, no S2.4 test, no network/LLM, active registry unchanged; RWI-0018
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-23T06:29:58.373211+00:00 - B2b prohibition-permission read-only diagnostic; strict evidence whitelist failed instantiation threshold

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_b2b_prohibition_diagnostic_v1；阶段=S2.7-B0-ENHANCED-DEV-B2b；方法=permission_to_prohibition_strong_negation_scope_diagnostic；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/analyze_estg150_b0_b2b_prohibition_diagnostic_v1.py`
- manifest：formal_experiment/outputs/development/s27_estg150_b0_b2b_prohibition_diagnostic_v1/manifest.json
- 结果摘要：not_instantiated: aligned prohibition-to-permission=6; allowed-rule triggers=1; recoverable upper bound=1; permission TP loss=0; at-least-three gate failed; no All150
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1310 passed, 22 skipped in 137.93s (0:02:17)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：404 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：diagnostic sha=e0cdc8956eafb76c97a915460b2fcf62f53a8b671eb04f00d27cae0c92de9d44; summary sha=571fc2977fc9017d4ec049311142f764e121a2c73ab0919c0010cc9513d43886; prereg sha=N/A not created; fixed All150 command=N/A not executed; B2b run manifest sha=N/A; promotion report sha=N/A; promotion=not applicable/not instantiated; failed instantiation condition=at_least_three_recoverable_errors; Gold read-only; evaluator unchanged 28ce332564c5d10da08dea515aefe31cc2aacd91b6c6877aa1bfebe44f39ae7f; S2.4 test unread; Independent-82 unread; LLM/API/network=0; active registry unchanged; no production resolver; no B2c/B3/BERT/lexicon/Tregex
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-24T04:05:25.247797+00:00 - B3a constraint Tregex diagnostic only; not_instantiated; no All-150; v10-A remains parent

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：否；正式实验就绪：否
- 测试：1 failed, 1309 passed, 22 skipped in 164.68s (0:02:44)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：406 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：diagnostic bf1c8180; decision 08ab34fc; union FN recover 7<8; new spans 0; only 2/6 patterns met floor; no registry/runner/prereg/All-150; lexicon/bridge/Tsurgeon unchanged; active registry unchanged
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-24T04:21:55.526524+00:00 - B3a not_instantiated integrity green after catalog refresh; diagnostic only; no All-150

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1310 passed, 22 skipped in 186.20s (0:03:06)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：406 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：prior event integrity_pass=false due to stale FILE_CATALOG only; 1310 passed; decision not_instantiated; diagnostic bf1c8180; decision 08ab34fc; v10-A parent unchanged
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-25T04:13:02.054087+00:00 - B3a diagnostic correction v2: live CoreNLP/Tregex opportunity attribution with real instance keys and v10-A dedup

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1342 passed, 22 skipped in 186.43s (0:03:06)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：410 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：v1 corrected status=inconclusive_not_instantiated_invalid_for_tregex_opportunity_attribution; diagnostic manifest=ddcf26581d8dde61eb9b95fd015d5cbb34b17763c74db6888af7efffed6a4cc0; status correction=6ac545ae38776075bc78902ddf739418ed11067746b4024fdc610c68f7343de0; six frozen patterns live compile 6/6; raw/accepted/final=106/98/76; exact/normalized/containment/partial/new=40/0/24/2/10; add-only TP/FP/FN delta=0/10/0; 32 focused tests and 1342 full tests passed; no production candidate, candidate All-150, B3b, network, LLM/API, S2.4 test, Independent-82, registry or production bridge change
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-25T05:40:05.198791+00:00 - B3b typed condition-constraint ownership opportunity diagnostic and stop-gate decision

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_b3b_typed_ownership_diagnostic_v1；阶段=S2.7-B0-ENHANCED-DEV-B3b；方法=typed_condition_constraint_ownership；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/analyze_estg150_b0_b3b_typed_ownership_diagnostic_v1.py --runtime-home D:\environment\stanford-corenlp-4.5.10`
- manifest：formal_experiment/outputs/development/s27_estg150_b0_b3b_typed_ownership_diagnostic_v1/manifest.json
- 结果摘要：development Gold opportunity diagnostic only; 87 spans/53 records changed; 11/18 instantiation gates failed; decision not_instantiated; no production candidate or candidate All-150
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1368 passed, 22 skipped in 247.87s (0:04:07)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：412 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Fixed v10-A/lexicon/scope/Tregex/evaluator bindings matched; parent scope replay exact for 580 condition/constraint spans; pre-result JSON-array loader correction changed no rule or threshold; active registry unchanged; Independent-82 and S2.4 test not used; B3c/actor/marker expansion/Tsurgeon/BERT not started.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-25T06:35:53.990650+00:00 - B4 constraint marker lexicon expansion single-candidate development run and stop-gate decision

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_enhanced_b4；阶段=S2.7-B0-ENHANCED-DEV-B4；方法=b0_enhanced_b4_constraint_marker_expansion；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_b0_enhanced_b4_development.py --config formal_experiment/configs/models/estg150_b0_enhanced_s27_b4.json --runtime-home D:\environment\stanford-corenlp-4.5.10 --device cpu`
- manifest：formal_experiment/outputs/development/s27_estg150_b0_enhanced_b4/manifest.json
- 结果摘要：single preregistered All-150 succeeded; constraint 130/224/172 P/R/F1 0.367232/0.430464/0.396341; overall 462/430/362 P/R/F1 0.517937/0.560680/0.538462; performance gates failed; not promoted; v10-A remains parent
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：否；正式实验就绪：否
- 测试：2 failed, 1379 passed, 22 skipped in 176.78s (0:02:56)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：420 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：25 new active constraint markers loaded, 21 invoked, 70 invocations, 19 final new spans across 18 clauses, zero parent spans removed; purity, locked components, coverage, schema, and nonconstraint fields passed; 10 constraint/overall performance gates failed; no tuning or rerun; active registry unchanged; network/LLM/API/test dataset not used; final audit integrity true with 1381 passed and 22 skipped.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-25T06:40:33.006415+00:00 - B4 provenance verification correction after sandbox-only test false negative

- 事件类型：里程碑（`milestone`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：否；正式实验就绪：否
- 测试：2 failed, 1379 passed, 22 skipped in 182.20s (0:03:02)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：420 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Corrects only the verification status of the immediately preceding B4 experiment event: its two test failures came from restricted pytest temp-directory execution after a verification-receipt mismatch. The B4 run, artifacts, metrics, not-promoted decision, marker set, and active registry are unchanged; no All-150 or model process was rerun. Elevated offline verification is authorized solely for isolated pytest temp-directory creation/cleanup.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-25T06:49:15.629637+00:00 - B4 final UTF-8 provenance verification correction

- 事件类型：里程碑（`milestone`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1381 passed, 22 skipped in 169.63s (0:02:49)
- 测试证据：本次新运行（`fresh_run`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：420 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Final correction for B4 provenance verification only. With explicit UTF-8 child-process I/O and isolated pytest temp access, the unchanged project state passes the complete offline suite. The two preceding integrity=false events are retained as immutable Windows execution-environment false negatives. No B4 resource, preregistration, output, metric, decision, model process, or active registry was changed; All-150 was not rerun.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-25T10:03:50.540451+00:00 - B5 genuine Tsurgeon and post-surgery Tregex diagnostic with concurrent preregistration drift disclosed

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=s27_estg150_b0_enhanced_b5；阶段=S2.7-B0-ENHANCED-B5-DEV；方法=b0_enhanced_b5_tsurgeon_post_surgery_tregex_consumed；状态=部分完成（`partial`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_b0_enhanced_b5_development.py --config formal_experiment/configs/models/estg150_b0_enhanced_s27_b5.json --runtime-home D:\environment\stanford-corenlp-4.5.10 --device cpu`
- manifest：formal_experiment/outputs/development/s27_estg150_b0_enhanced_b5/manifest.json
- 结果摘要：Structurally instantiated; synthetic 15/15; sole All-150 raw/attempted/accepted/rejected=1103/338/336/2; A/B/C/E/F fail, D pass; actor/action/overall Table8 F1=0.428571/0.574431/0.505585; not promoted; v10-A remains. Concurrent Grok write changed prereg during the run, so manifest prereg sha 38a11e... differs from frozen/current 2b3062...; outputs retained diagnostic-only and not rerun.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1396 passed, 22 skipped in 146.48s (0:02:26)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：429 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：RWI-0021 records the concurrent-write provenance defect. Original frozen B5 files were restored byte-exact from local session history and all 22 bindings pass. Existing B5 manifest/output artifacts were not edited. Grok's later duplicate command failed closed in about 5 seconds and did not execute a second All-150. Active registry unchanged; B4 lexicon not loaded; Independent-82 and S2.4 test not read; network/API=0; no B6/BERT stage or training started. The first record_change invocation timed out before append while its fallback pytest run was incomplete; this invocation completed the required evidence run and remains the sole appended B5 event.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-25T12:18:39.427431+00:00 - EStG-150 原始候选协议 C0：锁定 canonical external serializer、历史路由、四类 provider adapter、preregistration、fixture 与审计门禁

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1408 passed, 22 skipped in 238.00s (0:03:58)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：438 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：历史隐藏 Codex transport payload 未归档，因此仅声明 canonical external protocol v1；Layer D/E/Gold 不进入候选请求；C1-C4 未运行。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-25T12:52:07.238397+00:00 - EStG-150 C1 DeepSeek-V4-Pro 官方 transport pilot：验证固定 strict JSON Schema envelope

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=c1_deepseek_v4_pro_transport_pilot_v1；阶段=C1；方法=deepseek-v4-pro；状态=失败（`failed`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_candidate_protocol.py --stage c1 --execute-api --confirm-authorized-provider-budget --provider-adapter deepseek_official --model deepseek-v4-pro --endpoint https://api.deepseek.com/chat/completions --run-id c1_deepseek_v4_pro_transport_pilot_v1 --max-calls 1 --max-total-tokens 13000 --max-cost 0.01 --cost-currency USD --input-price-per-million 0.435 --output-price-per-million 0.87 --api-key-env-name DEEPSEEK_API_KEY --timeout-seconds 300`
- manifest：data/development/estg/llm_candidate_runs/c1_deepseek_v4_pro_transport_pilot_v1/failure.json
- 结果摘要：Official DeepSeek endpoint rejected the frozen strict JSON Schema request envelope with HTTP 400; status=protocol_incompatible; request_count=1; retry_count=0; no candidate and no evaluation.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1408 passed, 22 skipped in 172.76s (0:02:52)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：442 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：No protocol downgrade, content repair, content retry, C2 transition, Layer D/E/Gold read, or P/R evaluation occurred.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-25T13:05:51.446551+00:00 - EStG-150 C1 ChatAnywhere gpt-4o transport pilot：验证冻结 canonical strict envelope

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=c1_relay_gpt4o_transport_pilot_v1；阶段=C1；方法=gpt-4o；状态=失败（`failed`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_candidate_protocol.py --stage c1 --execute-api --confirm-authorized-provider-budget --provider-adapter relay_openai_compatible --model gpt-4o --endpoint https://api.chatanywhere.tech/v1/chat/completions --run-id c1_relay_gpt4o_transport_pilot_v1 --max-calls 1 --max-total-tokens 13000 --max-cost 0.60 --cost-currency CA --input-price-per-million 17.5 --output-price-per-million 70 --api-key-env-name CHATANYWHERE_API_KEY --timeout-seconds 300`
- manifest：data/development/estg/llm_candidate_runs/c1_relay_gpt4o_transport_pilot_v1/failure.json
- 结果摘要：ChatAnywhere rejected the frozen relay gpt-4o request envelope with HTTP 400; status=protocol_incompatible; request_count=1; retry_count=0; no candidate and no evaluation.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1408 passed, 22 skipped in 154.19s (0:02:34)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：446 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Relay identity is unverified_relay_report. No envelope downgrade, content repair/retry, C2 transition, Layer D/E/Gold read, or P/R evaluation occurred; the HTTP 400 body was not archived, so no single envelope field is claimed as the cause.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-25T13:38:06.102556+00:00 - EStG-150 C1 HTTP 失败诊断加固：保留限长 provider error body/hash/request ID/retry，阻断密钥回显落盘且保持请求字节不变

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1411 passed, 22 skipped in 239.69s (0:03:59)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：446 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：RWI-0023 mitigated. 既有 DeepSeek V4 Pro 与 ChatAnywhere gpt-4o 两次 HTTP 400 正文不可恢复；本批次未发真实 API。15 项聚焦测试通过；完整验证 1411 passed, 22 skipped；serializer SHA d20ae560a627c4d3faa88439908c517e7726aabb1121128af7b9013f5512edef，既有 gpt-4o transport SHA 601f0e88e569dcf826acd57799d72db99c3bddcdb9d39b462e7ae1c7a7fbea27 均未变化。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-25T14:00:35.531250+00:00 - EStG-150 C1 七模型 transport 兼容性矩阵与字段级失败诊断

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=c1_transport_compatibility_matrix_20260725_v1；阶段=C1；方法=canonical_external_transport_matrix；状态=失败（`failed`）
- 实际运行命令：`run_estg150_candidate_protocol.py C1: ChatAnywhere gpt-5.6-luna,gpt-5.4-nano,gpt-5-nano,gpt-4.1-nano,gpt-4o,gpt-3.5-turbo plus official deepseek-v4-pro; one synthetic per model; fixed canonical request`
- manifest：data/development/estg/llm_candidate_runs/c1_transport_compatibility_matrix_20260725_v1/manifest.json
- 结果摘要：7 logical requests, 2 identical-byte transport retries, 0 valid candidates, 0 evaluations, P/R not applicable, C2 not started. Failures separate into strict-schema type requirement, unsupported reasoning_effort, unsupported DeepSeek developer role, relay 503 exhaustion, and relay disconnect.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1413 passed, 22 skipped in 237.97s (0:03:57)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：481 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：User ceilings: relay 6 models/78000 tokens/1.25 CA; official DeepSeek 1 model/13000 tokens/0.01 USD; per-run relay caps sum 1.15 CA. Provider usage and actual billed cost were unavailable, so zero cost is not claimed. RWI-0023 diagnostic capture worked; RWI-0024 RemoteDisconnected retry classification fixed offline without an extra API call. No request/schema downgrade, C2, Layer D/E/Gold generation read, candidate, or evaluation.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T04:58:45.914106+00:00 - EStG-150 C1 strict transport v1.1 离线兼容性修复与 fail-closed 预检

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1437 passed, 22 skipped in 238.24s (0:03:58)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`3c3d07c5dcd0036d39d0e8a23b3ec85ab4c6e8ad`；相关未提交路径：489 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Canonical v1 schema/config/lock/prompts/messages/synthetic/serializer remained unchanged; added an exact six-type strict transport derivation, recursive Structured Outputs and seven-model capability preflight, dual-provenance receipts, and Windows nested-test UTF-8 hardening. Full verification: 1437 passed, 22 skipped, integrity errors=0. Real API=0; user-attested billed tokens=0; C1 passed=false; P/R=null; C2=false. git diff --check only reported pre-existing trailing spaces in untouched frozen D1/H1 prompt files.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T06:15:48.687824+00:00 - EStG-150 C1 strict transport v1.1 单条 ChatAnywhere gpt-5.6-luna 真实兼容性验证

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=c1_relay_gpt56_luna_strict_v1_1_pilot_v1；阶段=c1；方法=estg150_canonical_external_candidate_protocol；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_candidate_protocol.py --stage c1 --execute-api --confirm-authorized-provider-budget --provider-adapter relay_openai_compatible --model gpt-5.6-luna --endpoint https://api.chatanywhere.tech/v1/chat/completions --run-id c1_relay_gpt56_luna_strict_v1_1_pilot_v1 --max-calls 1 --max-total-tokens 13000 --max-cost 0.32 --cost-currency CA --input-price-per-million 7 --output-price-per-million 42 --api-key-env-name CHATANYWHERE_API_KEY --timeout-seconds 300`
- manifest：data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_strict_v1_1_pilot_v1/manifest.json
- 结果摘要：succeeded_frozen；1 candidate；canonical schema/exact-span/cue validation passed；1167 input + 829 output = 1996 tokens；0.042987 CA；0 retry；C1=true；evaluation=0；P/R=null；C2=false
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1437 passed, 22 skipped in 236.73s (0:03:56)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`c4df936c62fa4a2b3b23e9629ba1d73a739703df`；相关未提交路径：496 个
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：用户明确授权 ChatAnywhere gpt-5.6-luna 仅 1 条 synthetic、最多 13000 tokens、最多 0.32 CA，验证后停止且不得自动进入 C2。调用使用 strict transport adapter v1.1；canonical serializer/schema 未改；Layer D/E/Gold 未参与生成；provider_reported_model=gpt-5.6-luna-2026-07-09 为 unverified relay report。完整离线验证 1437 passed、22 skipped、integrity errors=0；RWI-0025 resolved。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T06:59:23.793420+00:00 - Freeze EStG-150 C2 six-request offline preparation and preregistration

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1438 passed, 22 skipped in 233.78s (0:03:53)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`c4df936c62fa4a2b3b23e9629ba1d73a739703df`；相关未提交路径：510 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Created no-overwrite C2 dry-run receipt for indices 0-2 Pass A/B: 6/6 strict transport preflights passed, request_downgrade_applied=false, guardrails 6 calls/78000 tokens/1.92 CA. Three Pass-B hashes are historical validated Pass-A fixture scope only; future live hashes remain deferred. Real API not called, billed tokens 0, C2 not started, evaluation 0, P/R null. Full audit: Integrity=True, Errors=0, Passes=47; 1438 passed, 22 skipped.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T07:46:53.382305+00:00 - EStG-150 C1 ChatAnywhere gpt-5.4-nano single-call validation

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=c1_relay_gpt54_nano_strict_v1_1_pilot_v1；阶段=c1；方法=estg150_canonical_external_candidate_protocol；状态=失败（`failed`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_candidate_protocol.py --stage c1 --execute-api --confirm-authorized-provider-budget --provider-adapter relay_openai_compatible --model gpt-5.4-nano --endpoint https://api.chatanywhere.tech/v1/chat/completions --run-id c1_relay_gpt54_nano_strict_v1_1_pilot_v1 --max-calls 1 --max-total-tokens 13000 --max-cost 0.07 --cost-currency CA --input-price-per-million 1.4 --output-price-per-million 8.75 --api-key-env-name CHATANYWHERE_API_KEY --timeout-seconds 300`
- manifest：data/development/estg/llm_candidate_runs/c1_relay_gpt54_nano_strict_v1_1_pilot_v1/failure.json
- 结果摘要：failed_closed; 1 logical call; 0 retry; provider usage 1167 input + 1789 output = 2956 tokens; recorded cost from provider usage 0.01728755 CA; provider-reported model gpt-5.4-nano-2026-03-17 unverified; candidate rejected because clause_span.end=58 exceeds proposed_text length 57; 0 valid candidates; evaluation=0; P/R=null; C1=false; C2=false
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1439 passed, 22 skipped in 256.11s (0:04:16)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`7b2b780a3d2cdab14e4c4fa9993bff84e599bb51`；相关未提交路径：427 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：User explicitly authorized one ChatAnywhere gpt-5.4-nano synthetic call with ceilings 1 call/13000 tokens/0.07 CA and prices 1.4/8.75 CA per million. Strict transport preflight passed and request SHA was 85ef4b632ddeba1e15e4309c3859302b1ae736965dce92f7b7671f7387b67cff; no downgrade. Original failure/raw response preserved. RWI-0027 corrects the original failure receipt's zero-usage accounting via a hash-bound no-overwrite correction and changes future accounting order; no API retry. Temporary credential helper and environment key were cleared.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T08:18:40.485156+00:00 - 记录获授权的 ChatAnywhere gpt-5.6-luna C2 首条 Pass A fail-closed 运行及 usage 账务边界修复

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=c2_relay_gpt56_luna_strict_v1_1_pilot3_live_v1；阶段=C2；方法=estg150_external_candidate_protocol_relay_gpt56_luna；状态=失败（`failed`）
- 实际运行命令：`python scripts/run_estg150_candidate_protocol.py --stage c2 --execute-api --confirm-authorized-provider-budget --provider-adapter relay_openai_compatible --model gpt-5.6-luna --endpoint https://api.chatanywhere.tech/v1/chat/completions --run-id c2_relay_gpt56_luna_strict_v1_1_pilot3_live_v1 --max-calls 6 --max-total-tokens 78000 --max-cost 1.92 --cost-currency CA --input-price-per-million 7 --output-price-per-million 42 --api-key-env-name ESTG_C2_CHATANYWHERE_API_KEY`
- manifest：data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_live_v1/preregistration.json, data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_live_v1/failure.json, data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_live_v1/accounting_correction.json
- 结果摘要：1 logical content call, 0 retry; provider-reported gpt-5.6-luna-2026-07-09 returned finish_reason=length with empty content; 1339 input + 6500 output/reasoning = 7839 tokens; corrected cost 0.282373 CA; 0 valid candidates; remaining five calls not sent; C2 started but incomplete; evaluation_count=0, P/R=null; no C3/C4
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1441 passed, 22 skipped in 263.22s (0:04:23)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`fd505ff55a9bf3c1c06b0eaea5017964793d4fb2`；相关未提交路径：426 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Independent C2 authorization ceilings: 6 content calls, 78000 tokens, 1.92 CA at 7/42 CA per million input/output tokens. Strict transport request SHA 9add2487dd36233b3e258ae451a27cebaa5de6b10de70a18b08ef7d527960aac matched offline preparation; no downgrade. Original failure/preregistration/raw response preserved; hash-bound accounting correction added because the immutable failure receipt recorded zero usage before the finish-reason accounting-order fix. No API retry for correction. Temporary key environment variable cleared. Layer D/E/Gold not read during generation; no evaluation.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T09:03:41.748050+00:00 - Add EStG-150 portable transport adapter v1.2 with GPT-4o strict-schema and JSON-mode compatibility profiles

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1449 passed, 22 skipped in 217.94s (0:03:37)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`5643e5f293ccf8c2cd20734e0af58e8c6213910b`；相关未提交路径：422 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：B0, D1/H1, candidate prompt assets, canonical schema, serializer, frozen v1.1 receipts, Event 121, Layer D/E/Gold, and P/R remain unchanged. Full audit: 1449 passed, 22 skipped, Integrity=True, Errors=0, Passes=47.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T10:38:25.061890+00:00 - Freeze authorized ChatAnywhere gpt-4o single-call C1 fail-closed runtime evidence

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=c1_relay_gpt4o_portable_v1_2_runtime_v1；阶段=C1；方法=relay_openai_compatible ChatAnywhere gpt-4o adapter v1.2；状态=失败（`failed`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_candidate_protocol.py --stage c1 --execute-api --provider-adapter relay_openai_compatible --model gpt-4o --endpoint https://api.chatanywhere.tech/v1/chat/completions --confirm-authorized-provider-budget --run-id c1_relay_gpt4o_portable_v1_2_runtime_v1 --max-calls 1 --max-total-tokens 13000 --max-cost 0.60 --cost-currency CA --input-price-per-million 17.5 --output-price-per-million 70 --api-key-env-name ESTG150_CHATANYWHERE_KEY --timeout-seconds 180`
- manifest：data/development/estg/llm_candidate_runs/c1_relay_gpt4o_portable_v1_2_runtime_v1/failure.json
- 结果摘要：One real call, no retry; provider-reported gpt-4o stop; 1201 input plus 287 output equals 1488 tokens; 0.0411075 CA; six semantic collections returned but exact-span validation failed; valid candidates 0; C2 false; evaluation 0; P/R null.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1449 passed, 22 skipped in 259.23s (0:04:19)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`4be636e1d519edfa461939784b13939b47af6f25`；相关未提交路径：423 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Transport preflight passed; request SHA 08c7c1fc345688b3070a644bec452c23aa2e5c7d2831d966c94ba046e21c201a; request_downgrade_applied=false; Layer D/E/Gold not read; credential echo false; no second API call.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T11:01:32.111311+00:00 - Add EStG-150 portable adapter v1.3 deterministic exact-text coordinate canonicalization and GPT-4o real-response offline regression

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1451 passed, 22 skipped in 257.43s (0:04:17)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`1b9c8089a7b8f274b8d61fed4039525ec6690e87`；相关未提交路径：424 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：B0, D1/H1, all EStG-150 prompt bytes, canonical schema, serializer, semantic fixture, and transport schema remain unchanged. v1.3 changes only start/end when unchanged span text has exactly one match inside its parent; zero/multiple matches fail closed; semantic content repair and content retry remain forbidden. Seven profiles pass offline preflight. Immutable GPT-4o v1.2 raw response replays with five coordinate changes and passes schema/exact-span/cue validation; no API, C2, evaluation, or P/R.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T11:08:25.702806+00:00 - Finalize tested EStG-150 portable adapter v1.3 GPT-4o coordinate-portability correction

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1451 passed, 22 skipped in 260.58s (0:04:20)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`1b9c8089a7b8f274b8d61fed4039525ec6690e87`；相关未提交路径：425 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Final commit-state verification after restoring the pre-existing mixed-worktree audit.py content: 1451 passed, 22 skipped; Integrity true. Adapter v1.3 and tests preserve B0, D1/H1, prompt/schema/serializer bytes and semantic content; only uniquely exact parent-scoped start/end coordinates may be canonicalized with receipt; ambiguous/unmatched text fails closed. Seven profiles pass offline preflight; real GPT-4o v1.2 response passes offline v1.3 replay after five coordinate-only changes. No API, C2, evaluation, or P/R.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T11:43:41.059353+00:00 - Freeze authorized ChatAnywhere GPT-4o portable v1.3 C1 success

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=c1_relay_gpt4o_portable_v1_3_runtime_v1；阶段=C1；方法=relay_openai_compatible ChatAnywhere gpt-4o adapter v1.3；状态=成功（`succeeded`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_candidate_protocol.py --stage c1 --execute-api --confirm-authorized-provider-budget --provider-adapter relay_openai_compatible --model gpt-4o --endpoint https://api.chatanywhere.tech/v1/chat/completions --run-id c1_relay_gpt4o_portable_v1_3_runtime_v1 --max-calls 1 --max-total-tokens 13000 --max-cost 0.60 --cost-currency CA --input-price-per-million 17.5 --output-price-per-million 70 --api-key-env-name ESTG150_CHATANYWHERE_KEY --timeout-seconds 180`
- manifest：data/development/estg/llm_candidate_runs/c1_relay_gpt4o_portable_v1_3_runtime_v1/manifest.json
- 结果摘要：One real call, no retry; provider-reported gpt-4o stop; 1201 input plus 274 output equals 1475 tokens; 0.0401975 CA; candidate_count 1; five coordinate-only unique exact-text reanchors; canonical schema, exact-span, and normative-cue validation passed; C1 true for this run; C2 false; evaluation 0; P/R null.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1451 passed, 22 skipped in 229.00s (0:03:48)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`0a55198c77e744153ab521c9780072875d8ad97a`；相关未提交路径：423 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Authorized ceilings: 1 content call, 13000 total tokens, 0.60 CA at 17.5/70 CA per million input/output tokens. Request SHA 08c7c1fc345688b3070a644bec452c23aa2e5c7d2831d966c94ba046e21c201a; request_downgrade_applied=false; response_coordinate_mode=deterministic_exact_text_unique_reanchor; semantic_content_unchanged=true; provider identity remains unverified relay report. B0, D1/H1, canonical prompt/schema/serializer/transport hashes unchanged. Layer D/E/Gold not read during generation; no evaluation or C2. Credential stored outside the repository in Windows Credential Manager and not printed.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T11:58:59.670393+00:00 - Freeze GPT-4o portable v1.3 C2 six-request offline preregistration

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1451 passed, 22 skipped in 227.65s (0:03:47)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`507ccfc60d786a40305b453a4a30f7341f55470b`；相关未提交路径：430 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：C2 offline-only run_id=c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1; samples 0/1/2, each Pass A then Pass B, exactly six prepared requests; all six strict transport preflights passed; request_downgrade_applied=false; response coordinate mode deterministic_exact_text_unique_reanchor. Transport SHAs: 520a254aed2c6df29e466084a5ac0ea5c869fdc8e406a460246c5bbd53959fb3, 4df5de55f13800a35100a61ed2dfd59f0127e31e29cda92bc07b61530ef55822, 4dacfd0c34683974edcc80bef3bd7ceb0c4bb845e58c9e0a9e883ff4ea3c3afc, 2a95a940ec4b6e8d4aa1fb1935214cc9d22f67f2019a150737b19ec3bd85d72c, d805c1c3c94f39f4b0f41a9b17c701edb58cc8c5ca0f4da922d3986c710d6c6a, e29683c32ff7bb7da3f1fc786afcd875a2c0e1820ef41615ca725065e42e277b. Pass A hashes are exact for locked inputs/model/profile; Pass B hashes are offline fixture-only and must bind actual Pass A output in any separately authorized live run. Offline budget configuration only: 6 calls, 78000 tokens, 3.60 CA, prices 17.5/70 CA per million; not API authorization. Canonical schema/serializer/adapter/transport hashes unchanged; Layer D/E/Gold not read; credential not read; real API false; billed tokens 0; C2 not started; evaluation 0; P/R null.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T14:11:56.568491+00:00 - Freeze authorized ChatAnywhere GPT-4o v1.3 C2 fail-closed span-text evidence

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=c2_relay_gpt4o_portable_v1_3_pilot3_live_v1；阶段=C2；方法=relay_openai_compatible ChatAnywhere gpt-4o adapter v1.3；状态=失败（`failed`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_candidate_protocol.py --stage c2 --execute-api --confirm-authorized-provider-budget --provider-adapter relay_openai_compatible --model gpt-4o --endpoint https://api.chatanywhere.tech/v1/chat/completions --run-id c2_relay_gpt4o_portable_v1_3_pilot3_live_v1 --max-calls 6 --max-total-tokens 78000 --max-cost 3.60 --cost-currency CA --input-price-per-million 17.5 --output-price-per-million 70 --api-key-env-name ESTG150_CHATANYWHERE_KEY --timeout-seconds 180`
- manifest：data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_live_v1/failure.json
- 结果摘要：Fail-closed after the first Pass A content call; provider-reported gpt-4o stop; 1373 input plus 1249 output equals 2622 tokens; 0.1114575 CA; retry 0; clauses[2].conditions[0] model text was not an exact substring of its clause, so valid candidates 0 and remaining five calls were not made; evaluation 0; P/R null.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1451 passed, 22 skipped in 227.34s (0:03:47)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`53e5b4fc76b2c9aa966f62182a0574aeaac30a5b`；相关未提交路径：421 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Authorized ceilings: 6 content calls, 78000 total tokens, 3.60 CA at 17.5/70 CA per million input/output tokens. First request SHA 520a254aed2c6df29e466084a5ac0ea5c869fdc8e406a460246c5bbd53959fb3 matched the frozen offline Pass A request; request_downgrade_applied=false. The condition text omitted the intervening phrase 'of a business' from the immutable proposed text, so this was semantic span-text inconsistency rather than coordinate-only drift; v1.3 correctly refused semantic repair and content retry. C2 started then failed closed; prior C1 success evidence unchanged. Layer D/E/Gold not read; no evaluation; credential not printed.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T14:28:54.233556+00:00 - Add EStG-150 portable adapter v1.4 exact-span output guard and freeze GPT-4o C2 offline preparation

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1452 passed, 22 skipped in 241.87s (0:04:01)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`567d4919d326c67569869e83e67f79ea52abe27b`；相关未提交路径：436 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Adapter v1.4 appends one transport-only exact-span self-check after the unchanged canonical semantic request. It requires every span text to be a verbatim contiguous proposed_text_en substring, prohibits deletion of internal words, requires child containment and visible normative-cue evidence, and tells optional fields to stay empty/uncertain rather than fabricate spans. Response semantic repair and content retry remain forbidden; v1.3 C2 raw response still fails offline because its condition omitted 'of a business'. B0, D1/H1, all canonical candidate prompt assets, canonical protocol/schema/serializer/semantic fixture/transport schema, Layer D/E/Gold, and prior frozen runs remain unchanged. Adapter config SHA e7ff366f2df0baa6de03ce3dbb1d3fe77ea74ed2d2a41b05c8d8d2ee93cb356b; guard SHA d7432611183a6b8cd36bcd2da8f481f7090368d660e7a5fc77cbf0001f693f98. New C2 offline run_id=c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1 has six passing preflights, request_downgrade_applied=false, requests c1b5bc47c0cdc8e61cd2eccdfc96be9296b34f8ba53185f99c46420174fd9a9e/7358dae5e890d1922ac673d71d29de9cf57712a693a9388ae08bdc49bc1c401a/4334d37ba91ff24953c450ac00876b66abb59f97e426be7fc1c1bf4dcf5c6e7e/b34eae7c808a8c24e9b747fb70d53c2be41868b7250c721bea2fd99143a106dd/022a591c1a28e14c05ed3368fe1df40fb58ff5ab390a40b7b74f7059ed8fc54e/dfe14fbb1b8a6625423846b2b36f010fd1e43844516c16975e27373890756b54. Pass B hashes are fixture-only/live-dependent. Credential not read; real API false; billed tokens/cost zero; C2 not started; evaluation 0; P/R null; a v1.4 live run requires new authorization.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T14:39:16.881746+00:00 - Freeze the authorized ChatAnywhere GPT-4o portable v1.4 C2 failed-closed run after Pass B returned an unchanged edited translation

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=c2_relay_gpt4o_portable_v1_4_pilot3_live_v1；阶段=C2；方法=estg150_original_candidate_generation；状态=失败（`failed`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_candidate_protocol.py --stage c2 --execute-api --confirm-authorized-provider-budget --provider-adapter relay_openai_compatible --model gpt-4o --endpoint https://api.chatanywhere.tech/v1/chat/completions --run-id c2_relay_gpt4o_portable_v1_4_pilot3_live_v1 --max-calls 6 --max-total-tokens 78000 --max-cost 3.60 --cost-currency CA --input-price-per-million 17.5 --output-price-per-million 70 --api-key-env-name ESTG150_CHATANYWHERE_KEY --timeout-seconds 180`
- manifest：formal_experiment/data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_live_v1/failure.json
- 结果摘要：failed_closed after 2 of at most 6 calls; sample 0 Pass A accepted, Pass B declared edited but proposed translation was byte-identical; 0 frozen candidates; 4378 input + 2405 output = 6783 tokens; 0.244965 CA; 0 retries; evaluation_count=0; P/R=null
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1452 passed, 22 skipped in 155.59s (0:02:35)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`4bf1f8d05e858785f8660d69a7820c1d23eadb99`；相关未提交路径：425 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：User explicitly authorized only this v1.4 C2 run with maxima 6 calls, 78000 total tokens, and 3.60 CA at 17.5/70 CA per million input/output tokens. Actual request SHAs were c1b5bc47c0cdc8e61cd2eccdfc96be9296b34f8ba53185f99c46420174fd9a9e and d548fdcff80f93ea1f4fac21f077a1d99c6b71a3d9e8d4ed5d499d14cda55388. Provider reported gpt-4o; relay backend identity remains unverified. request_downgrade_applied=false; semantic_contract_downgrade_applied=false; exact-span self-check guard applied; local canonical validation failed only on edited translation unchanged. Canonical schema fbbb628ad0f25639958c6d02db9bac90ed06865e634bd4e8eeb7b50ac7108ca9, serializer d20ae560a627c4d3faa88439908c517e7726aabb1121128af7b9013f5512edef, adapter config e7ff366f2df0baa6de03ce3dbb1d3fe77ea74ed2d2a41b05c8d8d2ee93cb356b, and transport schema ef8c684b2456196eac14cc7748bb687aef5ef32fd8a405c3003bd831ad380af7 did not drift. Layer D, Layer E, and Gold were not read during generation; credential echo false. No response repair, content retry, evaluation, C3, or C4 occurred. B0 and D1/H1 prompts were unchanged. Full audit after run: Integrity true, Errors 0, 1452 passed, 22 skipped; seven pre-existing blockers are unrelated.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T15:06:36.258236+00:00 - Mitigate GPT-4o C2 unchanged-edited output and bind Pass B validation to the same-run Pass A text with portable adapter v1.5

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1454 passed, 22 skipped in 277.08s (0:04:37)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`4727975d3ad7dab7e94b40f32a60366483546902`；相关未提交路径：437 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：RWI-0028 records the v1.4 GPT-4o Pass B contradiction: decision=edited with character-identical proposed text, plus the discovered runner defect that compared Pass B against the original sample instead of the same-run validated Pass A text. Adapter v1.5 adds only a transport-generation decision/text self-check while retaining the exact-span guard; response repair and content retry remain forbidden. Runner pass_a/full_extract uses original frozen English and pass_b uses same-run Pass A proposed_text_en. Historical v1.4 loader and immutable failure replay remain. B0, D1/H1, canonical prompt assets, canonical schema fbbb628ad0f25639958c6d02db9bac90ed06865e634bd4e8eeb7b50ac7108ca9, serializer d20ae560a627c4d3faa88439908c517e7726aabb1121128af7b9013f5512edef, semantic fixture eb074081cc52d22025e263e3f94b2165f95493f511ddc454b9ea5f5923c085e1, and transport schema ef8c684b2456196eac14cc7748bb687aef5ef32fd8a405c3003bd831ad380af7 are unchanged. v1.5 adapter config SHA=3d4508612b4d15533dbaf4ceea291eab232598bcd347d7a5ed5bd254f6969e2b; guard SHA=c68d59ca1e25d0e4bde6faef3544e07a2b74b60e186a88c75de5fc4d32a78b5a. Offline run c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1 froze six passing strict preflights with SHAs a61b4041917dfb92b71a1475f0090cb4147130ff938dbe74f14bb588f2575c97/3bea8469870b55e356d922ce8eb5595d278b566ad6a559d2d5aec23f977acfe5/4e66cc9b1a17e3a0519ad139d9c9d6ba522390a5f5ff2e564cf46a9300a68933/eab5d93397633640ad5097da319eed872ed142245167d5cdf9349bb189e81b15/9323f5f012a16cbd8be80fbaaf3198f7a6df784d54854944fdb1ab5270574643/a8042a5bec2a7aa7acbf0f9622e4039de90336726bd0bc540c1766dd39984bda; Pass B hashes are fixture-only/live-dependent. Budget config is 6 calls, 78000 tokens, 3.60 CA at 17.5/70 CA per million, with worst reservation 3.4125 CA. request_downgrade_applied=false; Layer D/E/Gold reads false; API/key/network false; billed tokens/cost zero; C2=false; evaluation=0 and P/R=null. Focused tests 57 passed; full audit Integrity true, Errors 0, 1454 passed, 22 skipped. Runtime status remains mitigated pending a new explicit v1.5 API authorization and no-overwrite live run ID.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T15:22:00.516333+00:00 - Freeze authorized ChatAnywhere GPT-4o v1.5 C2 failed-closed ambiguous modality evidence runtime

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=c2_relay_gpt4o_portable_v1_5_pilot3_live_v1；阶段=C2；方法=estg150_original_candidate_generation；状态=失败（`failed`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_candidate_protocol.py --stage c2 --execute-api --confirm-authorized-provider-budget --provider-adapter relay_openai_compatible --model gpt-4o --endpoint https://api.chatanywhere.tech/v1/chat/completions --run-id c2_relay_gpt4o_portable_v1_5_pilot3_live_v1 --max-calls 6 --max-total-tokens 78000 --max-cost 3.60 --cost-currency CA --input-price-per-million 17.5 --output-price-per-million 70 --api-key-env-name ESTG150_CHATANYWHERE_KEY --timeout-seconds 180`
- manifest：formal_experiment/data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_live_v1/failure.json
- 结果摘要：Failed closed on call 1/6, Pass A sample index 0: CandidateValidationError because modality evidence text 'shall' occurs twice inside its parent clause, so exact coordinate canonicalization found 2 matches. request_count=1; retry_count=0; input_tokens=1661; output_tokens=1128; total_tokens=2789; recorded_cost=0.1080275 CA; valid_candidate_count=0; remaining_calls_not_made=5; evaluation_count=0; precision=null; recall=null.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1454 passed, 22 skipped in 262.20s (0:04:22)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`2601407185be71f7280ffc10f2dfd71ceedb0cdf`；相关未提交路径：423 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Request SHA a61b4041917dfb92b71a1475f0090cb4147130ff938dbe74f14bb588f2575c97 matched the frozen v1.5 offline preregistration. Provider returned model gpt-4o with finish_reason stop. Adapter v1.5 correctly avoided the former decision/text contradiction, but the response supplied an ambiguous repeated modality cue with incorrect coordinates; no response repair, content retry, or guessed occurrence selection was applied. request_downgrade_applied=false. Canonical schema, serializer, semantic fixture, adapter config, guard, and transport schema hashes were recorded in the failure receipt. Layer D, Layer E, and Gold were not read; no evaluation was run. Relay backend identity remains unverified.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T15:41:55.749632+00:00 - Add EStG-150 portable adapter v1.6 duplicate modality-cue output guard and freeze GPT-4o C2 offline preparation

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1456 passed, 22 skipped in 255.47s (0:04:15)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`4317e0a04ff873cfb8ea43199a313bf5d846ecc1`；相关未提交路径：436 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Minimal transport-only v1.6 change: when a normative cue repeats inside one clause_span, require modality.evidence.text to be the shortest verbatim contiguous cue-containing phrase unique in that clause; guessing, response repair, and content retry remain forbidden. Canonical prompt assets, schema, serializer, transport schema, B0, and D1/H1 are unchanged. Historical v1.5 loader and real raw-response replay remain fail closed with found 2. Focused tests: 59 passed. Full audit: 1456 passed, 22 skipped, Integrity true, Errors 0. Offline run c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1 froze six strict preflight slots for sample indices 0-2 Pass A/B; all passed, request_downgrade_applied=false, max calls/tokens/cost=6/78000/3.60 CA, 17.5/70 CA per million, hard guards passed. Adapter config SHA 30d4fca5959cdfbcab09df780642742b1847eaf6ff8fb88bed99e01fa85fcb35; guard SHA 3b74d2f87fc57d47375b20b18c940fa0c851f66debfbe1c239b96189bfa267b0. Real API not called, billed tokens=0, billed cost=0, C2 not started, evaluation_count=0, P/R null, Layer D/E/Gold not read. Any real v1.6 run requires a new explicit authorization and new no-overwrite run ID.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T16:19:01.009202+00:00 - Freeze authorized ChatAnywhere GPT-4o v1.6 C2 repeated-cue failed-closed runtime

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=c2_relay_gpt4o_portable_v1_6_pilot3_live_v1；阶段=C2；方法=estg150_original_candidate_generation；状态=失败（`failed`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_candidate_protocol.py --stage c2 --execute-api --confirm-authorized-provider-budget --provider-adapter relay_openai_compatible --model gpt-4o --endpoint https://api.chatanywhere.tech/v1/chat/completions --run-id c2_relay_gpt4o_portable_v1_6_pilot3_live_v1 --max-calls 6 --max-total-tokens 78000 --max-cost 3.60 --cost-currency CA --input-price-per-million 17.5 --output-price-per-million 70 --api-key-env-name ESTG150_CHATANYWHERE_KEY --timeout-seconds 180`
- manifest：formal_experiment/data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_live_v1/failure.json
- 结果摘要：Failed closed on call 3/6, sample index 1 Pass A: modality evidence text 'may' occurs twice inside its parent clause and supplied coordinates were reversed start=116,end=115, so unique-exact coordinate canonicalization found 2 matches. Sample index 0 Pass A/B passed; request_count=3; retry_count=0; input_tokens=6528; output_tokens=3813; total_tokens=10341; recorded_cost=0.381150 CA; valid_candidate_count=1 but no candidates.json or success manifest was frozen; remaining_calls_not_made=3; evaluation_count=0; precision=null; recall=null.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1456 passed, 22 skipped in 266.54s (0:04:26)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`fc450b43e2958ab2b07ebdde1eb366f65055e983`；相关未提交路径：430 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Failing request SHA 0a5f108d561040ef7e9873817e40be0c4aba1b3a35fe22616a1d60d7c92cf835 matched the frozen v1.6 sample-1 Pass-A offline request. The live sample-0 Pass-B SHA deef43fbd7f86dd49855cbb3231aed8ab4c96ad5190a67e61374e58ee70435f9 was recorded after its validated live Pass A. Provider returned model gpt-4o with finish_reason stop. The v1.6 duplicate-cue output instruction was not reliably followed; no response repair, content retry, or guessed occurrence selection was applied. request_downgrade_applied=false. Layer D, Layer E, and Gold were not read; no evaluation was run. Relay backend identity remains unverified. The v1.6 authorization is exhausted and cannot be transferred to a future adapter version.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-26T16:38:08.537250+00:00 - Add EStG-150 portable adapter v1.7 bounded nearest-start coordinate policy and freeze GPT-4o C2 offline preparation

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1459 passed, 22 skipped in 282.30s (0:04:42)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`744cea5c2ae732ea5f2110f0a2d60ba2cd4c15c8`；相关未提交路径：437 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Minimal v1.7 response-boundary change: repeated exact span text may be coordinate-corrected only when the model supplied an integer start, the nearest parent-scoped match is unique, and start displacement is <=8 characters; ties, larger displacement, zero matches, and missing integer starts fail closed. Only start/end may change and receipts record candidate count, selection method, and displacement. The transport-only guard adds exact clause construction order and a duplicated-may example; canonical prompt assets, schema, serializer, transport schema, B0, and D1/H1 are unchanged. Historical v1.6 remains loadable. Replaying v1.5 still fails when nearest displacement is 30>8. Replaying v1.6 gets past the close duplicated may but still rejects the non-verbatim clause-2 condition with zero matches, proving no semantic deletion/fuzzy repair. Focused tests: 62 passed. Full audit: 1459 passed, 22 skipped, Integrity true, Errors 0. Offline run c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1 froze six strict preflight slots; all passed, request_downgrade_applied=false, budget 6/78000/3.60 CA at 17.5/70 CA per million, worst guard cost 3.4125. Adapter config SHA 52313835e630d7afee466b95b1e70350bc0181ee0e7eddabbefbfaab433e9ec2; guard SHA 9afd5ccbf457ec737f9815d21ab3224d06683b370302adcca69febc8a9f5d7c7. Real API not called, billed tokens=0, billed cost=0, C2 not started, evaluation=0, P/R null, Layer D/E/Gold not read. Any real v1.7 run requires new explicit authorization and a new no-overwrite run ID.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-27T07:22:49.395050+00:00 - Freeze GPT-4o v1.7 C2 failed-closed run and prepare v1.8 path-scoped mitigation

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=c2_relay_gpt4o_portable_v1_7_pilot3_live_v1；阶段=EStG-150 C2；方法=relay_openai_compatible GPT-4o adapter v1.7; offline repair v1.8；状态=失败（`failed`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_candidate_protocol.py --stage c2 --execute-api --confirm-authorized-provider-budget --provider-adapter relay_openai_compatible --model gpt-4o --endpoint https://api.chatanywhere.tech/v1/chat/completions --run-id c2_relay_gpt4o_portable_v1_7_pilot3_live_v1 --max-calls 6 --max-total-tokens 78000 --max-cost 3.60 --cost-currency CA --input-price-per-million 17.5 --output-price-per-million 70`
- manifest：data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_live_v1/failure.json
- 结果摘要：v1.7 failed closed after 3/6 calls; 6897 input + 3679 output tokens; 0.3782275 CA; v1.8 offline six-slot strict preflight frozen; no evaluation
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1462 passed, 22 skipped in 277.67s (0:04:37)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`0687cd8ed5007e796a32b4fe570312297bdce3c7`；相关未提交路径：449 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：User explicitly authorized saved ChatAnywhere GPT-4o through unverified relay, C2 then at least 50 candidates, read-only development evaluation, and a 35 CA cumulative cap including repairs. v1.7 sample0 Pass A/B validated; sample1 Pass A repeated may had nearest exact start displacement 23>8 and failed closed. Candidate set not frozen; evaluation=0; P/R=null; Layer D/E/Gold not read during generation. Minimal v1.8 makes only repeated modality.evidence cues use unbounded unique-nearest exact reanchor; other repeated semantic spans remain bounded at 8, ties/zero matches fail. Archived v1.7 replay still rejects a later non-verbatim action, proving no semantic repair. Canonical prompt/schema/serializer/transport schema, B0, D1/H1 unchanged. Focused tests 65 passed; full audit 1462 passed, 22 skipped, Integrity true, Errors 0. v1.8 offline run c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1 passed 6/6 preflights, request_downgrade=false, API=0, billed tokens/cost=0, C2=false, evaluation=0, P/R=null. Adapter config SHA 715c803fef5f8c91c6c4b8fb83002182aca01e461745c2c38a5d48254ac72462; guard SHA ff5813a7410a891b6d87966950d8f7ef0223da52e76f28644bbbc0d9304ae25e.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-27T07:52:42.487077+00:00 - Freeze GPT-4o v1.8 C2 fail-closed evidence and preregister v1.9 schema-guided C2

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=c2_relay_gpt4o_portable_v1_8_pilot3_live_v1；阶段=EStG-150 C2；方法=ChatAnywhere GPT-4o portable adapter v1.8/v1.9；状态=失败（`failed`）
- 实际运行命令：`python formal_experiment/scripts/run_estg150_candidate_protocol.py --stage c2 --execute-api --provider-adapter relay_openai_compatible --model gpt-4o --max-calls 6 --max-total-tokens 78000 --max-cost 3.60`
- manifest：data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_live_v1/failure.json
- 结果摘要：v1.8 stopped fail-closed at 3/6 calls on a noncontiguous condition span; 7155 input + 3494 output tokens, 0.3697925 CA, no frozen candidate set or evaluation. v1.9 adds description-only strict-schema span guidance; 6/6 offline preflights passed, API/tokens/cost 0, request_downgrade=false.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1463 passed, 22 skipped in 261.75s (0:04:21)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`ceac334ef6151d84916c3cecec488ce58540d709`；相关未提交路径：449 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Canonical schema, serializer, B0, and D1/H1 prompts unchanged. Relay identity remains unverified. Full audit: Integrity=True, Errors=0, 1463 passed, 22 skipped; seven existing unrelated blockers.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-28T08:08:06.675923+00:00 - EStG-150 paper-level best-effort LLM extraction pilot (D1 + H1-naive + H1-selective) on 150 samples; bypasses canonical strict protocol

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=paper_pilot_d1_h1naive_h1selective_150_20260728；阶段=stage2；方法=best_effort_llm_paper_pilot；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/run_d1_paper_pilot.py --samples 5; python scripts/run_h1_paper_pilot.py --samples 150 --start 0; python scripts/run_h1_selective_pilot.py --samples 50 --start 0/50/100`
- manifest：outputs/paper_h1_pilot/h1_combined_150_1785152419656231300.json, outputs/paper_h1_selective_pilot/h1s_combined_150_summary.json, outputs/paper_d1_pilot/d1_pilot_1785145982.json
- 结果摘要：D1 F1=0.840 (TP=184, FP=29, FN=41); H1-naive F1=0.668 (TP=165, FP=104, FN=60); H1-selective F1=0.796 (TP=185, FP=52, FN=43); B0 baseline F1=0.669. Bypasses canonical protocol: simple token-IoU clause alignment (threshold 0.3), no exact span canonicalization, no SHA-bound receipts. 12 parse errors (2 D1 + 10 H1s) fell back to B0. LLM=DeepSeek V4 Pro via official API (BPC_HYBRID_LLM_* in .env); 536K total tokens; ~1.3 USD. Disclosure in per-script output JSONs.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：否；正式实验就绪：否
- 测试：1 failed, 1462 passed, 22 skipped in 205.51s (0:03:25)
- 测试证据：本次新运行（`fresh_run`）
- Git：`ceac334ef6151d84916c3cecec488ce58540d709`；相关未提交路径：454 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：User explicitly authorized deviation from canonical protocol to obtain P/R quickly for paper results table. Scope limited to outputs/paper_*_pilot/ and scripts/run_*_pilot.py. Canonical schema/serializer/B0/D1/H1 prompts and all existing manifests unchanged. Known limitations: (1) does not use canonical validator, span alignment is token-IoU>=0.3 not exact; (2) H1-selective triggers LLM anchoring effect, FP inflates from 29 to 52; (3) best-effort only, not valid as formal Gold publication evidence; (4) DeepSeek V4 Pro chosen because .env only had DeepSeek + Qwen, no ChatAnywhere gpt-4o. Analysis: current B0 v10a weaker than Sun's original (H1<D1 attributed to this); Sun-strength H1 simulation as future work.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`

## 2026-07-28T10:42:01.652905+00:00 - EStG-150 Sun-strength H1 controlled perturbation simulation; identifies B0 F1 threshold where H1>D1

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=paper_sun_strength_simulation_150_20260728；阶段=stage2；方法=controlled_perturbation_simulation；状态=成功（`succeeded`）
- 实际运行命令：`python scripts/run_sun_strength_simulation.py`
- manifest：outputs/paper_sun_strength_simulation/sun_strength_simulation_results.json, outputs/paper_d1_pilot/d1_full150/d1_predicted_150.json
- 结果摘要：CONTROLLED SIMULATION, NOT REAL BENCHMARK. Uses Gold as 'ideal B0', perturbs with prob p in {0.05, 0.10, 0.20, 0.30, 0.50, 0.67}, 5 seeds each. D1 candidates are cached from real DeepSeek V4 Pro run (n=150, F1=0.8019). Crossover point: B0_sim F1 ~ 0.80 (H1=0.844 vs D1=0.802, +0.04). Above 0.80: H1 wins (max +0.14 at p=0.05). Below 0.80: D1 wins. Our real B0 F1=0.674 falls in D1-dominant regime, explaining why real H1<D1. Perturbation mix 50% wrong_modality, 30% wrong_text, 20% delete (matches real B0 error profile). Zero new LLM calls.
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：否；正式实验就绪：否
- 测试：1 failed, 1462 passed, 22 skipped in 184.12s (0:03:04)
- 测试证据：本次新运行（`fresh_run`）
- Git：`ceac334ef6151d84916c3cecec488ce58540d709`；相关未提交路径：455 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：纯计算扰动实验，零 LLM 调用。D1 候选来自先前 paper_pilot 实跑（DeepSeek V4 Pro, 150 样本, F1=0.8019）。结果明确：H1 > D1 要求 B0 F1 > 0.80；我们真实 B0=0.67 处于 D1 主导区。论文 supplementary material。重要 caveat：(1) 扰动模型是模拟不是真实 B0 错误分布；(2) 仅方向性证明，真实 Sun-strength B0 复现仍为 future work。
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`
## 2026-07-28T13:20:43.248224+00:00 - Paper Validation R1 Phase 0 audit (paper_validation_r1_20260728)

- 事件类型：变更（`change`）
- 实验：run_id=paper_validation_r1_20260728；阶段=phase_0_audit；方法=read_only_audit；状态=成功（`succeeded`）
- 实际运行命令：（无命令；只读审计）
- manifest：formal_experiment/outputs/paper_validation_r1_20260728/manifest.json, formal_experiment/outputs/paper_validation_r1_20260728/file_hashes.json, formal_experiment/outputs/paper_validation_r1_20260728/environment.json, formal_experiment/docs/experiments/paper_validation_r1/00_AUDIT.md
- 结果摘要：仅只读审计，未调用任何 LLM/API。已确认项目根目录 = D:\Paper\experiment\bpc-hybrid；HEAD = ceac334；当前分支 = main；工作区存在 313 项未提交变更，全部位于 formal_experiment/ 内部路径或根目录 STAGE2_CONTRACT_v0.1_DRAFT.md，与本任务新建的 4 个目录（outputs/paper_validation_r1_20260728/, docs/experiments/paper_validation_r1/, scripts/paper_validation/, tests/paper_validation/）重叠 0 项。已确认 Gold = 150 records / 231 clauses；modality 分布 = permission 62 / obligation 97 / definition 39 / prohibition 33，obligation 实际 97，论文报告文本"109"是文字错误（已记录、不修改 Gold）。B0 v10a = 150 records / 256 clauses；D1 prior 150 = 150 records；H1 prior 150 = 仅 aggregate summary。difficulty mapping = estg_150_independence_audit_v1.jsonl，82 独立 / 26 上下文 / 42 不独立 = 150，明确标注 analysis_aid_not_human_gold。six-field Gold 覆盖率：modality 100%、actions 99.6%、conditions 70.1%、constraints 80.5%、actors 19.9%、exceptions 4.8%。char-span v3 evaluator 已存在但不能直接消费 paper pilot 输出格式（缺 clause_span 整数坐标），记为 secondary_evaluator=unavailable。最终违规检测 Gold 不存在，Phase 10 必产生 blocker。
- 命令：（无；只读审计）
- 完整性通过：是；正式实验就绪：否（Phase 0 gate 已通过；Phase 1 才能开始冻结配置；付费 API 在 Phase 3 smoke 之前不得调用）
- 测试：本阶段未运行测试（Phase 3 任务）
- 测试证据：（Phase 3 待补）
- Git：ceac334ef6151d84916c3cecec488ce58540d709（未在本任务中提交新 commit；将在 Phase 0 commit checkpoint 一次性提交本审计文件）
- Gold：仅完整性检查读取（`audit_read_only`）；LLM/API：未调用（`not_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：six_field_evaluation_blocked_by_actor_exception_coverage、final_violation_detection_blocked_by_missing_stage3_gold、paper_pilot_model_identity_not_independently_verified、paper_pilot_run_to_run_variance_unquantified
- 备注：本审计是执行性任务的 Phase 0，不改变既有研究设计、Prompt、B0、Gold。已记录的关键偏差：(1) 任务描述中 D1 / H1 Prompt 的"独立文件"实际上以字符串常量内联在脚本里，Phase 1 会把规范化版本写到独立文件但文本保持字节级一致；(2) char-span v3 evaluator 不能直接消费 paper pilot 输出，secondary_evaluator 标记 unavailable；(3) Gold 六字段覆盖不均，Phase 9 会产生 blocker 文件；(4) 最终违规检测 Gold 不存在，Phase 10 会产生 blocker 文件。
- 机器实验事件：formal_experiment/docs/EXPERIMENT_EVENTS.jsonl

## 2026-07-28T19:21:45.345579+00:00 - Paper Validation R1 Phase 1-2-3-4-5-6-7-8 completed

- 事件类型：实验运行（`experiment_run`）
- 实验：run_id=paper_validation_r1_20260728；阶段=phase_1_through_phase_8；状态=部分完成
- 结果摘要：
  * Phase 1: frozen 5x30 batches + 3 normalized Prompt files + prompt_hashes.json (1_FROZEN_CONFIG.md)。
  * Phase 2: 7 个 wrapper script 写完 (run_repeated_llm_experiment, evaluate_predictions, bootstrap_record_level, analyze_anchoring, analyze_thresholds, analyze_subsets, build_validation_report, build_preflight_estimate)。
  * Phase 3: pytest 18 测试 15 通过 + 3 等待 Phase 5 输出 (后已跳过→已运行)；smoke 3 record × 3 method 全成功 (smoke_summary.json)。
  * Phase 4: 9 次完整 EStG-150 运行尝试，最终有效 repeats：D1×2 (r1, r3) + H1-primed×3 + H1-empty×3 = 8 个有效。d1_unprimed/repeat_02 因 batch_01 撞 max_tokens=20000 标记 invalid（3 次重试用尽）。
  * Phase 5: run_level_summary + per-modality/per-record metrics。主指标 F1：D1 mean=0.8486, H1-primed mean=0.8156, H1-empty mean=0.8540。
  * Phase 6: 锚定分析。81 B0-FP 中 H1-primed 25.9% 存活，H1-empty 14.4%，D1 12.7%。primed 高于 empty 11.5 个百分点，方向一致 → "结果与 B0 草稿造成的锚定效应一致"。
  * Phase 7: 阈值敏感性 τ∈(0.2, 0.3, 0.5, 0.7)。排序 H1-empty > D1 > H1-primed 在 4 个阈值下稳定。
  * Phase 8: difficulty subset (82/26/42) + definition 专项；definition 是 hardest class，3 个方法都 over-predict。
- 命令：`python formal_experiment/scripts/paper_validation/build_validation_report.py ...`
- 完整性通过：部分（D1 一个 repeat 无效；n=3 小，bootstrap CI 多跨 0）
- 测试：formal_experiment/tests/paper_validation/ pytest 15 passed / 3 skipped
- 测试证据：formal_experiment/outputs/paper_validation_r1_20260728/test_logs/pytest_full.txt
- Git：dc1146a (commit 2) → eab11bf (fix) → 待 commit 3/4
- Gold：仅读取，未修改（`audit_read_only`）；LLM/API：已授权调用（`authorized_called`）；产物：新建且未覆盖（`created_no_overwrite`）
- 仍存在 blocker：six_field_evaluation_blocked_by_actor_exception_coverage、final_violation_detection_blocked_by_missing_stage3_gold
- 备注：D1 repeat_02 因 DeepSeek V4 Pro 的 reasoning mode 占用了 30000 max_tokens 而失败。这是模型侧变化，不属于结果调优。已在 docs/ 中记录 max_tokens 从 4000 调整到 30000 的原因。
- 机器实验事件：formal_experiment/docs/EXPERIMENT_EVENTS.jsonl


## 2026-07-29T08:52:51.406023+00:00 - docs-only: add scope-limitation clarification explaining why paper_validation_r1 main table reports clause-level modality only (real blockers: LLM output format vs span-level evaluator + task §0.3 no-prompt-change rule; false blocker: Gold coverage low — schema permits empty arrays, not a Gold defect)

- 事件类型：变更（`change`）
- 命令：`python formal_experiment/scripts/record_change.py`
- 完整性通过：是；正式实验就绪：否
- 测试：1480 passed, 23 skipped in 165.76s (0:02:45)
- 测试证据：同一文件状态的已验证凭证（`verified_receipt`）
- Git：`c564c7c060779dfda722d0ff17ddc189ad37c703`；相关未提交路径：457 个
- Gold：未读取或修改（`not_read_or_modified`）；LLM/API：未调用（`not_called`）；产物：未创建或覆盖（`not_created_or_overwritten`）
- 仍存在 blocker：final_version_route_alignment_pending、stage2_dataset_route_relock_pending、formal_gold_publication_paused、final_experiment_not_ready、formal_methods_not_ready、formal_capsule_not_frozen、stage3_benchmark_not_locked
- 备注：Strictly docs-only change. No prompt, no Gold, no method, no evaluator, no manifest, no report asset modified. New file formal_experiment/docs/experiments/paper_validation_r1/11_MODALITY_ONLY_SCOPE.md added as a clarification of 09_SIX_FIELD_BLOCKER.md (its argument about Gold coverage being the primary blocker is overreaching; the real blockers are output-format/evaluator mismatch and task §0.3). 09_SIX_FIELD_BLOCKER.md itself is NOT rewritten in this batch. FILE_CATALOG.md regeneration was triggered to keep the catalog consistent with the new file, but its 1197-line diff is a cascade effect of pre-existing uncommitted changes from other agents/users and is staged separately or left for the next batch owner.
- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`
