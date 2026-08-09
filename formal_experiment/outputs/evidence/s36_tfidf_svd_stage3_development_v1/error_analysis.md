# Stage 3 development error analysis - s36_tfidf_svd (DEV_ONLY)

## matching FP/FN (binary rule) or ranking notes

- m001 gdpr_1_data_breach x article33: gold=True pred=False matching_score=0.480918
- m003 gdpr_1_data_breach x article15: gold=False pred=True matching_score=0.830993
- m006 gdpr_2_consent_to_use_the_data x article6: gold=True pred=False matching_score=0.395739
- m008 gdpr_2_consent_to_use_the_data x article33: gold=False pred=True matching_score=0.502977
- m009 gdpr_2_consent_to_use_the_data x article34: gold=False pred=True matching_score=0.72248
- m013 gdpr_4_right_of_portability x article20: gold=True pred=False matching_score=0.429622
- m014 gdpr_4_right_of_portability x article15: gold=False pred=True matching_score=0.713433
- m016 gdpr_5_right_to_withdraw x article7: gold=True pred=False matching_score=0.220948
- m017 gdpr_5_right_to_withdraw x article17: gold=True pred=False matching_score=0.151859
- m020 gdpr_6_right_to_rectify x article16: gold=True pred=False matching_score=0.440105
- m023 gdpr_7_right_to_be_forgotten x article17: gold=True pred=False matching_score=0.266456
- m024 gdpr_7_right_to_be_forgotten x article15: gold=False pred=True matching_score=0.809136

## violation missed / wrong-type / unobservable

- v003 gdpr_1_data_breach x article33: gold=out_of_order pred=None scores={'missing_action': 0.8, 'incorrect_actor': 1.0, 'out_of_order': 0.0}
- v006 gdpr_1_data_breach x article34: gold=out_of_order pred=None scores={'missing_action': 0.857143, 'incorrect_actor': 1.0, 'out_of_order': 0.0}
- v009 gdpr_2_consent_to_use_the_data x article7: gold=out_of_order pred=None scores={'missing_action': 0.5, 'incorrect_actor': 1.0, 'out_of_order': 0.0}
- v012 gdpr_2_consent_to_use_the_data x article6: gold=out_of_order pred=None scores={'missing_action': 0.6, 'incorrect_actor': 1.0, 'out_of_order': 0.0}
- v015 gdpr_2_consent_to_use_the_data x article22: gold=out_of_order pred=None scores={'missing_action': 0.333333, 'incorrect_actor': 1.0, 'out_of_order': 0.0}
- v017 gdpr_3_right_to_access x article15: gold=incorrect_actor pred=None scores={'missing_action': 1.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0} [actor unobservable]
- v018 gdpr_3_right_to_access x article15: gold=out_of_order pred=None scores={'missing_action': 1.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0} [actor unobservable]
- v020 gdpr_4_right_of_portability x article20: gold=incorrect_actor pred=None scores={'missing_action': 1.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0} [actor unobservable]
- v021 gdpr_4_right_of_portability x article20: gold=out_of_order pred=None scores={'missing_action': 1.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0} [actor unobservable]
- v023 gdpr_5_right_to_withdraw x article7: gold=incorrect_actor pred=None scores={'missing_action': 1.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0} [actor unobservable]
- v024 gdpr_5_right_to_withdraw x article7: gold=out_of_order pred=None scores={'missing_action': 1.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0} [actor unobservable]
- v026 gdpr_5_right_to_withdraw x article17: gold=incorrect_actor pred=None scores={'missing_action': 1.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0} [actor unobservable]
- v027 gdpr_5_right_to_withdraw x article17: gold=out_of_order pred=None scores={'missing_action': 1.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0} [actor unobservable]
- v029 gdpr_6_right_to_rectify x article16: gold=incorrect_actor pred=None scores={'missing_action': 1.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0} [actor unobservable]
- v030 gdpr_6_right_to_rectify x article16: gold=out_of_order pred=None scores={'missing_action': 1.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0} [actor unobservable]
- v032 gdpr_7_right_to_be_forgotten x article17: gold=incorrect_actor pred=None scores={'missing_action': 1.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0} [actor unobservable]
- v033 gdpr_7_right_to_be_forgotten x article17: gold=out_of_order pred=None scores={'missing_action': 1.0, 'incorrect_actor': 0.0, 'out_of_order': 0.0} [actor unobservable]

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
