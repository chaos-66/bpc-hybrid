# SEP-C3 Definition Targeted Evaluation Contract v1

- Status: **FROZEN_BEFORE_NEW_API**
- Suite: `SEP-C3-DEFINITION-TARGETED-REFINEMENT-001`
- Panel SHA-256: `8ba4517f21402566d61364e86a5516e0ea89f1f82a32781b303eb7a53d97ec61`
- API input unit: `sample_id`
- Gold read timing: `after_predictions_are_frozen_and_hashed`

## Primary targeted metrics

### modality

- modality_accuracy_on_targeted_clause_set
- definition_precision
- definition_recall
- definition_f1
- confusion_definition_to_obligation_count
- confusion_obligation_to_definition_count
- confusion_prohibition_to_definition_count
- confusion_permission_to_definition_count

### shall_definition

- accuracy_on_all_15_shall_definition_clauses
- definition_recall_on_all_15_shall_definition_clauses
- numbered_corrected_relative_to_A
- numbered_regressed_relative_to_A

### non_definition_shall_controls

- modality_accuracy_on_15_controls
- false_definition_count
- false_definition_rate
- per_label_breakdown

### apply_applies_stress

- per_case_A_BASE_R_DEF_predictions
- aggregate_descriptive_counts_only

### definition_action_presence

- fraction_of_Gold_definition_clauses_with_at_least_one_predicted_action
- empty_action_count
- diagnostic_action_span_f1

## Secondary diagnostics

- actor/action/condition/constraint/exception field F1
- five-field micro-F1 if supported by frozen evaluator
- parse/schema validity
- prediction_count
- output_validation_failures

## Arithmetic and interpretation rules

- Do not average modality accuracy and span-field F1.
- Do not make significance claims from this targeted development run.

## Ambiguity policy

- Apply/applies: `NEEDS_GOLD_ADJUDICATION`
- No lexical apply=>definition rule: `True`

## Gold inconsistency cases

- `estg_000505 c2` modality=obligation in_panel=False status=POTENTIAL_GOLD_INCONSISTENCY
- `estg_000509 c2` modality=definition in_panel=True status=POTENTIAL_GOLD_INCONSISTENCY
