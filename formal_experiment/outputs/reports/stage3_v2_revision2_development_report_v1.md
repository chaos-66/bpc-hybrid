# Stage 3-v2 Revision 2 Development Report v1

- status: `REVISION2_INCOMPLETE_PHASE_A_COMPLETE_PHASE_B_BLOCKED`
- Phase A: complete; U_r provenance resolved; order implementation blocked on evidence
- Phase B: blocked at official MPNet snapshot download-size anomaly; MPNet sweep not run
- Phase C: not attempted because Phase A gate forbids implementation

## Overall Development Reference (v1 retained, not a revision-2 run)

| Method | Precision | Recall | F1 | Macro-F1 | Coverage | Unknown rate |
|---|---:|---:|---:|---:|---:|---:|
| sun | 0.5000 | 0.4898 | 0.4948 | 0.3587 | 0.7034 | 0.2966 |
| ours | 0.4909 | 0.5510 | 0.5192 | 0.3652 | 0.7862 | 0.2138 |

## Per-Type P/R/F1

| Method | Type | TP | FP | FN | TN | Precision | Recall | F1 | Coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| sun | missing_action | 12 | 20 | 10 | 30 | 0.3750 | 0.5455 | 0.4444 | 0.9211 |
| sun | incorrect_actor | 12 | 4 | 10 | 16 | 0.7500 | 0.5455 | 0.6316 | 0.5926 |
| sun | out_of_order | 0 | 0 | 5 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| ours | missing_action | 12 | 17 | 10 | 37 | 0.4138 | 0.5455 | 0.4706 | 1.0000 |
| ours | incorrect_actor | 15 | 11 | 7 | 11 | 0.5769 | 0.6818 | 0.6250 | 0.7037 |
| ours | out_of_order | 0 | 0 | 5 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Mapping Diagnostics

| Backend | Method | Action map success | Action map rate | Actor observable | Actor scored | Missing FP |
|---|---:|---:|---:|---:|---:|---:|
| spacy_en_core_web_sm | sun | 50/88 | 0.5682 | 38/76 | 76 | 20 |
| spacy_en_core_web_sm | ours | 61/93 | 0.6559 | 48/76 | 76 | 17 |
| spacy_en_core_web_md | sun | 74/88 | 0.8409 | 51/76 | 76 | 10 |
| spacy_en_core_web_md | ours | 82/93 | 0.8817 | 58/76 | 76 | 5 |
| sentence_transformers_all_mpnet_base_v2 | sun | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| sentence_transformers_all_mpnet_base_v2 | ours | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |

## TYPE-A Order

| Method | Eligible reqs | Positive variants | Baseline controls | Other satisfied controls | Scored negative cells | Scored cells | U_r generated | U_r absent | TP | FP | FN | TN | P | R | F1 | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ours | 5 | 5 | 5 | 5 | 10 | 15 | 0 | 15 | 0 | 0 | 5 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| sun | 5 | 5 | 5 | 5 | 10 | 15 | 0 | 15 | 0 | 0 | 5 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

Revision 1 TYPE-A Order F1 remains `0.0000`. Revision 2 did not change it because order implementation is blocked on U_r construction evidence.

## Integrity
- benchmark_modified: `False`
- bpmn_modified: `False`
- final_table3_run: `False`
- final_unseen_holdout_created: `False`
- gold_modified: `False`
- legacy_test_read: `False`
- legacy_test_rerun: `False`
- llm_api_calls: `0`
- ours_stage2_predictions_modified: `False`
- stage3_v2_revision1_overwritten: `False`
- sun_stage2_predictions_modified: `False`

## Readiness
- DEVELOPMENT_REVISION2_COMPLETE: `False`
- MPNET_DEV_SWEEP_COMPLETE: `False`
- MPNET_DOWNLOADED: `True`
- MPNET_PROMOTED: `False`
- ORDER_METHOD_FINAL_FROZEN: `False`
- ORDER_METHOD_STATUS: `BLOCKED_ON_EVIDENCE`
- SEMANTIC_BACKEND_FINAL_FROZEN: `False`
- STAGE3_V2_R1_PRESERVED: `True`
- SUN_U_R_PROVENANCE_RESOLVED: `True`
- TABLE3_V1_PRESERVED: `True`
- WINTER_ARCHIVED: `True`
