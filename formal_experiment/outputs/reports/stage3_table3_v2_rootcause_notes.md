# Stage 3 Table 3 v2 repair notes

Status: experiment run complete; Ours superiority claim not supported.

## Verified root cause of the old F1=1 row

1. `outputs/development/stage3_ours_v1/automatic_grounding_predictions_v1.json` grounded each
   pair's rule actions against the pair CONTROL BPMN. Its `detector_activity_ids` were the
   union of all retained candidates. The 13 eligible pairs had candidate sets that covered
   the entire control in 10/13 cases (verified from the persisted grounding file and the
   Stage-1 control process records).
2. `scripts/run_stage3_ours_v1.py` then checked the CURRENT item BPMN only by asking whether a
   control candidate id was absent (`missing_action`) or whether that activity's lane changed
   relative to the control (`incorrect_actor`). This reproduces the synthetic structural
   mutation, not semantic matching between the regulation and the process.
3. The persisted `actor_predictions` were not used by `decide_item`. Actor decisions came from
   `activity_lane_map` copied from the control process, so an actor change could be detected
   without ever comparing the rule actor-action relation with the current process executor.
4. `scripts/run_stage3_predecessors_paired_v1.py` used the development rule extractor for Sun
   instead of the persisted B0/Sun Stage-2 capsule, and selected the arm output using
   `target_violation_type`. It is therefore not the same protocol as the repaired comparison.

## Retracted

- The old Ours F1=1.0 and any reading that Ours achieved semantic compliance detection or
  outperformed Sun/Winter on the paired panel.
- The old Table 3 Oracle row remains a supplied-binding diagnostic, not an automatic method
  and not Ours.

## Repaired comparison protocol

- Inference view: `data/development/stage3_synth/stage3_paired_benchmark_inference_view_v2.json`
  with only `item_id,pair_id,bpmn_path,rule_id,process_id`; no role, target type, mutation answer,
  control reference or gold field is passed to inference.
- Sun and Ours use the same `gdpr_capsule_converter` and one frozen `SunScorer` instance with
  the same `tau/gamma/theta` thresholds. They differ only in the persisted Stage-2 capsule.
- Winter uses the existing native wrapper, frozen config and corrected reachability mode.
- Every item records all three detector signals before the evaluator loads labels.
- Evaluation is target-check only: each eligible pair is a positive variant plus its control;
  non-target alarms are preserved but marked unevaluated.
- Unknown positives count as misses; unknown negatives are not counted as correct rejections.
- `out_of_order` is N/A because the frozen rule records contain no rule-side order relation.

## Repaired results (eligible target-check denominators)

| Method | missing P/R/F1 | actor P/R/F1 | order | macro-F1 | micro P/R/F1 | positive/negative | unknown + / - |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ours | 0.5000/1.0000/0.6667 | N/A/0.0000/0.0000 | N/A | 0.3333 | 0.5000/0.6154/0.5517 | 13/13 | 5/5 |
| Sun | 0.5000/1.0000/0.6667 | N/A/0.0000/0.0000 | N/A | 0.3333 | 0.5000/0.6154/0.5517 | 13/13 | 5/5 |
| Winter | 0.5000/1.0000/0.6667 | N/A/0.0000/0.0000 | N/A | 0.3333 | 0.5000/0.6154/0.5517 | 13/13 | 5/0 |

Counts:
- Ours: missing_action TP/FP/FN/TN=8/8/0/0; incorrect_actor TP/FP/FN/TN=0/0/5/0; out_of_order positive_count=0.
- Sun: missing_action TP/FP/FN/TN=8/8/0/0; incorrect_actor TP/FP/FN/TN=0/0/5/0; out_of_order positive_count=0.
- Winter: missing_action TP/FP/FN/TN=8/8/0/0; incorrect_actor TP/FP/FN/TN=0/0/5/5; out_of_order positive_count=0.

Independent evidence: 13 eligible pairs use 6 unique control BPMNs; 7 control items are repeats.

## Acceptance reading

The repaired run is a real, zero-API, label-separated experiment and the old F1=1 claim is
removed. It does not satisfy a positive acceptance criterion for Ours: Sun, Ours and Winter have
the same macro-F1 0.3333 and micro-F1 0.5517 on the supported target checks. Missing-action
precision is 0.5 because all controls are false-positive; incorrect-actor is unobservable under
the frozen SunScorer for Sun/Ours and is unknown for all five Winter positives because the
variant BPMN lacks resource labels under the native wrapper. Order remains N/A. Next work should be separately
pre-registered and must not tune this run: either a rule-action-to-activity grounded detector
declared as an extra arm with the added variable stated, or correct order-side annotations that
create a legitimate order denominator. Until then Table 3 is a completed repaired comparison,
not evidence that Ours wins.
