# S3-TABLE3-R5 Formal Table 3 Results v1

- status: `formal_run_completed`
- core scope: 33 requirements, 113 cases, 33 missing_action, 33 incorrect_actor, 14 out_of_order
- semantic challenges / condition / exception: scored separately, not in core F1
- prediction-blind Formal Gold packet released before method execution

## Overall

| Method | Precision | Recall | F1 |
|---|---:|---:|---:|
| Sun | 0.3168 | 0.4000 | 0.3536 |
| Winter | 0.4713 | 0.5125 | 0.4910 |
| Ours | 0.3504 | 0.5125 | 0.4162 |

## Per violation type

### missing_action

| Method | Precision | Recall | F1 | TP | FP | FN | TN | support | unknown+ | unknown- | NA | not_scored |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Sun | 0.3043 | 0.8485 | 0.4480 | 28 | 64 | 5 | 7 | 113 | 4 | 9 | 0 | 0 |
| Winter | 0.2979 | 0.4242 | 0.3500 | 14 | 33 | 19 | 47 | 113 | 0 | 0 | 0 | 0 |
| Ours | 0.3333 | 1.0000 | 0.5000 | 33 | 66 | 0 | 14 | 113 | 0 | 0 | 0 | 0 |

### incorrect_actor

| Method | Precision | Recall | F1 | TP | FP | FN | TN | support | unknown+ | unknown- | NA | not_scored |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Sun | 0.4444 | 0.1212 | 0.1905 | 4 | 5 | 29 | 0 | 80 | 29 | 42 | 33 | 0 |
| Winter | 0.6857 | 0.7273 | 0.7059 | 24 | 11 | 9 | 36 | 80 | 0 | 0 | 33 | 0 |
| Ours | 0.4444 | 0.2424 | 0.3137 | 8 | 10 | 25 | 0 | 80 | 25 | 37 | 33 | 0 |

### out_of_order

| Method | Precision | Recall | F1 | TP | FP | FN | TN | support | unknown+ | unknown- | NA | not_scored |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Sun | null | 0.0000 | null | 0 | 0 | 14 | 0 | 42 | 14 | 28 | 14 | 57 |
| Winter | 0.6000 | 0.2143 | 0.3158 | 3 | 2 | 11 | 4 | 42 | 11 | 22 | 14 | 57 |
| Ours | null | 0.0000 | null | 0 | 0 | 14 | 0 | 42 | 14 | 28 | 14 | 57 |

## Coverage and order-family coverage

- NA counts: `{'sun': {'not_applicable': 47, 'not_scored': 57, 'unknown_positive': 47, 'unknown_negative': 79}, 'winter': {'not_applicable': 47, 'not_scored': 57, 'unknown_positive': 11, 'unknown_negative': 22}, 'ours': {'not_applicable': 47, 'not_scored': 57, 'unknown_positive': 39, 'unknown_negative': 65}}`
- not_scored counts: `{'sun': {'not_applicable': 47, 'not_scored': 57, 'unknown_positive': 47, 'unknown_negative': 79}, 'winter': {'not_applicable': 47, 'not_scored': 57, 'unknown_positive': 11, 'unknown_negative': 22}, 'ours': {'not_applicable': 47, 'not_scored': 57, 'unknown_positive': 39, 'unknown_negative': 65}}`
- order families: `{'TYPE_A_explicit_action_precedence': 7, 'TYPE_B_trigger_precedence': 6, 'TYPE_C_deadline_arithmetic': 1, 'deadline_is_not_scored': True}`

## Development / Test

| Method | Split | Precision | Recall | F1 |
|---|---|---:|---:|---:|
| Sun | development | 0.3188 | 0.4074 | 0.3577 |
| Sun | test | 0.3125 | 0.3846 | 0.3448 |
| Winter | development | 0.4746 | 0.5185 | 0.4956 |
| Winter | test | 0.4643 | 0.5000 | 0.4815 |
| Ours | development | 0.3590 | 0.5185 | 0.4242 |
| Ours | test | 0.3333 | 0.5000 | 0.4000 |

## Failure summary

- Ours Stage2 canonicalization: `{'coordinate_reanchored': 19, 'degraded': 0, 'empty': 0, 'malformed_or_failed': 0, 'new_prediction_capsule': {'path': 'data/predictions/stage3_table3_r5_ours_stage2_new19_v1/predictions.json', 'sha256': '87ad4d864fb278397833de981d0397fc270c327f2235720f5401501e83f0c620'}, 'valid': 19}`
- Sun Stage2: `{'counts': {'empty': 0, 'failed': 0, 'ok': 33, 'records': 33}, 'failures': []}`
- Winter native: `{'cases': 113, 'rule_records': 33, 'signals': 33561}`

## Method provenance

- `benchmark_manifest_sha256`: `50d92bf5bc45374d1355a20e3d987c2f1c2df2b2bb3beb338eea295390d3f2ce`
- `config_sha256`: `7d000659e0dfbc4f531aeb63cbe36dc4b2c8d71887d732e953aef8bc712cc83b`
- `methods_manifest_sha256`: `b7c379d2b44d991b3617abf3707f362afc2eb135548e1964d81bc449dfa8b8b4`
- `signals_matrix_sha256`: `6b3e62bab25a2c7f94da712fadf19d43abc31af98297a21bc9e8fdfe1d87a03c`
- `predictions_sha256`: `1d2f710e0d5dbb48b3b4179a138dc564d33d332314f832dd80bb96779f90329c`
- `stage1_manifest_sha256`: `6db83bef1c619fb818097d3e0759349185a9b159abdf40b3fb0bcb82d051265c`
- `winter_manifest_sha256`: `1307a934caad1cdcaae09726fdf7c673670fdd6f26bcb37a66757185648354df`
- `ours_prediction_manifest_sha256`: `255bc52746521f61f59c41bc4852f1e7fe18f2301b911e206b26fc0bad2e0960`
- `ours_prediction_freeze_sha256`: `700b6ff3dab6ca44446d3975b66d67866a68309c91d7d7da801f6284721656a9`
- `sun_manifest_sha256`: `c75c03b2d4b46681788b8b47a1bc9492c811ca186f838ca773fe2ac34e83f54f`
- `evaluation_code_sha256`: `00df70e4e5d61c2ff4e1798bcd5933e66c8277bf74df9c7f2044d5f7096b854e`

Descriptive only: no method, prompt, Gold, threshold, sample, or denominator was changed after seeing these results.