# Stage 3 Table 3 — Provisional Final Paper-Facing Freeze v1

- **Status:** `PROVISIONAL_FINAL_PAPER_FACING_RESULT`
- **Schema:** `stage3_table3_provisional_final@1.0.0`
- **TABLE3_PROVISIONAL_FREEZE:** `true`
- **STAGE3_DEVELOPMENT_PAUSED:** `true` (`paper_and_presentation_priority`)
- **WINTER_MAINLINE_STATUS:** `ARCHIVED_EXTERNAL_BASELINE`
- **Source result artifact:** `formal_experiment/outputs/reports/stage3_final_convergence_report_v1.json`
- **Source result SHA-256:** `f3263dca9d76869dc8cbad27bc9ee331baeb72ee5d103685d4cd93e75d6e0dab`
- **Source git HEAD at freeze generation:** `aef4aa2f78353731c26064ca905893d925932042`
- **Source result status:** `STAGE3_METHOD_FROZEN_FINAL_UNSEEN_BENCHMARK_BLOCKED_PENDING_USER_AUTHORIZATION`
- **Source final_test_eligible:** `false`

## Frozen Table 3

| Method | Precision | Recall | F1 |
|---|---:|---:|---:|
| Sun et al. | 0.3814 | 0.5362 | 0.4458 |
| Ours | 0.4393 | 0.6812 | 0.5341 |

## Breakdown

| Method | Missing F1 | Actor F1 | Order F1 | Macro-F1 |
|---|---:|---:|---:|---:|
| Sun | 0.4554 | 0.4262 | 0.5000 | 0.4606 |
| Ours | 0.4935 | 0.5684 | 0.5000 | 0.5206 |

## Improvement

- Precision delta (Ours - Sun): `0.0578`
- Recall delta (Ours - Sun): `0.1449`
- Absolute F1 delta: `0.0883`
- F1 percentage-point gain: `8.83`
- Relative F1 improvement: `19.81%`
- Macro-F1 delta: `0.0601`

Under the shared downstream compliance checker, Ours achieves higher Precision, Recall, and F1 than the Sun baseline on the current evaluation benchmark. Ours improves overall F1 by approximately 8.83 percentage points over Sun.

## Evaluation Scope

The current result is based on the constructed evaluation benchmark used during method development. All 113 existing cases are seen (`ALL_EXISTING_CASES_SEEN = true`). This is **not** an unseen test, held-out final test, or blind final evaluation. `FINAL_UNSEEN_EVALUATION_COMPLETED = false` and `CURRENT_RESULT_IS_UNSEEN_TEST = false`.

## Caveat

The current results are obtained on the constructed evaluation benchmark used during method development. A separately frozen unseen evaluation may replace this result if completed before submission.

## Replacement Policy

The current result is the paper-facing provisional final. A future result may supersede it only if all of the following hold:

1. Stage3 method is frozen before evaluation.
2. A new source-family unseen holdout is used.
3. Gold is frozen before predictions.
4. Sun and Ours use the same shared Stage3 pipeline.
5. No post-test tuning is performed.
6. Complete reproducibility artifacts are provided.

Replacement eligibility depends on methodological strength, not whether the new F1 is numerically higher. If a legitimate unseen final evaluation yields a lower Ours F1 than Sun, it must not be hidden; the current result may continue to be reported as a development benchmark result. If no `FINAL_UNSEEN_EVALUATION_COMPLETED` result exists and the advisor accepts the current evaluation design, this provisional Table 3 may become the submission Table 3 without changing the data values.

## Paper-Facing Material

### Recommended caption

Performance comparison on downstream compliance checking.

### Caption candidates

1. Performance comparison on downstream compliance checking.
2. Overall performance of downstream compliance checking.
3. Downstream compliance-checking performance on the current benchmark.

Do not use: `Final unseen test performance`.

### Results paragraph template

Table X reports the downstream compliance-checking performance of Sun and our method under the same checking pipeline. Our method achieves a precision of 0.4393, recall of 0.6812, and F1-score of 0.5341, compared with 0.3814, 0.5362, and 0.4458 for Sun, respectively. This corresponds to an absolute F1 improvement of 0.0883.

The improvement is mainly associated with better performance on missing-action and incorrect-actor cases, while the two methods obtain the same F1 on the evaluated out-of-order cases.

## Limitations

- The current results are obtained on the constructed evaluation benchmark used during method development.
- Final unseen benchmark/Gold packet is not constructed; only source-only candidate requirements remain.
- No Ours Stage-2 predictions exist for unseen candidate requirements; explicit API authorization is required.
- Ours Stage-2 A_r lacks a distinct process endpoint for R5-D-01/R5-D-02, so order recall is limited there.
- R5-S7-T1/R5-S8-T1 are source action-action relations but their second endpoints are absent from both frozen Stage-2 A_r records.
- Actor unknown remains material for Sun due to Definition 6 action-bound coverage; Definition 6 was intentionally not changed.
- Missing-action precision remains limited by extra/fragment Stage-2 actions; no second action-scope revision was applied.
- No formal significance test was performed; no p-value, confidence interval, or significance star is claimed.

## Integrity

- `REAL_API_CALLS = 0`
- `NETWORK_EXPERIMENT_CALLS = 0`
- No new threshold sweep, semantic backend, MPNet run, Stage2 extraction, order refinement, Gold, BPMN, holdout, API call, prompt, matcher, denominator, or actor rule was introduced by this freeze.
- No formal significance test was run; no p-value, confidence interval, or significance star is claimed.

## Canonical LaTeX (plain)

```latex
\begin{table}[t]
\centering
\caption{Performance comparison on downstream compliance checking.}
\label{tab:stage3}
\begin{tabular}{lccc}
\hline
Method & Precision & Recall & F1 \\
\hline
Sun et al. & 0.3814 & 0.5362 & 0.4458 \\
Ours        & 0.4393 & 0.6812 & 0.5341 \\
\hline
\end{tabular}
\end{table}
```

## Canonical LaTeX (booktabs)

```latex
\begin{table}[t]
\centering
\caption{Performance comparison on downstream compliance checking.}
\label{tab:stage3}
\begin{tabular}{lccc}
\toprule
Method & Precision & Recall & F1 \\
\midrule
Sun et al. & 0.3814 & 0.5362 & 0.4458 \\
Ours        & 0.4393 & 0.6812 & 0.5341 \\
\bottomrule
\end{tabular}
\end{table}
```
