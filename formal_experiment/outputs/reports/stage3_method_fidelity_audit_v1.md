# Stage 3 / Table 3 Method Fidelity & Integration Audit v1

- status: `read_only_diagnosis_complete`
- real API calls: `0`
- worktree: `D:\Paper\experiment\bpc-hybrid\.tmp\s3_table3_preflight_worktree`
- branch: `paper-final-repair`
- HEAD: `a422364d660793f3a60ea64c6554f8a78cc47d89`
- origin/paper-final-repair: `a422364d660793f3a60ea64c6554f8a78cc47d89`

## A. Historical formal result v1 (unchanged)

| Method | Overall P | Overall R | Overall F1 | Test F1 |
|---|---:|---:|---:|---:|
| Sun | 0.3168 | 0.4000 | 0.3536 | 0.3448 |
| Winter | 0.4713 | 0.5125 | 0.4910 | 0.4815 |
| Ours | 0.3504 | 0.5125 | 0.4162 | 0.4000 |

The v1 result JSON and freeze manifest are not modified.

## B. Winter fidelity map

| Component | Paper | Prototype | Current implementation | Judgment |
|---|---|---|---|---|
| regulation paragraph splitting | UNVERIFIED | Document_Collection.get_paragraphs uses spaCy sentence boundaries and signalwords | winter_clause.parse_regulation_paragraph mirrors it | FAITHFUL_RECONSTRUCTION |
| clause/subtree extraction | UNVERIFIED | Sentence/Clause dependency subtrees, sort, subject propagation | winter_clause WinterSentence/WinterClause mirrors it | FAITHFUL_RECONSTRUCTION_WITH_MINOR_LEMMA_DEVIATION |
| signal/sequence/stop words | UNVERIFIED | gdpr.config and three text files | same read-only files, SHA-bound by run manifest | FAITHFUL_RECONSTRUCTION |
| model obligation list | UNVERIFIED | start/end events + tasks + intermediate events | same | FAITHFUL_RECONSTRUCTION |
| resource_set | UNVERIFIED | global all files, process@name, lower/strip | global all inference BPMNs, process@name; empty names skipped | PROTOTYPE_NATIVE_SCOPE_WITH_BENCHMARK_INTERACTION |
| fitness / cost_obligation | UNVERIFIED | max spaCy similarity per clause; fraction < gamma | same formulas | FAITHFUL_RECONSTRUCTION |
| cost_resource | UNVERIFIED | resource in clause, dissimilar to model participant, model participant not literal | same formula with global vocabulary | FAITHFUL_RECONSTRUCTION_BEHAVIOUR |
| cost_so / reachability | UNVERIFIED | is_reachable_from returns target in reachability[target] (always True), so cost_so is vacuous | corrected target in reachability[source] | BUG_FIX_RELATIVE_TO_PROTOTYPE_ALIGNED_WITH_PAPER_INTENT |
| cost weights | UNVERIFIED | 1/3 each | 1/3 each | FAITHFUL_RECONSTRUCTION |
| gamma/delta | UNVERIFIED | gdpr.config gamma=0.4 delta=0.8; main.py hardcodes same | same | PROTOTYPE_NATIVE |
| evaluator conversion | UNVERIFIED | CSV costs/ranking; no P/R/F1 threshold | cost>0 -> binary violated for Table 3 | PROJECT_ADAPTATION |

### Winter resource-set verdict

- `WINTER_RESOURCE_SCOPE = PROTOTYPE_NATIVE`
- benchmark interaction: `CROSS_CASE_BENCHMARK_ADAPTATION`
- roles (7): `board, certification body, controller, controller and processor, data subject, processor, supervisory authority`
- prototype evidence: references/winter_2020_model_check/model_check/lib/main.py lines 92-135: resource_set is accumulated across every file in modeldir before Pair construction.
- verdict: global all-loaded-models is prototype-native; applying it to all 113 benchmark variants gives cross-case role vocabulary but no Gold leakage. Do not restrict Winter to the current process as a fairness fix.

### Winter actor diagnosis

Representative actor traces are recorded in the JSON artifact. The table below is a compact summary.

| Case | Requirement | Gold | Winter final | cost_resource | model resources | key trigger |
|---|---|---|---|---|---|---|
| case_a9fd75331508 | R5-D-01 | violated | violated | 0.3333 | Data subject | controller->0.3892 |
| case_0164a880bf44 | R5-D-08 | violated | violated | 0.2500 | Data subject | controller->0.3892 |
| case_026d89f057e8 | R5-D-11 | violated | violated | 0.5000 | Data subject | controller->0.3892; controller->0.3892; controller->0.3892 |
| case_9c6fcd32f03c | R5-D-01 | satisfied | satisfied | 0.0000 | Controller | - |
| case_ff937cc4c24e | R5-D-02 | satisfied | satisfied | 0.0000 | Controller | - |
| case_f6dc7b084b03 | R5-D-03 | satisfied | satisfied | 0.0000 | Controller | - |
| case_1fd8d9be0c9d | R5-D-12 | satisfied | violated | 0.3333 | Controller | supervisory authority->0.4186 |
| case_6209f221b20b | R5-S1-T4 | satisfied | violated | 0.2500 | Controller | data subject->0.3892 |
| case_50f498770ae9 | R5-D-03 | violated | satisfied | 0.0000 | Data subject | - |
| case_89f6d9e7047b | R5-D-06 | violated | satisfied | 0.0000 | Data subject | - |

Winter incorrect_actor confusion on the 80 scored cells: TP=24, FP=11, FN=9, TN=36, P=0.6857, R=0.7273, F1=0.7059, coverage=1.0. The signal is observable because `resource_set` contains 7 global role candidates. TP/FP/FN are driven by the prototype's literal resource logic: a known role mentioned in the clause is compared to the model participant, with exact literal suppression of the model participant.

### Winter reachability verdict

- literal prototype: `targetid in reachability[targetid]` => always True => `cost_so` always 0.
- current formal run: `REACHABILITY_CORRECTED` (`targetid in reachability[sourceid]`).
- verdict: prototype bug fix aligned with paper intent; report as **Winter reproduction with corrected reachability**, not literal native.

## C. Sun method fidelity

| Component | Paper | Current implementation | Judgment |
|---|---|---|---|
| Definition 4 matching score | max(action fraction > tau, actor/object fraction > tau) | SunScorer.matching_score | VERIFIED_FAITHFUL |
| Definition 5 missing action | fraction of A_r with sim < gamma | SunScorer.missing_action | VERIFIED_FAITHFUL |
| Definition 6 incorrect actor | R = actors with matched action > gamma; C = business objects of actions/events union process actors; exists dissimilar member < theta | SunScorer.incorrect_actor builds C from action-bound business objects; business_objects is populated only from record.activities, not record.events | PROJECT_ADAPTATION_DECLARED_EVENT_OBJECTS_OMITTED |
| Definition 7 out-of-order | U_r subset A_r x A_r; both endpoints map > gamma; forward reachable and not backward | SunScorer.out_of_order | FORMULA_FAITHFUL_BUT_DATA_PATH_DERIVED_AND_TYPE_B_UNSUPPORTED |
| thresholds | tau/gamma=0.8; theta=0.8/0.7 depending on model | all 0.8, fixed pre-registration | VERIFIED_FAITHFUL / declared threshold choice |
| similarity backend | unspecified 'existing semantic similarity' | spaCy en_core_web_sm, no word vectors | PROJECT_ADAPTATION |
| outer matching gate | strongly associated rule records; automatic selection underspecified | NoGateSunChecker applies Def 5-7 to all 33 rules; evaluator indexes target rule only | PAPER_AMBIGUOUS + PROJECT_ADAPTATION |
| actor role surface normalization | not specified in detail | casefold/whitespace/leading-article only; controller and processor distinct | PROJECT_ADAPTATION_DISCLOSED |
| order relation source | U_r from rule record | all frozen Stage2 native order_relations empty; temporal_projection_v3 derives from conditions/constraints | PROJECT_ADAPTATION_DECLARED |

### Sun/Ours full-rule-base protocol verdict

- verdict: `PROTOCOL_AMBIGUOUS_TARGET_BOUND_PROJECT_ADAPTATION`
- scored unit: signal for (case, target bound requirement_id, check_type)
- unrelated-rule FP into target metrics: `False`
- explanation: NoGateSunChecker computes all rules, but the evaluator indexes the target requirement's signal only. Therefore the Ours missing_action FP=66 is not an unrelated-rule relevance artifact; it is the target rule's own Def 5 result.
- relation to Sun paper: Sun 4.3 uses matching/association and 5.3.2 checks the resulting matched rule-process collection. The project cannot reproduce whole-model multi-label checking because the released Gold is target-bound.

## D. Missing-action FP analysis

### Sun

| FP cause | Count |
|---|---|
| mandatory_primary_action_not_detected_below_gamma | 59 |
| mandatory_action_detected_but_extra_rule_action_below_gamma | 5 |

Representative FP traces are stored in the JSON artifact.

### Ours

| FP cause | Count |
|---|---|
| mandatory_action_detected_but_extra_rule_action_below_gamma | 8 |
| mandatory_primary_action_not_detected_below_gamma | 58 |

Representative FP traces are stored in the JSON artifact.

No target-rule FP is caused by an unrelated rule under the current evaluator: it looks up exactly `(method, case_id, target requirement_id, check_type)`.

## E. Actor integration analysis

| Method | scored cells | observable | action_mapping_below_gamma | empty_rule_actor_denominator | incomplete_actor_action_map | actor violation | actor satisfied |
|---|---|---|---|---|---|---|---|
| sun | 80 | 9 | 44 | 24 | 3 | 9 | 0 |
| ours | 80 | 18 | 54 | 8 | 0 | 18 | 0 |

Observable actor cells are always violated. The dominant failure is `action_mapping_below_gamma` (44 Sun, 54 Ours), followed by Stage2 empty actor denominators (24 Sun, 8 Ours). Where action matching succeeds, Sun Definition 6's C set includes action-bound business objects, so a dissimilar business object can trigger an actor violation under the paper's existential formula.

## F. Order 14-case failure-stage matrix

| Req | Case | Gold order type | Method | Native U_r | Adapter edges | Denominator | Failure stage | Final | Winter final |
|---|---|---|---|---|---|---|---|---|---|
| R5-D-01 | case_3b01b9c36d0f | TYPE_A_explicit_action_precedence | sun | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-D-01 | case_3b01b9c36d0f | TYPE_A_explicit_action_precedence | ours | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-D-02 | case_ff937cc4c24e | TYPE_A_explicit_action_precedence | sun | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-D-02 | case_ff937cc4c24e | TYPE_A_explicit_action_precedence | ours | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-D-03 | case_f6dc7b084b03 | TYPE_A_explicit_action_precedence | sun | 0 | be informed by the controller -> the restriction of processing | 0 | endpoint_mapping_below_gamma | unknown | unknown |
| R5-D-03 | case_f6dc7b084b03 | TYPE_A_explicit_action_precedence | ours | 0 | be informed -> the restriction of processing | 0 | endpoint_mapping_below_gamma | unknown | unknown |
| R5-D-04 | case_a2f445c641d1 | TYPE_A_explicit_action_precedence | sun | 0 | carry out an assessment of the impact of the envisaged processing operations on -> the processing | 0 | endpoint_mapping_below_gamma | unknown | unknown |
| R5-D-04 | case_a2f445c641d1 | TYPE_A_explicit_action_precedence | ours | 0 | carry out an assessment of the impact of the envisaged processing operations on the protection of personal data -> the processing | 0 | endpoint_mapping_below_gamma | unknown | unknown |
| R5-D-05 | case_d8029187c213 | TYPE_A_explicit_action_precedence | sun | 0 | consult the supervisory authority -> processing | 0 | endpoint_mapping_below_gamma | unknown | unknown |
| R5-D-05 | case_d8029187c213 | TYPE_A_explicit_action_precedence | ours | 0 | consult the supervisory authority -> processing | 0 | endpoint_mapping_below_gamma | unknown | unknown |
| R5-D-12 | case_27553ad672b2 | TYPE_B_trigger_precedence | sun | 0 | having become aware of it -> notify the personal data breach to the supervisory authority competent in | 0 | endpoint_mapping_below_gamma | unknown | violated |
| R5-D-12 | case_27553ad672b2 | TYPE_B_trigger_precedence | ours | 0 | having become aware of it -> notify the personal data breach to the supervisory authority competent in accordance with Article 55 | 0 | endpoint_mapping_below_gamma | unknown | violated |
| R5-S1-T3 | case_250418025567 | TYPE_B_trigger_precedence | sun | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-S1-T3 | case_250418025567 | TYPE_B_trigger_precedence | ours | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-S1-T4 | case_2e0630dc5be5 | TYPE_B_trigger_precedence | sun | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-S1-T4 | case_2e0630dc5be5 | TYPE_B_trigger_precedence | ours | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-S3-T1 | case_d391f7745e2d | TYPE_B_trigger_precedence | sun | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-S3-T1 | case_d391f7745e2d | TYPE_B_trigger_precedence | ours | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-S3-T2 | case_ba895d210eaf | TYPE_B_trigger_precedence | sun | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-S3-T2 | case_ba895d210eaf | TYPE_B_trigger_precedence | ours | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-S5-T4 | case_8c729ed572f4 | TYPE_C_deadline_arithmetic_only | sun | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-S5-T4 | case_8c729ed572f4 | TYPE_C_deadline_arithmetic_only | ours | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-S6-T3 | case_cecd14adb006 | TYPE_B_trigger_precedence | sun | 0 | becoming aware of a personal data breach -> notify the controller without undue delay | 0 | endpoint_mapping_below_gamma | unknown | violated |
| R5-S6-T3 | case_cecd14adb006 | TYPE_B_trigger_precedence | ours | 0 | becoming aware of a personal data breach -> notify the controller | 0 | endpoint_mapping_below_gamma | unknown | violated |
| R5-S7-T1 | case_7dcc88ac3cf1 | TYPE_A_explicit_action_precedence | sun | 0 | relates to processing activities in several Member States, the supervisory -> approving the draft code, amendment | 0 | endpoint_mapping_below_gamma | unknown | unknown |
| R5-S7-T1 | case_7dcc88ac3cf1 | TYPE_A_explicit_action_precedence | ours | 0 | [] | 0 | order_relation_absent | unknown | unknown |
| R5-S8-T1 | case_3af5fd62647b | TYPE_A_explicit_action_precedence | sun | 0 | [] | 0 | order_relation_absent | unknown | violated |
| R5-S8-T1 | case_3af5fd62647b | TYPE_A_explicit_action_precedence | ours | 0 | [] | 0 | order_relation_absent | unknown | violated |

Interpretation: Sun/Ours order target signals have denominator 0 for all 14 positives. The failures divide into (a) no derived adapter edge and (b) an adapter edge whose endpoint action similarity is <= gamma=0.8. The TYPE_B trigger-precedence cases are not fully representable under Sun Definition 7's `U_r subset A_r x A_r`.

## G. Stage2 -> Stage3 field consumption

| Stage2 field | Direct Stage3 consumer | Indirect consumer | Currently used? | Lost at adapter? |
|---|---|---|---|---|
| modality | converter obligation gate | none | yes, obligation only | no, counted/excluded, but permission/prohibition/definition never enter Def 5-7 |
| action | SunScorer.matching_score / missing_action / incorrect_actor R | temporal_projection_v3 main-action endpoint | yes | no, but span validity and source SHA are enforced |
| actor | SunScorer.matching_score / incorrect_actor | none | yes when present | no, but Stage2 empty actor lists remain empty by contract |
| actor_action_pairs / actor_action_map | SunScorer.incorrect_actor f_r | none | yes when present | no, but 10 Sun records and 2 Ours records have no pairs in frozen Stage2 |
| condition | none for scoring | temporal_projection_v3 marker scope | only to bound order markers | condition truth is not evaluated; declared core exclusion |
| constraint | none directly | temporal_projection_v3 order-edge source | yes, as derived order source | no conversion loss, but Definition 3 U_r subset A_r x A_r is not claimed for derived endpoints |
| exception | none for scoring | temporal_projection_v3 marker-inside-exception rejection | only as marker rejection | exception truth is not evaluated; declared core exclusion |
| native order_relations | temporal_projection_v3 native-priority path | SunScorer.out_of_order when native edges exist | yes if non-empty | all 33 Sun and all 33 Ours frozen records have empty native order_relations; derived edges are used instead |
| source_text / character offsets | canonical converter span slicing and source SHA validation | temporal_projection_v3 audited spans | yes | no, provenance-carrying |

## H. Findings

| ID | Severity | Classification | Title | Affected | Gold independent | Eligible fix | Metric direction known |
|---|---|---|---|---|---|---|---|
| AUDIT-W-01 | P2 | LABELING_DEVIATION | Winter formal method id says native but uses corrected_reachability | winter | True | False | False |
| AUDIT-W-02 | P2 | BENCHMARK_METHOD_INTERACTION | Winter global role vocabulary is prototype-native but cross-case in this benchmark | winter | True | False | True |
| AUDIT-W-03 | P2 | PROJECT_ADAPTATION | Winter cost > 0 is converted to binary violation for Table 3 | winter | True | False | True |
| AUDIT-W-04 | P3 | DEVIATION_NO_EFFECT_ON_CURRENT_DATA | Minor Winter transcription deviations | winter | True | False | False |
| AUDIT-S-01 | P1 | PROTOCOL_MISMATCH | Sun/Ours run full-rule-base Def 5-7 but evaluation is target-requirement-bound | sun,ours | True | False | False |
| AUDIT-S-02 | P1 | PROJECT_ADAPTATION | en_core_web_sm no-vector similarity drives low action and endpoint scores | sun,ours | True | False | False |
| AUDIT-S-03 | P2 | PAPER_AMBIGUOUS | Definition 6 C includes business objects, causing actor FP under the existential formula | sun,ours | True | False | True |
| AUDIT-S-10 | P2 | PROJECT_ADAPTATION | Definition 6 C omits business objects extracted from event labels | sun,ours | True | False | True |
| AUDIT-S-04 | P1 | METHOD_LIMITATION | Order detection is structurally blocked by absent U_r and endpoint mapping | sun,ours | True | False | False |
| AUDIT-S-05 | P3 | DIAGNOSTIC_LABELING | no_rule_order_endpoints conflates absent U_r with endpoint mapping failure | sun,ours | True | False | False |
| AUDIT-S-06 | P1 | METHOD_LIMITATION | Missing-action FP are caused by Stage2 action fragmentation/under-specification, not unrelated-rule alarms | sun,ours | True | False | True |
| AUDIT-S-07 | P1 | METHOD_LIMITATION | Actor observability is low because action mapping and actor-action links fail | sun,ours | True | False | True |
| AUDIT-S-08 | P2 | PROJECT_ADAPTATION | Derived order endpoints are not guaranteed to satisfy U_r subset A_r x A_r | sun,ours | True | False | False |
| AUDIT-S-09 | P2 | PROTOCOL_MISMATCH | Gold is target-bound; complete multi-label compliance is not available | sun,ours,winter | True | False | False |

### AUDIT-W-01 — Winter formal method id says native but uses corrected_reachability

- severity: `P2`
- classification: `LABELING_DEVIATION`
- affected methods: `winter`
- Gold-independent: `True`; eligible for fix: `False`; metric direction known: `False`
- evidence: Prototype Process.py is_reachable_from returns targetid in self.reachability[targetid] (always True); current runner passes REACHABILITY_CORRECTED and the formal result freeze binds reachability_mode corrected_reachability.
- note: The running semantics are a prototype bug fix aligned with paper intent, but the label winter_2020_native_full_pipeline overclaims native. Rename for reporting; do not rerun only for a label.

### AUDIT-W-02 — Winter global role vocabulary is prototype-native but cross-case in this benchmark

- severity: `P2`
- classification: `BENCHMARK_METHOD_INTERACTION`
- affected methods: `winter`
- Gold-independent: `True`; eligible for fix: `False`; metric direction known: `True`
- evidence: Prototype main.py accumulates resource_set across every file in modeldir. Current global_roles scans all 113 inference BPMNs and unions process@name; all actor mutations and required-role BPMNs are present, yielding 7 roles.
- note: Restricting to the current process would be less faithful to the prototype and would suppress actor detections. No Gold/reference is read; it is a benchmark-method interaction, not a Gold leak.

### AUDIT-W-03 — Winter cost > 0 is converted to binary violation for Table 3

- severity: `P2`
- classification: `PROJECT_ADAPTATION`
- affected methods: `winter`
- Gold-independent: `True`; eligible for fix: `False`; metric direction known: `True`
- evidence: winter_signals maps cost_obligation/cost_resource/cost_so > 0 to violated. The prototype emits continuous costs and CSV ranks/scores, not a P/R/F1 threshold.
- note: Necessary for a shared three-state evaluator; must be disclosed as project adaptation, not original Winter evaluation protocol.

### AUDIT-W-04 — Minor Winter transcription deviations

- severity: `P3`
- classification: `DEVIATION_NO_EFFECT_ON_CURRENT_DATA`
- affected methods: `winter`
- Gold-independent: `True`; eligible for fix: `False`; metric direction known: `False`
- evidence: Current global_roles ignores empty process@name; prototype adds ''. Current BPMN duplicate-participant handling extends rather than overwrites. All 113 benchmark process@names are nonempty and each file has one process.
- note: No observed metric effect on R5; record for fidelity completeness.

### AUDIT-S-01 — Sun/Ours run full-rule-base Def 5-7 but evaluation is target-requirement-bound

- severity: `P1`
- classification: `PROTOCOL_MISMATCH`
- affected methods: `sun, ours`
- Gold-independent: `True`; eligible for fix: `False`; metric direction known: `False`
- evidence: NoGateSunChecker applies Definitions 5-7 to every one of the 33 rule records, while evaluate_stage3_table3_r5_formal_v1.py indexes only (method, case, target requirement_id, type). Sun paper 4.3 says strongly associated rule records enter checking; 5.3.2 evaluates a checking collection, not a target-rule lookup.
- note: Paper does not specify the exact automatic association threshold; current no-gate is a declared project adaptation. Fixing would require a complete multi-label Gold and a specified association protocol, so it is outside this task.

### AUDIT-S-02 — en_core_web_sm no-vector similarity drives low action and endpoint scores

- severity: `P1`
- classification: `PROJECT_ADAPTATION`
- affected methods: `sun, ours`
- Gold-independent: `True`; eligible for fix: `False`; metric direction known: `False`
- evidence: SunScorer uses WinterSimilarity -> spaCy en_core_web_sm. spaCy warns W007 that the model has no word vectors; Doc.similarity is tensor-based and not a calibrated semantic metric. Fixed tau/gamma/theta=0.8 are from Sun 2024.
- note: The backend is shared by Sun and Ours and was selected for controlled comparison; changing it is a method/config redesign. Prior R3 M2 using en_core_web_lg did not improve order.

### AUDIT-S-03 — Definition 6 C includes business objects, causing actor FP under the existential formula

- severity: `P2`
- classification: `PAPER_AMBIGUOUS`
- affected methods: `sun, ours`
- Gold-independent: `True`; eligible for fix: `False`; metric direction known: `True`
- evidence: Sun Definition 6 defines C = bs_obj(Am union Em) union Rm and violation exists r' in C with sim(r,r')<theta. Current process_actor_candidates contains business objects in addition to process actors. Baseline cases such as R5-D-05 flag violation because an activity object is dissimilar to the rule actor.
- note: Code matches the paper formula as written. Removing business objects to improve F1 would be paper-unfaithful and is explicitly forbidden.

### AUDIT-S-10 — Definition 6 C omits business objects extracted from event labels

- severity: `P2`
- classification: `PROJECT_ADAPTATION`
- affected methods: `sun, ours`
- Gold-independent: `True`; eligible for fix: `False`; metric direction known: `True`
- evidence: Paper Definition 1/4 states business objects are extracted from activity and event labels and C = bs_obj(Am union Em) union Rm. SunProcessModel.business_objects is populated only from record['activities']; the formal config declares activity-bound business objects. In the current 80 scored actor cells, observable actor predictions all match activity IDs, so this omitted term does not change Table 3 v1 target metrics, but it is an under-inclusive adaptation relative to the paper formula.
- note: Keep activity-bound C for v1 and disclose the omission. Adding event-label business objects would be a method change and could introduce noisy objects; it is not required for the historical v1 comparison.

### AUDIT-S-04 — Order detection is structurally blocked by absent U_r and endpoint mapping

- severity: `P1`
- classification: `METHOD_LIMITATION`
- affected methods: `sun, ours`
- Gold-independent: `True`; eligible for fix: `False`; metric direction known: `False`
- evidence: All 33 Sun and all 33 Ours frozen Stage2 records have native order_relations=[]; temporal_projection_v3 derives edges from conditions/constraints. For the 14 order-positive cases, every target out_of_order denominator is 0, either because no edge was derived or because endpoint similarity <= gamma=0.8.
- note: TYPE A projection/endpoint failure and TYPE B trigger precedence are mixed. Sun Definition 7 uses U_r subset A_r x A_r; trigger-to-action ordering is not fully representable. No Gold-derived relation may be invented.

### AUDIT-S-05 — no_rule_order_endpoints conflates absent U_r with endpoint mapping failure

- severity: `P3`
- classification: `DIAGNOSTIC_LABELING`
- affected methods: `sun, ours`
- Gold-independent: `True`; eligible for fix: `False`; metric direction known: `False`
- evidence: normalize_sun_signal sets reason no_rule_order_endpoints whenever denominator <= 0. SunScorer.out_of_order includes details for endpoints below gamma, so the reason string is not stage-specific.
- note: Status/coverage are correct; only reason granularity is misleading. Keep frozen outputs and use this audit's stage matrix.

### AUDIT-S-06 — Missing-action FP are caused by Stage2 action fragmentation/under-specification, not unrelated-rule alarms

- severity: `P1`
- classification: `METHOD_LIMITATION`
- affected methods: `sun, ours`
- Gold-independent: `True`; eligible for fix: `False`; metric direction known: `True`
- evidence: Ours missing_action: TP=33, FP=66, FN=0. Of 66 FP, 58 primary mandatory action strings fail gamma and 8 have the target action mapped but an extra Stage2 action fragment below gamma. Sun: 64 FP, 59 and 5 respectively. The evaluator indexes only the target requirement, so unrelated rules contribute 0 FP.
- note: Ours recall=1.0 because every missing mutant deletes the target activity; precision=1/3 because the same Stage2 record also contains non-mandatory fragments (or an under-specified mandatory action) that fail gamma on compliant/actor cases.

### AUDIT-S-07 — Actor observability is low because action mapping and actor-action links fail

- severity: `P1`
- classification: `METHOD_LIMITATION`
- affected methods: `sun, ours`
- Gold-independent: `True`; eligible for fix: `False`; metric direction known: `True`
- evidence: Sun actor target cells: 80 scored, only 9 observable (44 action_mapping_below_gamma, 24 empty_rule_actor_denominator, 3 incomplete_rule_actor_action_map). Ours: only 18 observable (54 action_mapping_below_gamma, 8 empty_rule_actor_denominator). Observable actor predictions are exactly the violated cells; no actor cell is observable and satisfied.
- note: Stage2 actors/pairs are absent in 10 Sun and 2 Ours core records; where present, action similarity still blocks R_{r,m,gamma}. Stage2 Ours is frozen and no API is allowed.

### AUDIT-S-08 — Derived order endpoints are not guaranteed to satisfy U_r subset A_r x A_r

- severity: `P2`
- classification: `PROJECT_ADAPTATION`
- affected methods: `sun, ours`
- Gold-independent: `True`; eligible for fix: `False`; metric direction known: `False`
- evidence: temporal_projection_v3 accepts bounded nominal endpoints (e.g. the restriction of processing) and verbal endpoints; the v4 R2 execution contract declares difference_from_sun_definition_3 for derived endpoints.
- note: Declared project adaptation. v4_r3 is an alternative projection that preserves local event predicates, but it is still derived and prior M2 showed no order improvement under fixed gamma.

### AUDIT-S-09 — Gold is target-bound; complete multi-label compliance is not available

- severity: `P2`
- classification: `PROTOCOL_MISMATCH`
- affected methods: `sun, ours, winter`
- Gold-independent: `True`; eligible for fix: `False`; metric direction known: `False`
- evidence: reference_cases and the released packet label one bound requirement per case. The evaluator cannot distinguish unrelated-rule alarms from errors; Table 3 therefore evaluates target-rule signals, not whole-model checking.
- note: Creating complete multi-label Gold is outside this task's authority and would require new benchmark construction, not a fidelity repair.

## I. Fixes

**NO FIDELITY-ELIGIBLE FIXES.**

## J. Corrected Table 3

Not run. No P0/P1 finding met all FIDELITY_ELIGIBLE_FIX conditions. The historical v1 result remains frozen and unchanged.

## K. Final verdict

- `TABLE3_V1_STATUS = VALID_WITH_DISCLOSURES`
- `WINTER_REPRODUCTION_LABEL = Winter reproduction with corrected reachability (prototype-native global roles; adapted binary cost evaluation; not native literal prototype)`
- `PRIMARY_COMPARISON_VALID = True`
- `CORRECTED_RUN_REQUIRED = False`
- `FIDELITY_ELIGIBLE_FIXES = []`
- `interpretation = Sun vs Ours remains a controlled Stage2 replacement over the same frozen Stage3 adaptation. Winter is an external adapted reproduction. The v1 P/R/F1 are meaningful only with the protocol, backend, benchmark-granularity, and order limitations disclosed.`

## L. Remaining method limitations

- Sun/Ours target-bound Gold prevents whole-model multi-label checking; unrelated-rule alarms are not scored.
- `en_core_web_sm` has no word vectors; Sun/Winter semantic similarity is not calibrated to the paper's threshold semantics.
- Sun Definition 6's C set includes business objects under an existential comparison; observable correct actors can still be marked violated.
- All frozen Stage2 records lack native order relations; derived projection is required and TYPE B trigger precedence is only partially representable.
- Winter uses a global role vocabulary over all 113 benchmark BPMNs; this is prototype-native scope but is a cross-case benchmark interaction.
- Winter R5 actor and order performance depends on the prototype's literal resource suppression and sequence-marker coverage (`before`/`prior to` are absent from the Winter sequencemarker file).
- Continuous Winter costs are converted to binary violations for Table 3; this is a project adaptation, not the original evaluation protocol.

