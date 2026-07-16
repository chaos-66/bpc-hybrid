# 退役迁移清单

**迁移日期**：2026-07-15  
**迁移原则**：只迁移已被替代、仅供历史追溯或不应继续出现在活动目录的文件；
不删除数据，不触碰根 `references/`、根 `archive/`、Gold、正式结果或活动审核面。

| 原路径 | 归档路径 | 理由 / 活动替代物 |
|---|---|---|
| `docs/history/2026-07/CCF_C_POSITIONING_AND_SUPERVISOR_FIGURE.md` | `_retired/docs/2026-07/CCF_C_POSITIONING_AND_SUPERVISOR_FIGURE.md` | 日期版导师材料；当前路线见 `docs/MASTER_PIPELINE.md` |
| `docs/history/2026-07/CURRENT_HANDOFF_2026-07-12.md` | `_retired/docs/2026-07/CURRENT_HANDOFF_2026-07-12.md` | 旧交接；当前状态见 `docs/PROJECT_AUDIT.md` |
| `docs/history/2026-07/DATA_TRANSLATION_PROTOCOL.md` | `_retired/docs/2026-07/DATA_TRANSLATION_PROTOCOL.md` | 旧翻译协议；仅保留数据来源追溯 |
| `docs/history/2026-07/EStG_150_SAMPLING_PROTOCOL.md` | `_retired/docs/2026-07/EStG_150_SAMPLING_PROTOCOL.md` | 旧抽样协议；当前成员锁见 `docs/ESTG150_DATA_MAP.md` |
| `docs/history/2026-07/EXPERIMENT_FOR_BEGINNER.md` | `_retired/docs/2026-07/EXPERIMENT_FOR_BEGINNER.md` | 已被中文目录地图和主 Pipeline 取代 |
| `docs/history/2026-07/REORGANIZATION_PLAN.md` | `_retired/docs/2026-07/REORGANIZATION_PLAN.md` | 已执行的旧整理计划 |
| `docs/history/2026-07/STATUS_REPORT.md` | `_retired/docs/2026-07/STATUS_REPORT.md` | 日期版旧状态 |
| `docs/history/2026-07/STATUS_SNAPSHOT_2026-07-12.md` | `_retired/docs/2026-07/STATUS_SNAPSHOT_2026-07-12.md` | 日期版旧快照 |
| `docs/history/2026-07/SUN2024_FINAL_GAP_AND_ROADMAP.md` | `_retired/docs/2026-07/SUN2024_FINAL_GAP_AND_ROADMAP.md` | 旧路线；当前路线见主 Pipeline |
| `docs/changes/ESTG150_HUMAN_REVIEW_START_GATE_SPLIT_CHANGESET_2026-07-13.json` | `_retired/changes/2026-07/ESTG150_HUMAN_REVIEW_START_GATE_SPLIT_CHANGESET_2026-07-13.json` | 已记录的历史变更集 |
| `docs/changes/ESTG150_LLM_ASSISTED_V2_CHANGESET_2026-07-13.json` | `_retired/changes/2026-07/ESTG150_LLM_ASSISTED_V2_CHANGESET_2026-07-13.json` | 已记录的历史变更集 |
| `docs/changes/ESTG150_REVIEW_GATE_GOVERNANCE_ALIGNMENT_CHANGESET_2026-07-13.json` | `_retired/changes/2026-07/ESTG150_REVIEW_GATE_GOVERNANCE_ALIGNMENT_CHANGESET_2026-07-13.json` | 已记录的历史变更集 |
| `docs/changes/ESTG150_REVIEW_TOOL_READY_CHANGESET_2026-07-13.json` | `_retired/changes/2026-07/ESTG150_REVIEW_TOOL_READY_CHANGESET_2026-07-13.json` | 已记录的历史变更集 |
| `outputs/reports/experiment_design_overview.svg` | `_retired/outputs/reports/2026-07/experiment_design_overview.svg` | 旧设计图，不是冻结结果生成物 |
| `outputs/reports/experiment_overview_for_supervisor_2026-07-12.html` | `_retired/outputs/reports/2026-07/experiment_overview_for_supervisor_2026-07-12.html` | 日期版旧导师概览 |
| `data/development/legacy_r15_0/sun_rule_only_manifest.json` | `_retired/data/legacy_r15_0/sun_rule_only_manifest.json` | R15.0 历史输出，不得混入当前 development/formal 结果 |
| `data/development/legacy_r15_0/sun_rule_only_predictions.jsonl` | `_retired/data/legacy_r15_0/sun_rule_only_predictions.jsonl` | R15.0 历史输出，只保留回归证据 |
| `data/development/human_review/convert_jsonl_to_json.py` | `_retired/data/human_review_user_audit/convert_jsonl_to_json.py` | 只服务于已退役熟悉用副本 |
| `data/development/human_review/estg150_review_pack_user_audit_v1.json` | `_retired/data/human_review_user_audit/estg150_review_pack_user_audit_v1.json` | 被五层 Layer E 审核面取代 |
| `data/development/human_review/estg150_review_pack_user_audit_v1.jsonl` | `_retired/data/human_review_user_audit/estg150_review_pack_user_audit_v1.jsonl` | 被五层 Layer E 审核面取代 |
| `scripts/build_user_override_review_pack.py` | `_retired/scripts/build_user_override_review_pack.py` | 只生成已退役熟悉用副本 |
| `docs/AUDIT_LOG.md` | `_retired/logs/AUDIT_LOG_legacy_through_event_29.md` | 迁移前旧人类日志；新入口为 `docs/EXPERIMENT_LOG.md` |

机器事件日志没有归档或重写：`docs/AUDIT_EVENTS.jsonl` 原样迁移为
`docs/EXPERIMENT_EVENTS.jsonl`，其中事件 1—29 保持原始 JSONL 内容。

