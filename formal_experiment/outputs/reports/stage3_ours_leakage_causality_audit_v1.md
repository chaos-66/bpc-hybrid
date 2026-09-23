# Stage 3 Ours leakage / causality audit v1

**Status: PASS**

Ours inference does not read Gold, target_activity_id, mutation type, expected lane, binding reference or the benchmark grounding block. The automatic-grounding predictions are persisted before evaluation; the evaluator reads Gold only after persistence; and injecting forbidden fields into a temporary inference view leaves grounding rows and predictions unchanged.

## A. Ours inference input field whitelist

- formal inference view: `data/development/stage3_synth/stage3_paired_benchmark_inference_view_v1.json`
- allowed item keys: `["bpmn_path", "item_id", "pair_id", "process_id", "role", "rule_id"]`
- whitelist declared and observed: `True`
- view source benchmark hash matches current full benchmark: `True`
- serialized view safety metadata: `{"binding_gold_present": false, "gold_labels_present": false, "mutation_answers_present": false}`

The view contains only the six allowed item keys. The automatic grounding package further projects items through the same allow-list before use.

## B. Forbidden fields explicitly checked

| Forbidden field | In serialized view item keys | In Ours predictions | In grounding predictions |
|---|---:|---:|---:|
| `expected_violation_type` | False | False | False |
| `gold_label` | False | False | False |
| `gold_violation_type` | False | False | False |
| `target_violation_type` | False | False | False |
| `target_activity_id` | False | False | False |
| `expected_lane_id` | False | False | False |
| `binding_gold` | False | False | False |
| `mutation_answer` | False | False | False |
| `mutation_type` | False | False | False |
| `oracle_mapping` | False | False | False |
| `grounding` | False | False | False |
| `structural_observation` | False | False | False |
| `bpmn_sha256` | False | False | False |

Static inference-path matches are listed below; all are in forbidden field declarations, removal lists, comments or safety metadata, not in `.get(...)` reads:

- `scripts/build_stage3_inference_view_v1.py`: 9 textual matches
  - line 5: `Mutation manifests, grounding blocks, target ids, expected lanes, order pairs`
  - line 40: `"grounding", "target_violation_type", "gold_violation_type",`
  - line 40: `"grounding", "target_violation_type", "gold_violation_type",`
  - line 40: `"grounding", "target_violation_type", "gold_violation_type",`
  - line 41: `"structural_observation", "bpmn_sha256",`
  - ... 4 more
- `src/bpc_hybrid/stage3_grounding/automatic_rule_process_grounding_v1.py`: 16 textual matches
  - line 2: `"""Automatic rule-to-process grounding for the Stage 3 paired benchmark.`
  - line 10: `reference process.  It never reads the benchmark grounding block, target`
  - line 26: `from bpc_hybrid.s3_semantic_grounding_v1 import (`
  - line 44: `SCHEMA_VERSION = "stage3_automatic_grounding_predictions@1.0.0"`
  - line 45: `METHOD_ID = "automatic_rule_process_grounding_v1"`
  - ... 11 more
- `scripts/run_stage3_ours_v1.py`: 32 textual matches
  - line 2: `"""Run Stage-3 Ours: automatic grounding followed by the compliance detector.`
  - line 6: `2. build automatic grounding predictions on each pair's reference/control BPMN;`
  - line 10: `The detector consumes the persisted grounding predictions and the item BPMN.`
  - line 11: `It never reads mutation answers (`grounding`, `target_activity_id`,`
  - line 11: `It never reads mutation answers (`grounding`, `target_activity_id`,`
  - ... 27 more

### Taint replay

- status: `pass`
- forbidden sentinel fields injected: `["expected_violation_type", "gold_label", "gold_violation_type", "target_violation_type", "target_activity_id", "expected_lane_id", "binding_gold", "mutation_answer", "mutation_type", "oracle_mapping", "grounding", "structural_observation", "bpmn_sha256"]`
- grounding rows identical: `True`
- predictions semantically identical: `True`

The temporary tainted view is deleted after the comparison.

## C. Per-eligible-pair causal evidence

| Pair | Type | Target activity | Automatic grounding | Detector-consumed binding | Final prediction | Gold | Correct |
|---|---|---|---|---|---|---|---:|
| `syn_incorrect_actor_01` | incorrect_actor | `sid-20C5FDD3-8014-432D-8595-CD780D866E38` "Retrieve breached subjects" | top1_target_hit=False; candidate_target_hit=True; candidate_count=6 | target_in_binding=True; expected_lane=sid-4035AA0F-2D62-46AC-A369-4151026920A3; control_lane=sid-4035AA0F-2D62-46AC-A369-4151026920A3; variant_lane=syn_lane_sid-20C5FDD3-8014-432D-8595-CD780D866E38_0D866E38 | `incorrect_actor` | `incorrect_actor` | True |
| `syn_incorrect_actor_02` | incorrect_actor | `sid-28448355-C13E-462C-8D66-8CEB2F6B557C` "Handle delay" | top1_target_hit=True; candidate_target_hit=True; candidate_count=6 | target_in_binding=True; expected_lane=sid-4035AA0F-2D62-46AC-A369-4151026920A3; control_lane=sid-4035AA0F-2D62-46AC-A369-4151026920A3; variant_lane=syn_lane_sid-28448355-C13E-462C-8D66-8CEB2F6B557C_2F6B557C | `incorrect_actor` | `incorrect_actor` | True |
| `syn_incorrect_actor_04` | incorrect_actor | `sid-2147FDF3-2F2C-4874-B263-CFE22F8D7F6F` "Add "existence of the right to withdraw"" | top1_target_hit=False; candidate_target_hit=True; candidate_count=19 | target_in_binding=True; expected_lane=sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB; control_lane=sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB; variant_lane=syn_lane_sid-2147FDF3-2F2C-4874-B263-CFE22F8D7F6F_2F8D7F6F | `incorrect_actor` | `incorrect_actor` | True |
| `syn_incorrect_actor_05` | incorrect_actor | `sid-7CABF962-BFAE-4BFD-9C33-E7ED63548824` "Retrieve elaborations" | top1_target_hit=False; candidate_target_hit=True; candidate_count=3 | target_in_binding=True; expected_lane=sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F; control_lane=sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F; variant_lane=syn_lane_sid-7CABF962-BFAE-4BFD-9C33-E7ED63548824_63548824 | `incorrect_actor` | `incorrect_actor` | True |
| `syn_incorrect_actor_08` | incorrect_actor | `sid-1A48D305-CB15-4C57-A988-B39ED62DE531` "Stop using withdrawn data" | top1_target_hit=True; candidate_target_hit=True; candidate_count=5 | target_in_binding=True; expected_lane=sid-DCB3F2D9-6A70-4CA7-90B8-63D710F86A7C; control_lane=sid-DCB3F2D9-6A70-4CA7-90B8-63D710F86A7C; variant_lane=syn_lane_sid-1A48D305-CB15-4C57-A988-B39ED62DE531_D62DE531 | `incorrect_actor` | `incorrect_actor` | True |
| `syn_missing_action_01` | missing_action | `sid-20C5FDD3-8014-432D-8595-CD780D866E38` "Retrieve breached subjects" | top1_target_hit=False; candidate_target_hit=True; candidate_count=6 | target_in_binding=True; expected_lane=sid-4035AA0F-2D62-46AC-A369-4151026920A3; control_lane=sid-4035AA0F-2D62-46AC-A369-4151026920A3; variant_lane=None | `missing_action` | `missing_action` | True |
| `syn_missing_action_02` | missing_action | `sid-CD9ABA3B-996B-4F9A-A701-7F4C125A91F0` "Retrieve breached data" | top1_target_hit=True; candidate_target_hit=True; candidate_count=6 | target_in_binding=True; expected_lane=sid-4035AA0F-2D62-46AC-A369-4151026920A3; control_lane=sid-4035AA0F-2D62-46AC-A369-4151026920A3; variant_lane=None | `missing_action` | `missing_action` | True |
| `syn_missing_action_03` | missing_action | `sid-2147FDF3-2F2C-4874-B263-CFE22F8D7F6F` "Add "existence of the right to withdraw"" | top1_target_hit=False; candidate_target_hit=True; candidate_count=19 | target_in_binding=True; expected_lane=sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB; control_lane=sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB; variant_lane=None | `missing_action` | `missing_action` | True |
| `syn_missing_action_04` | missing_action | `sid-2CFD3957-D6FB-4CA6-95B4-86EEC4B4B4B8` "Add "existence of the right to rectify of personal data"" | top1_target_hit=False; candidate_target_hit=True; candidate_count=19 | target_in_binding=True; expected_lane=sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB; control_lane=sid-1EFFB55B-1F5D-4446-A232-417CC5AE81BB; variant_lane=None | `missing_action` | `missing_action` | True |
| `syn_missing_action_05` | missing_action | `sid-BB84BABD-20ED-4C97-B755-BDA101C57A8D` "Communicate data and elaborations" | top1_target_hit=False; candidate_target_hit=True; candidate_count=3 | target_in_binding=True; expected_lane=sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F; control_lane=sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F; variant_lane=None | `missing_action` | `missing_action` | True |
| `syn_missing_action_06` | missing_action | `sid-07817A82-69C2-45A1-9ABC-277F17D93747` "Stop running BPs using withdrawn data" | top1_target_hit=True; candidate_target_hit=True; candidate_count=5 | target_in_binding=True; expected_lane=sid-DCB3F2D9-6A70-4CA7-90B8-63D710F86A7C; control_lane=sid-DCB3F2D9-6A70-4CA7-90B8-63D710F86A7C; variant_lane=None | `missing_action` | `missing_action` | True |
| `syn_missing_action_09` | missing_action | `sid-BB84BABD-20ED-4C97-B755-BDA101C57A8D` "Communicate data and elaborations" | top1_target_hit=False; candidate_target_hit=True; candidate_count=3 | target_in_binding=True; expected_lane=sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F; control_lane=sid-4B676321-4DD2-470E-9CBE-51E1ECB93A5F; variant_lane=None | `missing_action` | `missing_action` | True |
| `syn_missing_action_10` | missing_action | `sid-2D1BF282-F735-4BE0-996F-4D9C7DBED814` "Rectify data" | top1_target_hit=True; candidate_target_hit=True; candidate_count=2 | target_in_binding=True; expected_lane=sid-95D07626-A357-422E-830F-B1E57917DB74; control_lane=sid-95D07626-A357-422E-830F-B1E57917DB74; variant_lane=None | `missing_action` | `missing_action` | True |

The `Gold` column is populated only here, after the frozen prediction files were persisted; it is not an inference input.

## Evaluator consumption checks

- `grounding_persisted_before_automatic_eval`: `True`
- `grounding_persisted_before_ours_eval`: `True`
- `automatic_eval_gold_read_after_prediction`: `True`
- `automatic_eval_binding_reference_read_after_prediction`: `True`
- `ours_eval_has_gold_rows`: `True`
- `table3_has_ours_and_oracle_separate`: `True`

## Final pass criteria

- `inference_view_whitelist_ok`: `True`
- `forbidden_fields_absent_from_view`: `True`
- `grounding_safety_flags`: `True`
- `run_manifest_declares_gold_blind`: `True`
- `predictions_clean_of_forbidden_keys`: `True`
- `evaluator_reads_after_persistence`: `True`
- `taint_replay_grounding_and_predictions_unchanged`: `True`

**Overall audit result: PASS**

