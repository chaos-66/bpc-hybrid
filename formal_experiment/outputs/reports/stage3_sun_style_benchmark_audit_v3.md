# Stage 3 v3 blinded benchmark and control audit

- source mutation panel: `data/development/stage3_synth/synthetic_controlled_error_extension_v1.json`
- pairs: 30
- eligible pairs: 13
- eligible missing-action: 8
- eligible incorrect-actor: 5
- eligible out-of-order: 0
- out-of-order unavailable: 10
- unique control BPMNs: 6

## Scope

single-mutation target seeds; full-rule-base matching is run, but checking metrics are scoped to the labeled target rule/type and the matching stage is evaluated separately with AP/MAP

## Control compliance

- target-seed evidence: unmutated source BPMN; mutation manifest verifies source_bytes_untouched and non-target-unchanged; human binding reference confirms the target action/actor relation for eligible pairs
- full multi-label Gold: **not available**
- full-rule-base control compliance established: **no**

## Pair audit

| Pair | Type | Eligible | Reason |
|---|---|---|---|
| syn_incorrect_actor_01 | incorrect_actor | yes | eligible |
| syn_incorrect_actor_02 | incorrect_actor | yes | eligible |
| syn_incorrect_actor_03 | incorrect_actor | no | action_binding_not_human_complete |
| syn_incorrect_actor_04 | incorrect_actor | yes | eligible |
| syn_incorrect_actor_05 | incorrect_actor | yes | eligible |
| syn_incorrect_actor_06 | incorrect_actor | no | actor_or_lane_binding_not_human_complete |
| syn_incorrect_actor_07 | incorrect_actor | no | actor_or_lane_binding_not_human_complete |
| syn_incorrect_actor_08 | incorrect_actor | yes | eligible |
| syn_incorrect_actor_09 | incorrect_actor | no | action_binding_not_human_complete |
| syn_incorrect_actor_10 | incorrect_actor | no | actor_or_lane_binding_not_human_complete |
| syn_missing_action_01 | missing_action | yes | eligible |
| syn_missing_action_02 | missing_action | yes | eligible |
| syn_missing_action_03 | missing_action | yes | eligible |
| syn_missing_action_04 | missing_action | yes | eligible |
| syn_missing_action_05 | missing_action | yes | eligible |
| syn_missing_action_06 | missing_action | yes | eligible |
| syn_missing_action_07 | missing_action | no | action_binding_not_human_complete |
| syn_missing_action_08 | missing_action | no | action_binding_not_human_complete |
| syn_missing_action_09 | missing_action | yes | eligible |
| syn_missing_action_10 | missing_action | yes | eligible |
| syn_out_of_order_01 | out_of_order | no | ineligible_no_explicit_rule_order |
| syn_out_of_order_02 | out_of_order | no | ineligible_no_explicit_rule_order |
| syn_out_of_order_03 | out_of_order | no | action_binding_not_human_complete;ineligible_no_explicit_rule_order |
| syn_out_of_order_04 | out_of_order | no | ineligible_no_explicit_rule_order |
| syn_out_of_order_05 | out_of_order | no | ineligible_no_explicit_rule_order |
| syn_out_of_order_06 | out_of_order | no | ineligible_no_explicit_rule_order |
| syn_out_of_order_07 | out_of_order | no | ineligible_no_explicit_rule_order |
| syn_out_of_order_08 | out_of_order | no | ineligible_no_explicit_rule_order |
| syn_out_of_order_09 | out_of_order | no | ineligible_no_explicit_rule_order |
| syn_out_of_order_10 | out_of_order | no | ineligible_no_explicit_rule_order |

## Inference-view guarantee

The v3 inference view contains only `case_id`, `bpmn_path`, and `process_id`.
It contains no pair role, rule id, target type, mutation type, target activity, or Gold label.
