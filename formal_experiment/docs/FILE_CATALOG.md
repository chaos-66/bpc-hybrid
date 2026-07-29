# 项目逐文件目录

**生成日期**：2026-07-29

**收录文件**：1720 个（不含 `.env`、`.tmp/`、`.pytest_cache/`、`pytest_*/`、`__pycache__/`）

**生成命令**：`python formal_experiment/scripts/generate_file_catalog.py`

本文件由脚本按路径生成，用于快速定位，不替代各文件自身说明。状态“退役归档”
表示只可追溯；“开发/溯源”表示不能直接用于最终论文表格；“正式区（受门禁）”
表示只有冻结和运行门禁通过后才能写入。

## `.env.example`

| 文件 | 状态 | 用途 |
|---|---|---|
| `.env.example` | 活动 | 不含密钥的配置示例 |

## `_retired`

| 文件 | 状态 | 用途 |
|---|---|---|
| `_retired/changes/2026-07/ESTG150_HUMAN_REVIEW_START_GATE_SPLIT_CHANGESET_2026-07-13.json` | 退役归档 | 机器可读配置、数据、事件或产物 |
| `_retired/changes/2026-07/ESTG150_LLM_ASSISTED_V2_CHANGESET_2026-07-13.json` | 退役归档 | 机器可读配置、数据、事件或产物 |
| `_retired/changes/2026-07/ESTG150_REVIEW_GATE_GOVERNANCE_ALIGNMENT_CHANGESET_2026-07-13.json` | 退役归档 | 机器可读配置、数据、事件或产物 |
| `_retired/changes/2026-07/ESTG150_REVIEW_TOOL_READY_CHANGESET_2026-07-13.json` | 退役归档 | 机器可读配置、数据、事件或产物 |
| `_retired/data/human_review_user_audit/convert_jsonl_to_json.py` | 退役归档 | Python 实现、脚本或测试 |
| `_retired/data/human_review_user_audit/estg150_review_pack_user_audit_v1.json` | 退役归档 | 机器可读配置、数据、事件或产物 |
| `_retired/data/human_review_user_audit/estg150_review_pack_user_audit_v1.jsonl` | 退役归档 | 机器可读配置、数据、事件或产物 |
| `_retired/data/legacy_r15_0/sun_rule_only_manifest.json` | 退役归档 | 机器可读配置、数据、事件或产物 |
| `_retired/data/legacy_r15_0/sun_rule_only_predictions.jsonl` | 退役归档 | 机器可读配置、数据、事件或产物 |
| `_retired/docs/2026-07/CCF_C_POSITIONING_AND_SUPERVISOR_FIGURE.md` | 退役归档 | 说明、规范或研究文档 |
| `_retired/docs/2026-07/CURRENT_HANDOFF_2026-07-12.md` | 退役归档 | 说明、规范或研究文档 |
| `_retired/docs/2026-07/DATA_TRANSLATION_PROTOCOL.md` | 退役归档 | 说明、规范或研究文档 |
| `_retired/docs/2026-07/EStG_150_SAMPLING_PROTOCOL.md` | 退役归档 | 说明、规范或研究文档 |
| `_retired/docs/2026-07/EXPERIMENT_FOR_BEGINNER.md` | 退役归档 | 说明、规范或研究文档 |
| `_retired/docs/2026-07/REORGANIZATION_PLAN.md` | 退役归档 | 说明、规范或研究文档 |
| `_retired/docs/2026-07/STAGE2_CONTRACT_v0.1_DRAFT.md` | 退役归档 | 说明、规范或研究文档 |
| `_retired/docs/2026-07/STATUS_REPORT.md` | 退役归档 | 说明、规范或研究文档 |
| `_retired/docs/2026-07/STATUS_SNAPSHOT_2026-07-12.md` | 退役归档 | 说明、规范或研究文档 |
| `_retired/docs/2026-07/SUN2024_FINAL_GAP_AND_ROADMAP.md` | 退役归档 | 说明、规范或研究文档 |
| `_retired/logs/AUDIT_LOG_legacy_through_event_29.md` | 退役归档 | 说明、规范或研究文档 |
| `_retired/MANIFEST.md` | 退役归档 | 结构或迁移清单 |
| `_retired/outputs/reports/2026-07/experiment_design_overview.svg` | 退役归档 | 历史可视化或报告 |
| `_retired/outputs/reports/2026-07/experiment_overview_for_supervisor_2026-07-12.html` | 退役归档 | 历史可视化或报告 |
| `_retired/README.md` | 退役归档 | 所在目录的入口说明 |
| `_retired/scripts/build_user_override_review_pack.py` | 退役归档 | Python 实现、脚本或测试 |

## `AGENTS.md`

| 文件 | 状态 | 用途 |
|---|---|---|
| `AGENTS.md` | 活动 | Agent 强制合同与操作边界 |

## `configs`

| 文件 | 状态 | 用途 |
|---|---|---|
| `configs/complexity_contract.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/datasets/gdpr_articles_5_50_s211.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/datasets/gdpr_eurlex_reuse_evidence_s211.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/datasets/stage1_stage3_gdpr7_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/datasets/sun_modality_dataset.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/datasets/sun_modality_license_evidence.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/datasets/sun_modality_local_research_use.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_ai_review_gpt56sol_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_candidate_preregistration_template_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_candidate_preregistration_template_v1_1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_candidate_protocol_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_candidate_protocol_v1.lock.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_layer_d.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_openai_strict_transport_schema_adapter_v1_1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_openai_strict_transport_schema_adapter_v1_2.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_openai_strict_transport_schema_adapter_v1_3.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_openai_strict_transport_schema_adapter_v1_4.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_openai_strict_transport_schema_adapter_v1_5.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_openai_strict_transport_schema_adapter_v1_6.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_openai_strict_transport_schema_adapter_v1_7.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_openai_strict_transport_schema_adapter_v1_8.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/estg150_openai_strict_transport_schema_adapter_v1_9.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/evaluation/sun_table8_compatible_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/evaluation/sun_table8_literal_overlap_v2.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/experiment_contract.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/methods.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_active_registry_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_active_registry_v2.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_active_registry_v3.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_active_registry_v4.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_b1_preregistration_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_b2a2_preregistration_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_b2a_preregistration_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_b4_preregistration_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_b5_preregistration_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_development_s27.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_b1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_b2a.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_b2a2.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_b4.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_b5.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_v10a.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_v2.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_v3.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_v4.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_v5.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_v6.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_v7.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_v8a.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_v8b.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_v8c.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_enhanced_s27_v9a.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_v10_preregistration_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_v10_preregistration_v2.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_v8_preregistration_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_b0_v9_preregistration_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/estg150_h1_d1_low_quota_pilot_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/s24_bert_textcnn_candidate_registry_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/s27_non_llm_baselines.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/sun_b0_s26.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/sun_b0_s26_candidate_B_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/sun_bert_textcnn_s24.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/sun_d1_s29.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/models/sun_h1_s28.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/paths.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/s212_analysis_protocol.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/complex_legal_human_gold.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/complexity_profile.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/dataset_manifest.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/estg150_ai_review_model_output.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/estg150_ai_review_model_output_openai_strict_transport_v1_1.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/estg150_ai_review_model_output_openai_strict_transport_v1_2.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/estg_150_canonical_review.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/human_gold_review.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/process_record.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/stage1_evaluation_report.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/stage1_human_annotation.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/stage1_label_semantics.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/stage2_evaluation_report.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/stage2_evaluation_report_v3.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/stage2_prediction.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/schemas/style_equivalent_review.schema.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/stage1_annotation_protocol_s15.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/stage1_evaluator_s16.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/stage1_label_semantics_s13.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/stage1_structural_s11_s14.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/stage2_evaluator_s210.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/stage2_evaluator_s210_v3.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/stage2_evaluator_s210_v3_b0_enhanced.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/stage2_extraction_bundle_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/stage2_extraction_contract_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/stage2_extraction_pilot_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `configs/sun_corenlp_runtime.json` | 活动 | 机器可读配置、数据、事件或产物 |

## `data`

| 文件 | 状态 | 用途 |
|---|---|---|
| `data/development/complex_legal/gdpr_2016_679_oj_en/gdpr_articles_5_50_seeded50_human_gold_v1.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/complex_legal/gdpr_2016_679_oj_en/gdpr_articles_5_50_seeded50_v1.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/complex_legal/gdpr_2016_679_oj_en/gdpr_articles_5_50_seeded50_v1.membership.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/complex_legal/gdpr_2016_679_oj_en/source/DOC_1_metadata.xml` | 开发/溯源 | 流程模型或测试 fixture |
| `data/development/complex_legal/gdpr_2016_679_oj_en/source/DOC_2_body.xml` | 开发/溯源 | 流程模型或测试 fixture |
| `data/development/estg/estg_150_membership_hashes.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/estg_150_prepared_v1.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/estg_gold_150_llm_draft.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/estg_gold_150_v1_backup.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/estg_gold_150_v2_distribution_targeted.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/estg_selected_150_de.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/estg_selected_150_en_llm_translated.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/estg_sentences_de.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_deepseek_v4_pro_diag_v2/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_deepseek_v4_pro_diag_v2/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_deepseek_v4_pro_diag_v2/requests/001_synthetic_c1_utf8_full_extract.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_deepseek_v4_pro_diag_v2/requests/001_synthetic_c1_utf8_full_extract.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_deepseek_v4_pro_diag_v2/responses/001_synthetic_c1_utf8_full_extract.http_error.body` | 开发/溯源 | 项目文件 |
| `data/development/estg/llm_candidate_runs/c1_deepseek_v4_pro_transport_pilot_v1/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_deepseek_v4_pro_transport_pilot_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_deepseek_v4_pro_transport_pilot_v1/requests/001_synthetic_c1_utf8_full_extract.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_deepseek_v4_pro_transport_pilot_v1/requests/001_synthetic_c1_utf8_full_extract.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt35_turbo_diag_v2/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt35_turbo_diag_v2/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt35_turbo_diag_v2/requests/001_synthetic_c1_utf8_full_extract.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt35_turbo_diag_v2/requests/001_synthetic_c1_utf8_full_extract.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt35_turbo_diag_v2/responses/001_synthetic_c1_utf8_full_extract.http_error.body` | 开发/溯源 | 项目文件 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt41_nano_diag_v2/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt41_nano_diag_v2/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt41_nano_diag_v2/requests/001_synthetic_c1_utf8_full_extract.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt41_nano_diag_v2/requests/001_synthetic_c1_utf8_full_extract.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt41_nano_diag_v2/responses/001_synthetic_c1_utf8_full_extract.http_error.body` | 开发/溯源 | 项目文件 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_diag_v2/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_diag_v2/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_diag_v2/requests/001_synthetic_c1_utf8_full_extract.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_diag_v2/requests/001_synthetic_c1_utf8_full_extract.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_portable_v1_2_runtime_v1/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_portable_v1_2_runtime_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_portable_v1_2_runtime_v1/requests/001_synthetic_c1_utf8_full_extract.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_portable_v1_2_runtime_v1/requests/001_synthetic_c1_utf8_full_extract.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_portable_v1_2_runtime_v1/responses/001_synthetic_c1_utf8_full_extract.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_portable_v1_3_runtime_v1/candidates.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_portable_v1_3_runtime_v1/manifest.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_portable_v1_3_runtime_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_portable_v1_3_runtime_v1/request_manifest.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_portable_v1_3_runtime_v1/requests/001_synthetic_c1_utf8_full_extract.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_portable_v1_3_runtime_v1/requests/001_synthetic_c1_utf8_full_extract.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_portable_v1_3_runtime_v1/responses/001_synthetic_c1_utf8_full_extract.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_transport_pilot_v1/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_transport_pilot_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_transport_pilot_v1/requests/001_synthetic_c1_utf8_full_extract.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt4o_transport_pilot_v1/requests/001_synthetic_c1_utf8_full_extract.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt54_nano_diag_v2/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt54_nano_diag_v2/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt54_nano_diag_v2/requests/001_synthetic_c1_utf8_full_extract.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt54_nano_diag_v2/requests/001_synthetic_c1_utf8_full_extract.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt54_nano_diag_v2/responses/001_synthetic_c1_utf8_full_extract.http_error.body` | 开发/溯源 | 项目文件 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt54_nano_strict_v1_1_pilot_v1/accounting_correction.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt54_nano_strict_v1_1_pilot_v1/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt54_nano_strict_v1_1_pilot_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt54_nano_strict_v1_1_pilot_v1/requests/001_synthetic_c1_utf8_full_extract.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt54_nano_strict_v1_1_pilot_v1/requests/001_synthetic_c1_utf8_full_extract.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt54_nano_strict_v1_1_pilot_v1/responses/001_synthetic_c1_utf8_full_extract.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_diag_v2/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_diag_v2/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_diag_v2/requests/001_synthetic_c1_utf8_full_extract.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_diag_v2/requests/001_synthetic_c1_utf8_full_extract.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_diag_v2/responses/001_synthetic_c1_utf8_full_extract.http_error.body` | 开发/溯源 | 项目文件 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_strict_v1_1_pilot_v1/candidates.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_strict_v1_1_pilot_v1/manifest.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_strict_v1_1_pilot_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_strict_v1_1_pilot_v1/request_manifest.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_strict_v1_1_pilot_v1/requests/001_synthetic_c1_utf8_full_extract.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_strict_v1_1_pilot_v1/requests/001_synthetic_c1_utf8_full_extract.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt56_luna_strict_v1_1_pilot_v1/responses/001_synthetic_c1_utf8_full_extract.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt5_nano_diag_v2/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt5_nano_diag_v2/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt5_nano_diag_v2/requests/001_synthetic_c1_utf8_full_extract.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt5_nano_diag_v2/requests/001_synthetic_c1_utf8_full_extract.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c1_relay_gpt5_nano_diag_v2/responses/001_synthetic_c1_utf8_full_extract.http_error.body` | 开发/溯源 | 项目文件 |
| `data/development/estg/llm_candidate_runs/c1_transport_compatibility_matrix_20260725_v1/manifest.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1/offline_preparation.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_dry_run_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_live_v1/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_live_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_live_v1/requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_live_v1/requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_3_pilot3_live_v1/responses/001_estg_000080_pass_a.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1/offline_preparation.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_dry_run_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_live_v1/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_live_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_live_v1/request_manifest.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_live_v1/requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_live_v1/requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_live_v1/requests/002_estg_000080_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_live_v1/requests/002_estg_000080_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_live_v1/responses/001_estg_000080_pass_a.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_4_pilot3_live_v1/responses/002_estg_000080_pass_b.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1/offline_preparation.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_dry_run_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_live_v1/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_live_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_live_v1/requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_live_v1/requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_5_pilot3_live_v1/responses/001_estg_000080_pass_a.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1/offline_preparation.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_dry_run_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_live_v1/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_live_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_live_v1/request_manifest.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_live_v1/requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_live_v1/requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_live_v1/requests/002_estg_000080_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_live_v1/requests/002_estg_000080_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_live_v1/requests/003_estg_000070_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_live_v1/requests/003_estg_000070_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_live_v1/responses/001_estg_000080_pass_a.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_live_v1/responses/002_estg_000080_pass_b.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_6_pilot3_live_v1/responses/003_estg_000070_pass_a.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1/offline_preparation.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_dry_run_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_live_v1/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_live_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_live_v1/request_manifest.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_live_v1/requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_live_v1/requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_live_v1/requests/002_estg_000080_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_live_v1/requests/002_estg_000080_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_live_v1/requests/003_estg_000070_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_live_v1/requests/003_estg_000070_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_live_v1/responses/001_estg_000080_pass_a.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_live_v1/responses/002_estg_000080_pass_b.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_7_pilot3_live_v1/responses/003_estg_000070_pass_a.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1/offline_preparation.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_dry_run_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_live_v1/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_live_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_live_v1/request_manifest.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_live_v1/requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_live_v1/requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_live_v1/requests/002_estg_000080_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_live_v1/requests/002_estg_000080_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_live_v1/requests/003_estg_000070_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_live_v1/requests/003_estg_000070_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_live_v1/responses/001_estg_000080_pass_a.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_live_v1/responses/002_estg_000080_pass_b.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_8_pilot3_live_v1/responses/003_estg_000070_pass_a.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_9_pilot3_dry_run_v1/offline_preparation.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_9_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_9_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_9_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_9_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_9_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_9_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_9_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_9_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_9_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_9_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_9_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_9_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt4o_portable_v1_9_pilot3_dry_run_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/offline_preparation.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/offline_requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/offline_requests/002_estg_000080_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/offline_requests/003_estg_000070_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/offline_requests/004_estg_000070_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/offline_requests/005_estg_000062_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/offline_requests/006_estg_000062_pass_b.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_dry_run_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_live_v1/accounting_correction.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_live_v1/failure.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_live_v1/preregistration.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_live_v1/requests/001_estg_000080_pass_a.semantic.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_live_v1/requests/001_estg_000080_pass_a.transport.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/c2_relay_gpt56_luna_strict_v1_1_pilot3_live_v1/responses/001_estg_000080_pass_a.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/ai_review_candidates.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_003_007.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_008_012.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_013_017.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_018_022.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_023_027.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_028_032.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_033_037.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_038_042.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_043_047.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_048_052.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_053_057.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_058_062.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_063_067.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_068_072.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_073_077.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_078_082.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_083_087.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_088_092.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_093_097.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_098_102.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_103_107.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_108_112.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_113_117.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_118_122.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_123_127.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_128_135.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_136_142.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/batch_143_149.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/manifest.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_full150_v1/run_config.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_pilot3_v1/manifest.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_pilot3_v1/pass_a_candidates.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_pilot3_v1/pass_b_candidates.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_pilot3_v1/run_config.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/codex_internal_gpt56sol_pilot3_v1/run_summary.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/run_20260718_layerd_deepseek_v4_flash_v1/layer_d_v2.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/run_20260718_layerd_deepseek_v4_flash_v1/manifest.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/run_20260718_layerd_deepseek_v4_flash_v1/run_config.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/run_20260718_layerd_deepseek_v4_flash_v1/run_summary.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/run_20260718_layerd_deepseek_v4_flash_v2_nonthinking/layer_d_v2.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/run_20260718_layerd_deepseek_v4_flash_v2_nonthinking/manifest.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/run_20260718_layerd_deepseek_v4_flash_v2_nonthinking/run_config.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/estg/llm_candidate_runs/run_20260718_layerd_deepseek_v4_flash_v2_nonthinking/run_summary.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/gdpr50/r15_gdpr50_candidate_samples.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/gdpr50/r15_gdpr50_gold.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/gold_review/sun_stage2_gold_review_candidates.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/gold_review/sun_stage2_gold_review_template.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/human_review/estg150_review_pack_v1.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/human_review/ESTG150_REVIEW_WORKFLOW_V1.md` | 开发/溯源 | 说明、规范或研究文档 |
| `data/development/human_review/estg_150_canonical_review_v1.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/human_review/estg_150_human_correction_v1.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/human_review/estg_150_llm_six_element_candidates_v1.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/human_review/estg_150_review_aids_zh_v1.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/human_review/estg_150_review_aids_zh_v2.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/human_review/estg_150_translation_en_v1.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/human_review/stage1_gdpr7_annotation_blank_v1.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/human_review/stage1_gdpr7_human_correction_v1.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/human_review/stage1_gdpr7_process_records_v1.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/metadata/exploratory_spacy_manifest.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/metadata/sun_llm_fallback_manifest.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/metadata/sun_rule_only_manifest.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/modality/sun_estg_modality_v1/.gitignore` | 开发/溯源 | 项目文件 |
| `data/development/modality/sun_estg_modality_v1/manifest.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/modality/sun_estg_modality_v1/quarantine_manifest.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/modality/sun_estg_modality_v1/README.md` | 开发/溯源 | 所在目录的入口说明 |
| `data/development/modality/sun_estg_modality_v1/records.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/modality/sun_estg_modality_v1/schema_audit.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/modality/sun_estg_modality_v1/split_summary.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/modality/sun_estg_modality_v1/splits/dev.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/modality/sun_estg_modality_v1/splits/test.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/modality/sun_estg_modality_v1/splits/train.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/predictions/exploratory_spacy.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/predictions/sun_llm_fallback.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/predictions/sun_rule_only.jsonl` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/development/sun_modality/raw/.gitignore` | 开发/溯源 | 项目文件 |
| `data/development/sun_modality/raw/Decision_Logic_data.zip` | 开发/溯源 | 项目文件 |
| `data/development/sun_modality/source_manifest.json` | 开发/溯源 | 机器可读配置、数据、事件或产物 |
| `data/gold/.gitkeep` | 正式区（受门禁） | 保留当前空目录 |
| `data/input/.gitkeep` | 正式区（受门禁） | 保留当前空目录 |
| `data/input/stage1_stage3/gdpr7/gdpr_1_data_breach.bpmn` | 正式区（受门禁） | 流程模型或测试 fixture |
| `data/input/stage1_stage3/gdpr7/gdpr_2_consent_to_use_the_data.bpmn` | 正式区（受门禁） | 流程模型或测试 fixture |
| `data/input/stage1_stage3/gdpr7/gdpr_3_right_to_access.bpmn` | 正式区（受门禁） | 流程模型或测试 fixture |
| `data/input/stage1_stage3/gdpr7/gdpr_4_right_of_portability.bpmn` | 正式区（受门禁） | 流程模型或测试 fixture |
| `data/input/stage1_stage3/gdpr7/gdpr_5_right_to_withdraw.bpmn` | 正式区（受门禁） | 流程模型或测试 fixture |
| `data/input/stage1_stage3/gdpr7/gdpr_6_right_to_rectify.bpmn` | 正式区（受门禁） | 流程模型或测试 fixture |
| `data/input/stage1_stage3/gdpr7/gdpr_7_right_to_be_forgotten.bpmn` | 正式区（受门禁） | 流程模型或测试 fixture |
| `data/predictions/.gitkeep` | 正式区（受门禁） | 保留当前空目录 |
| `data/README.md` | 正式区（受门禁） | 所在目录的入口说明 |
| `data/results/.gitkeep` | 正式区（受门禁） | 保留当前空目录 |

## `docs`

| 文件 | 状态 | 用途 |
|---|---|---|
| `docs/AGENT_RUNBOOK.md` | 活动 | Agent 分阶段派工规则与可复制 Prompt |
| `docs/AI_CHANGE_PROTOCOL.md` | 活动 | 实验日志与自动检查协议 |
| `docs/ANNOTATION_PROTOCOL.md` | 活动 | 说明、规范或研究文档 |
| `docs/B0_RECONSTRUCTION_DESIGN.md` | 活动 | 说明、规范或研究文档 |
| `docs/COMPLEX_LEGAL_GOLD_GUIDE.md` | 活动 | 说明、规范或研究文档 |
| `docs/DIRECTORY_GUIDE.md` | 活动 | 中文目录职责地图 |
| `docs/ESTG150_CANDIDATE_PROTOCOL_V1.md` | 活动 | 说明、规范或研究文档 |
| `docs/ESTG150_DATA_MAP.md` | 活动 | 说明、规范或研究文档 |
| `docs/EVAL_3DIM_SPEC.md` | 活动 | 说明、规范或研究文档 |
| `docs/EXPERIMENT_EVENTS.jsonl` | 活动 | 追加式机器实验事件 |
| `docs/EXPERIMENT_LOG.md` | 活动 | 中文人类可读实验日志 |
| `docs/experiments/paper_validation_r1/00_AUDIT.md` | 活动 | 说明、规范或研究文档 |
| `docs/experiments/paper_validation_r1/01_FROZEN_CONFIG.md` | 活动 | 说明、规范或研究文档 |
| `docs/experiments/paper_validation_r1/09_SIX_FIELD_BLOCKER.md` | 活动 | 说明、规范或研究文档 |
| `docs/experiments/paper_validation_r1/10_DOWNSTREAM_BLOCKER.md` | 活动 | 说明、规范或研究文档 |
| `docs/experiments/paper_validation_r1/11_MODALITY_ONLY_SCOPE.md` | 活动 | 说明、规范或研究文档 |
| `docs/experiments/paper_validation_r1/FINAL_REPORT.md` | 活动 | 说明、规范或研究文档 |
| `docs/experiments/STAGE2_RUN_INVENTORY.md` | 活动 | 说明、规范或研究文档 |
| `docs/FILE_CATALOG.md` | 活动 | 自动生成的逐文件目录 |
| `docs/HUMAN_GOLD_GUIDE.md` | 活动 | 说明、规范或研究文档 |
| `docs/HUMAN_GOLD_REVIEW_PACK_SCHEMA_v2.md` | 活动 | 说明、规范或研究文档 |
| `docs/INDEX.md` | 活动 | 说明、规范或研究文档 |
| `docs/LLM_BUDGET_PROPOSAL_2026-07-12.md` | 活动 | 说明、规范或研究文档 |
| `docs/MASTER_PIPELINE.md` | 活动 | 唯一完整三阶段路线与任务树 |
| `docs/PROJECT_AUDIT.md` | 活动 | 唯一实时项目状态（兼容文件名） |
| `docs/REAL_WORLD_ISSUE_REGISTER.md` | 活动 | 说明、规范或研究文档 |
| `docs/REPRODUCTION_PROTOCOL.md` | 活动 | 说明、规范或研究文档 |
| `docs/research/BARRIENTOS_BORROWING_AUDIT_2026-07-12.md` | 研究证据 | 说明、规范或研究文档 |
| `docs/research/BARRIENTOS_LLM_ROLE.md` | 研究证据 | 说明、规范或研究文档 |
| `docs/research/PUBLIC_MARKER_LEXICON_RECONSTRUCTION.md` | 研究证据 | 说明、规范或研究文档 |
| `docs/research/SUN_BASELINE_AUDIT.md` | 研究证据 | 说明、规范或研究文档 |
| `docs/research/SUN_CORENLP_RUNTIME_ALIGNMENT.md` | 研究证据 | 说明、规范或研究文档 |
| `docs/research/SUN_FINAL_VERSION_AND_DATA_AUDIT.md` | 研究证据 | 说明、规范或研究文档 |
| `docs/research/SUN_MODALITY_DATASET_INGESTION.md` | 研究证据 | 说明、规范或研究文档 |
| `docs/research/SUN_OFFICIAL_LICENSE_RECORD.md` | 研究证据 | 说明、规范或研究文档 |
| `docs/research/SUN_REFERENCE_SNOWBALL_AND_MARKER_AUDIT.md` | 研究证据 | 说明、规范或研究文档 |
| `docs/research/SUN_WINTER_CODE_SEPARATION_AUDIT.md` | 研究证据 | 说明、规范或研究文档 |
| `docs/ROUTE_LOCK.md` | 活动 | 说明、规范或研究文档 |
| `docs/STAGE1_HUMAN_GOLD_GUIDE.md` | 活动 | 说明、规范或研究文档 |
| `docs/STAGE2_CANONICAL_SCHEMA_SPEC.md` | 活动 | 说明、规范或研究文档 |
| `docs/STAGE2_EXTRACTION_CONTRACT_V1.md` | 活动 | 说明、规范或研究文档 |
| `docs/STAGE2_LLM_INNOVATION_DESIGN.md` | 活动 | 说明、规范或研究文档 |
| `docs/STYLE_EQUIVALENT_SPEC.md` | 活动 | 说明、规范或研究文档 |
| `docs/USER_DECISION_LOCK_2026-07-12.md` | 活动 | 说明、规范或研究文档 |

## `MANIFEST.md`

| 文件 | 状态 | 用途 |
|---|---|---|
| `MANIFEST.md` | 活动 | 结构或迁移清单 |

## `outputs`

| 文件 | 状态 | 用途 |
|---|---|---|
| `outputs/development/estg150_independence_audit_v1/estg_150_independence_audit_v1.jsonl` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/estg150_independence_audit_v1/estg_150_independence_audit_v1.xlsx` | 活动 | 项目文件 |
| `outputs/development/estg150_independence_audit_v1/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/estg_150_review_actions_v1.jsonl` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T071756369432Z_n0001.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T071842115012Z_n0002.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T071843979575Z_n0003.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T071846238863Z_n0004.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T074236235490Z_n0001.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T082450623969Z_n0001.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T085944336464Z_n0001.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T100216794679Z_n0001.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T100501037420Z_n0002.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T100502103543Z_n0003.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T100503451172Z_n0004.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T100508388422Z_n0005.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T100509272470Z_n0006.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T100510000958Z_n0007.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T100512334077Z_n0008.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T100513080796Z_n0009.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T100652393956Z_n0010.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T103202512784Z_n0001.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T103202616346Z_n0002.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T103205209551Z_n0003.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T103212495269Z_n0004.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T104411817372Z_n0005.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T104551360479Z_n0006.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T104602503156Z_n0007.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T105117376033Z_n0008.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T105117755917Z_n0009.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T105118782077Z_n0010.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T105119429853Z_n0011.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T105120954706Z_n0012.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T105320672741Z_n0013.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T105320804044Z_n0014.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T105332993628Z_n0015.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112517899332Z_n0016.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112517951258Z_n0017.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112610365857Z_n0018.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112626491664Z_n0019.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112629555217Z_n0020.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112636947286Z_n0021.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112639325305Z_n0022.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112643066705Z_n0023.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112725205059Z_n0024.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112725302482Z_n0025.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112733184971Z_n0026.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112737484308Z_n0027.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112848213921Z_n0028.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112855806425Z_n0029.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112945864661Z_n0030.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T112946525716Z_n0031.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T113214771373Z_n0032.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T113241685144Z_n0033.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T113256108049Z_n0034.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260718T135508833787Z_n0035.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260719T105544440969Z_n0001.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260719T110000648627Z_n0002.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260719T110004846966Z_n0003.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260719T110005304682Z_n0004.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260719T110005798073Z_n0005.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260719T110006396538Z_n0006.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260719T110007119154Z_n0007.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260719T110134849524Z_n0008.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260719T111947491085Z_n0009.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T035727053361Z_n0001.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T035727164562Z_n0002.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T035734340887Z_n0003.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T035750877293Z_n0004.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T035753991962Z_n0005.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T035809584077Z_n0006.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T035812029175Z_n0007.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T035816549946Z_n0008.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T035816632693Z_n0009.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T035817489782Z_n0010.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T035826323730Z_n0011.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T035841269136Z_n0012.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T035842781622Z_n0013.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T035848111086Z_n0014.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T040155609224Z_n0015.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T040252865434Z_n0016.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T041034028056Z_n0017.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T041040447678Z_n0018.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T041040527891Z_n0019.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T041244691018Z_n0020.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T041244789327Z_n0021.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T041253149259Z_n0022.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T041304787937Z_n0023.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T041305370769Z_n0024.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043339418819Z_n0025.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043611163385Z_n0001.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043612179297Z_n0002.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043613022356Z_n0003.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043614590255Z_n0004.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043625218600Z_n0005.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043625317849Z_n0006.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043625957981Z_n0007.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043630047841Z_n0008.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043635441714Z_n0009.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043638487257Z_n0010.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043642179460Z_n0011.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043706360768Z_n0012.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043707558336Z_n0013.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043718554479Z_n0014.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043744351370Z_n0015.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043745217098Z_n0016.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043746851347Z_n0017.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043809564505Z_n0018.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043809675678Z_n0019.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043810680257Z_n0020.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043820424555Z_n0021.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043824092734Z_n0022.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043856049478Z_n0023.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043856381296Z_n0024.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043901773756Z_n0025.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043902649451Z_n0026.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043903127063Z_n0027.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043904366581Z_n0028.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043905485525Z_n0029.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T043914088965Z_n0030.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T075237713051Z_n0031.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T075251243396Z_n0032.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T075251795078Z_n0033.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T075252110636Z_n0034.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T075302371196Z_n0035.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T075302474007Z_n0036.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T075307170968Z_n0037.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T075307274701Z_n0038.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260720T081056766344Z_n0039.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052010400215Z_n0001.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052017845669Z_n0002.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052018279912Z_n0003.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052018457588Z_n0004.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052018651634Z_n0005.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052018828850Z_n0006.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052019018100Z_n0007.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052019278826Z_n0008.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052019431019Z_n0009.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052019514349Z_n0010.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052019654296Z_n0011.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052019848978Z_n0012.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052020907768Z_n0013.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052021354808Z_n0014.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052021777698Z_n0015.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052022182423Z_n0016.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052022515511Z_n0017.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052022886827Z_n0018.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052023242150Z_n0019.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052023550863Z_n0020.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052023877678Z_n0021.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052024247205Z_n0022.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052024613207Z_n0023.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052024973859Z_n0024.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052025319958Z_n0025.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052025673393Z_n0026.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052026001773Z_n0027.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052026333234Z_n0028.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052026719784Z_n0029.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052027021206Z_n0030.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052027371913Z_n0031.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052027752139Z_n0032.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052028118935Z_n0033.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052028461463Z_n0034.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052028805275Z_n0035.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052029168377Z_n0036.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052029446961Z_n0037.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052029648302Z_n0038.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052029832663Z_n0039.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052029984634Z_n0040.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052030255679Z_n0041.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052030441858Z_n0042.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052030762822Z_n0043.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052030988625Z_n0044.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052031267271Z_n0045.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052031491610Z_n0046.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052031773974Z_n0047.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052032005060Z_n0048.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052032276447Z_n0049.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052032527887Z_n0050.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052032821758Z_n0051.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052033081112Z_n0052.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052033349994Z_n0053.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052033613724Z_n0054.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052033842741Z_n0055.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052034152039Z_n0056.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052034430193Z_n0057.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052034717608Z_n0058.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052034974633Z_n0059.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052035240210Z_n0060.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052035464956Z_n0061.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052035741347Z_n0062.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052035980007Z_n0063.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052036234028Z_n0064.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052036473627Z_n0065.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052036735587Z_n0066.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052036983456Z_n0067.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052037243210Z_n0068.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052037528629Z_n0069.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052037774455Z_n0070.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052038184017Z_n0071.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052038452162Z_n0072.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052038716371Z_n0073.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052038949757Z_n0074.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052039256967Z_n0075.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052039541319Z_n0076.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052039872859Z_n0077.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052040174830Z_n0078.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052040473970Z_n0079.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052040736526Z_n0080.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052041083618Z_n0081.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052041320542Z_n0082.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052041626569Z_n0083.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052041925976Z_n0084.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052042135218Z_n0085.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052042376322Z_n0086.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052042645451Z_n0087.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052042881018Z_n0088.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052043196396Z_n0089.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052043481448Z_n0090.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052043741900Z_n0091.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052044102780Z_n0092.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052044407625Z_n0093.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052044703283Z_n0094.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052044984293Z_n0095.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052045244557Z_n0096.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052045499991Z_n0097.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052045761661Z_n0098.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052046051240Z_n0099.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052046331421Z_n0100.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052046583899Z_n0101.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052046862258Z_n0102.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052047093642Z_n0103.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052047363307Z_n0104.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052047603662Z_n0105.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052047851432Z_n0106.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052048111215Z_n0107.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052048354876Z_n0108.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052048605618Z_n0109.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052048886208Z_n0110.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052049105282Z_n0111.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052049354958Z_n0112.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052049636844Z_n0113.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052049850314Z_n0114.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052050102079Z_n0115.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052050334852Z_n0116.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052050566784Z_n0117.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052050800850Z_n0118.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052051031510Z_n0119.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052051252301Z_n0120.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052051469114Z_n0121.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052051711910Z_n0122.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052051941453Z_n0123.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052052157865Z_n0124.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052052392923Z_n0125.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052052633547Z_n0126.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052052860904Z_n0127.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052053089967Z_n0128.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052053302954Z_n0129.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052053526609Z_n0130.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052053761527Z_n0131.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052053998561Z_n0132.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052054214858Z_n0133.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052054436348Z_n0134.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052054663995Z_n0135.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052054882288Z_n0136.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052055110770Z_n0137.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052055325943Z_n0138.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052055551870Z_n0139.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052055773181Z_n0140.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052056002548Z_n0141.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052056228504Z_n0142.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052056447649Z_n0143.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052056667971Z_n0144.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052056871925Z_n0145.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052057078006Z_n0146.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052057303614Z_n0147.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052057500833Z_n0148.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052058115997Z_n0149.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/human_review/review_backups/estg_150_human_correction_v1_20260721T052227603707Z_n0150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s24_candidate_A_unweighted_seed20260717_v1/best_model.pt` | 活动 | 项目文件 |
| `outputs/development/s24_candidate_B_invsqrt_weighted_seed20260717_v1/aggregate_history.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s24_candidate_B_invsqrt_weighted_seed20260717_v1/best_model.pt` | 活动 | 项目文件 |
| `outputs/development/s24_candidate_B_invsqrt_weighted_seed20260717_v1/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s24_candidate_C_balanced_sampler_seed20260717_v1/aggregate_history.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s24_candidate_C_balanced_sampler_seed20260717_v1/best_model.pt` | 活动 | 项目文件 |
| `outputs/development/s24_candidate_C_balanced_sampler_seed20260717_v1/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s24_legal_bert_textcnn_seed20260717_v1/aggregate_history.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s24_legal_bert_textcnn_seed20260717_v1/best_model.pt` | 活动 | 项目文件 |
| `outputs/development/s24_legal_bert_textcnn_seed20260717_v1/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_b2a2_route_diagnostic_v1/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_b2a2_route_diagnostic_v1/new_record_fallback_clauses.jsonl` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_b2a2_route_diagnostic_v1/summary.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_b2a_definition_diagnostic_v1/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_b2b_prohibition_diagnostic_v1/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_b2b_prohibition_diagnostic_v1/summary.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_b3a_constraint_tregex_diagnostic_v1/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_b3a_constraint_tregex_diagnostic_v2/diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_b3a_constraint_tregex_diagnostic_v2/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_b3b_typed_ownership_diagnostic_v1/diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_b3b_typed_ownership_diagnostic_v1/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_development_v1/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_development_v1/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_development_v1/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_development_v1/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b1/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b1/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b1/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b1/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b1/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b2a/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b2a/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b2a/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b2a/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b2a/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b2a2/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b2a2/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b2a2/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b2a2/promotion_gate_report.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b2a2/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b4/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b4/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b4/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b4/promotion_gate_report.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b4/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b5/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b5/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b5/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b5/promotion_gate_report.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_b5/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v10a/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v10a/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v10a/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v10a/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v2/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v2/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v2/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v2/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v2/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v3/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v3/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v3/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v3/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v3/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v4/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v4/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v4/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v4/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v4/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v5/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v5/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v5/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v5/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v5/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v6/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v6/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v6/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v6/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v6/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v7/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v7/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v7/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v7/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v7/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8a/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8a/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8a/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8a/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8a/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8b/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8b/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8b/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8b/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8b/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8c/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8c/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8c/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8c/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v8c/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v9a/b0_attempts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v9a/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v9a/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v9a/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_enhanced_v9a/sun_table8_any_overlap_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/attempts_gold_seg_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/attempts_gold_seg_marker.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/attempts_gold_seg_real_classifier.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/attempts_v5_classifier_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/attempts_v5_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/attempts_v5_marker_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/attempts_v6_classifier_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/attempts_v6_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/attempts_v6_marker_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/invalid_v6_phase_a_autopsy.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/overlap_audit_de_s24.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/report_gold_seg_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/report_gold_seg_marker.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/report_gold_seg_real_classifier.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/report_v5_classifier_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/report_v5_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/report_v5_marker_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/report_v6_classifier_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/report_v6_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/report_v6_marker_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/v5_attempts_with_real_classifier.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v1/v6_attempts_with_real_classifier.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/attempts_gold_seg_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/attempts_gold_seg_marker.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/attempts_gold_seg_real_classifier.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/attempts_v5_classifier_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/attempts_v5_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/attempts_v5_marker_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/attempts_v6_classifier_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/attempts_v6_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/attempts_v6_marker_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/invalid_v6_phase_a_autopsy.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/overlap_audit_de_s24.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/report_gold_seg_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/report_gold_seg_marker.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/report_gold_seg_real_classifier.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/report_v5_classifier_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/report_v5_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/report_v5_marker_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/report_v6_classifier_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/report_v6_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/report_v6_marker_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/v5_attempts_with_real_classifier.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_correction_v2/v6_attempts_with_real_classifier.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_residual_v3/alignment_stats.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_residual_v3/attempts_enriched_alignment.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_residual_v3/classifier_aligned_only_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_residual_v3/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_residual_v3/marker_supported_and_abstention.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_residual_v3/report_classifier_all_including_misaligned.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_residual_v3/report_gold_seg_v5_routing_fixed.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_residual_v3/report_gold_seg_v8_hypothetical.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_phase_a_residual_v3/report_hybrid_stored.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_sun_table8_compatible_v1/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_sun_table8_compatible_v1/metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_sun_table8_literal_v2/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_sun_table8_literal_v2/metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v3_error_analysis_v1/error_analysis.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v3_evaluation_v1/evaluation_all150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v3_evaluation_v1/evaluation_independent82.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v3_evaluation_v1/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v5_error_oracle_v1/oracle.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic/overlap_audit.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic/per_class_error_buckets.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic/per_unit_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic/phase_a_diagnostic_summary.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic/report_v5_current_hybrid_classifier_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic/report_v5_current_hybrid_current_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic/report_v5_current_hybrid_marker_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic/report_v6_hybrid_classifier_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic/report_v6_hybrid_current_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic/report_v6_hybrid_marker_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic/route_confusion.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic_v5/overlap_audit.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic_v5/per_class_error_buckets.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic_v5/per_unit_diagnostic.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic_v5/phase_a_diagnostic_summary.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic_v5/report_v5_current_hybrid_classifier_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic_v5/report_v5_current_hybrid_current_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic_v5/report_v5_current_hybrid_marker_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic_v5/report_v6_hybrid_missing_classifier_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic_v5/report_v6_hybrid_missing_current_hybrid.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic_v5/report_v6_hybrid_missing_marker_only.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_b0_v6_phase_a_diagnostic_v5/route_confusion.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/development/s27_estg150_s24_overlap_audit_v2/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_d1_pilot/d1_full150/d1_pilot_1785232222.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_d1_pilot/d1_full150/d1_pilot_1785232897.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_d1_pilot/d1_full150/d1_pilot_1785233677.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_d1_pilot/d1_full150/d1_pilot_1785234301.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_d1_pilot/d1_full150/d1_pilot_1785235067.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_d1_pilot/d1_full150/d1_predicted_150.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_d1_pilot/d1_pilot_1785145982.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_h1_pilot/h1_combined_150_1785152419656231300.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_h1_pilot/h1_pilot_1785146607.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_h1_pilot/h1_pilot_1785146729.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_h1_pilot/h1_pilot_1785147286.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_h1_pilot/h1_pilot_1785147740.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_h1_pilot/h1_pilot_1785148261.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_h1_pilot/h1_pilot_1785150783.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_h1_pilot/h1_pilot_1785151490.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_h1_pilot/h1_pilot_1785152419.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_h1_selective_pilot/h1s_batch1/h1s_pilot_1785159862.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_h1_selective_pilot/h1s_batch2/h1s_pilot_1785160851.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_h1_selective_pilot/h1s_batch3/h1s_pilot_1785161869.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_h1_selective_pilot/h1s_combined_150_summary.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_h1_selective_pilot/h1s_pilot_1785158932.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_sun_strength_simulation/sun_strength_simulation_results.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_synthesis/PAPER_DATA_SYNTHESIS.md` | 活动 | 说明、规范或研究文档 |
| `outputs/paper_synthesis/paper_full_data_synthesis.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/anchoring/b0_false_positives.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/anchoring/error_provenance.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/anchoring/inheritance_by_repeat.csv` | 活动 | 项目文件 |
| `outputs/paper_validation_r1_20260728/environment.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/file_hashes.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/frozen_batches.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/frozen_batches.sha256` | 活动 | 项目文件 |
| `outputs/paper_validation_r1_20260728/git_status_at_audit.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/PAPER_VALIDATION_SYNTHESIS.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/PAPER_VALIDATION_SYNTHESIS.md` | 活动 | 说明、规范或研究文档 |
| `outputs/paper_validation_r1_20260728/pip_freeze.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/preflight_cost_estimate.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/prompts/d1_prompt.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/prompts/h1_selective_empty_prompt_template.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/prompts/h1_selective_primed_prompt_template.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/prompts/prompt_hashes.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/all_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_01/api_errors.jsonl` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_01/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_01/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_01/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_02/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_02/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_02/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_03/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_03/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_03/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_04/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_04/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_04/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_05/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_05/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/batch_05/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/cost_estimate.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/metrics_token_iou_0.3.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/per_modality_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/per_record_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/timing.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_01/token_usage.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/all_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_01/api_errors.jsonl` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_01/parse_errors.jsonl` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_01/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_01/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_01/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_02/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_02/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_02/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_03/api_errors.jsonl` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_03/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_03/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_03/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_04/api_errors.jsonl` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_04/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_04/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_04/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_05/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_05/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/batch_05/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/cost_estimate.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/metrics_token_iou_0.3.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/per_modality_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/per_record_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/timing.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_02/token_usage.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/all_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_01/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_01/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_01/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_02/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_02/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_02/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_03/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_03/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_03/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_04/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_04/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_04/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_05/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_05/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/batch_05/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/cost_estimate.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/metrics_token_iou_0.3.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/per_modality_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/per_record_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/timing.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_03/token_usage.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_01/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_01/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_01/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_02/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_02/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_02/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_03/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_03/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_03/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_04/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_04/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_04/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_05/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_05/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/batch_05/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/timing.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/d1_unprimed/repeat_04/token_usage.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/all_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_01/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_01/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_01/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_02/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_02/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_02/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_03/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_03/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_03/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_04/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_04/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_04/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_05/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_05/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/batch_05/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/cost_estimate.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/metrics_token_iou_0.3.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/per_modality_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/per_record_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/timing.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_01/token_usage.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/all_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_01/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_01/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_01/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_02/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_02/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_02/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_03/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_03/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_03/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_04/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_04/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_04/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_05/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_05/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/batch_05/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/cost_estimate.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/metrics_token_iou_0.3.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/per_modality_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/per_record_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/timing.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_02/token_usage.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/all_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_01/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_01/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_01/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_02/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_02/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_02/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_03/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_03/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_03/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_04/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_04/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_04/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_05/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_05/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/batch_05/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/cost_estimate.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/metrics_token_iou_0.3.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/per_modality_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/per_record_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/timing.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_empty/repeat_03/token_usage.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/all_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_01/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_01/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_01/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_02/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_02/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_02/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_03/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_03/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_03/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_04/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_04/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_04/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_05/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_05/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/batch_05/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/cost_estimate.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/metrics_token_iou_0.3.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/per_modality_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/per_record_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/timing.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_01/token_usage.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/all_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_01/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_01/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_01/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_02/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_02/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_02/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_03/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_03/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_03/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_04/api_errors.jsonl` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_04/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_04/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_04/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_05/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_05/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/batch_05/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/cost_estimate.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/metrics_token_iou_0.3.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/per_modality_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/per_record_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/timing.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_02/token_usage.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/all_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_01/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_01/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_01/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_02/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_02/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_02/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_03/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_03/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_03/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_04/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_04/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_04/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_05/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_05/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/batch_05/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/cost_estimate.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/metrics_token_iou_0.3.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/per_modality_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/per_record_metrics.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/timing.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/runs/h1_selective_primed/repeat_03/token_usage.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/d1_unprimed/batch_01/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/d1_unprimed/batch_01/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/smoke/d1_unprimed/batch_01/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/d1_unprimed/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/d1_unprimed/timing.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/d1_unprimed/token_usage.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/h1_selective_empty/batch_01/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/h1_selective_empty/batch_01/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/smoke/h1_selective_empty/batch_01/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/h1_selective_empty/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/h1_selective_empty/timing.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/h1_selective_empty/token_usage.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/h1_selective_primed/batch_01/parsed_predictions.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/h1_selective_primed/batch_01/raw_response.txt` | 活动 | 文本清单或依赖说明 |
| `outputs/paper_validation_r1_20260728/smoke/h1_selective_primed/batch_01/request_metadata.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/h1_selective_primed/run_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/h1_selective_primed/timing.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/h1_selective_primed/token_usage.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/smoke/smoke_summary.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/statistics/bootstrap_repeat_01.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/statistics/bootstrap_repeat_02.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/statistics/bootstrap_repeat_03.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/statistics/bootstrap_summary.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/statistics/run_level_summary.csv` | 活动 | 项目文件 |
| `outputs/paper_validation_r1_20260728/statistics/run_level_summary.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/subsets/definition_errors.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/paper_validation_r1_20260728/subsets/difficulty_metrics.csv` | 活动 | 项目文件 |
| `outputs/paper_validation_r1_20260728/subsets/modality_confusion.csv` | 活动 | 项目文件 |
| `outputs/paper_validation_r1_20260728/threshold_analysis/all_metrics.csv` | 活动 | 项目文件 |
| `outputs/paper_validation_r1_20260728/threshold_analysis/ranking_by_threshold.csv` | 活动 | 项目文件 |
| `outputs/paper_validation_r1_20260728/threshold_analysis/summary.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/README.md` | 活动 | 所在目录的入口说明 |
| `outputs/reports/.gitkeep` | 目录占位 | 保留当前空目录 |
| `outputs/reports/g05_complexity_contract_synthetic_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s11_s14_stage1_structural_synthetic_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s13_stage1_label_semantics_synthetic_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s15_s31_gdpr7_membership_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s15_stage1_annotation_protocol_synthetic_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s16_stage1_evaluator_contract_synthetic_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s210_stage2_evaluator_contract_synthetic_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s210_stage2_evaluator_contract_synthetic_v2.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s210_stage2_evaluator_contract_synthetic_v3.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s211_gdpr_complex_dataset_freeze_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s212_analysis_protocol_synthetic_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s212_analysis_protocol_synthetic_v2.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s22_estg150_human_annotation_freeze_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s24_bert_textcnn_candidate_selection_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s24_candidate_B_invsqrt_weighted_seed20260717_v1.adapter_s24_schema.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s24_candidate_B_invsqrt_weighted_seed20260717_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s24_candidate_C_balanced_sampler_seed20260717_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s24_legal_bert_textcnn_seed20260717_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s26_sun_b0_canonical_composition_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s26_sun_b0_canonical_composition_v2.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s26_sun_b0_canonical_composition_v3.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s27_estg150_b0_b1_pre_correction_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s27_estg150_b0_b3a_not_instantiated_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s27_estg150_b0_b3a_status_correction_v2.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s27_estg150_b0_v10_selection_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s27_estg150_b0_v8_selection_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s27_estg150_b0_v8_status_correction_v2.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s27_estg150_b0_v9_selection_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s27_estg150_b0_v9_status_correction_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s27_non_llm_modality_baselines_seed20260717_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s28_sun_h1_selective_dry_run_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s28_sun_h1_selective_dry_run_v2.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s28_sun_h1_selective_dry_run_v3.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s28_sun_h1_selective_dry_run_v4.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s28_sun_h1_selective_dry_run_v5.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s28_sun_h1_selective_dry_run_v6.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s29_sun_d1_offline_prereg_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s29_sun_d1_offline_prereg_v2.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s29_sun_d1_offline_prereg_v3.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s29_sun_d1_offline_prereg_v4.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/s29_sun_d1_offline_prereg_v5.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `outputs/reports/stage2_run_inventory_20260729.json` | 活动 | 机器可读配置、数据、事件或产物 |

## `paper`

| 文件 | 状态 | 用途 |
|---|---|---|
| `paper/CLAIM_EVIDENCE_MATRIX.md` | 活动 | 科学主张、证据状态和解锁条件 |
| `paper/README.md` | 活动 | 所在目录的入口说明 |
| `paper/THESIS_DRAFT.md` | 活动 | 中文论文连续工作稿与结果占位 |

## `prompts`

| 文件 | 状态 | 用途 |
|---|---|---|
| `prompts/estg150_ai_review/internal_sol_full_extract_v1.md` | 活动 | 说明、规范或研究文档 |
| `prompts/estg150_ai_review/pass_a_blind_review_v1.md` | 活动 | 说明、规范或研究文档 |
| `prompts/estg150_ai_review/pass_b_adjudicator_v1.md` | 活动 | 说明、规范或研究文档 |
| `prompts/sun_compat/direct_llm_few_shot_fixtures.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `prompts/sun_compat/direct_llm_sun_record_prompt.md` | 活动 | 说明、规范或研究文档 |
| `prompts/sun_compat/dry_run_back_translation.md` | 活动 | 说明、规范或研究文档 |
| `prompts/sun_compat/dry_run_six_element.md` | 活动 | 说明、规范或研究文档 |
| `prompts/sun_compat/dry_run_zh_gloss.md` | 活动 | 说明、规范或研究文档 |
| `prompts/sun_compat/rule_first_llm_fallback_prompt.md` | 活动 | 说明、规范或研究文档 |
| `prompts/zh_aid/en_back_translation.md` | 活动 | 说明、规范或研究文档 |
| `prompts/zh_aid/zh_translation.md` | 活动 | 说明、规范或研究文档 |

## `pyproject.toml`

| 文件 | 状态 | 用途 |
|---|---|---|
| `pyproject.toml` | 活动 | 配置或工程元数据 |

## `README.md`

| 文件 | 状态 | 用途 |
|---|---|---|
| `README.md` | 活动 | 所在目录的入口说明 |

## `requirements-audit.txt`

| 文件 | 状态 | 用途 |
|---|---|---|
| `requirements-audit.txt` | 活动 | 文本清单或依赖说明 |

## `resources`

| 文件 | 状态 | 用途 |
|---|---|---|
| `resources/corenlp/s25b_runtime_verification_manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/corenlp/sun_phrase_patterns_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/corenlp/sun_phrase_patterns_v2_enhanced.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/corenlp/sun_phrase_patterns_v3_enhanced.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/corenlp/sun_phrase_patterns_v4_expanded.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/corenlp/sun_phrase_patterns_v5_b5_tsurgeon.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/actor_markers_en_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/actor_markers_en_v2.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/condition_markers_en_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/condition_markers_en_v2.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/constraint_markers_en_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/constraint_markers_en_v2.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/constraint_markers_en_v3_b4.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/development_extensions_en_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/exception_markers_en_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/exception_markers_en_v2.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/modality_markers_en_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/modality_markers_en_v2.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/public_marker_lexicon_en_v1.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/public_marker_lexicon_en_v2.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/public_marker_lexicon_en_v3_b4.manifest.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/public_marker_sources_en_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/public_marker_sources_en_v2.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/lexicon/public_marker_sources_en_v3_b4.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `resources/sun_marker_lexicon.json` | 活动 | 机器可读配置、数据、事件或产物 |

## `scripts`

| 文件 | 状态 | 用途 |
|---|---|---|
| `scripts/_precheck_estg150.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/analyze_estg150_b0_b2a2_route_diagnostic_v1.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/analyze_estg150_b0_b2b_prohibition_diagnostic_v1.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/analyze_estg150_b0_b3a_constraint_tregex_correction_v2.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/analyze_estg150_b0_b3a_constraint_tregex_v1.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/analyze_estg150_b0_b3b_typed_ownership_diagnostic_v1.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/analyze_estg150_b0_phase_a_correction_v1.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/analyze_estg150_b0_phase_a_residual_v3.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/analyze_estg150_b0_v6_components.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/audit_ingest_sun_modality_official.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/audit_project.py` | 活动 | 离线项目完整性检查（兼容文件名） |
| `scripts/audit_stage2_to_stage3.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/build_canonical_review.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/build_complex_legal_s211.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/build_d1_few_shot_fixtures.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/build_estg150_internal_sol_bundle.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/build_estg150_review_layers.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/build_estg_human_review_pack.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/build_gold_review_pack.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/build_public_marker_lexicon.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/build_stage1_annotation_protocol.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/build_stage1_gdpr7.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/check_sun_baseline.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/clean_estg150_german.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/compute_estg_membership_hashes.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/dry_run_llm_estimate.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/estg150_review_tool.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/estg150_simple_review_tool.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/evaluate_estg150_b0_sun_table8_compatible.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/evaluate_estg150_b0_sun_table8_literal_v2.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/evaluate_stage1_s16.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/evaluate_stage2_s210.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/generate_file_catalog.py` | 活动 | 重建本逐文件目录 |
| `scripts/ingest_sun_modality.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/paper_validation/analyze_anchoring.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/paper_validation/analyze_subsets.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/paper_validation/analyze_thresholds.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/paper_validation/bootstrap_record_level.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/paper_validation/build_preflight_estimate.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/paper_validation/build_validation_report.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/paper_validation/evaluate_predictions.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/paper_validation/run_repeated_llm_experiment.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/promote_layer_d_v2.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/rebuild_d1_prompt.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/record_change.py` | 活动 | 追加经过验证的变更/运行/里程碑事件 |
| `scripts/reevaluate_estg150_b0_v3.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_d1_paper_pilot.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_direct_llm.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_ai_review.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_b0_development.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_b0_enhanced_b1_development.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_b0_enhanced_b2a2_development.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_b0_enhanced_b2a_development.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_b0_enhanced_b4_development.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_b0_enhanced_b5_development.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_b0_enhanced_development.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_b0_enhanced_v10_development.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_b0_enhanced_v4_development.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_b0_enhanced_v6_development.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_b0_enhanced_v7_development.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_b0_enhanced_v8_development.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_b0_enhanced_v9_development.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_estg150_candidate_protocol.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_formal_pipeline.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_h1_paper_pilot.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_h1_selective_pilot.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_llm_zh_aid.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_s27_modality_baselines.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_stage1_label_semantics.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_stage1_structural.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_stage3_fixture_harness.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_sun_llm_fallback.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_sun_rule_only.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/run_sun_strength_simulation.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/status.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/train_s24_bert_textcnn_candidates.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/train_sun_bert_textcnn.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/validate_canonical_review.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/validate_complex_legal_human_gold.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/validate_estg_human_review.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/validate_gold.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/validate_human_correction.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/validate_layer_d_v2.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/validate_legacy_gold_review.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_complex_legal_s211.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_complexity_contract_g05.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_corenlp_s25b.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_d1_few_shot_fixtures.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_estg150_b0_development.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_estg150_b0_v3.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_estg150_s22_freeze.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_s212_analysis_protocol.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_stage1_annotation_protocol_s15.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_stage1_evaluator_s16.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_stage1_label_semantics_s13.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_stage1_stage3_gdpr7.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_stage1_structural_s11_s14.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_stage2_evaluator_s210.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_stage2_evaluator_s210_v3.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_sun_b0_s26.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_sun_d1_s29.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_sun_h1_s28.py` | 活动 | Python 实现、脚本或测试 |
| `scripts/verify_sun_modality_zip.py` | 活动 | Python 实现、脚本或测试 |

## `src`

| 文件 | 状态 | 用途 |
|---|---|---|
| `src/bpc_hybrid/__init__.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v10/__init__.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v10/actor_action.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v10/actor_action_tregex_b5.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v10/alignment.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v10/clause_probability_adapter_b2a2.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v10/definition_resolver.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v10/definition_resolver_b2a2.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v10/diagnostics.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v10/modality.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v10/pipeline.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v10/profile.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v10/scope.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v10/segmentation.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v9/__init__.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v9/actor_action.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v9/alignment.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v9/diagnostics.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v9/modality.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v9/pipeline.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v9/profile.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/b0_v9/scope.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/complex_legal.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/complexity.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/datasets/__init__.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/datasets/sun_modality_importer.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/datasets/sun_modality_official.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/estg150_b0_development.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/estg150_b0_development_b1.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/estg150_b0_development_b2a.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/estg150_b0_development_b2a2.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/estg150_b0_development_b4.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/estg150_b0_development_b5.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/estg150_b0_development_v10.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/estg150_b0_development_v2.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/estg150_b0_development_v3.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/estg150_b0_development_v4.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/estg150_b0_development_v5.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/estg150_b0_development_v6.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/estg150_b0_development_v9.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/evaluation/__init__.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/evaluation/concept_level_eval.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/evaluator.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/extractor.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/fallback.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/llm_client.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/llm_config.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/llm_provider.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/mini_pilot_evaluator.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/normalization.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/prompt_loader.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/s212_analysis.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/schema.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/schema_alignment.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/smoke.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/splitter.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/stage1_evaluation.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/stage1_formal_dataset.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/stage1_human_annotation.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/stage1_label_semantics.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/stage1_process.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/stage2_canonical.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/stage2_evaluation.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/stage2_evaluation_v3.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/stage2_sun_table8_compatible.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_compat/__init__.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_compat/clause_adapter.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_compat/schema.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_compat/similarity_engine.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_compat/stage3_adapter.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/__init__.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/bert_modality_classifier.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/bert_textcnn.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/bpmn_semantics.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/corenlp_runtime.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/d1_direct.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/h1_selective.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/lexicon_v2_runtime.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/marker_lexicon.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/modality_classifier.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/non_llm_modality_baselines.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/public_marker_lexicon.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/rule_record.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/semantic_extractor.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/spacy_semantic_extractor.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/spacy_syntactic_rules.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/sun_b0.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/syntactic_rules.py` | 活动 | Python 实现、脚本或测试 |
| `src/bpc_hybrid/sun_style/violation_detection.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/__init__.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/audit.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/corenlp_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/estg150_c1_transport.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/estg150_candidate_protocol.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/estg150_service.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/estg150_simple_review.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/estg150_validator.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/g05_complexity_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/gold.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/layer_d_security.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/layer_d_validator.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/paths.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s1_annotation_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s1_evaluator_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s1_label_semantics_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s1_membership_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s1_structural_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s2_10_evaluator_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s2_10_evaluator_v3_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s2_11_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s2_12_analysis_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s2_2_freeze_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s2_4_license_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s2_6_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s2_7_b0_development_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s2_7_modality_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s2_8_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/s2_9_gate.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/status.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/sun_baseline.py` | 活动 | Python 实现、脚本或测试 |
| `src/formal_experiment/sun_modality_gate.py` | 活动 | Python 实现、脚本或测试 |

## `tests`

| 文件 | 状态 | 用途 |
|---|---|---|
| `tests/fixtures/bpmn/minimal_bpmn_incorrect_actor.bpmn` | 活动 | 流程模型或测试 fixture |
| `tests/fixtures/bpmn/minimal_bpmn_missing_action.bpmn` | 活动 | 流程模型或测试 fixture |
| `tests/fixtures/bpmn/minimal_bpmn_out_of_order.bpmn` | 活动 | 流程模型或测试 fixture |
| `tests/fixtures/complexity/bpmn_cycle_fixture.bpmn` | 活动 | 流程模型或测试 fixture |
| `tests/fixtures/complexity/text_two_sentence_fixture.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/corenlp/b5_tsurgeon_synthetic_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/corenlp/obligation_condition_constraint.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/corenlp/s25b_live_expected.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/corenlp/s25b_smoke_input.txt` | 活动 | 文本清单或依赖说明 |
| `tests/fixtures/d1_s29/s29_offline_contract_fixture.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/estg150_candidate_protocol/canonical_semantic_request_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/estg150_candidate_protocol/strict_transport_invalid_candidate_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/estg150_candidate_protocol/strict_transport_valid_candidate_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/estg150_candidate_protocol/synthetic_record_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/public_marker_lexicon/marker_cases_en_v1.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/s212_analysis/s212_synthetic_counts.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/stage1/s11_branch_parallel.bpmn` | 活动 | 流程模型或测试 fixture |
| `tests/fixtures/stage1/s13_label_edge_cases.bpmn` | 活动 | 流程模型或测试 fixture |
| `tests/fixtures/stage1/s14_cycle_unreachable.bpmn` | 活动 | 流程模型或测试 fixture |
| `tests/fixtures/stage1/s16_synthetic_semantic_reference.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/stage2_evaluator/s210_contract_fixture.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/sun_compat_incorrect_actor.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/sun_compat_missing_action.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/sun_compat_out_of_order.json` | 活动 | 机器可读配置、数据、事件或产物 |
| `tests/fixtures/sun_modality/_fixture_builder.py` | 活动 | Python 实现、脚本或测试 |
| `tests/fixtures/sun_modality/README.md` | 活动 | 所在目录的入口说明 |
| `tests/fixtures/sun_modality/synthetic_cross_split_leakage.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_duplicate_id.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_duplicate_text_conflicting_label.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_duplicate_text_same_label.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_empty_text.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_encoding_error.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_headerless_integer.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_large_normal.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_missing_label_column.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_no_source_id.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_normal.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_one_hot_all_zero.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_one_hot_multi_hot.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_one_hot_non_binary.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_small_class.csv` | 活动 | 项目文件 |
| `tests/fixtures/sun_modality/synthetic_unknown_label.csv` | 活动 | 项目文件 |
| `tests/paper_validation/conftest.py` | 活动 | Python 实现、脚本或测试 |
| `tests/paper_validation/test_paper_validation.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_audit.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_b0_b1_deontic_segmentation.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_b0_b2a2_definition_constrained_decoding.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_b0_b2a_definition_resolver.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_b0_b3a_constraint_tregex_correction_v2.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_b0_b3b_typed_ownership_diagnostic_v1.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_b0_b4_constraint_marker_expansion.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_b0_b5_tsurgeon_tregex_consumed.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_b0_v10_scope_and_alignment.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_b0_v9_core_and_registry.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_change_record.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_estg150_ai_review_runner.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_estg150_b0_development.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_estg150_b0_enhanced_v2.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_estg150_b0_enhanced_v4.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_estg150_b0_enhanced_v6.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_estg150_b0_enhanced_v8.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_estg150_c1_transport_adapter.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_estg150_candidate_protocol.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_estg150_simple_review.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_estg_150_canonical_review.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_estg_150_review_tool.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_estg_human_review.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_evaluator.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_event23_gate_hardening.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_extractor.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_fallback.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_fallback_pipeline.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_formal_project_audit.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_g05_complexity_contract.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_gold_review_pack.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_layer_d_runner_and_validator.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_lexicon_v2_and_tsurgeon_honesty.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_llm_client.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_llm_config.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_master_pipeline_and_layout.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_normalization.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_phase_a_correction_v1.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_project_structure.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_prompt_contract.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_public_marker_lexicon.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_r15_sun_style_g1_lexicon_classifier.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_r15_sun_style_g2_extraction_rules.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_r15_sun_style_g3_bpmn_violation.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_r15_sun_style_g4_outputs_overclaim.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s1_1_s1_4_stage1_structural.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s1_3_stage1_label_semantics.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s1_5_stage1_annotation_protocol.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s1_6_stage1_evaluator.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s1_s3_gdpr7_membership.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s210_v3_exact_gates.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s22_estg150_annotation_freeze.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s24_bert_textcnn.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s24_license_gate.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s25_corenlp_contract.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s26_sun_b0.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s27_non_llm_baselines.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s28_h1_selective.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s29_d1_direct.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s2_10_stage2_evaluation.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s2_10_stage2_evaluation_v3.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s2_11_complex_legal.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_s2_12_analysis_protocol.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_sampling_params.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_schema.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_schema_alignment.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_smoke.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_splitter.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_stage2_extraction_contract_v1.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_stage2_prediction_schema.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_stage2_sun_table8_compatible.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_sun_compat.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_sun_modality_gate.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_sun_modality_ingestion.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_sun_modality_official.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_sun_modality_source_manifest.py` | 活动 | Python 实现、脚本或测试 |
| `tests/test_verification_receipt.py` | 活动 | Python 实现、脚本或测试 |

## `tools`

| 文件 | 状态 | 用途 |
|---|---|---|
| `tools/corenlp/SunPhraseRuleBatchBridge.java` | 活动 | 项目文件 |
| `tools/corenlp/SunPhraseRuleBatchBridgeMulti.java` | 活动 | 项目文件 |
| `tools/corenlp/SunPhraseRuleBatchBridgeSafeV2.java` | 活动 | 项目文件 |
| `tools/corenlp/SunPhraseRuleBatchBridgeTsurgeonB5.java` | 活动 | 项目文件 |
| `tools/corenlp/SunPhraseRuleBridge.java` | 活动 | 项目文件 |
| `tools/corenlp/SunPhraseRuleDiagnosticB3aV2.java` | 活动 | 项目文件 |
