# Stage 3-v2 Legacy Seen-Test Diagnostic v1

- label: `LEGACY_SEEN_TEST_DIAGNOSTIC`
- final unseen test: `false`
- frozen backend: `spacy_en_core_web_sm`
- frozen gamma/theta: `0.65` / `0.4`
- no post-result modification: `true`

## Overall

| Method | Missing F1 | Actor F1 | TYPE-A Order F1 | Macro-F1 | Micro-F1 |
|---|---:|---:|---:|---:|---:|
| Sun | 0.4634 | 0.5862 | 0.0000 | 0.3499 | 0.4898 |
| Ours | 0.4938 | 0.6111 | 0.0000 | 0.3683 | 0.5250 |

## Split Summary

| Split | Method | Macro-F1 | Micro-F1 |
|---|---|---:|---:|
| development | sun | 0.3587 | 0.4948 |
| development | ours | 0.3652 | 0.5192 |
| test | sun | 0.3333 | 0.4800 |
| test | ours | 0.3722 | 0.5357 |

## Quarantine Statement

This is ONE post-freeze replay on the legacy seen test split. It is not a blind final test and must not be cited as final Table 3. No backend, threshold, projection, Gold, prediction, or metric was changed after this diagnostic.
