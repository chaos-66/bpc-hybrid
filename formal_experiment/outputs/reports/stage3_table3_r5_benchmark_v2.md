# S3-TABLE3-R5.1 Benchmark v2 — Targeted Correction Report

- status: **DATA_READY_FOR_FROZEN_SCOPE / METHODS_NOT_READY / API_AUTHORIZATION_PENDING / FORMAL_RELEASE_NOT_APPROVED**
- not formal Gold; no Table 3 score is claimed; real LLM/API calls = 0; `.env` not read.

## 1. Assets retained directly

- R5 v1 config/data/reports are preserved untouched (`D:/Paper/experiment/bpc-hybrid/formal_experiment/data/development/stage3_table3_r5_benchmark_v1`).
- 36 source requirements, the 5 R1-R4 historical rules, and all 108 v1 BPMN are retained as provenance.
- Sun/Ours/Winter detection formulas, similarity backend and thresholds were not changed.
- Old predictions, raw answers, old Gold and R1-R4 results were not modified.

## 2. Requirements/cases modified, migrated or exited core scoring

- Core requirements: 31; candidate (out of core) requirements: 5.
- per-type eligibility replaced all-or-nothing `has_variants`.
- A1 R5-S1-T1/T2: the 'at the time when' simultaneity relation was removed from out_of_order scoring.
- A2 R5-S6-T1: risk-appropriateness is no longer treated as a strict two-activity order.
- A3 R5-S6-T4: 'without undue delay' no longer proves the invented 'assess high risk -> notify' order.
- A4 R5-S2-T3/T4 (and the same rule for R5-S2-T1): permission requirements left the frozen three-class scoring; no permission formula was added.
- A5 R5-S3-T3/T4: the invented Stop/Cease tasks were removed; prohibition/cessation cases left core scoring.
- A6 R5-S4-T3: the excerpt was narrowed to the 28(3)(a) sentence with an explicit char span; the local snapshot is flagged as processed, not official verbatim.

| requirement | v1 split | v2 split | v2 eligibility (MA/IA/OO) | disposition | main issue |
|---|---|---|---|---|---|
| R5-D-01 | development | development | Y/Y/Y | core | none |
| R5-D-02 | development | development | Y/Y/Y | core | none |
| R5-D-03 | development | development | Y/Y/Y | core | none |
| R5-D-04 | development | development | Y/Y/Y | core | none |
| R5-D-05 | development | development | Y/Y/Y | core | none |
| R5-D-06 | development | development | Y/Y/N | core | order_evidence_text_is_not_order_rule |
| R5-D-07 | development | development | Y/Y/N | core | simultaneity_not_order |
| R5-D-08 | development | development | Y/Y/N | core | right_not_order_rule |
| R5-D-09 | development | development | Y/Y/N | core | deadline_without_explicit_trigger |
| R5-D-10 | development | development | Y/Y/N | core | deadline_without_explicit_trigger |
| R5-D-11 | development | development | Y/Y/N | core | right_not_order_rule |
| R5-D-12 | development | development | Y/Y/Y | core | condition_text_confused_with_exception |
| R5-S1-T1 | development | development | Y/Y/N | core | simultaneity_misread_as_order; missing_condition_flag |
| R5-S1-T2 | development | development | Y/Y/N | core | simultaneity_misread_as_order; missing_condition_flag |
| R5-S1-T3 | development | development | Y/Y/Y | core | missing_condition_flag |
| R5-S1-T4 | development | development | Y/Y/Y | core | missing_condition_flag |
| R5-S2-T1 | test | test | N/N/N | candidate_semantic | permission_modelled_as_positive_duty |
| R5-S2-T2 | test | test | Y/Y/N | core | none |
| R5-S2-T3 | test | test | N/N/N | candidate_semantic | permission_modelled_as_positive_duty; condition_and_negated_condition_confused_with_exception |
| R5-S2-T4 | test | test | N/N/N | candidate_semantic | permission_modelled_as_positive_duty; negated_condition_misstated_as_exception |
| R5-S3-T1 | test | test | Y/Y/Y | core | missing_condition_flag |
| R5-S3-T2 | test | test | Y/Y/Y | core | missing_condition_flag |
| R5-S3-T3 | test | test | N/N/N | candidate_semantic | prohibition_cessation_modelled_as_missing_action; invented_stop_task |
| R5-S3-T4 | test | test | N/N/N | candidate_semantic | prohibition_cessation_modelled_as_missing_action; invented_cease_task |
| R5-S4-T1 | test | test | Y/Y/N | core | lifecycle_not_strict_order |
| R5-S4-T2 | test | test | Y/Y/N | core | simultaneity_not_order |
| R5-S4-T3 | test | test | Y/Y/N | core | excerpt_includes_subsequent_subparagraphs; condition_precondition_misread_as_order; processed_source_not_flagged |
| R5-S4-T4 | test | test | Y/Y/N | core | missing_condition_flag |
| R5-S5-T1 | development | development | Y/Y/N | core | simultaneity_not_order |
| R5-S5-T2 | development | development | Y/Y/N | core | implicit_preference_not_strict_order |
| R5-S5-T3 | development | development | Y/Y/N | core | condition_not_order |
| R5-S5-T4 | development | development | Y/Y/Y | core | missing_condition_flag |
| R5-S6-T1 | test | test | Y/Y/N | core | risk_appropriateness_misread_as_order |
| R5-S6-T2 | test | test | Y/Y/N | core | prohibition_not_order |
| R5-S6-T3 | development | development | Y/Y/Y | core | missing_condition_flag |
| R5-S6-T4 | development | development | Y/Y/N | core | undue_delay_misread_as_assessment_order; invented_assessment_task |

## 3. Corrected real scale, positives/negatives and independent source families

- unique inputs (requirements): 36 (core 31 + candidate 5)
- source families: 21 (development 12, test 9); cross-split families: []
- core cases: 105 = 31 baselines + 31 missing_action + 31 incorrect_actor + 12 out_of_order
- development / test requirements: 22 / 14 (core test 9, candidate test 5)
- independent core test source families: ['gdpr_art12', 'gdpr_art19', 'gdpr_art24', 'gdpr_art25', 'gdpr_art28', 'gdpr_art32', 'gdpr_art8']
- candidate (non-core) test source families: ['gdpr_art21', 'gdpr_art8', 'gdpr_art9']
- per-type positive/negative cells:
  - missing_action: positive(violated)=31, negative(satisfied)=74, not_applicable=0, not_scored=0
  - incorrect_actor: positive(violated)=31, negative(satisfied)=43, not_applicable=31, not_scored=0
  - out_of_order: positive(violated)=12, negative(satisfied)=24, not_applicable=12, not_scored=57
- no forced 12/24 or 108; the test split shrank because exposed families were moved to development.

## 4. Six elements: present vs actually in the task input

| element | present records | in input / provided | declared external context only |
|---|---|---|---|
| modality | 36 | 35 | 1 |
| actor | 36 | 32 | 4 |
| action | 36 | 36 | 0 |
| condition | 35 | 32 | 3 |
| constraint | 36 | 35 | 1 |
| exception | 18 | 17 | 1 |

- modality/actor/action are implemented and used by the frozen scorer.
- condition and exception truth remain **unsupported** by the frozen three-class scorer (recorded in the challenge layer).
- constraint is `indirect_only` (explicit source order pairs only).
- an exception whose cross-reference text was not provided is explicitly marked `counts_as_in_input=false` and is not counted as an in-input exception.

## 5. Old predictions strictly verified as reusable

- Ours verified reusable: 14 / 36
- Sun verified reusable: 14
- verified rows have a per-record evidence chain (record + manifest + frozen input, source SHA, prompt/model binding, schema/output binding).
- 5 D1 rows use an explicit per-record input_binding and an explicit output SHA-256.
- 9 GDPR7 rows have no inline input_binding; they are verified via manifest -> input file -> record, prompt SHA and capsule path/schema. Their output binding has no explicit SHA-256 and is marked weaker.
- rows whose input or context changed are NOT marked exact-input reuse.

## 6. New requests and budget change

- v1 budget: 22 calls, USD 1.18 cap (NOT inherited).
- v2 corrected core request list: 17 new Ours Direct-LLM calls (one per unique regulation input; no per-BPMN calls), 14 reused.
- total input token cap: 364949; output cap: 69632 (4096/call); retries: 0.
- cost cap with 20% margin: USD 0.91 (cap, not a predicted bill).
- the 5 non-core candidate requirements are NOT in the current request list; they would add 5 calls if a future permission/prohibition authorization exists.
- request material: each call is an independent `messages` request with no conversation history; the frozen extraction instruction belongs to that request only (no cross-request memory); no reference answer, variant class, target node or other case result is passed; prompt, full input, parameters and model identity are bindable.

## 7. Remaining gaps before a Table 3 run

- API authorization for the corrected request list is absent.
- METHODS_NOT_READY (not fixed this round): R4 actor-surface equivalence, action mis-matching, same-action-different-object, actor/business-object candidate scope, coordinate postprocessing.
- condition/exception/prohibition/permission truth is still unsupported; condition/exception challenges are assets, not detector capability.
- core test coverage is 9 requirements over 7 independent families, and only 2 test requirements are out_of_order eligible.
- no new Stage2/Stage3 main matrix, no parameter search and no full test suite were run this round.
- validator: structural=True, content_qualification=True (7 structural + 6 content checks).

## 8. v1 -> v2 artifact mapping

| item | v1 | v2 | change |
|---|---|---|---|
| config | configs/stage3_table3_r5_benchmark_v1.json | configs/stage3_table3_r5_benchmark_v2.json | per-type eligibility + source_family_id + corrected conditions/excerpt |
| core cases | 108 | 105 | eligible-only variants |
| baseline controls | 36 | 31 | core-only baselines |
| variants/type | {'incorrect_actor': 24, 'missing_action': 24, 'out_of_order': 24} | {'incorrect_actor': 31, 'missing_action': 31, 'out_of_order': 12} | no forced 24 |
| dev/test requirements | 12/24 | 22/14 | exposure-aware |
| semantic challenges | 6 condition + 6 exception pairs, answer-hinting BPMN | same count, condition/exception separated, neutral valid BPMN | rewritten |
| prediction reuse | v1 default-match | per-record evidence-chain verification | corrected |
| API budget | 22 / USD 1.18 | 17 / USD 0.91 | recomputed from actual request list |

## 9. Status

- data: DATA_READY_FOR_FROZEN_SCOPE
- methods: METHODS_NOT_READY
- api: API_AUTHORIZATION_PENDING
- formal_release: FORMAL_RELEASE_NOT_APPROVED

