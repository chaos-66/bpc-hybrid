# Grounded Stage 3 checker on the paired benchmark

Method id: `grounded_structural_checker_v1` - 60 items - 0 LLM calls - scope `dev_only_benchmark_not_human_gold`.

## Per-type results

| Violation type | Precision | Recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| missing_action | 1.0000 | 1.0000 | 1.0000 | 10 | 0 | 0 |
| incorrect_actor | 1.0000 | 1.0000 | 1.0000 | 10 | 0 | 0 |
| out_of_order | 1.0000 | 1.0000 | 1.0000 | 10 | 0 | 0 |

## Aggregate

- Macro-F1 (three types): **1.0000**
- Micro-F1 (60 items): **1.0000** (P 1.0000 / R 1.0000)
- Compliant specificity: **1.0000** (30/30 controls correct)
- Compliant false-positive rate: 0.0000
- Variant exact-type accuracy: 1.0000 (30/30)
- Unobservable: 0

## Sanity verdict

**PASS.** A correctly grounded checker reaches a perfect score, so the benchmark is measurable and its Ground Truth is internally consistent. Predecessor arms that score degenerate values on the same items are therefore failing at grounding, not at the benchmark.
