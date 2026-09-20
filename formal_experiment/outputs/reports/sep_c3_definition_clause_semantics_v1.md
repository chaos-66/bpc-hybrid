# SEP-C3 Definition-Clause Semantics & Prompt Coverage Study v1

- Task: Definition-Clause Semantics & Prompt Coverage Study
- Role: evidence analyst / annotation-semantics researcher / engineering assistant
- New BPC / LLM / API calls: **0**
- Gold: `data/gold/stage2/estg150_formal_gold_v1.json`
- Predictions: persisted `sep_c3_targeted_refinement_v1` A/B/C/D canonical outputs
- Prompt material audited: `common_system.md`, `examples_E.md`, `semantic_rules_S.md`
- No Prompt was designed, modified, or tested in this round.

## 0. Executive summary

The definition-clause corpus contains **39 Gold definition clauses across 34 samples**; **29 samples** have a definition as their first clause and therefore are the record-level evaluator view. All **39/39 definition clauses have at least one Gold action span** (46 action spans total). The prior count of 20 all-arm modality failures is reproduced exactly at first-definition-sample level; at definition-clause level the count is **25/39** because later definition clauses also fail.

The dominant modality confusion is **definition -> obligation**, followed by definition -> prohibition. `shall` is the largest single confusion source: 15/15 definition clauses containing `shall` are non-definition in all four arms, and 12/20 first-definition all-wrong samples contain `shall` in the first clause. The second clear problem is **action emptiness**: E4 explicitly teaches that a definition clause has empty actions, and S rule 11 says a definition clause may have no actions; Gold instead gives action spans to 39/39 definition clauses.

E4 is therefore **`CONFLICTS_WITH_GOLD`** on action presence and under-covers definition conditions/constraints, though its `definition` modality label and its mostly-empty actor pattern are not the primary problem.

## 1. Corpus construction

| Corpus view | Count | Definition |
| --- | --- | --- |
| Gold clauses with modality == definition | 39 | clause-level corpus |
| Distinct samples with any definition clause | 34 | any-position corpus |
| First-clause definition samples | 29 | record-level evaluator view / prior report count |
| Definition action spans | 46 | all definitions |
| Definition clauses with empty action | 0 | Gold action occurrence |
| Definition clauses with actor | 2 | actor occurrence |
| Definition clauses with condition | 28 | condition occurrence |
| Definition clauses with constraint | 28 | constraint occurrence |
| Definition clauses with exception | 5 | exception occurrence |
| Broad definition-like candidates outside Gold definition label | 14 | manual-review lexical candidates |

The broad candidate set is deliberately recall-oriented and is not asserted to be a set of missed Gold definitions. It contains **14 clauses** with definition-like surface triggers but non-definition Gold labels. The strongest candidate is `estg_000505 c2`, which is near-identical to Gold definition `estg_000509 c2`.

## 2. Modality findings

### 2.1 Gold semantics of `definition` (Q1)

Gold `definition` is not limited to lexical definitions such as `X means Y`. The 39 clauses show at least six recurring semantic shapes:

1. Explicit definition / copular classification: `Profit is the difference`; `Income from employment (wages) is`; `Expenditure on repairs means`; `Dependants also include`.
2. Legal fiction / deeming: `shall be deemed`, `is deemed`, `shall be treated as`, `be deemed to be`.
3. Classification / membership: `shall constitute income from capital`, `be income from letting and leasing`, `are not eligible`, `are stock corporations`.
4. Scope / application: `Item 13 applies`, `the following applies`, `does not apply`, `also applies`.
5. Event/relational definitions: `occurs when`, `runs from`, `amounts to`, `is the case when`.
6. Enumerated definitions: `shall include:` followed by lists.

`shall` in a definition clause is therefore not deontic obligation. It functions as a definitional/legal-fictional marker in `shall include`, `shall be deemed`, `shall be treated`, `shall constitute`, `shall be assumed`, and `shall apply`.

### 2.2 Current Prompt modality coverage (Q2)

| Source | Current wording / behavior | Compatible with Gold? | Risk |
| --- | --- | --- | --- |
| Common | `- modality: label, evidence.` Required field only; no class semantics. | Partial | MISSING_GUIDANCE: no definition-class semantics. |
| E4 | `definition; evidence "means"; actors and actions empty` | Modality label yes; action/fields no | Conflict on action emptiness; narrow trigger coverage. |
| S2 | `label each clause obligation, prohibition, permission, or definition`; smallest sufficient trigger | Partial | MISSING_GUIDANCE: no definition semantics or `shall` ambiguity. |
| S11 | `a definition clause may have no actions` | Unsupported by Gold action distribution | POTENTIALLY_MISLEADING / conflict-adjacent. |
| R_A / R_C (A-D targeted arms) | No modality rule; R_A actor, R_C constraint recall | No direct effect | Do not correct definition modality/action. |
| Default v6 rule 19 (context) | same `actions may be empty` concept | Conflicts with Gold | May reinforce E4/S11 behaviour if v6 is used. |

### 2.3 Definition modality error patterns (Q3)

- First-definition samples: 29; all-four-arm non-definition: **20**.
- Definition clauses: 39; all-four-arm non-definition: **25**.
- `shall` definition clauses: 15; all-four-arm non-definition: **15**.

The 20 first-definition failures decompose as follows: 12 are obligation in all four arms, 6 are prohibition in all four arms, and 2 are mixed non-definition patterns. Thus the most common confusion is **definition -> obligation**; the second is **definition -> prohibition**.

Example ids:

```text
definition -> obligation: estg_000037 c1, estg_000071 c1, estg_000080 c4, estg_000082 c1, estg_000136 c1, estg_000293 c1, estg_000302 c1, estg_000414 c1, estg_000509 c2, estg_000522 c1, estg_000572 c1, estg_000664 c1, estg_000773 c1, estg_000776 c1
definition -> prohibition: estg_000020 c1, estg_000083 c1/c2, estg_000087 c1, estg_000209 c1/c2, estg_000210 c1, estg_000800 c1
mixed/non-standard: estg_000218 c1 (non_obligation/prohibition), estg_000232 c2 (obligation/assertion), estg_000854 c1 (obligation/permission)
```

### 2.4 Syntactic concentration (Q4)

| Construction family | Definition support | All-four-arm failure | Interpretation |
| --- | --- | --- | --- |
| `shall` + definitional/legal-fiction verb | 15 | 15 | Strongest concentration; model follows `shall` -> obligation. |
| explicit `means` | 1 | 0 | E4's own pattern is not the dominant failure. |
| `within the meaning` / copular classification | 7 | mixed | Model often labels definition but drops action; fewer modality errors. |
| deeming / legal fiction | 9 | most fail | `shall be deemed` is read as obligation; `is deemed` often is definition. |
| scope/application (`applies`, `does not apply`) | 7 | most fail | `applies` is read as obligation, `does not apply` as prohibition. |
| negative eligibility / status (`are not eligible`) | 2 | all fail | Model reads status as prohibition. |

## 3. `shall` specific audit (Q9 / section 9)

| Construction | Definition count | Predicted modality pattern | Action pattern |
| --- | --- | --- | --- |
| `shall include` | 1 | obligation x4 | action present; `include` |
| `shall be deemed` | 5 | mostly obligation; one prohibition association | `be deemed...` present but often boundary-shifted |
| `shall be treated` | 1 | obligation/prohibition x4 | predicate action present |
| `shall constitute` | 1 | obligation x4 | action present |
| `shall be assumed` | 2 | obligation x4 | action present/merged |
| `shall apply` | 1 | obligation x4 | action empty in A/B/C/D aligned clause |
| other `shall be ...` | 4 | obligation x4 mostly | mixed |

All 15 `shall` definition clauses are non-definition in all four arms. `shall` is therefore the largest single confusion source, but it is not the only one: `does not apply`, `applies`, and `are not eligible` also fail without `shall`.

## 4. Action findings

### 4.1 Why every definition clause has an action (Q1)

Gold treats the definitional predicate itself as the action. This includes copulas (`is`, `are shares`), definitional verbs (`means`, `include`), legal fictions (`be deemed`), classifications (`constitute`, `be income`), and scope predicates (`applies`, `does not apply`). The action is therefore not the regulated conduct: it is the definitional/classification predicate.

Gold action taxonomy by primary category:

| Primary taxonomy | Gold action spans | Examples |
| --- | --- | --- |
| action_span_includes_subordinate_phrase | 2 | is that the free drink allowance may not be sold by the employee and that it is only granted in such quantity as to actually preclude a sale; the additional amounts shall be treate |
| classification_verb | 9 | not form part; compensated; are shares; are not eligible; are not eligible; are stock corporations; constitute income from capital; be income from letting and leasing; be treated |
| copular_action | 6 | is the difference; is irrelevant; is; is the case; is subject; is obligated to follow |
| deeming_legal_fiction | 10 | shall be deemed as the acquisition cost; be deemed to exist; is deemed; be determined; be deemed discharged; be assumed; be deemed to be; be deemed a single activity; be assumed; b |
| definitional_verb | 3 | shall include; include; means |
| other_event_predicate | 6 | are acquired; are newly issued; are acquired; is declared; leaves; works |
| relational_predicate | 10 | amounts to; applies; does not apply; applies; also applies; does not apply; runs; occurs; apply; does not apply |

Multiple actions are present in 4 definition clauses (one with 2 actions, three with 3 actions). The 46 spans are predominantly short predicate-centred units.

### 4.2 E4's definition action demonstration (Q2)

E4 explicitly states `actors and actions empty` for its definition clause. Therefore the earlier suspicion is confirmed: **E4 does demonstrate definition action = empty**. The action-empty count is 0/39 in Gold. This is a direct prompt-Gold mismatch on action presence.

### 4.3 S action guidance (Q3)

See `sep_c3_S_modality_action_audit.md`. Core result: S4 is broadly compatible with the 46 Gold actions as verb-centred units, S8 is compatible except estg_000020, and S11 is unsupported by the Gold action distribution.

## 5. Definition action boundary taxonomy

| Taxonomy | Primary count | Gold evidence | Boundary note |
| --- | --- | --- | --- |
| copular action | 6 | is, are shares, are stock corporations, is the case | Short predicative complements may be included. |
| definitional verb | 3 | means, include, shall include | Object/enumerated complements often move to constraints. |
| classification verb | 9 | constitute, be income, are not eligible, be treated | Status/classification predicate is still action. |
| deeming / legal fiction | 10 | shall be deemed, is deemed, be assumed | `shall` can be inside the definition action. |
| relational predicate | 10 | applies, does not apply, runs, amounts to | Scope/application counts as definition here. |
| noun-phrase predicate | 0 | none in definition corpus | No support. |
| action span includes subordinate phrase | 2 | estg_000020, estg_000083 c2 | Small outlier family. |
| other event predicate | 6 | are acquired, are newly issued, leaves, works | Needs manual boundary review. |
| uncertain | 0 | manual flags | Not forced into a category. |

## 6. Condition / constraint in definition clauses (secondary)

- Conditions: 28/39 definition clauses.
- Constraints: 28/39 definition clauses.
- Exceptions: 5/39 definition clauses.
- All three empty: 0/39.
- Only estg_000020 has action-condition span overlap in the definition corpus; it has 2 overlapping condition spans.
- No definition action span overlaps a Gold constraint or exception span.

This does not justify a new R_C study in this round, but it shows that E4's empty condition/constraint pattern is not representative of definition clauses.

## 7. Gold consistency audit pointer

See `sep_c3_definition_gold_consistency_audit.md`.

## 8. E4 coverage audit pointer

See `sep_c3_E4_coverage_audit.md`. Status: **`CONFLICTS_WITH_GOLD`**.

## 9. E examples coverage matrix pointer

See `sep_c3_E_examples_coverage_matrix.md`.

## 10. S modality/action audit pointer

See `sep_c3_S_modality_action_audit.md`.

## 11. Instruction missing vs conflict diagnosis

| Stable failure | Diagnosis | Sample evidence |
| --- | --- | --- |
| `shall` definition -> obligation/prohibition | `MISSING_GUIDANCE` | 15/15 shall definition clauses fail all four arms |
| negative scope/status (`does not apply`, `are not eligible`) -> prohibition | `MISSING_GUIDANCE` + `AMBIGUOUS_GUIDANCE` | estg_000083 c1, estg_000209 c1, estg_000210 c1, estg_000800 c1 |
| definition -> non-definition for `applies` | `AMBIGUOUS_GUIDANCE` | estg_000071 c1 vs estg_000128 c2; 7 definition vs 5 non-definition apply clauses |
| definition action empty | `CONFLICTING_GUIDANCE` | E4 says empty; Gold has 39/39 non-empty |
| definition action boundary shift (be/deemed/determined/assumed) | `GUIDANCE_PRESENT_BUT_EXECUTION_UNSTABLE` | estg_000080, estg_000136, estg_000509 etc. |
| exact action complement inclusion | `GOLD_SEMANTICS_UNCLEAR` | estg_000020, estg_000031 vs estg_000273, estg_000083 c2 |
| same `shall be assumed` text -> two Gold modalities | `GOLD_SEMANTICS_UNCLEAR` | estg_000505 c2 vs estg_000509 c2 |

Approximate stable-failure accounting this round:

- `MISSING_GUIDANCE`: modality class semantics and `shall`-in-definition coverage; at least 15/25 all-wrong clauses are directly `shall`-driven.
- `CONFLICTING_GUIDANCE`: action emptiness from E4/S11 (39/39 Gold counterexamples).
- `AMBIGUOUS_GUIDANCE`: S4 vs S11 for definition action; apply-family modality.
- `GUIDANCE_PRESENT_BUT_EXECUTION_UNSTABLE`: definition action boundary variants across arms.
- `GOLD_SEMANTICS_UNCLEAR`: estg_000505/509 pair; apply family; action complement granularity.

## 12. Candidate annotation principles

# Candidate Annotation Principles (NOT YET PROMPT RULES)

- Status: **`NOT YET A PROMPT RULE`**
- API calls: **0**.

## Candidate principle 1: Definition clauses receive an action span

> Definition clauses still receive an action span representing the definitional predicate.

- Support: 39/39 definition clauses have at least one Gold action; 46 action spans.
- Counterexamples: 0 empty-action definition clauses.
- Unresolved cases: estg_000020 action contains condition material; estg_000083 c2 includes subject + coordination; estg_000112 is a fragment.
- Confidence: high for action presence, medium for exact boundary.

## Candidate principle 2: `definition` modality is broader than `means`

> Gold `definition` covers explicit definitions, legal fictions/classification (`shall be deemed`, `shall be treated`, `shall constitute`, `shall include`), status predicates (`are not eligible`), and scope-application predicates (`applies`, `does not apply`). Surface `shall` does not by itself imply obligation.

- Support: 39 definition clauses; 15 with `shall`; 7 with apply/application; 7 within-the-meaning/copular classification.
- Counterexamples / unresolved: 5 non-definition apply clauses; 2 obligation `shall apply`; estg_000505 c2 vs estg_000509 c2 near-identical pair.
- Confidence: medium-high for the broad coverage; medium because Gold modality semantics still has unresolved same-trigger cases.

## Candidate principle 3: Definition action boundaries are predicate-centred, but not uniformly complement-free

> Definition action spans are predicate-centred; complements that are conditions, constraints, or exception material are generally kept out, but short predicative complements may be included depending on construction.

- Support: 44/46 action spans have no measured overlap with condition/constraint/exception; most spans are short predicates.
- Counterexamples / unresolved: estg_000020 action contains two condition spans; estg_000083 c2 contains subject + coordination; copular complement inclusion varies.
- Confidence: medium-low; requires annotation adjudication before Prompt use.

These candidate principles are annotation-level observations only. They must not be rewritten as Prompt instructions in this round.


## 13. Sample-level decision table (all 39 definition clauses)

| Sample | Gold modality | Pred modality A/B/C/D | Gold action | Pred action | E4-like? | S conflict? | Error type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| estg_000020 c1 | definition | prohibition/prohibition/prohibition/prohibition | is that the free drink allowance may not be sold by the employee and that it is only granted in such quantity as to actually preclude a sale | sold || granted | E4 yes | S8 direct | definition_to_prohibition_all_arms |
| estg_000031 c1 | definition | definition/definition/definition/definition | is the difference |  | E4 yes | S11 risk | partially_correct |
| estg_000037 c1 | definition | obligation/obligation/obligation/obligation | shall include | include | E4 yes | S11 risk | definition_to_obligation_all_arms |
| estg_000040 c1 | definition | definition/definition/definition/definition | include |  | E4 yes | S11 risk | partially_correct |
| estg_000046 c2 | definition | definition/definition/definition/statement | amounts to | amounts to | E4 yes | S11 risk | partially_correct |
| estg_000057 c1 | definition | definition/definition/definition/definition | means |  | E4 yes | S11 risk | partially_correct |
| estg_000071 c1 | definition | obligation/obligation/obligation/obligation | applies | Item 13 applies | E4 yes | S11 risk | definition_to_obligation_all_arms |
| estg_000080 c4 | definition | obligation/obligation/obligation/obligation | shall be deemed as the acquisition cost | be deemed as the acquisition cost (deemed acquisition cost) | E4 yes | S11 risk | definition_to_obligation_all_arms |
| estg_000082 c1 | definition | obligation/obligation/obligation/obligation | not form part | does not form part of the acquisition or production costs of the asset || be reported as a receivable | E4 yes | S11 risk | definition_to_obligation_all_arms |
| estg_000083 c1 | definition | prohibition/prohibition/prohibition/prohibition | does not apply | apply | E4 yes | S11 risk | definition_to_prohibition_all_arms |
| estg_000083 c2 | definition | prohibition/prohibition/prohibition/prohibition | the additional amounts shall be treated as business income and the reduced amounts as business expenses | apply | E4 yes | S11 risk | definition_to_prohibition_all_arms |
| estg_000087 c1 | definition | prohibition/prohibition/prohibition/prohibition | be deemed to exist | exchange || deemed to exist || takes place || result in liquidation taxation | E4 yes | S11 risk | definition_to_prohibition_all_arms |
| estg_000112 c1 | definition | none/None/definition/definition | is deemed | acquisition | E4 yes | S11 risk | partially_correct |
| estg_000136 c1 | definition | obligation/obligation/obligation/obligation | be determined | be determined | E4 yes | S11 risk | definition_to_obligation_all_arms |
| estg_000164 c1 | definition | definition/definition/definition/definition | applies |  | E4 yes | S11 risk | partially_correct |
| estg_000164 c2 | definition | definition/obligation/obligation/obligation | compensated | compensated | E4 yes | S11 risk | partially_correct |
| estg_000195 c1 | definition | definition/definition/definition/definition | is irrelevant |  | E4 yes | S11 risk | partially_correct |
| estg_000208 c3 | definition | definition/definition/definition/definition | are shares |  | E4 yes | S11 risk | partially_correct |
| estg_000208 c4 | definition | definition/definition/definition/definition | are newly issued |  | E4 yes | S11 risk | partially_correct |
| estg_000209 c1 | definition | prohibition/prohibition/prohibition/prohibition | are not eligible | are not eligible | E4 yes | S11 risk | definition_to_prohibition_all_arms |
| estg_000209 c2 | definition | prohibition/prohibition/prohibition/prohibition | also applies | are not eligible | E4 yes | S11 risk | definition_to_prohibition_all_arms |
| estg_000210 c1 | definition | prohibition/prohibition/prohibition/prohibition | are not eligible | are not eligible | E4 yes | S11 risk | definition_to_prohibition_all_arms |
| estg_000210 c2 | definition | definition/definition/definition/definition | are stock corporations |  | E4 yes | S11 risk | partially_correct |
| estg_000218 c1 | definition | non_obligation/prohibition/prohibition/prohibition | does not apply | apply | E4 yes | S11 risk | definition_to_other_or_mixed_nondefinition |
| estg_000232 c2 | definition | obligation/assertion/obligation/assertion | runs | runs from the time of the deposit of those profit participation certificates or shares whose acquisition costs were deducted as special expenses | E4 yes | S11 risk | definition_to_other_or_mixed_nondefinition |
| estg_000273 c1 | definition | definition/definition/definition/definition | is |  | E4 yes | S11 risk | partially_correct |
| estg_000283 c1 | definition | definition/definition/definition/definition | occurs | leaves their duty station (office, permanent establishment, factory premises, warehouse, etc.) on the employer’s orders to perform work duties || works so far away from their permanent place of residence (family home) that they cannot reasonably be expected to return to that permanent place of residence (family home) on a daily basis | E4 yes | S11 risk | partially_correct |
| estg_000293 c1 | definition | obligation/obligation/obligation/obligation | constitute income from capital | constitute income from capital | E4 yes | S11 risk | definition_to_obligation_all_arms |
| estg_000302 c1 | definition | obligation/obligation/obligation/obligation | be income from letting and leasing | be income from letting and leasing | E4 yes | S11 risk | definition_to_obligation_all_arms |
| estg_000414 c1 | definition | obligation/obligation/obligation/obligation | be deemed discharged | deemed discharged || held liable || carried out | E4 yes | S11 risk | definition_to_obligation_all_arms |
| estg_000417 c1 | definition | obligation/obligation/definition/definition | is the case | is subject to the direction of the employer || follow the employer's instructions within the business organization of the employer | E4 yes | S11 risk | partially_correct |
| estg_000509 c2 | definition | obligation/obligation/obligation/obligation | be assumed | be taxed like a current payment in accordance with the wage tax rate schedule | E4 yes | S11 risk | definition_to_obligation_all_arms |
| estg_000522 c1 | definition | obligation/obligation/obligation/obligation | be treated | treated as such | E4 yes | S11 risk | definition_to_obligation_all_arms |
| estg_000572 c1 | definition | obligation/obligation/obligation/obligation | be deemed to be | be deemed to be at least the actually expended working time | E4 yes | S11 risk | definition_to_obligation_all_arms |
| estg_000664 c1 | definition | obligation/obligation/obligation/obligation | apply |  | E4 yes | S11 risk | definition_to_obligation_all_arms |
| estg_000773 c1 | definition | obligation/obligation/obligation/obligation | be deemed a single activity | deemed a single activity | E4 yes | S11 risk | definition_to_obligation_all_arms |
| estg_000776 c1 | definition | obligation/obligation/obligation/obligation | be assumed | assumed | E4 yes | S11 risk | definition_to_obligation_all_arms |
| estg_000800 c1 | definition | prohibition/prohibition/prohibition/prohibition | does not apply | apply | E4 yes | S11 risk | definition_to_prohibition_all_arms |
| estg_000854 c1 | definition | obligation/obligation/permission/obligation | be deemed secure | be deemed secure || may be withdrawn | E4 yes | S11 risk | definition_to_other_or_mixed_nondefinition |

## 14. Field priority re-evaluation

# SEP-C3 Definition Field Priority Re-evaluation

- API calls: **0**.
- This is an evidence status only; it does not authorize Prompt design or modification.

| Field | Current evidence status | Rationale | Remaining unresolved issue |
| --- | --- | --- | --- |
| modality | READY_FOR_PROMPT_DESIGN_REVIEW | Stable, corpus-wide confusion: 20/29 first-definition samples and 25/39 definition clauses are non-definition in all four arms; 15/15 definition clauses containing `shall` are all four arms wrong. | `apply`/`shall apply` family and the near-identical estg_000505 c2 vs estg_000509 c2 pair need annotation adjudication. |
| action | READY_FOR_PROMPT_DESIGN_REVIEW (presence); NEEDS_MORE_GOLD_ANALYSIS (exact boundary) | Gold definition action presence is unambiguous: 39/39 clauses; E4 explicit empty-action example conflicts with Gold and gives a high-risk local explanation for empty definition actions. | Action complement/boundary granularity is heterogeneous; taxonomy is partly manual-review. |
| condition | NEEDS_MORE_GOLD_ANALYSIS | 28/39 definition clauses have conditions, so definition-context condition coverage is real but was secondary in this round. | Interaction with definition action boundaries and E4 emptiness is unresolved. |
| constraint | NEEDS_MORE_GOLD_ANALYSIS | 28/39 definition clauses have constraints; prior condition/constraint boundary work remains relevant. | Definition-specific constraint interaction and R_C scope are unresolved. |

`READY_FOR_PROMPT_DESIGN_REVIEW` means the evidence is sufficient for a Prompt design review, not that a Prompt should be changed or written by this study.


## 15. Final answers

1. Definition clause corpus: **39 clauses / 34 samples**; **29** first-definition samples.
2. Modality four-arm all-wrong: **20/29** first-definition samples; **25/39** definition clauses.
3. Most common modality confusion: **definition -> obligation**, then **definition -> prohibition**.
4. `shall` as main confusion source: **yes, largest single source**; 15 definition clauses contain `shall`, and all 15 fail all four arms; 12/20 first-definition all-wrong samples contain `shall`.
5. Gold definition action pattern: **46 predicate-centred action spans** across 39 clauses; copular, definitional, classification, deeming, relational, and event predicates.
6. 39/39 action check: **confirmed**; empty-action definition clauses = 0.
7. E4 vs Gold: **conflicts on action emptiness**; E4 status `CONFLICTS_WITH_GOLD`.
8. E4 misleading modality/action: modality label itself is not the conflict; **action emptiness is directly misleading**; condition/constraint emptiness is under-representative.
9. Current S modality/action rules: **S2 missing definition semantics; S11 conflict-adjacent/unsupported; S8 has one direct Gold counterexample (estg_000020); S4 is mostly compatible but boundary-ambiguous**.
10. Main stable action-boundary pattern: definitional predicate gets an action; conditions/constraints/exceptions are generally separate, with a small subordinate/complement outlier family.
11. Gold inconsistency: **suspected**; strongest case is estg_000505 c2 vs estg_000509 c2; apply family also needs adjudication. No Gold was modified.
12. Instruction diagnosis counts: `MISSING_GUIDANCE` (shall/class semantics), `CONFLICTING_GUIDANCE` (action empty), `AMBIGUOUS_GUIDANCE` (S4/S11; apply family), `GUIDANCE_PRESENT_BUT_EXECUTION_UNSTABLE` (action boundary), `GOLD_SEMANTICS_UNCLEAR` (same-text modality pair).
13. Stable candidate annotation principle: **yes**; strongest is definition clauses still receive an action span (39/39 support, 0 counterexamples).
14. Counterexamples: **0** for action presence; **1 clause / 2 condition spans** for the no-action-condition-overlap boundary principle; **1 near-identical pair** for modality uniformity.
15. Modality status: **`READY_FOR_PROMPT_DESIGN_REVIEW`**, with unresolved same-trigger annotation cases.
16. Action status: **`READY_FOR_PROMPT_DESIGN_REVIEW` for presence; `NEEDS_MORE_GOLD_ANALYSIS` for exact boundary**.
17. Condition/constraint new evidence: definition clauses frequently contain both (28/39 each), but this round did not extend R_C.
18. Reports path: `formal_experiment/outputs/reports/sep_c3_definition_*`.
19. Script/test: `formal_experiment/scripts/analyze_sep_c3_definition_clause_v1.py`, `formal_experiment/tests/test_sep_c3_definition_clause_v1.py`.
20. Git commit/push status: scoped commit and normal push were performed after report generation; see final task response.
21. Unresolved issues: apply-family modality, estg_000505/509 inconsistency, action-boundary taxonomy, E4 wording (not modified).

## 16. Stop condition

No Prompt design, no API calls, no new experiment arms. This report stops at annotation semantics and evidence.
