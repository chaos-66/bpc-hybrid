# R4 independent mechanism/development check

- backend: `r4_sm`
- status: `pass`

## Implementation contract checks

- PASS `action_comparison_uses_action_surface_not_legacy_join`
- PASS `missing_model_action_surface_does_not_fallback_to_full_label`
- PASS `missing_rule_action_surface_does_not_fallback_to_full_label`
- PASS `def4_def5_def6_def7_share_action_comparison_function`
- PASS `business_object_surface_retained_for_def6_candidate_scope`

## Behaviour probes

- PASS `article18_before_passive_projection` (projection)
- PASS `multi_predicate_projection_rejected` (projection)
- PASS `be_informed_inform_normalization` (action)
- PASS `correct_action_missing_only_other_action` (action)
- PASS `model_action_surface_missing_no_full_label_fallback` (action)
- PASS `rule_action_surface_missing_no_full_label_fallback` (action)
- PASS `duplicate_action_stable_id_tie` (action)
- PASS `same_verb_different_object_limitation` (action)
- PASS `same_verb_correct_object_candidate_absent_limitation` (action)
- PASS `normal_order_satisfied` (order)
- PASS `reverse_order_violated` (order)

## Known limitation reproductions

- observed=True `same_verb_different_object_limitation`: action-surface-only cannot distinguish business objects; both candidates tie on action text
- observed=True `same_verb_correct_object_candidate_absent_limitation`: action-surface-only accepts a same-verb wrong-object candidate when the correct-object candidate is absent

Known-limitation reproductions are regression checks, not capability passes.
