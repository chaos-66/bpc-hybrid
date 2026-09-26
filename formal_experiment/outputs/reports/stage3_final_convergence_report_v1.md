# Stage 3 Final Convergence Report v1

- status: `STAGE3_METHOD_FROZEN_FINAL_UNSEEN_BENCHMARK_BLOCKED_PENDING_USER_AUTHORIZATION`
- selected backend: `sentence_transformers_all_mpnet_base_v2`
- gamma / theta / tau: `0.55` / `0.45` / `0.8`
- stage3 method frozen: `True`
- final unseen benchmark prepared: `False`

## A. Git

- branch: `paper-final-repair`
- starting HEAD: `5b2e1ffaf7189992a5f7c779aa41dffcb8a6787c`
- HEAD at report generation: `5b2e1ffaf7189992a5f7c779aa41dffcb8a6787c`
- force push allowed: `False`

## B. Root Causes

| ID | Status | Root cause |
|---|---|---|
| RC-SEM-01 | FIXED_AND_FROZEN | The small spaCy model has no static word vectors and only weak context tensors; shared action matching lacked a sentence-level semantic encoder. |
| RC-MISS-01 | DEFERRED_SINGLE_ALLOWED_REVISION | Stage-2 action spans sometimes contain subordinate fragments (e.g. prepositional continuations) and non-core clause actions; the denominator is not obligation-scoped. |
| RC-ACTOR-01 | FROZEN_NO_CHANGE | Definition 6 is intentionally action-bound; Stage-2 actor-action maps are incomplete for some records, so the cell is legitimately unknown rather than guessed. |
| RC-ORDER-01 | FIXED_AND_FROZEN | Sun's paper requires U_r subset A_r x A_r but does not publish an automatic extraction algorithm; the project had no shared U_r adapter. |
| RC-ORDER-02 | DOCUMENTED_FROZEN | Frozen Stage-2 A_r does not contain the second endpoint (e.g. approving, informing, lifted) for R5-S7-T1/R5-S8-T1 and some nominalized cases. |
| RC-COV-01 | REPRESENTATION_LIMITATION_FROZEN | Ours extracts the `provide ... prior to further processing` predicate as one action and does not separately extract `process`; this is a Stage-2 representation coverage gap. |

## C. MPNet / Backend Comparison

- model: `D:\Paper\experiment\bpc-hybrid\.tmp\hf_cache\hub\models--sentence-transformers--all-mpnet-base-v2\snapshots\e8c3b32edf5434bc2275fc9bab85f82640a19130`
- core inference size MiB: `418.35`
- pooling: `sentence-transformers declared mean-token pooling (1_Pooling/config.json) + L2 normalize`
- selected gamma/theta: `0.55` / `0.45`

| Backend | gamma | theta | Sun macro | Ours macro | Sun micro | Ours micro | Sun order F1 | Ours order F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| sentence_transformers_all_mpnet_base_v2 | 0.55 | 0.45 | 0.4606 | 0.5206 | 0.4458 | 0.5341 | 0.5000 | 0.5000 |
| spacy_en_core_web_md | 0.80 | 0.40 | 0.4354 | 0.5012 | 0.4333 | 0.5224 | 0.5000 | 0.5000 |
| spacy_en_core_web_sm | 0.50 | 0.40 | 0.4703 | 0.4394 | 0.4715 | 0.5072 | 0.5000 | 0.4000 |

## D. Order Eligibility

| Requirement | Type | Evidence | Main metric? | Reason |
|---|---|---|---|---|
| R5-D-01 | TYPE_A_explicit_action_precedence | provide information prior to further processing | True | Explicit action-action precedence; Sun A_r contains a process endpoint; Ours may be unbound and therefore legitimately unknown. |
| R5-D-02 | TYPE_A_explicit_action_precedence | provide information prior to further processing | True | Explicit action-action precedence; same interface logic as R5-D-01. |
| R5-D-03 | TEMPORAL_CONSTRAINT_OUTSIDE_MAIN_DEF7_SCOPE | be informed before the restriction of processing is lifted | False | The second endpoint is a passive state/event, not a reliably extractable Stage-2 action in either method. |
| R5-D-04 | TEMPORAL_CONSTRAINT_OUTSIDE_MAIN_DEF7_SCOPE | carry out DPIA prior to the processing | False | Nominalised processing endpoint is not present as a distinct action in either method's A_r; retained as outside-scope diagnostic. |
| R5-D-05 | TEMPORAL_CONSTRAINT_OUTSIDE_MAIN_DEF7_SCOPE | consult supervisory authority prior to processing | False | Nominalised processing endpoint is not present as a distinct action in either method's A_r; retained as outside-scope diagnostic. |
| R5-D-06 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-D-07 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-D-08 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-D-09 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-D-10 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-D-11 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-D-12 | TYPE_B_trigger_precedence | notify after becoming aware of a breach | False | Event-trigger precedence; no deadline arithmetic scored. |
| R5-S1-T1 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-S1-T2 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-S1-T3 | TYPE_B_trigger_precedence | provide information after obtaining personal data | False | Event-trigger precedence; one-month deadline not evaluated. |
| R5-S1-T4 | TYPE_B_trigger_precedence | provide information after obtaining personal data | False | Event-trigger precedence; one-month deadline not evaluated. |
| R5-S2-T2 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-S3-T1 | TYPE_B_trigger_precedence | provide response after receipt of request | False | Event-trigger precedence; one-month deadline not evaluated. |
| R5-S3-T2 | TYPE_B_trigger_precedence | inform after receipt of request | False | Event-trigger precedence; one-month deadline not evaluated. |
| R5-S4-T1 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-S4-T2 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-S4-T3 | TYPE_A_explicit_action_precedence | inform controller before processing | True | Both actions are present in Sun and Ours Stage-2 A_r; development-only order supplement supplies the missing out_of_order control. |
| R5-S4-T4 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-S5-T1 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-S5-T2 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-S5-T3 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-S5-T4 | TYPE_C_deadline_arithmetic_only | provide written advice within eight weeks of receipt of request | False | Deadline arithmetic only; outside action-action Definition 7 scope. |
| R5-S6-T1 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-S6-T2 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-S6-T3 | TYPE_B_trigger_precedence | notify controller after becoming aware of a breach | False | Event-trigger precedence; deadline not evaluated. |
| R5-S6-T4 | None | None | False | No explicit action-action temporal relation in the source requirement. |
| R5-S7-T1 | ACTION_ACTION_SOURCE_EXPLICIT_BUT_ENDPOINT_UNBOUND | submit draft code before approving it | False | Source relation is action-action, but neither frozen Stage-2 A_r contains both endpoints; retained in diagnostics, not main F1. |
| R5-S8-T1 | ACTION_ACTION_SOURCE_EXPLICIT_BUT_ENDPOINT_UNBOUND | issue or renew certification after informing the supervisory authority | False | Source relation is action-action, but the informing endpoint is absent from both frozen Stage-2 A_r records; retained in diagnostics, not main F1. |

## E. Shared Rule Order Adapter

- adapter: `SharedRuleOrderAdapterV3`
- Gold used: `False`
- generated U_r: `{'sun': ['R5-D-01', 'R5-S4-T3', 'R5-D-02'], 'ours': ['R5-S4-T3']}`
- U_r generation rates: `{'sun': {'generated_main_requirements': 3, 'main_requirements': 3, 'rate': 1.0}, 'ours': {'generated_main_requirements': 1, 'main_requirements': 3, 'rate': 0.3333333333333333}}`

## F. Final Development Result

| Method | Precision | Recall | F1 |
|---|---:|---:|---:|
| Sun | 0.3814 | 0.5362 | 0.4458 |
| Ours | 0.4393 | 0.6812 | 0.5341 |

| Method | Missing F1 | Actor F1 | Order F1 | Macro-F1 | Coverage | Unknown rate |
|---|---:|---:|---:|---:|---:|---:|
| Sun | 0.4554 | 0.4262 | 0.5000 | 0.4606 | 0.6667 | 0.3333 |
| Ours | 0.4935 | 0.5684 | 0.5000 | 0.5206 | 0.8905 | 0.1095 |

## G. Improvement Attribution

- backend comparison: `{'sun': {'sm_to_mpnet_overall_micro_f1_delta': -0.02576158291703401, 'sm_to_mpnet_macro_f1_delta': -0.009706800598092591, 'sm_to_mpnet_missing_f1_delta': 0.20090009000900094, 'sm_to_mpnet_actor_f1_delta': -0.23002049180327871, 'sm_to_mpnet_order_f1_delta': 0.0}, 'ours': {'sm_to_mpnet_overall_micro_f1_delta': 0.026844532279314826, 'sm_to_mpnet_macro_f1_delta': 0.08123553307424025, 'sm_to_mpnet_missing_f1_delta': 0.2582123758594347, 'sm_to_mpnet_actor_f1_delta': -0.1145057766367138, 'sm_to_mpnet_order_f1_delta': 0.09999999999999998}}`
- order representation: `{'old_frozen_r1_order_f1_on_previous_scope': 0.0, 'new_selected_order_f1': 0.5, 'components': ['RC-ORDER-01 shared RuleRecord U_r adapter made order_relations non-empty where endpoints exist', 'RC-ORDER-02 capability-aligned eligibility moved endpoint-unbound requirements out of the main F1 and retained them as diagnostics', 'DEVELOPMENT-ONLY supplement supplied the missing R5-S4-T3 out_of_order control for an already-extracted action pair'], 'isolation_note': 'The order change is a bundle of adapter + eligibility + supplement; it is not claimed as a single algorithmic F1 delta.'}`

## H. Remaining Limitations

- Final unseen benchmark/Gold packet is not constructed; only five source-only candidate requirements remain.
- No Ours Stage-2 predictions exist for the unseen candidate requirements; explicit API authorization is required.
- Ours Stage-2 A_r lacks a distinct process endpoint for R5-D-01/R5-D-02, so order recall is limited there.
- R5-S7-T1/R5-S8-T1 are source action-action relations but their second endpoints are absent from both frozen Stage-2 A_r records.
- Actor unknown remains material for Sun due to Definition 6 action-bound coverage; Definition 6 was intentionally not changed.
- Missing-action precision remains limited by extra/fragment Stage-2 actions; no second action-scope revision was applied.

## I. Freeze Status

- SEMANTIC_BACKEND_FINAL_FROZEN = `True`
- GAMMA_FINAL_FROZEN = `True`
- THETA_FINAL_FROZEN = `True`
- MISSING_ACTION_METHOD_FROZEN = `True`
- ACTOR_METHOD_FROZEN = `True`
- ORDER_ELIGIBILITY_FROZEN = `True`
- ORDER_U_R_ADAPTER_FROZEN = `True`
- STAGE3_METHOD_FROZEN = `True`

## J. Final Table 3 Readiness

- FINAL_TABLE3_READY = `False`
- FINAL_UNSEEN_BENCHMARK_PREPARED = `False`
- API_AUTHORIZATION_PACKET_READY = `True`
- exact blocker: There is no authorized unseen Stage-2/Gold packet for a 12-16 requirement source-family-separated GDPR holdout. The five remaining benchmark-v2 candidate requirements are source-only candidates and have no BPMN mutation packet or Ours prediction.
- exact next action: User must approve the final unseen source split, Gold/BPMN freeze, and bounded Ours Stage-2 API calls.

## API Gate

- status: `API_AUTHORIZATION_REQUIRED`
- candidate unseen requirements: `['R5-S2-T1', 'R5-S2-T3', 'R5-S2-T4', 'R5-S3-T3', 'R5-S3-T4']`
- do not execute without explicit authorization: `True`
