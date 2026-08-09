# Stage 3 development error analysis - sun_2024 (DEV_ONLY)

## matching FP/FN (binary rule) or ranking notes

- m001 gdpr_1_data_breach x article33: gold=True pred=False matching_score=0.0
- m002 gdpr_1_data_breach x article34: gold=True pred=False matching_score=0.0
- m005 gdpr_2_consent_to_use_the_data x article7: gold=True pred=False matching_score=0.142857
- m006 gdpr_2_consent_to_use_the_data x article6: gold=True pred=False matching_score=0.1
- m007 gdpr_2_consent_to_use_the_data x article22: gold=True pred=False matching_score=0.166667
- m010 gdpr_3_right_to_access x article15: gold=True pred=False matching_score=0.0
- m013 gdpr_4_right_of_portability x article20: gold=True pred=False matching_score=0.0
- m016 gdpr_5_right_to_withdraw x article7: gold=True pred=False matching_score=0.0
- m017 gdpr_5_right_to_withdraw x article17: gold=True pred=False matching_score=0.142857
- m020 gdpr_6_right_to_rectify x article16: gold=True pred=False matching_score=0.0
- m023 gdpr_7_right_to_be_forgotten x article17: gold=True pred=False matching_score=0.0

## violation missed / wrong-type / unobservable

- v002 gdpr_1_data_breach x article33: gold=incorrect_actor pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 10, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v003 gdpr_1_data_breach x article33: gold=out_of_order pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 10, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v005 gdpr_1_data_breach x article34: gold=incorrect_actor pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 7, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v006 gdpr_1_data_breach x article34: gold=out_of_order pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 7, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v008 gdpr_2_consent_to_use_the_data x article7: gold=incorrect_actor pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 8, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v009 gdpr_2_consent_to_use_the_data x article7: gold=out_of_order pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 8, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v011 gdpr_2_consent_to_use_the_data x article6: gold=incorrect_actor pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 10, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v012 gdpr_2_consent_to_use_the_data x article6: gold=out_of_order pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 10, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v015 gdpr_2_consent_to_use_the_data x article22: gold=out_of_order pred=None scores={'incorrect_actor': 1.0, 'incorrect_actor_denominator': 6, 'incorrect_actor_observable': True, 'incorrect_actor_reason': None, 'missing_action': 0.833333, 'missing_action_denominator': 6, 'out_of_order': 0.0, 'out_of_order_denominator': 0}
- v017 gdpr_3_right_to_access x article15: gold=incorrect_actor pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 13, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v018 gdpr_3_right_to_access x article15: gold=out_of_order pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 13, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v020 gdpr_4_right_of_portability x article20: gold=incorrect_actor pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 5, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v021 gdpr_4_right_of_portability x article20: gold=out_of_order pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 5, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v023 gdpr_5_right_to_withdraw x article7: gold=incorrect_actor pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 8, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v024 gdpr_5_right_to_withdraw x article7: gold=out_of_order pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 8, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v026 gdpr_5_right_to_withdraw x article17: gold=incorrect_actor pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 7, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v027 gdpr_5_right_to_withdraw x article17: gold=out_of_order pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 7, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v029 gdpr_6_right_to_rectify x article16: gold=incorrect_actor pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 2, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v030 gdpr_6_right_to_rectify x article16: gold=out_of_order pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 2, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v032 gdpr_7_right_to_be_forgotten x article17: gold=incorrect_actor pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 7, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]
- v033 gdpr_7_right_to_be_forgotten x article17: gold=out_of_order pred=None scores={'incorrect_actor': 0.0, 'incorrect_actor_denominator': 0, 'incorrect_actor_observable': False, 'incorrect_actor_reason': 'action_mapping_below_gamma', 'missing_action': 1.0, 'missing_action_denominator': 7, 'out_of_order': 0.0, 'out_of_order_denominator': 0} [actor unobservable]

## threshold sensitivity

- primary thresholds are pre-registered (Winter gamma 0.4/delta 0.8;
  Sun tau/gamma/theta 0.8); sweep values are sensitivity reports only
  and are NOT used to pick primary thresholds (see threshold_sensitivity.json).

## error attribution

- method differences (Winter clause-bag vs Sun Rule Record action/actor
  separation and order relations), actor observability (empty lane names;
  pool names present), rule extraction quality of the development adapter,
  and similarity backend limits (en_core_web_sm, no word vectors) are the
  expected error sources; no Gold/sample/threshold adjustment was performed.
