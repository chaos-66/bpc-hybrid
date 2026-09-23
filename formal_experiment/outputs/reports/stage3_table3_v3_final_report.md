# Paper final repair: Stage 3 Sun-protocol realignment and Table 3 v3

This report is generated from the persisted v3 run, the separate evaluator, and the protocol-realignment audit. Zero API calls, zero network calls, zero Gold writes.

## A. Sun Protocol Alignment

- Stage 1: canonical BPMN -> Process Record parser is shared by Sun and Ours (`stage1_process.py`; `stage1_structural_s11_s14.json`).
- Rule Base entry: all nine GDPR rule records are converted with the same frozen converter from the two Stage-2 capsules.
- Definition 4 matching: full Rule Base ranking by action and actor/business-object highest-similarity fractions; `tau=0.8` frozen from Sun Table 9/11.
- Missing Action: Definition 5 over all rule actions after full matching.
- Incorrect Actor: Definition 6 over the actual rule actor-action relation; missing actor-action maps are unknown, never inferred.
- Out-of-order: Definition 7 requires a real rule-side `U_r`; the frozen rule records have zero order relations, so order is N/A, not zero-filled.
- Experiment construction: one-error mutation variants are used as the Sun §5.3.2 construction analogue; each eligible pair has one labeled target rule/type and a control built from the unmutated source BPMN.

## B. What Was Wrong Before

- v1 Ours F1=1.0 came from automatic grounding against the paired control BPMN plus target activity/lane difference detection. That consumed benchmark control/Gold information and is permanently retracted.
- v1 bound the Oracle/grounded upper bound as a separate diagnostic, not Ours.
- v2 repaired leakage but still fed the item `rule_id` (the target rule) and scored only that target check. It was therefore a target-pair diagnostic, not a full-rule-base Stage 3 pipeline.
- v2 and v1 are retained as diagnostic/superseded assets only; they are not the main Table 3.

## C. Final Benchmark

- Pair count: 30
- Unique control BPMNs: 6 (eligible controls: 6; eligible duplicate control items: 7).
- Total cases: 60 (30 controls + 30 variants).
- Full Rule Base size: 9 rules / 74 source sentences.
- Eligible pairs: 13 (missing_action=8, incorrect_actor=5, out_of_order=0).
- Out-of-order unavailable: 10; no rule record has a real order relation, so order Gold is not manufactured.
- Excluded pairs: 17. Reasons are recorded per pair in `outputs/reports/stage3_sun_style_benchmark_audit_v3.json`.
- Control compliance basis: the control is the unmutated source BPMN; mutation validation proves only the declared target changed; human binding reference confirms the target action/actor relation for eligible pairs. This is a scoped target-seed basis. A complete multi-label compliance Gold for all nine rules is not available.

## D. Matching Results

| Method | MAP | Binary P | Binary R | Binary F1 | Recall@3 | Recall@5 |
|---|---:|---:|---:|---:|---:|---:|
| Ours | 0.4159 | 0.0000 | 0.0000 | 0.0000 | 0.3000 | 0.6000 |
| Sun | 0.3877 | 0.3333 | 0.1000 | 0.1538 | 0.2000 | 0.4000 |
| Winter | 0.4343 | 0.4545 | 1.0000 | 0.6250 | 0.5000 | 0.7000 |

## E. Compliance Checking

Main table (target-seeded detection after full Rule Base matching; eligible pairs=13):

| Method | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ours | 0 | 0 | 13 | 13 | 0.0000 | 0.0000 | 0.0000 |
| Sun | 0 | 0 | 13 | 13 | 0.0000 | 0.0000 | 0.0000 |
| Winter | 8 | 8 | 5 | 5 | 0.5000 | 0.6154 | 0.5517 |

Diagnostic all-alarm view (incomplete multi-label Gold; do not publish as the complete Table 3):

| Method | Any-alarm P | Any-alarm R | Any-alarm F1 | Strict TP | Strict FP | Strict FN |
|---|---:|---:|---:|---:|---:|---:|
| Ours | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 13 |
| Sun | 0.5000 | 0.1538 | 0.2353 | 0 | 20 | 13 |
| Winter | 0.5000 | 1.0000 | 0.6667 | 8 | 229 | 5 |

## F. Secondary Per-type Results

| Method | Type | Positive | Negative | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|
| Ours | missing_action | 8 | 8 | 0.0000 | 0.0000 | 0.0000 |
| Ours | incorrect_actor | 5 | 5 | 0.0000 | 0.0000 | 0.0000 |
| Ours | out_of_order | 0 | 0 | N/A | N/A | N/A |
| Sun | missing_action | 8 | 8 | 0.0000 | 0.0000 | 0.0000 |
| Sun | incorrect_actor | 5 | 5 | 0.0000 | 0.0000 | 0.0000 |
| Sun | out_of_order | 0 | 0 | N/A | N/A | N/A |
| Winter | missing_action | 8 | 8 | 0.5000 | 1.0000 | 0.6667 |
| Winter | incorrect_actor | 5 | 5 | 0.0000 | 0.0000 | 0.0000 |
| Winter | out_of_order | 0 | 0 | N/A | N/A | N/A |

## G. Controlled Comparison Conclusion

Changing Stage 2 from Sun Rules-Only to Direct-LLM did not improve downstream design-time checking on the valid v3 benchmark. Both Sun and Ours failed to match the labeled target rules after full Rule Base matching and therefore produced no target-seeded true positives (F1=0.0000). Ours had slightly higher MAP (0.4159 vs 0.3877) but zero binary matching recall and no downstream detection. Winter, as an independent predecessor pipeline, reached F1=0.5517 on the target-seeded metric and F1=0.6667 on the diagnostic any-alarm metric, but did so with many control false alarms (8/13 controls in the target-seeded metric). No result-driven tuning or stronger backend was used.

## H. Tests

- `python formal_experiment/scripts/audit_project.py`: PASS, 0 errors, integrity_pass=True.
- `python -m pytest tests/test_stage3_table3_v2.py tests/test_stage3_paired_benchmark_v1.py tests/test_stage3_table3_v3.py -q`: 22 passed.
- `python -m pytest tests/test_stage3_table3_v3.py -q`: 7 passed.
- Full suite was not run because this task did not require full-suite authorization and focused checks cover the changed behavior.

## I. Git

Branch: `paper-final-repair`. Pipeline/analysis checkpoint commit: `9cbcdc0` (`S3-TABLE3-V3: restore Sun full-rule-base matching and target-seeded diagnostic`). Pushed to `origin/paper-final-repair` successfully before this final report Git note was added. The report-note commit is the follow-up scoped commit for this line.

## Acceptance gates

- G10_independent_test_bpmn: True
- G11_full_rule_base_matching: True
- G12_relevant_rules_only: True
- G13_control_compliance: true_for_scoped_target_seed
- G14_gold_read_after_persistence: True
- G15_threshold_not_tuned: True
- G1_method_level_reconstruction: True
- G2_shared_stage1: True
- G3_shared_stage3: True
- G4_only_stage2_varies: True
- G5_inference_no_rule_id: True
- G6_inference_no_target_activity: True
- G7_inference_no_mutation_type: True
- G8_inference_no_gold_type: True
- G9_inference_no_binding_gold: True
- complete_multi_label_gold_available: False
- complete_multi_label_main_table_publishable: False

The v3 main result is target-seeded: it answers whether the complete pipeline detects the independently constructed single mutation after doing its own full Rule Base matching. The complete multi-label Table 3 is not publishable from the current data because a complete control-vs-violation Gold for all nine rules does not exist.
