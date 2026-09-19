# SEP-C3 condition-preservation v1 — recovered run report

Status: **completed_with_unresolved_response**

## Five answers

1. Recovery completed: 354 new attempts, 450 cumulative; 449 real responses, 1 unknown unresolved response not resent.
2. RC1/estg_000074 was not recovered; terminal/no-resend; 150-sample failed empty envelope; no fake raw response.
3. RC_KEEP vs RC1 condition F1: main point 0.020638, 95% interval [-0.020993, 0.064513] (contains zero).
4. RC_KEEP vs BASE five-field mean F1: -0.004786; micro F1 0.798795; actor F1 0.662782 vs BASE 0.710760.
5. Retention rule failed: required intervals contain zero and multiple criteria fail; missing-response sensitivity does not change the decision.

## Counts

| arm | attempts | real responses | denominator | failed envelopes | terminal unknown | output-processing failures |
|---|---:|---:|---:|---:|---:|---:|
| BASE | 150 | 150 | 150 | 13 | 0 | 13 |
| RC1 | 150 | 149 | 150 | 9 | 1 | 8 |
| RC_KEEP | 150 | 150 | 150 | 10 | 0 | 10 |

## Main comparisons (150 samples)

| comparison | point | bootstrap mean | 95% CI | contains zero |
|---|---:|---:|---|---:|
| RC_KEEP-RC1_condition_f1 | 0.020638 | 0.020702 | [-0.020993, 0.064513] | True |
| RC_KEEP-BASE_five_field_mean_f1 | -0.004786 | -0.005327 | [-0.056064, 0.036880] | True |

## Retention criteria

| criterion | left | right | diff | pass |
|---|---:|---:|---:|---:|
| condition_f1_improves_vs_RC1 | 0.7885728159268401 | 0.7679349896305075 | 0.020637826296332595 | True |
| condition_missed_decreases_vs_RC1 | 35 | 41 | -6 | True |
| five_field_mean_f1_improves_vs_BASE | 0.7282272954206368 | 0.7330134313635933 | -0.004786135942956515 | False |
| micro_f1_improves_vs_BASE | 0.7987948874811702 | 0.7871922035197941 | 0.011602683961376092 | True |
| actor_f1_not_below_BASE | 0.6627822286962854 | 0.7107601184600197 | -0.047977889763734294 | False |
| actor_fp_not_above_BASE | 33 | 27 | 6 | False |
| condition_fp_not_above_BASE | 15 | 16 | -1 | True |
| constraint_recall_not_below_RC1 | 0.725925925925926 | 0.7481481481481481 | -0.022222222222222143 | False |
| constraint_fp_not_above_RC1 | 47 | 49 | -2 | True |
| output_processing_failures_not_above_each_control | 10 | 8 | 2 | False |
all_criteria_pass=False; all_intervals_exclude_zero=False; decision=keep_BASE_or_evidence_uncertain

## 149-sample missing-response sensitivity

| comparison | point | bootstrap mean | 95% CI | contains zero |
|---|---:|---:|---|---:|
| RC_KEEP-RC1_condition_f1 | 0.015155 | 0.015037 | [-0.026498, 0.057721] | True |
| RC_KEEP-BASE_five_field_mean_f1 | -0.004571 | -0.004656 | [-0.054487, 0.037940] | True |

## Costs and evidence

- known actual cost: USD 0.84437985; unknown reserve: USD 0.03056592; known+unknown: USD 0.87494577
- pre-send peak/all-miss reserve: USD 8.39028960
- known tokens: prompt 545389, completion 378497, cache hit 415360, cache miss 130029
- condition recovered vs RC1: 10 samples: estg_000020, estg_000039, estg_000046, estg_000052, estg_000074, estg_000083, estg_000106, estg_000121, estg_000124, estg_000133
- condition lost vs RC1: 4 samples: estg_000060, estg_000062, estg_000218, estg_000800
- new condition FP vs RC1: 4 samples: estg_000059, estg_000079, estg_000161, estg_000507

## Decision

`candidate_not_retained_keep_BASE`. `completed_with_unresolved_response` is retained explicitly; the unknown response is a failure, not a success. No automatic default-prompt replacement.
