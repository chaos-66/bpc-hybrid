# Actor semantic error audit v1

> Read-only development audit. No new API calls, no Prompt changes, no Gold changes, no prediction changes, no actor rule changes.

## Actor metrics

| field | value |
|---|---:|
| ground_truth | 48 |
| extracted | 86 |
| matched_predictions | 46 |
| matched_ground_truth | 45 |
| precision | 0.5349 |
| recall | 0.9375 |
| f1 | 0.6811 |
| tp_count (prediction side) | 46 |
| fp_count | 40 |
| fn_count | 3 |

## FN taxonomy

| taxonomy | count | share | sample IDs |
|---|---:|---:|---|
| FN-B_EMBEDDED_IN_CONDITION | 3 | 1.0000 | estg_000206, estg_000417, estg_000776 |

## Cross-field projection

- cross_field_presence_rate: 1.0000
- embedded in condition: 3
- embedded in constraint: 0
- embedded in action: 0
- embedded in exception: 0

## FP taxonomy

| taxonomy | count | share | representative examples |
|---|---:|---:|---|
| FP-A_PRONOUN_DEMONSTRATIVE | 9 | 0.2250 | This; it; they; this |
| FP-B_NON_ROLE_GRAMMATICAL_SUBJECT | 28 | 0.7000 | A change of the fiscal year to a different closing date; A transfer to tangible assets; Certain income, in particular foreign income; Item 13; Section 10(2) last sentence; Shares issued as a result of a capital increase |
| FP-C_LEGAL_NORMATIVE_ROLE_BUT_GOLD_UNANNOTATED | 3 | 0.0750 | Persons with limited tax liability; the building society; the insured person |

## Pronoun analysis

- total: 10
- prompt-pronoun total: 10
- prompt-pronoun TP: 1
- prompt-pronoun FP: 9
- precision: 0.1000
- surface distribution: {'It': 1, 'This': 3, 'it': 4, 'they': 1, 'this': 1}

## Prompt rule → observed evidence

| rule | evidence | strength | potential issue |
|---|---|---|---|
| actor_definition_rule_10 | {"prompt_pronoun_total": 10, "prompt_pronoun_tp": 1, "prompt_pronoun_fp": 9, "non_role_fp": 28} | directly_consistent_with_pronoun_output; correlated_with_non_role_subjects | The rule licenses pronoun output even when the reference is unresolved; in this fixed run it enables one pronoun TP but also emits nine pronoun/demonstrative FPs. |
| unresolved_pronoun_rule_17 | {"pronoun_total": 10, "pronoun_tp": 1, "pronoun_fp": 9, "pronoun_surface_distribution": {"It": 1, "This": 3, "it": 4, "they": 1, "this": 1}} | directly_consistent_with_observed_pronoun_prediction | The model follows the instruction and emits unresolved pronouns as actors; one overlaps Gold, but nine are FPs. |
| passive_no_performer_rule_18 | {"non_role_fp_cases": 28} | not_directly_tested_by_actor_error_taxonomy | No direct evidence of failure; retained only as a contrast rule for the next prompt-design round. |
| cross_field_projection_rules_10_12_27 | {"actor_fn_cross_field_presence": 3, "actor_fn_total": 3, "cross_field_presence_rate": 1.0} | correlated_with/FN evidence; no single-factor causal claim | Three Gold actors are inside emitted condition spans; this is a field-projection gap, not necessarily a recognition gap. |

## Factorial Actor delta (Full → No semantic guidance)

- full_actor_predictions_count: 82
- no_guidance_actor_predictions_count: 77
- delta_prediction_count: -5
- delta_matched_predictions_tp_side: 2
- delta_fp: -7
- delta_matched_ground_truth_recall_side: 0
- delta_fn: 0
- lost_surface_count: 25
- gained_surface_count: 20
- beneficial_removal_count: 21
- harmful_loss_count: 4

## Gold review candidates

- `estg_000037`: the insured person (FP-C_LEGAL_NORMATIVE_ROLE_BUT_GOLD_UNANNOTATED)
- `estg_000659`: Persons with limited tax liability (FP-C_LEGAL_NORMATIVE_ROLE_BUT_GOLD_UNANNOTATED)
- `estg_000716`: the building society (FP-C_LEGAL_NORMATIVE_ROLE_BUT_GOLD_UNANNOTATED)

## Limitations

- Single fixed development run (D-full-0813); not a formal or universal claim.
- FN/FP taxonomy uses character-span rules plus surface heuristics; every case carries classification_basis and confidence.
- Non-role grammatical subject and ontology-disagreement categories are heuristic and may need human review.
- Gold is read-only and was not changed; suspicious Gold is reported only as gold_review_candidate.
- Rules-Only behavior is shown only as post-hoc method-difference evidence and was not used to edit Direct-LLM predictions or rules.
- Factorial actor delta uses the existing frozen factorial canonical predictions, which were generated under the pre-promotion legacy policy; it is a within-factorial comparison only.
