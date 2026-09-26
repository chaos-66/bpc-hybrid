# Stage 3-v2 Development Report v1

- status: `DEVELOPMENT_COMPLETE_BACKEND_AND_ORDER_FROZEN`
- winter mainline: `ARCHIVED_EXTERNAL_BASELINE`
- Stage3-v1: `PRESERVED_HISTORICAL_FROZEN_RUN`
- selected backend: `spacy_en_core_web_sm`
- selected gamma/theta/tau: `0.65` / `0.4` / `0.8`
- legacy test used for calibration: `False`

## Selected Dev Table3-v2

| Method | Missing F1 | Actor F1 | TYPE-A Order F1 | Macro-F1 | Micro-F1 |
|---|---:|---:|---:|---:|---:|
| Sun | 0.4444 | 0.6316 | 0.0000 | 0.3587 | 0.4948 |
| Ours | 0.4706 | 0.6250 | 0.0000 | 0.3652 | 0.5192 |

## Old vs New Semantic Mapping Diagnostics

| Backend | Method | Action mapping success | Actor observable | Missing FP |
|---|---|---:|---:|---:|
| spacy_en_core_web_sm | sun | 50/88 (0.5682) | 38/76 | 20 |
| spacy_en_core_web_sm | ours | 61/93 (0.6559) | 48/76 | 17 |
| spacy_en_core_web_md | sun | 74/88 (0.8409) | 51/76 | 10 |
| spacy_en_core_web_md | ours | 82/93 (0.8817) | 58/76 | 5 |

## TYPE A Order Cases (dev)

| Case | Method | Edge generated | Edge endpoints | Order signal |
|---|---|---|---|---|
| case_3b01b9c36d0f | sun | False |  | unknown |
| case_3b01b9c36d0f | ours | False |  | unknown |
| case_9c6fcd32f03c | sun | False |  | unknown |
| case_9c6fcd32f03c | ours | False |  | unknown |
| case_a1712c670943 | sun | False |  | unknown |
| case_a1712c670943 | ours | False |  | unknown |
| case_a2f445c641d1 | sun | False |  | unknown |
| case_a2f445c641d1 | ours | False |  | unknown |
| case_b15419d68b21 | sun | False |  | unknown |
| case_b15419d68b21 | ours | False |  | unknown |
| case_d8029187c213 | sun | False |  | unknown |
| case_d8029187c213 | ours | False |  | unknown |
| case_ec2a9cc66fae | sun | False |  | unknown |
| case_ec2a9cc66fae | ours | False |  | unknown |
| case_f6dc7b084b03 | sun | False |  | unknown |
| case_f6dc7b084b03 | ours | False |  | unknown |
| case_f7bb207445df | sun | False |  | unknown |
| case_f7bb207445df | ours | False |  | unknown |
| case_ff937cc4c24e | sun | False |  | unknown |
| case_ff937cc4c24e | ours | False |  | unknown |

## Integrity

- Gold modified: `False`
- Benchmark modified: `False`
- Ours Stage2 modified: `False`
- Sun Stage2 modified: `False`
- Historical v1 result modified: `False`
- Real API calls: `0`

## Readiness

- STAGE3_V2_BACKEND_SELECTED = `spacy_en_core_web_sm`
- STAGE3_V2_GAMMA_FROZEN = `0.65`
- STAGE3_V2_THETA_FROZEN = `0.4`
- STAGE3_V2_TYPE_A_ORDER_SCOPE_FROZEN = `true`
- ACTION_SCOPE_CHANGE_IMPLEMENTED = `false`
- LEGACY_TEST_DIAGNOSTIC_COMPLETE = `false`
- FINAL_UNSEEN_HOLDOUT_CREATED = `false`
- FINAL_TABLE3_V2_RUN = `false`
