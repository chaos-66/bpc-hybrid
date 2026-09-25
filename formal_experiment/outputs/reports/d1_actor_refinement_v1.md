# D1 Actor-refinement development screening report

> One-factor-per-arm development screening. No combined arm and no promotion.

## A. Executive conclusion

- 600 primary calls completed: True; actual new calls in final invocation: 518; total accounted: 600.
- Fresh baseline successful record count: 150/150.

- R: Actor dP=0.0788, dR=0.0208, dF1=0.0703, dFP=-12, dFN=-1.
- P: Actor dP=0.1394, dR=-0.0208, dF1=0.1029, dFP=-21, dFN=1.
- C: Actor dP=-0.0328, dR=0.0208, dF1=-0.0246, dFP=9, dFN=-1.

Precision/Recall attribution and collateral effects are reported below; the report does not declare a final Prompt.

## B. Prompt integrity

| arm | Prompt SHA | changed sections | unexpected diff |
| --- | --- | --- | --- |
| B0 | 3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895 | fresh_unchanged_baseline | 0 |
| R | 57d42002060ff2909855bdb0eda1ec3c9af76933b6ebd5805d002fa9fe7626dd | actor_role_eligibility_only | 0 |
| P | 4ec0756bae791fdb0f013f80c93deeb6cfa3b14a0b2656ee89b16f76653f539f | unresolved_pronoun_policy_only | 0 |
| C | aac408ad9d1940eeee899d223cb51544afdc9d04de331b907d9a485e2e19792d | condition_actor_projection_only | 0 |

global unexpected_diff_count = 0

## C. Execution integrity

- model: deepseek-v4-pro
- provider: openai_compatible
- API config: temperature=0.0, top_p=1.0, max_tokens=4096, retry=0
- dataset: data\input\estg150_formal_inference_input_v2.json
- sample count per arm: 150
- planned calls: 600
- actual new calls: 518
- resumed completed: 82
- total accounted: 600
- repair policy: repair_v1
- evaluator: sun_literal_overlap_evaluation@2.0.0
- execution incident: exec-interruption-001 (KeyboardInterrupt during urllib response read after monitoring shell reset); resume policy: restart runner with --execute; completed raw rows are reused; the single in-flight sample may be resent

## D. Overall + six-field metrics

| arm | overall P | overall R | overall F1 | schema/legal rate | nonempty records |
| --- | --- | --- | --- | --- | --- |
| B0 | 0.8169 | 0.7564 | 0.7855 | 1.0000 | 149 |
| R | 0.8294 | 0.7554 | 0.7907 | 1.0000 | 149 |
| P | 0.8414 | 0.7450 | 0.7903 | 1.0000 | 149 |
| C | 0.8054 | 0.7564 | 0.7801 | 1.0000 | 148 |

Per field:

### B0

| field | Gold | Pred | matched_pred | matched_Gold | P | R | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| modality | 231 | 256 | 248 | 212 | 0.9688 | 0.9177 | 0.9426 |
| actor | 48 | 92 | 45 | 45 | 0.4891 | 0.9375 | 0.6429 |
| action | 247 | 231 | 211 | 213 | 0.9134 | 0.8623 | 0.8871 |
| condition | 214 | 142 | 127 | 149 | 0.8944 | 0.6963 | 0.7830 |
| constraint | 302 | 264 | 173 | 171 | 0.6553 | 0.5662 | 0.6075 |
| exception | 13 | 9 | 8 | 8 | 0.8889 | 0.6154 | 0.7273 |

### R

| field | Gold | Pred | matched_pred | matched_Gold | P | R | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| modality | 231 | 257 | 247 | 211 | 0.9611 | 0.9134 | 0.9366 |
| actor | 48 | 81 | 46 | 46 | 0.5679 | 0.9583 | 0.7132 |
| action | 247 | 234 | 212 | 215 | 0.9060 | 0.8704 | 0.8879 |
| condition | 214 | 140 | 126 | 147 | 0.9000 | 0.6869 | 0.7792 |
| constraint | 302 | 258 | 173 | 170 | 0.6705 | 0.5629 | 0.6120 |
| exception | 13 | 9 | 8 | 8 | 0.8889 | 0.6154 | 0.7273 |

### P

| field | Gold | Pred | matched_pred | matched_Gold | P | R | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| modality | 231 | 256 | 247 | 213 | 0.9648 | 0.9221 | 0.9430 |
| actor | 48 | 70 | 44 | 44 | 0.6286 | 0.9167 | 0.7458 |
| action | 247 | 230 | 211 | 214 | 0.9174 | 0.8664 | 0.8912 |
| condition | 214 | 141 | 127 | 149 | 0.9007 | 0.6963 | 0.7854 |
| constraint | 302 | 241 | 159 | 158 | 0.6598 | 0.5232 | 0.5836 |
| exception | 13 | 8 | 8 | 8 | 1.0000 | 0.6154 | 0.7619 |

### C

| field | Gold | Pred | matched_pred | matched_Gold | P | R | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| modality | 231 | 257 | 245 | 211 | 0.9533 | 0.9134 | 0.9329 |
| actor | 48 | 103 | 47 | 46 | 0.4563 | 0.9583 | 0.6182 |
| action | 247 | 233 | 212 | 214 | 0.9099 | 0.8664 | 0.8876 |
| condition | 214 | 141 | 127 | 150 | 0.9007 | 0.7009 | 0.7884 |
| constraint | 302 | 260 | 168 | 169 | 0.6462 | 0.5596 | 0.5998 |
| exception | 13 | 8 | 8 | 8 | 1.0000 | 0.6154 | 0.7619 |

## E. Actor comparison

| arm | Pred | matched pred | matched Gold | P | R | F1 | FP | FN |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 | 92 | 45 | 45 | 0.4891 | 0.9375 | 0.6429 | 47 | 3 |
| R | 81 | 46 | 46 | 0.5679 | 0.9583 | 0.7132 | 35 | 2 |
| P | 70 | 44 | 44 | 0.6286 | 0.9167 | 0.7458 | 26 | 4 |
| C | 103 | 47 | 46 | 0.4563 | 0.9583 | 0.6182 | 56 | 2 |

Deltas vs fresh B0:
| arm | dP | dR | dF1 | dFP | dFN |
| --- | --- | --- | --- | --- | --- |
| R | 0.0788 | 0.0208 | 0.0703 | -12 | -1 |
| P | 0.1394 | -0.0208 | 0.1029 | -21 | 1 |
| C | -0.0328 | 0.0208 | -0.0246 | 9 | -1 |

## F. Factor R attribution

- non-role FP: B0=36, R=25, delta=-11
- removed actors: 16 (beneficial FP removal=16, harmful TP removal=0)
- added actors: 5 (new TP=1, new FP=4)
- legal-role TP removed: 0
- actor FN delta: -1
- pronoun count B0=10, R=8

Changed actor cases:
| sample | text | span | change | gold overlap | base taxonomy |
| --- | --- | --- | --- | --- | --- |
| estg_000039 | The contributions | 201:218 | beneficial_FP_removal | False | FP-B_NON_ROLE_GRAMMATICAL_SUBJECT |
| estg_000044 | This | 0:4 | beneficial_FP_removal | False | FP-A_PRONOUN_DEMONSTRATIVE |
| estg_000130 | A transfer to tangible assets | 4:33 | beneficial_FP_removal | False | FP-B_NON_ROLE_GRAMMATICAL_SUBJECT |
| estg_000134 | Hidden reserves | 4:19 | beneficial_FP_removal | False | FP-B_NON_ROLE_GRAMMATICAL_SUBJECT |
| estg_000135 | The reserve (the tax-free amount) | 4:37 | beneficial_FP_removal | False | FP-B_NON_ROLE_GRAMMATICAL_SUBJECT |
| estg_000209 | Shares issued as a result of a capital increase | 0:47 | beneficial_FP_removal | False | FP-B_NON_ROLE_GRAMMATICAL_SUBJECT |
| estg_000218 | the notification obligation | 91:118 | beneficial_FP_removal | False | FP-B_NON_ROLE_GRAMMATICAL_SUBJECT |
| estg_000218 | Subsequent taxation of amounts tied up for eight years (Section 1(3)(a)) | 211:283 | beneficial_FP_removal | False | FP-B_NON_ROLE_GRAMMATICAL_SUBJECT |
| estg_000247 | expenses and outlays that are not deductible from the individual categories of income | 11:96 | beneficial_FP_removal | False | FP-B_NON_ROLE_GRAMMATICAL_SUBJECT |
| estg_000293 | The following income | 4:24 | beneficial_FP_removal | False | FP-B_NON_ROLE_GRAMMATICAL_SUBJECT |
| estg_000664 | taxation | 186:194 | beneficial_FP_removal | False | FP-B_NON_ROLE_GRAMMATICAL_SUBJECT |
| estg_000664 | the tax base | 274:286 | beneficial_FP_removal | False | FP-B_NON_ROLE_GRAMMATICAL_SUBJECT |
| estg_000664 | the tax | 290:297 | beneficial_FP_removal | False | FP-B_NON_ROLE_GRAMMATICAL_SUBJECT |
| estg_000800 | This | 0:4 | beneficial_FP_removal | False | FP-A_PRONOUN_DEMONSTRATIVE |
| estg_000800 | the following | 717:730 | beneficial_FP_removal | False | FP-B_NON_ROLE_GRAMMATICAL_SUBJECT |
| estg_000861 | the liquidation gain | 104:124 | beneficial_FP_removal | False | FP-B_NON_ROLE_GRAMMATICAL_SUBJECT |
| estg_000115 | the investment allowance | 60:84 | new_FP | False |  |
| estg_000131 | a transfer | 31:41 | new_FP | False |  |
| estg_000195 | the housing applicant | 35:56 | new_FP | False |  |
| estg_000417 | the person performing the activity | 22:56 | new_TP | True |  |
| estg_000861 | a taxpayer falling under Section 7(3) who has resolved to dissolve | 3:69 | new_FP | False |  |

## G. Factor P attribution

| arm | pronoun total | TP | FP | precision |
| --- | --- | --- | --- | --- |
| B0 | 10 | 1 | 9 | 0.1000 |
| P | 1 | 0 | 1 | 0.0000 |

- estg_000003 'It' disappeared: True
- non-pronoun actor symmetric difference: 15 (spillover flag=True)

## H. Factor C attribution

- condition-contained new actor predictions: 5
- TP additions: 1
- FP additions: 4
- projection precision: 0.2000

| sample | new actor | span | contained in B0 condition | gold overlap | classification |
| --- | --- | --- | --- | --- | --- |
| estg_000002 | Bookkeeping farmers and foresters | 0:33 | False | True | TP_addition |
| estg_000002 | registered traders | 38:56 | False | True | TP_addition |
| estg_000021 | employees in tobacco processing establishments | 49:95 | False | False | FP_addition |
| estg_000036 | he | 40:42 | False | False | FP_addition |
| estg_000095 | This depreciation | 0:17 | False | False | FP_addition |
| estg_000098 | Tax-free reserves | 4:21 | False | False | FP_addition |
| estg_000098 | tax-free amounts | 85:101 | True | False | FP_addition |
| estg_000109 | an investment allowance | 107:130 | False | False | FP_addition |
| estg_000131 | a transfer | 31:41 | False | False | FP_addition |
| estg_000143 | bearer partial debentures of domestic debtors with a nominal amount of at least 50% of the provision amount shown in the balance sheet at the end of the preceding financial year | 39:216 | False | False | FP_addition |
| estg_000195 | the housing applicant | 35:56 | True | False | FP_addition |
| estg_000285 | that rule | 152:161 | False | False | FP_addition |
| estg_000285 | The mileage allowance | 184:205 | False | False | FP_addition |
| estg_000417 | the person performing the activity | 22:56 | True | True | TP_addition |
| estg_000433 | the municipality | 7:23 | True | False | FP_addition |
| estg_000505 | such other emoluments | 73:94 | False | False | FP_addition |
| estg_000505 | a monthly wage payment period | 184:213 | False | False | FP_addition |
| estg_000659 | Persons with limited tax liability | 4:38 | False | False | FP_addition |
| estg_000861 | a taxpayer falling under Section 7(3) who has resolved to dissolve | 3:69 | True | False | FP_addition |

### estg_000206
- B0 actors: [{'sample_id': 'estg_000206', 'start': 602, 'end': 612, 'text_normalized': 'the spouse'}]
- C actors: [{'sample_id': 'estg_000206', 'start': 602, 'end': 612, 'text_normalized': 'the spouse'}]
- Gold actors: [{'id': 'c3_actor_1', 'text': 'the taxpayer', 'normalized': 'the taxpayer', 'start': 263, 'end': 275, 'coordinates': [263, 275]}, {'id': 'c3_actor_2', 'text': 'the spouse', 'normalized': 'the spouse', 'start': 602, 'end': 612, 'coordinates': [602, 612]}]
- recovered Gold: False; new FP: False

### estg_000417
- B0 actors: []
- C actors: [{'sample_id': 'estg_000417', 'start': 22, 'end': 56, 'text_normalized': 'the person performing the activity'}]
- Gold actors: [{'id': 'c1_actor_1', 'text': 'the person performing the activity', 'normalized': 'the person performing the activity', 'start': 22, 'end': 56, 'coordinates': [22, 56]}]
- recovered Gold: True; new FP: False

### estg_000776
- B0 actors: []
- C actors: []
- Gold actors: [{'id': 'c2_actor_1', 'text': 'the recipient', 'normalized': 'the recipient', 'start': 115, 'end': 128, 'coordinates': [115, 128]}]
- recovered Gold: False; new FP: False

## I. Other-field collateral effects

| field | B0 F1 | R delta | P delta | C delta |
| --- | --- | --- | --- | --- |
| modality | 0.9426 | -0.0059 | 0.0004 | -0.0096 |
| actor | 0.6429 | 0.0703 | 0.1029 | -0.0246 |
| action | 0.8871 | 0.0007 | 0.0040 | 0.0005 |
| condition | 0.7830 | -0.0038 | 0.0024 | 0.0054 |
| constraint | 0.6075 | 0.0045 | -0.0239 | -0.0077 |
| exception | 0.7273 | 0.0000 | 0.0346 | 0.0346 |
| overall | 0.7855 | 0.0052 | 0.0048 | -0.0054 |

## J. Gold-review sensitivity

| arm | raw evaluator FP | high-confidence semantic FP | Gold-review candidates |
| --- | --- | --- | --- |
| B0 | 47 | 45 | 2 |
| R | 35 | 32 | 3 |
| P | 26 | 23 | 3 |
| C | 56 | 50 | 6 |

No alternative F1 is produced; denominators are unchanged.

## K. Run-to-run context

Fresh B0 is the primary comparison. Historical runs are contextual only.

- historical repair_v1 D-full-0813: {'actor_metrics': {'ground_truth': 48, 'extracted': 86, 'matched_predictions': 46, 'matched_ground_truth': 45, 'misclassified': 40, 'missed': 3, 'precision': 0.5348837209302325, 'recall': 0.9375, 'f1': 0.6811451135241856}, 'tp_count': 46, 'fp_count': 40, 'fn_count': 3}
- historical legacy D-full-0813: {'actor_precision': 0.5487804878048781, 'actor_recall': 0.9166666666666666, 'actor_f1': 0.6865464632454924, 'actor_extracted': 82, 'actor_fp': 37}

## L. Safety / leakage audit

- gold_used_to_design_new_prompt_after_experiment_started: False
- iterative_prompt_search: False
- actor_lexicon_added: False
- benchmark_specific_whitelist_added: False
- benchmark_specific_blacklist_added: False
- rules_only_predictions_used_to_alter_direct_llm: False
- post_hoc_condition_to_actor_code_added: False
- combined_R_P_C_prompt_run: False
- formal_result_overwritten: False
- no_gold_in_prompt_construction: True
- no_gold_in_api_execution: True
- prompts_frozen_before_scores: True

## M. Recommended next step

- interaction experiment between supported factors

