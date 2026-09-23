# Stage 3 Table 3 v2 (repaired controlled comparison)

- benchmark: `stage3_paired_benchmark_v1`
- aggregation: target-check metrics on the pre-frozen eligible pairs; non-target alarms are retained as unevaluated
- eligible pairs: 13
- unique control BPMNs: 6
- duplicate control items: 7

| Method | Type | Positive | Negative | TP | FP | FN | TN | Unknown + | Unknown - | P | R | F1 | Coverage | Variant detected | Control FP | Pair both-correct |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Sun (Rules-Only Stage 2 + frozen Sun Stage 3) | missing_action | 8 | 8 | 8 | 8 | 0 | 0 | 0 | 0 | 0.5000 | 1.0000 | 0.6667 | 1.0000 | 8/8 | 8/8 | 0/8 |
| Sun (Rules-Only Stage 2 + frozen Sun Stage 3) | incorrect_actor | 5 | 5 | 0 | 0 | 5 | 0 | 5 | 5 | N/A | 0.0000 | 0.0000 | 0.0000 | 0/5 | 0/5 | 0/5 |
| Sun (Rules-Only Stage 2 + frozen Sun Stage 3) | out_of_order | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | N/A | N/A | N/A | N/A | 0/0 | 0/0 | 0/0 |
| Sun (Rules-Only Stage 2 + frozen Sun Stage 3) | **macro** |  |  |  |  |  |  |  |  |  |  | 0.3333 |  |  |  |  |
| Sun (Rules-Only Stage 2 + frozen Sun Stage 3) | **micro** | 13 | 13 | 8 | 8 | 5 |  | 5 | 5 | 0.5000 | 0.6154 | 0.5517 |  |  |  |  |
| Ours (Direct-LLM Stage 2 + frozen Sun Stage 3) | missing_action | 8 | 8 | 8 | 8 | 0 | 0 | 0 | 0 | 0.5000 | 1.0000 | 0.6667 | 1.0000 | 8/8 | 8/8 | 0/8 |
| Ours (Direct-LLM Stage 2 + frozen Sun Stage 3) | incorrect_actor | 5 | 5 | 0 | 0 | 5 | 0 | 5 | 5 | N/A | 0.0000 | 0.0000 | 0.0000 | 0/5 | 0/5 | 0/5 |
| Ours (Direct-LLM Stage 2 + frozen Sun Stage 3) | out_of_order | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | N/A | N/A | N/A | N/A | 0/0 | 0/0 | 0/0 |
| Ours (Direct-LLM Stage 2 + frozen Sun Stage 3) | **macro** |  |  |  |  |  |  |  |  |  |  | 0.3333 |  |  |  |  |
| Ours (Direct-LLM Stage 2 + frozen Sun Stage 3) | **micro** | 13 | 13 | 8 | 8 | 5 |  | 5 | 5 | 0.5000 | 0.6154 | 0.5517 |  |  |  |  |
| Winter (native wrapper, frozen config) | missing_action | 8 | 8 | 8 | 8 | 0 | 0 | 0 | 0 | 0.5000 | 1.0000 | 0.6667 | 1.0000 | 8/8 | 8/8 | 0/8 |
| Winter (native wrapper, frozen config) | incorrect_actor | 5 | 5 | 0 | 0 | 5 | 5 | 5 | 0 | N/A | 0.0000 | 0.0000 | 0.5000 | 0/5 | 0/5 | 0/5 |
| Winter (native wrapper, frozen config) | out_of_order | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | N/A | N/A | N/A | N/A | 0/0 | 0/0 | 0/0 |
| Winter (native wrapper, frozen config) | **macro** |  |  |  |  |  |  |  |  |  |  | 0.3333 |  |  |  |  |
| Winter (native wrapper, frozen config) | **micro** | 13 | 13 | 8 | 8 | 5 |  | 5 | 0 | 0.5000 | 0.6154 | 0.5517 |  |  |  |  |

`out_of_order` is N/A because the frozen rule records provide no rule-side order relation; it is not zero-filled.
`unknown` positives count as misses; `unknown` negatives are not counted as correct rejections.
Non-target alarms are retained in the per-item prediction evidence but marked unevaluated; the paired benchmark labels only the named target check.

## Error analysis

Per-item outcomes are in `outputs/reports/stage3_table3_v2_error_analysis.json` (180 rows). Rows no longer use `target_violation_type` to select a detector output; the evaluator joins labels only after prediction persistence. The old automatic-grounding Ours row is not used here: it consumed the paired control as reference and detected control-to-current structural changes. The repaired main comparison above uses only the current BPMN and the frozen, method-specific Stage-2 rule records.
