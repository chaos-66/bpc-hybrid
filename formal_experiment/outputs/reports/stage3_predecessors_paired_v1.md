# Predecessor arms on the paired compliance benchmark

Benchmark: `stage3_paired_benchmark_v1` - 60 items - 0 LLM calls.

## Per-type F1

| Arm | missing_action | incorrect_actor | out_of_order | Macro-F1 | Micro-F1 | Compliant specificity | Exact type | Unobservable |
|---|---|---|---|---|---|---|---|---|
| sun_reconstruction | 0.6667 | 0.2857 | 0.0000 | 0.3175 | 0.3871 | 0.3333 | 12/30 | 16 |
| winter_wrapper | 0.6667 | 0.0000 | 0.0000 | 0.2222 | 0.3846 | 0.6000 | 10/30 | 0 |
| grounded_structural_checker_v1 (reference) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 30/30 | 0 |

## Honest reading

A healthy benchmark must let a correctly grounded method score well (the reference row above does). The predecessor rows show what the SAME items look like when the rule-to-process binding is re-derived by embedding similarity instead of consumed; the gap is a grounding effect, not evidence that the predecessors' algorithms are weak.

`Unobservable` counts items where the arm's own precondition failed; those are counted as misses and never zero-filled.
