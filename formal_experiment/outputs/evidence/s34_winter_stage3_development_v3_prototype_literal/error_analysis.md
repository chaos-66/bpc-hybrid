# Stage 3 development error analysis - winter_2020 (DEV_ONLY)

## matching FP/FN (binary rule) or ranking notes

- m003 gdpr_1_data_breach x article15: gold=False pred=True matching_score=0.592061
- m004 gdpr_1_data_breach x article17: gold=False pred=True matching_score=0.600022
- m008 gdpr_2_consent_to_use_the_data x article33: gold=False pred=True matching_score=0.555847
- m009 gdpr_2_consent_to_use_the_data x article34: gold=False pred=True matching_score=0.581234
- m011 gdpr_3_right_to_access x article7: gold=False pred=True matching_score=0.490436
- m012 gdpr_3_right_to_access x article20: gold=False pred=True matching_score=0.481036
- m014 gdpr_4_right_of_portability x article15: gold=False pred=True matching_score=0.520624
- m015 gdpr_4_right_of_portability x article17: gold=False pred=True matching_score=0.482979
- m018 gdpr_5_right_to_withdraw x article15: gold=False pred=True matching_score=0.535982
- m019 gdpr_5_right_to_withdraw x article33: gold=False pred=True matching_score=0.540387
- m021 gdpr_6_right_to_rectify x article15: gold=False pred=True matching_score=0.452621
- m022 gdpr_6_right_to_rectify x article20: gold=False pred=True matching_score=0.435398
- m024 gdpr_7_right_to_be_forgotten x article15: gold=False pred=True matching_score=0.518229
- m025 gdpr_7_right_to_be_forgotten x article33: gold=False pred=True matching_score=0.520698

## violation missed / wrong-type / unobservable

- v002 gdpr_1_data_breach x article33: gold=incorrect_actor pred=None scores={'missing_action': 0.052632, 'incorrect_actor': 0.0, 'out_of_order': 0.5}
- v004 gdpr_1_data_breach x article34: gold=missing_action pred=None scores={'missing_action': 0.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v005 gdpr_1_data_breach x article34: gold=incorrect_actor pred=None scores={'missing_action': 0.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v006 gdpr_1_data_breach x article34: gold=out_of_order pred=None scores={'missing_action': 0.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v008 gdpr_2_consent_to_use_the_data x article7: gold=incorrect_actor pred=None scores={'missing_action': 0.2, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v009 gdpr_2_consent_to_use_the_data x article7: gold=out_of_order pred=None scores={'missing_action': 0.2, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v011 gdpr_2_consent_to_use_the_data x article6: gold=incorrect_actor pred=None scores={'missing_action': 0.142857, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v012 gdpr_2_consent_to_use_the_data x article6: gold=out_of_order pred=None scores={'missing_action': 0.142857, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v014 gdpr_2_consent_to_use_the_data x article22: gold=incorrect_actor pred=None scores={'missing_action': 0.2, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v015 gdpr_2_consent_to_use_the_data x article22: gold=out_of_order pred=None scores={'missing_action': 0.2, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v017 gdpr_3_right_to_access x article15: gold=incorrect_actor pred=None scores={'missing_action': 0.508772, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v018 gdpr_3_right_to_access x article15: gold=out_of_order pred=None scores={'missing_action': 0.508772, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v020 gdpr_4_right_of_portability x article20: gold=incorrect_actor pred=None scores={'missing_action': 0.6, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v021 gdpr_4_right_of_portability x article20: gold=out_of_order pred=None scores={'missing_action': 0.6, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v023 gdpr_5_right_to_withdraw x article7: gold=incorrect_actor pred=None scores={'missing_action': 0.266667, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v024 gdpr_5_right_to_withdraw x article7: gold=out_of_order pred=None scores={'missing_action': 0.266667, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v026 gdpr_5_right_to_withdraw x article17: gold=incorrect_actor pred=None scores={'missing_action': 0.32, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v027 gdpr_5_right_to_withdraw x article17: gold=out_of_order pred=None scores={'missing_action': 0.32, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v029 gdpr_6_right_to_rectify x article16: gold=incorrect_actor pred=None scores={'missing_action': 0.428571, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v030 gdpr_6_right_to_rectify x article16: gold=out_of_order pred=None scores={'missing_action': 0.428571, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v032 gdpr_7_right_to_be_forgotten x article17: gold=incorrect_actor pred=None scores={'missing_action': 0.2, 'incorrect_actor': 0.0, 'out_of_order': 0.0}
- v033 gdpr_7_right_to_be_forgotten x article17: gold=out_of_order pred=None scores={'missing_action': 0.2, 'incorrect_actor': 0.0, 'out_of_order': 0.0}

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
