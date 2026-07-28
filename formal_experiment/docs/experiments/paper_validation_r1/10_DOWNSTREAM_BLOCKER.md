# Phase 10 — Final Violation Detection Blocker

**Status**: BLOCKED. The project does not have a Stage 3 final-violation evaluator, a Stage 3 Gold, or a stable Stage 1 → Stage 2 → Stage 3 interface. We do not run a final-violation evaluation in this experiment.

## 1. Audit against task §13 criteria

| # | Criterion                                                                     | Status                                                                                            |
|---|-------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| 1 | Adjudicated Gold for `missing_action` / `incorrect_actor` / `out_of_order`     | **NOT FOUND** in any directory under the project root. No `*_violation*.json` or equivalent.       |
| 2 | Complete Stage 1 output for the 150 records                                    | **NOT PRODUCED** in this experiment. Stage 1 (the canonical s1 pipeline) was not invoked.         |
| 3 | Stable Stage 2 → Stage 3 interface                                            | **NOT FOUND** in the project. There is `s2_10_evaluator` and `stage2_canonical`, but no Stage 3.  |
| 4 | Stage 3 actually uses six fields                                              | **N/A** — there is no Stage 3.                                                                    |
| 5 | Method-independent Stage 3 evaluator                                          | **NOT FOUND**.                                                                                     |
| 6 | Three Stage 2 methods (D1 / H1-selective / H1-empty) can run under fixed Stage 1 + fixed Stage 3 | **NOT POSSIBLE** — Stage 1 and Stage 3 are not implemented.                                         |
| 7 | Final violation can be traced back to record_id                                | **N/A** — no Stage 3 to trace.                                                                    |

## 2. Hard-rule check (per task §13)

- We do not fabricate a final-violation Gold.
- We do not use the modality output as a substitute for final-violation output.
- We do not run any `Fixed Stage 1 + Different Stage 2 + Fixed Stage 3` experiment because the prerequisites are not met.

## 3. What is in the project (for context)

- `formal_experiment/src/bpc_hybrid/stage1_evaluation.py` and related Stage 1 code: structural / annotation / label-semantics layers exist for a different domain (complex legal). The Stage 1 *output* in the required form (six-field spans aligned to clauses) is not present in the EStG-150 project.
- `formal_experiment/src/bpc_hybrid/stage2_evaluation_v3.py`: the v3 evaluator takes Stage 2 outputs (clauses + char spans) and computes per-field metrics. It is **Stage 2** only.
- No Stage 3 code path in the project tree.

## 4. What would unblock the final-violation evaluation

1. An adjudicated final-violation Gold for at least one violation type (e.g., `missing_action`) for the 150-record EStG-150 set.
2. A Stage 3 method that takes the three method's Stage 2 outputs and produces a record-level violation set.
3. A method-independent Stage 3 evaluator (similar to the Stage 2 v3 evaluator).
4. A Stage 1 output that is the same across the three Stage 2 methods (i.e., a fixed Stage 1 source).

Each of these is significant work. The current experiment's role is to record the blocker honestly, not to build any of them.

## 5. Disposition

Phase 10 produces this blocker file. The modality-only results from Phase 5 stand. The final-violation results are explicitly **not claimed** in the synthesis or the final report.
