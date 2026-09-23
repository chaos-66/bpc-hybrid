# Stage 3 diagnostic: no-outer-gate counterfactual

- status: `diagnostic_complete`
- scope: 13-pair target-rule diagnostic and strict no-outer-gate counterfactual for Stage 3 Table 3 v3 Sun and Ours
- thresholds: tau=0.8, gamma=0.8, theta=0.8
- outer gate: `matching_score > tau (tau=0.8)`
- counterfactual change: Definition 4 matching rows are reused exactly as persisted by v3; the only change is that every matching row enters the unchanged Def5-7 block instead of only rows with matching_score > tau.

This is a diagnostic runner, not a formal method. It reuses the exact persisted v3 Definition 4 matching rows and changes only the gate into Definitions 5-7.

## A. Current v3 outer-gate summary (13 positive variants)

| Method | score>0.8 | score<=0.8 | rank1 | rank<=3 | rank<=5 | entered Def5-7 | blocked |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ours | 0 | 13 | 2 | 6 | 9 | 0 | 13 |
| Sun | 0 | 13 | 2 | 3 | 4 | 0 | 13 |

| Method | score min | median | mean | max | rank min | median | mean | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Ours | 0.0000 | 0.0000 | 0.0974 | 0.3333 | 1 | 4 | 3.62 | 6 |
| Sun | 0.0000 | 0.0000 | 0.0769 | 0.5000 | 1 | 6 | 4.85 | 6 |

## B. Strict no-outer-gate counterfactual

| Method | TP | FP | FN | TN | Precision | Recall | F1 | variant hits | control hits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Ours | 8 | 8 | 5 | 5 | 0.5000 | 0.6154 | 0.5517 | 8 | 8 |
| Sun | 8 | 8 | 5 | 5 | 0.5000 | 0.6154 | 0.5517 | 8 | 8 |

| Method | target type | variant emits | control emits | variant second-layer failure | control second-layer failure |
|---|---|---:|---:|---:|---:|
| Ours | incorrect_actor | 0 | 0 | 5 | 5 |
| Ours | missing_action | 8 | 8 | 0 | 0 |
| Sun | incorrect_actor | 0 | 0 | 5 | 5 |
| Sun | missing_action | 8 | 8 | 0 | 0 |

## C. Per-pair target-rule breakdown (current v3)

### Sun

| pair_id | case_id | process_id | type | rule_id | rank | score | action_ratio | actor_object_ratio | score>0.8 | entered Def5-7 | blocked_by_outer_gate |
|---|---|---|---|---|---:|---:|---:|---:|---|---|---|
| syn_incorrect_actor_01 | case_0002 | gdpr_1_data_breach | incorrect_actor | article33 | 6 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_incorrect_actor_02 | case_0004 | gdpr_1_data_breach | incorrect_actor | article33 | 6 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_incorrect_actor_04 | case_0008 | gdpr_2_consent_to_use_the_data | incorrect_actor | article22 | 6 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_incorrect_actor_05 | case_0010 | gdpr_3_right_to_access | incorrect_actor | article15 | 1 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_incorrect_actor_08 | case_0016 | gdpr_5_right_to_withdraw | incorrect_actor | article17 | 6 | 0.5000 | 0.0000 | 0.5000 | false | false | true |
| syn_missing_action_01 | case_0022 | gdpr_1_data_breach | missing_action | article33 | 6 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_missing_action_02 | case_0024 | gdpr_1_data_breach | missing_action | article33 | 6 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_missing_action_03 | case_0026 | gdpr_2_consent_to_use_the_data | missing_action | article22 | 6 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_missing_action_04 | case_0028 | gdpr_2_consent_to_use_the_data | missing_action | article22 | 6 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_missing_action_05 | case_0030 | gdpr_3_right_to_access | missing_action | article15 | 1 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_missing_action_06 | case_0032 | gdpr_5_right_to_withdraw | missing_action | article17 | 6 | 0.5000 | 0.0000 | 0.5000 | false | false | true |
| syn_missing_action_09 | case_0038 | gdpr_4_right_of_portability | missing_action | article20 | 4 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_missing_action_10 | case_0040 | gdpr_6_right_to_rectify | missing_action | article16 | 3 | 0.0000 | 0.0000 | 0.0000 | false | false | true |

### Ours

| pair_id | case_id | process_id | type | rule_id | rank | score | action_ratio | actor_object_ratio | score>0.8 | entered Def5-7 | blocked_by_outer_gate |
|---|---|---|---|---|---:|---:|---:|---:|---|---|---|
| syn_incorrect_actor_01 | case_0002 | gdpr_1_data_breach | incorrect_actor | article33 | 6 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_incorrect_actor_02 | case_0004 | gdpr_1_data_breach | incorrect_actor | article33 | 6 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_incorrect_actor_04 | case_0008 | gdpr_2_consent_to_use_the_data | incorrect_actor | article22 | 2 | 0.2000 | 0.2000 | 0.0000 | false | false | true |
| syn_incorrect_actor_05 | case_0010 | gdpr_3_right_to_access | incorrect_actor | article15 | 1 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_incorrect_actor_08 | case_0016 | gdpr_5_right_to_withdraw | incorrect_actor | article17 | 4 | 0.3333 | 0.0000 | 0.3333 | false | false | true |
| syn_missing_action_01 | case_0022 | gdpr_1_data_breach | missing_action | article33 | 6 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_missing_action_02 | case_0024 | gdpr_1_data_breach | missing_action | article33 | 6 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_missing_action_03 | case_0026 | gdpr_2_consent_to_use_the_data | missing_action | article22 | 2 | 0.2000 | 0.2000 | 0.0000 | false | false | true |
| syn_missing_action_04 | case_0028 | gdpr_2_consent_to_use_the_data | missing_action | article22 | 2 | 0.2000 | 0.2000 | 0.0000 | false | false | true |
| syn_missing_action_05 | case_0030 | gdpr_3_right_to_access | missing_action | article15 | 1 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_missing_action_06 | case_0032 | gdpr_5_right_to_withdraw | missing_action | article17 | 4 | 0.3333 | 0.0000 | 0.3333 | false | false | true |
| syn_missing_action_09 | case_0038 | gdpr_4_right_of_portability | missing_action | article20 | 4 | 0.0000 | 0.0000 | 0.0000 | false | false | true |
| syn_missing_action_10 | case_0040 | gdpr_6_right_to_rectify | missing_action | article16 | 3 | 0.0000 | 0.0000 | 0.0000 | false | false | true |

## D. Per-pair no-gate target signal

### Sun

| pair_id | role | target signal status | raw score | reason | emits target | second_layer_failure |
|---|---|---|---:|---|---|---|
| syn_incorrect_actor_01 | variant | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_01 | control | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_02 | variant | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_02 | control | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_04 | variant | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_04 | control | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_05 | variant | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_05 | control | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_08 | variant | unknown | None | incomplete_rule_actor_action_map | false | true |
| syn_incorrect_actor_08 | control | unknown | None | incomplete_rule_actor_action_map | false | true |
| syn_missing_action_01 | variant | violated | 1.0 | None | true | false |
| syn_missing_action_01 | control | violated | 1.0 | None | true | false |
| syn_missing_action_02 | variant | violated | 1.0 | None | true | false |
| syn_missing_action_02 | control | violated | 1.0 | None | true | false |
| syn_missing_action_03 | variant | violated | 1.0 | None | true | false |
| syn_missing_action_03 | control | violated | 1.0 | None | true | false |
| syn_missing_action_04 | variant | violated | 1.0 | None | true | false |
| syn_missing_action_04 | control | violated | 1.0 | None | true | false |
| syn_missing_action_05 | variant | violated | 1.0 | None | true | false |
| syn_missing_action_05 | control | violated | 1.0 | None | true | false |
| syn_missing_action_06 | variant | violated | 1.0 | None | true | false |
| syn_missing_action_06 | control | violated | 1.0 | None | true | false |
| syn_missing_action_09 | variant | violated | 1.0 | None | true | false |
| syn_missing_action_09 | control | violated | 1.0 | None | true | false |
| syn_missing_action_10 | variant | violated | 1.0 | None | true | false |
| syn_missing_action_10 | control | violated | 1.0 | None | true | false |

### Ours

| pair_id | role | target signal status | raw score | reason | emits target | second_layer_failure |
|---|---|---|---:|---|---|---|
| syn_incorrect_actor_01 | variant | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_01 | control | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_02 | variant | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_02 | control | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_04 | variant | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_04 | control | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_05 | variant | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_05 | control | unknown | None | action_mapping_below_gamma | false | true |
| syn_incorrect_actor_08 | variant | unknown | None | incomplete_rule_actor_action_map | false | true |
| syn_incorrect_actor_08 | control | unknown | None | incomplete_rule_actor_action_map | false | true |
| syn_missing_action_01 | variant | violated | 1.0 | None | true | false |
| syn_missing_action_01 | control | violated | 1.0 | None | true | false |
| syn_missing_action_02 | variant | violated | 1.0 | None | true | false |
| syn_missing_action_02 | control | violated | 1.0 | None | true | false |
| syn_missing_action_03 | variant | violated | 0.8 | None | true | false |
| syn_missing_action_03 | control | violated | 0.8 | None | true | false |
| syn_missing_action_04 | variant | violated | 0.8 | None | true | false |
| syn_missing_action_04 | control | violated | 0.8 | None | true | false |
| syn_missing_action_05 | variant | violated | 1.0 | None | true | false |
| syn_missing_action_05 | control | violated | 1.0 | None | true | false |
| syn_missing_action_06 | variant | violated | 1.0 | None | true | false |
| syn_missing_action_06 | control | violated | 1.0 | None | true | false |
| syn_missing_action_09 | variant | violated | 1.0 | None | true | false |
| syn_missing_action_09 | control | violated | 1.0 | None | true | false |
| syn_missing_action_10 | variant | violated | 1.0 | None | true | false |
| syn_missing_action_10 | control | violated | 1.0 | None | true | false |

## E. Target-rule-record digest

Full target-rule records are stored in the companion JSON report under `pair_breakdown[*].methods[*].target_rule_record`.

| pair_id | method | failed | actions | actors | actor-action pairs | order relations | actions preview |
|---|---|---:|---:|---:|---:|---:|---|
| syn_incorrect_actor_01 | Sun | false | 12 | 3 | 3 | 0 | notify the personal data breach to the supervisory authority competent in; , it shall be accompanied by reasons for the delay.; notify the controller without undue delay after becoming aware of a personal data breach. |
| syn_incorrect_actor_01 | Ours | false | 11 | 5 | 10 | 0 | notify the personal data breach to the supervisory authority competent in accordance with Article 55; be accompanied by reasons for the delay; notify the controller |
| syn_incorrect_actor_02 | Sun | false | 12 | 3 | 3 | 0 | notify the personal data breach to the supervisory authority competent in; , it shall be accompanied by reasons for the delay.; notify the controller without undue delay after becoming aware of a personal data breach. |
| syn_incorrect_actor_02 | Ours | false | 11 | 5 | 10 | 0 | notify the personal data breach to the supervisory authority competent in accordance with Article 55; be accompanied by reasons for the delay; notify the controller |
| syn_incorrect_actor_04 | Sun | false | 2 | 1 | 1 | 0 | have the right not to be subject to a decision based solely on automated; implement suitable measures to safeguard the data subject's rights and freedoms |
| syn_incorrect_actor_04 | Ours | false | 5 | 2 | 2 | 0 | have the right not to be subject to a decision; implement suitable measures to safeguard the data subject's rights and freedoms and legitimate interests; obtain human intervention on the part of the controller |
| syn_incorrect_actor_05 | Sun | false | 4 | 1 | 1 | 0 | have the right to obtain from the controller confirmation as to whether or not; have the right; have the right to be informed of the appropriate safeguards pursuant to Article |
| syn_incorrect_actor_05 | Ours | false | 15 | 3 | 25 | 0 | obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed; access to the personal data and the following information the purposes of the processing; access to the personal data and the categories of personal data concerned |
| syn_incorrect_actor_08 | Sun | false | 3 | 2 | 1 | 0 | have the right to obtain from the controller the erasure of personal data; have; take reasonable steps, including technical measures, to inform controllers which |
| syn_incorrect_actor_08 | Ours | false | 6 | 3 | 3 | 0 | obtain from the controller the erasure of personal data concerning him or her; erase personal data; withdraws consent |
| syn_missing_action_01 | Sun | false | 12 | 3 | 3 | 0 | notify the personal data breach to the supervisory authority competent in; , it shall be accompanied by reasons for the delay.; notify the controller without undue delay after becoming aware of a personal data breach. |
| syn_missing_action_01 | Ours | false | 11 | 5 | 10 | 0 | notify the personal data breach to the supervisory authority competent in accordance with Article 55; be accompanied by reasons for the delay; notify the controller |
| syn_missing_action_02 | Sun | false | 12 | 3 | 3 | 0 | notify the personal data breach to the supervisory authority competent in; , it shall be accompanied by reasons for the delay.; notify the controller without undue delay after becoming aware of a personal data breach. |
| syn_missing_action_02 | Ours | false | 11 | 5 | 10 | 0 | notify the personal data breach to the supervisory authority competent in accordance with Article 55; be accompanied by reasons for the delay; notify the controller |
| syn_missing_action_03 | Sun | false | 2 | 1 | 1 | 0 | have the right not to be subject to a decision based solely on automated; implement suitable measures to safeguard the data subject's rights and freedoms |
| syn_missing_action_03 | Ours | false | 5 | 2 | 2 | 0 | have the right not to be subject to a decision; implement suitable measures to safeguard the data subject's rights and freedoms and legitimate interests; obtain human intervention on the part of the controller |
| syn_missing_action_04 | Sun | false | 2 | 1 | 1 | 0 | have the right not to be subject to a decision based solely on automated; implement suitable measures to safeguard the data subject's rights and freedoms |
| syn_missing_action_04 | Ours | false | 5 | 2 | 2 | 0 | have the right not to be subject to a decision; implement suitable measures to safeguard the data subject's rights and freedoms and legitimate interests; obtain human intervention on the part of the controller |
| syn_missing_action_05 | Sun | false | 4 | 1 | 1 | 0 | have the right to obtain from the controller confirmation as to whether or not; have the right; have the right to be informed of the appropriate safeguards pursuant to Article |
| syn_missing_action_05 | Ours | false | 15 | 3 | 25 | 0 | obtain from the controller confirmation as to whether or not personal data concerning him or her are being processed; access to the personal data and the following information the purposes of the processing; access to the personal data and the categories of personal data concerned |
| syn_missing_action_06 | Sun | false | 3 | 2 | 1 | 0 | have the right to obtain from the controller the erasure of personal data; have; take reasonable steps, including technical measures, to inform controllers which |
| syn_missing_action_06 | Ours | false | 6 | 3 | 3 | 0 | obtain from the controller the erasure of personal data concerning him or her; erase personal data; withdraws consent |
| syn_missing_action_09 | Sun | false | 2 | 0 | 0 | 0 | have the right to have the personal data transmitted directly from one; be without prejudice to Article 17. |
| syn_missing_action_09 | Ours | false | 4 | 2 | 3 | 0 | receive the personal data concerning him or her, which he or she has provided to a controller, in a structured, commonly used and machine-readable format; transmit those data to another controller without hindrance from the controller to which the personal data have been provided; have the right to have the personal data transmitted directly from one controller to another |
| syn_missing_action_10 | Sun | false | 1 | 0 | 0 | 0 | have the right to obtain from the controller without undue delay the |
| syn_missing_action_10 | Ours | false | 2 | 2 | 2 | 0 | obtain from the controller without undue delay the rectification of inaccurate personal data concerning him or her; have the right to have incomplete personal data completed |

## F. Inputs and boundary

- v3 predictions SHA256: `eecdb1234f91d1793a6f6ab69f4647a35ec59f3349d3178edee20b431c92d072`
- case map SHA256: `052f1e802e2e9dd59f66ee28bb97939e56f2c2ab9916e7d68c026f01382b4eb8`
- target rule id policy: The target rule id is read from the evaluator-only case map after v3 predictions exist; it is used only for this diagnostic and is not fed into Definition 4 or formal inference.
- formal v3 checker, runner, evaluator and outputs were not modified.
