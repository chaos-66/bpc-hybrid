# SEP-C3 Definition-Clause Adjudication v1

- Task: Definition-Clause Adjudication & Prompt-Design Gate
- Role: evidence analyst / annotation-semantics reviewer / engineering assistant
- New BPC / LLM / API calls: **0**
- Prompt modifications: **none**
- Gold modifications: **none**
- Action: adjudicate modality/action presence only; no Prompt design.

## 1. Executive summary

Gold contains **39 definition clauses** across **34 samples**; **29 samples** have a definition as first clause. All **46 action spans** occur in definition clauses; empty-action definition clauses = **0**. The four-arm non-definition errors remain **25/39** at clause level and **20/29** at first-definition sample level. All **15** definition clauses containing `shall` are non-definition in all four arms.

The adjudication has two distinct outcomes:

- **Definition action presence is stable.** All 39 definition clauses receive an action span, all 46 spans lie inside their clause spans, and every span contains a predicate marker. No exception or segmentation artefact changes presence.
- **Definition modality is broad but not surface-decidable.** Legal fiction, classification, and scope/application are genuine Gold definition patterns. However, the `apply` family and the near-identical `shall be assumed` pair show that `shall` cannot be interpreted as definition or deontic from surface form alone. The strongest unresolved case is `estg_000505 c2` vs `estg_000509 c2`.

## 2. Corpus and method

| Item | Value |
| --- | --- |
| Gold definition clauses | 39 |
| Definition samples (any position) | 34 |
| First-definition samples | 29 |
| Definition action spans | 46 |
| Definition clauses with empty action | 0 |
| Definition clauses with actor | 2 |
| Definition clauses with condition | 28 |
| Definition clauses with constraint | 28 |
| Definition clauses with exception | 5 |
| Definition clauses with condition/constraint/exception all empty | 0 |
| Definition clauses non-definition in all four arms | 25 |
| First-definition samples non-definition in all four arms | 20 |
| Definition clauses containing shall | 15 |
| Shall-definition clauses non-definition in all four arms | 15 |

Sources: frozen Gold, persisted A/B/C/D `sep_c3_targeted_refinement_v1` canonical predictions, and the existing E/S prompt modules. No API was called and no new experiment was started.

## 3. `estg_000505 c2` vs `estg_000509 c2`

### `estg_000505` c2

- Source text: `To the extent the limits of the first and second sentences are exceeded, such other emoluments shall be taxed like current emoluments according to the wage tax scale; in this respect, a monthly wage payment period shall be assumed.`
- Clause text: `in this respect, a monthly wage payment period shall be assumed`
- Context previous: `To the extent the limits of the first and second sentences are exceeded, such other emoluments shall be taxed like current emoluments according to the wage tax scale`
- Context next: ``

Gold six fields:

```json
{
  "modality": "obligation",
  "actors": [],
  "actions": [
    {
      "text": "be assumed",
      "start": 220,
      "end": 230,
      "id": "c2_action_1"
    }
  ],
  "conditions": [],
  "constraints": [
    {
      "text": "a monthly wage payment period",
      "start": 184,
      "end": 213,
      "id": "c2_constraint_1"
    }
  ],
  "exceptions": []
}
```

Clause segmentation:

| clause_id | modality | clause_span | action_texts |
| --- | --- | --- | --- |
| c1 | obligation | To the extent the limits of the first and second sentences are exceeded, such other emoluments shall be taxed like current emoluments according to the wage tax scale | be taxed |
| c2 | obligation | in this respect, a monthly wage payment period shall be assumed | be assumed |

A/B/C/D predictions:

| Arm | modality | modality_evidence | actions | conditions | constraints | exceptions |
| --- | --- | --- | --- | --- | --- | --- |
| A | obligation |  | be taxed like current emoluments according to the wage tax scale \|\| a monthly wage payment period shall be assumed | To the extent the limits of the first and second sentences are exceeded |  |  |
| B | obligation |  | be taxed like current emoluments according to the wage tax scale \|\| be assumed | To the extent the limits of the first and second sentences are exceeded | in this respect |  |
| C | obligation |  | be taxed like current emoluments according to the wage tax scale | To the extent the limits of the first and second sentences are exceeded | according to the wage tax scale |  |
| D | obligation |  | be taxed like current emoluments according to the wage tax scale | To the extent the limits of the first and second sentences are exceeded | according to the wage tax scale |  |

### `estg_000509` c2

- Source text: `(10) Other remuneration that does not fall under subsections 1 to 8 shall be taxed like a current payment in accordance with the wage tax rate schedule; for this purpose, a monthly wage payment period shall be assumed.`
- Clause text: `for this purpose, a monthly wage payment period shall be assumed.`
- Context previous: `(10) Other remuneration that does not fall under subsections 1 to 8 shall be taxed like a current payment in accordance with the wage tax rate schedule`
- Context next: ``

Gold six fields:

```json
{
  "modality": "definition",
  "actors": [],
  "actions": [
    {
      "text": "be assumed",
      "start": 207,
      "end": 217,
      "id": "c2_action_1"
    }
  ],
  "conditions": [
    {
      "text": "for this purpose",
      "start": 153,
      "end": 169,
      "id": "c2_condition_1"
    }
  ],
  "constraints": [
    {
      "text": "a monthly wage payment period",
      "start": 171,
      "end": 200,
      "id": "c2_constraint_1"
    }
  ],
  "exceptions": []
}
```

Clause segmentation:

| clause_id | modality | clause_span | action_texts |
| --- | --- | --- | --- |
| c1 | obligation | (10) Other remuneration that does not fall under subsections 1 to 8 shall be taxed like a current payment in accordance with the wage tax rate schedule | be taxed |
| c2 | definition | for this purpose, a monthly wage payment period shall be assumed. | be assumed |

A/B/C/D predictions:

| Arm | modality | modality_evidence | actions | conditions | constraints | exceptions |
| --- | --- | --- | --- | --- | --- | --- |
| A | obligation |  | be taxed like a current payment in accordance with the wage tax rate schedule | Other remuneration that does not fall under subsections 1 to 8 | in accordance with the wage tax rate schedule |  |
| B | obligation |  | be taxed like a current payment in accordance with the wage tax rate schedule |  | that does not fall under subsections 1 to 8 |  |
| C | obligation |  | be taxed like a current payment |  | in accordance with the wage tax rate schedule |  |
| D | obligation |  | be taxed like a current payment in accordance with the wage tax rate schedule |  | in accordance with the wage tax rate schedule |  |

### Q1-Q3 adjudication

**Q1 — Is there enough semantic/contextual difference?** No. The two c2 propositions are essentially the same: 'a monthly wage payment period shall be assumed'. Both have no actor, the same action 'be assumed', and 'a monthly wage payment period' as a Gold constraint. The difference is not sufficient to explain a Gold modality shift from obligation to definition.

**Q2 — If yes, what is the difference?** Only surface/deictic differences exist: 000505 uses 'in this respect', while 000509 uses 'for this purpose'; 000509 c2 ends with a period and Gold annotates 'for this purpose' as a condition, whereas 000505 does not annotate that condition. These are two renderings of the same legal-fiction/computational-basis statement; they do not establish a deontic-vs-definition semantic boundary.

**Q3 — Marking.** `POTENTIAL_GOLD_INCONSISTENCY`. Gold is not modified.

## 4. Apply / applies family

Core active `apply/applies` family: **12 clauses**, **7 definition** and **5 non-definition**. The table below keeps the full clause and Gold action; the analytical question is whether a stable semantic difference exists.

| Sample | Clause | Full clause | Context (prev / next) | Gold modality | Gold action | Why definition/non-definition? | Confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| estg_000071 | c1 | For registered traders, Item 13 applies | next: The lump-sum depreciation is claimed only to the extent that no parti… | definition | applies | The clause says which item governs a class of traders; no duty-bearer or regulated conduct is expressed. | medium-high |
| estg_000083 | c1 | This does not apply if the input tax is adjusted under Section 12(10) and (11) of the Turnover Tax Act 1972 | next: in this case, the additional amounts shall be treated as business inc… | definition | does not apply | The clause defines a non-application case and carries the exception; no command to an actor is expressed. | high |
| estg_000164 | c1 | For the consideration of these expenses, the following applies: | next: a) For a one-way distance between the residence and the place of work… | definition | applies | An introductory applicability statement for the following computation rules; no actor or duty is expressed. | medium |
| estg_000209 | c2 | this also applies to capital reductions by a stock corporation or a limited liability company as the legal predecessor of the stock corporation (Sections 219 and 245 of the Stock Corporation Act 1965, Section 2 of the Federal Act on the Transformation of Commercial Companies, Federal Law Gazette) | prev: Shares issued as a result of a capital increase are not eligible if t… | definition | also applies | The clause extends a classification/eligibility rule to capital reductions; it does not impose a new behavioural duty. | medium |
| estg_000218 | c1 | In the case of a reduction in deductible insurance premiums (Section 1(2), last sentence), the notification obligation does not apply if the refunded amounts are offset against future insurance premiums | next: 2. a) Subsequent taxation of amounts tied up for eight years (Section… | definition | does not apply | The clause defines when the notification obligation does not apply; it is a scope/exception statement. | high |
| estg_000664 | c1 | The following shall apply to this provision: | next: Certain income, in particular foreign income, may be wholly or partia… | definition | apply | The clause introduces the applicability of a provision and contains no actor/duty-bearing predicate. | medium-high |
| estg_000800 | c1 | This does not apply as long as the sponsoring undertaking suspends the contribution payments (Section 4(4) no. 2 of the Income Tax Act 1988) | next: d) The pension commitments of the fund may not exceed 80% of the last… | definition | does not apply | The clause defines a non-application condition/exception; no deontic actor is expressed. | high |
| estg_000056 | c1 | (7) For buildings that form part of the fixed assets and are let for consideration for residential purposes to persons who are not employees of the enterprise, the following shall apply with regard to repair expenses: | next: Repair expenses that are incurred using correspondingly earmarked tax… | obligation | apply | Gold treats the clause as an obligation imposing that repair-expense rules apply; it is not merely a definition of scope. | medium |
| estg_000128 | c2 | Section 10(2) last sentence shall apply. | prev: (2) A transfer is only permissible if 1. the disposed-of asset at the… | obligation | apply | Gold reads the cross-reference as a mandatory application of Section 10(2), not as a definition. | high |
| estg_000145 | c1 | (6) Taxpayers who determine their profit in accordance with Section 4(3) may apply in the tax return for an amount to be left tax-free for the notional severance pay claims existing at the end of the business year | — | permission | apply | 'apply' here means to make/submit an application; it is an actor action and not the applicability predicate under review. | high |
| estg_000208 | c2 | Subsection (1)(3) shall also apply if, within the group of persons referred to in point 1, the lender or loan debtor on the one hand and the developer (owner) or housing applicant (beneficiary, tenant) on the other hand are not identical | prev: Similarly, amounts for which the reclaim of refunded income tax (wage… \|\| next: Young shares within the meaning of subsection (1)(4) are shares, aa)… | obligation | apply | Gold treats the extension of subsection (1)(3) as a normative application requirement in this context. | medium |
| estg_000306 | c1 | For buildings serving residential purposes, the following applies with respect to repair and maintenance expenses | next: Repair and maintenance expenses that are incurred using corresponding… | obligation | applies | Surface-parallel to definitional introductory 'applies', but Gold labels this obligation; no stable Gold discriminator is visible. | low-medium |

Observations that are merely analytical dimensions, not Prompt rules:

- `may apply` in `estg_000145 c1` is a **different verb sense** (submit an application); it is not the applicability predicate and should not be used as a contrastive definition/obligation case.
- `does not apply` is definitional in all Gold examples (`estg_000083 c1`, `estg_000218 c1`, `estg_000800 c1`): it defines scope/exception, not conduct.
- `applies/applies to` is definitional in `estg_000071 c1`, `estg_000164 c1`, and `estg_000209 c2`.
- `shall apply` is definitional in `estg_000664 c1` but obligation in `estg_000056 c1`, `estg_000128 c2`, and `estg_000208 c2`.
- `the following applies` is definitional in `estg_000164 c1` but obligation in `estg_000306 c1`; this near-identical pair prevents a stable surface or introductory statement rule.

**Conclusion:** a semantic distinction can be *described* (scope/classification statement vs deontic application command), but it is **not stably operationalized by Gold** in the current apply family. Mark the apply-family modality boundary `NEEDS_GOLD_ADJUDICATION`.

## 5. `shall be determined`: `estg_000136` vs `estg_000812`

### `estg_000136` c1

- Source text: `The assets to which the reserves (tax-free amounts) may be transferred shall be determined by the assets in respect of which the hidden reserves were disclosed (paragraph 3).`
- Clause text: `The assets to which the reserves (tax-free amounts) may be transferred shall be determined by the assets in respect of which the hidden reserves were disclosed (paragraph 3)`
- Context previous: ``
- Context next: `The assets to which the reserves (tax-free amounts) may be transferred`

Gold six fields:

```json
{
  "modality": "definition",
  "actors": [],
  "actions": [
    {
      "text": "be determined",
      "start": 77,
      "end": 90,
      "id": "c1_action_1"
    }
  ],
  "conditions": [],
  "constraints": [
    {
      "text": "by the assets in respect of which the hidden reserves were disclosed (paragraph 3)",
      "start": 91,
      "end": 173,
      "id": "c1_constraint_1"
    }
  ],
  "exceptions": []
}
```

Clause segmentation:

| clause_id | modality | clause_span | action_texts |
| --- | --- | --- | --- |
| c1 | definition | The assets to which the reserves (tax-free amounts) may be transferred shall be determined by the assets in respect of which the hidden reserves were disclosed (paragraph 3) | be determined |
| c2 | permission | The assets to which the reserves (tax-free amounts) may be transferred | be transferred |

A/B/C/D predictions:

| Arm | modality | modality_evidence | actions | conditions | constraints | exceptions |
| --- | --- | --- | --- | --- | --- | --- |
| A | obligation | shall | be determined |  | by the assets in respect of which the hidden reserves were disclosed (paragraph 3) |  |
| B | obligation | shall | determined |  | by the assets in respect of which the hidden reserves were disclosed (paragraph 3) |  |
| C | obligation | shall | be determined |  | by the assets in respect of which the hidden reserves were disclosed (paragraph 3) |  |
| D | obligation | shall | be determined |  | by the assets in respect of which the hidden reserves were disclosed (paragraph 3) |  |

### `estg_000812` c1

- Source text: `For commercial enterprises (Section 2) that are required to keep books under commercial law provisions, and for trading and business cooperatives, the profit shall be determined in accordance with Section 5 of the Income Tax Act 1988.`
- Clause text: `For commercial enterprises (Section 2) that are required to keep books under commercial law provisions, and for trading and business cooperatives, the profit shall be determined in accordance with Section 5 of the Income Tax Act 1988`
- Context previous: ``
- Context next: ``

Gold six fields:

```json
{
  "modality": "obligation",
  "actors": [],
  "actions": [
    {
      "text": "be determined",
      "start": 164,
      "end": 177,
      "id": "c1_action_1"
    }
  ],
  "conditions": [
    {
      "text": "For commercial enterprises (Section 2) that are required to keep books under commercial law provisions",
      "start": 0,
      "end": 102,
      "id": "c1_condition_1"
    },
    {
      "text": "for trading and business cooperatives",
      "start": 108,
      "end": 145,
      "id": "c1_condition_2"
    }
  ],
  "constraints": [
    {
      "text": "in accordance with Section 5 of the Income Tax Act 1988",
      "start": 178,
      "end": 233,
      "id": "c1_constraint_1"
    }
  ],
  "exceptions": []
}
```

Clause segmentation:

| clause_id | modality | clause_span | action_texts |
| --- | --- | --- | --- |
| c1 | obligation | For commercial enterprises (Section 2) that are required to keep books under commercial law provisions, and for trading and business cooperatives, the profit shall be determined in accordance with Section 5 of the Income Tax Act 1988 | be determined |

A/B/C/D predictions:

| Arm | modality | modality_evidence | actions | conditions | constraints | exceptions |
| --- | --- | --- | --- | --- | --- | --- |
| A | obligation | shall | the profit shall be determined |  | in accordance with Section 5 of the Income Tax Act 1988 |  |
| B | obligation | shall | the profit shall be determined | For commercial enterprises (Section 2) that are required to keep books under commercial law provisions, and for trading and business cooperatives | in accordance with Section 5 of the Income Tax Act 1988 |  |
| C | obligation | shall | the profit shall be determined |  | in accordance with Section 5 of the Income Tax Act 1988 |  |
| D | obligation | shall | the profit shall be determined | For commercial enterprises (Section 2) that are required to keep books under commercial law provisions, and for trading and business cooperatives | in accordance with Section 5 of the Income Tax Act 1988 |  |

### Adjudication

The difference is contextually explainable. 'X shall be determined by Y' defines the identity/content of X (Y supplies the determinant), while 'profit shall be determined in accordance with Section 5' imposes a method obligation on an identified taxpayer class.

Caveat: This interpretation comes from one pair only and rests on argument structure/context, not on a surface trigger that can be applied from 'shall be determined' alone; it is not written as a Prompt rule in this round.

Gold inconsistency: **NO**. The modality difference can be explained by argument structure/context, but only as a single-pair interpretation.

## 6. The 15 Gold-definition clauses containing `shall`

| Family | Gold def count | All-four-arm wrong | Sample IDs | Action spans | Superficially similar non-definition |
| --- | --- | --- | --- | --- | --- |
| shall_include | 1 | 1 | estg_000037 c1 | shall include | none in Gold corpus |
| shall_be_deemed | 6 | 6 | estg_000080 c4, estg_000087 c1, estg_000414 c1, estg_000572 c1, estg_000773 c1, estg_000854 c1 | shall be deemed as the acquisition cost \|\| be deemed to exist \|\| be deemed discharged \|\| be deemed to be \|\| be deemed a single activity \|\| be deemed secure | none in Gold corpus |
| shall_be_treated | 2 | 2 | estg_000083 c2, estg_000522 c1 | the additional amounts shall be treated as business income and the reduced amounts as business expenses \|\| be treated | none in Gold corpus |
| shall_constitute | 1 | 1 | estg_000293 c1 | constitute income from capital | none in Gold corpus |
| shall_be_assumed | 2 | 2 | estg_000509 c2, estg_000776 c1 | be assumed \|\| be assumed | estg_000505 c2 (obligation) |
| shall_apply | 1 | 1 | estg_000664 c1 | apply | estg_000056 c1 (obligation), estg_000128 c2 (obligation), estg_000208 c2 (obligation) |
| shall_be_determined | 1 | 1 | estg_000136 c1 | be determined | estg_000812 c1 (obligation) |
| shall_be_income | 1 | 1 | estg_000302 c1 | be income from letting and leasing | none in Gold corpus |

### Common semantics of the 15 `shall` definitions

The 15 clauses share a common annotation semantics: **`shall` marks legal status, identity, classification, membership, scope, or a computational/legal fiction rather than a required act of a duty-bearer.**

- All 15 have `actors = []` in Gold: no explicit duty-bearer is annotated.
- The action is a stative/copular/legal-fiction predicate (`include`, `be deemed`, `be treated`, `constitute`, `apply`, `be assumed`, `be determined`, `be income`), not an action performed by an actor.
- The clause typically equates X with Y, classifies X as Y, or extends the scope of an existing classification/rule.
- `shall` can be inside the action span (`shall include`, `shall be deemed`) or immediately before it; Gold action semantics consistently treats the definitional predicate as the action.

This is a semantic commonality, not a lexical test: `shall + verb` also occurs in deontic clauses.

### Is there an annotation-level principle separating definitional `shall` from deontic `shall`?

A **directional** principle exists: definitional `shall` is stative/classificatory/legal-fictional and lacks an actor/duty-bearer; deontic `shall` imposes required conduct or a required method of application on a duty-bearer. But it is **not yet stable for `shall apply`, `shall be assumed`, and `shall be determined`**, because these surfaces occur in both Gold classes. The apply family is the clearest blocker.

## 7. Definition modality candidate principle review

Candidate principle: *Gold definition modality is broader than explicit `means`; it includes legal fiction, classification, and some scope/application statements.*

| Review dimension | Evidence |
| --- | --- |
| Supporting cases | 39 definition clauses; explicit `means` = 1; `shall` definitions = 15; legal-fiction/deeming in 6 `shall be deemed` + 2 `shall be treated`; classification/constitution; 7 apply-family definitions. |
| Counterexamples / limits | `shall` is overwhelmingly deontic elsewhere; active apply family is 7 definition vs 5 non-definition; `shall be assumed` pair is mixed; `shall be determined` pair is mixed. |
| Unresolved pairs | `estg_000505 c2` vs `estg_000509 c2`; `the following applies` `estg_000164 c1` vs `estg_000306 c1`; `shall apply` `estg_000664 c1` vs `estg_000056/128/208`; `shall be determined` `estg_000136` vs `estg_000812`. |
| Consistency | Descriptive coverage of definition is internally consistent; a surface-based classifier is not. The apply family and the 505/509 pair require Gold adjudication before a clean Prompt rule could be written. |

**Status:** `MOSTLY_STABLE_WITH_EXCEPTIONS` for descriptive coverage of Gold definition; the apply-family boundary itself is `GOLD_ADJUDICATION_REQUIRED`.

## 8. Definition action presence: final confirmation

| Question | Result | Evidence / caveat |
| --- | --- | --- |
| Any exception to 39/39? | No: empty-action definition clauses = 0/39. | 46 Gold action spans; all definition clauses have at least one. |
| Could segmentation create the appearance? | No for presence; yes for exact boundaries. | 6 definition cases have an overlapping sibling clause span, so Gold segmentation is not always a strict partition; however every definition action remains inside its own clause span and is recorded in that clause's action array. |
| Do action spans contain a definitional predicate? | Yes: 39/39 definition cases have action spans with predicate markers and all actions inside the clause span. | Markers include is/are/be, means, include, apply/applies, deemed, treated, determined, constitute, assumed, eligible, occurs, runs, leaves, works, etc. |
| Do actor/condition/constraint affect action presence? | No. | Actors non-empty in 2/39; conditions non-empty in 28/39; constraints non-empty in 28/39; none removes the action. |
| Any suspected forced annotation? | No forced empty-to-nonempty case found. | Boundary outliers remain (`estg_000020`, `estg_000083 c2`, `estg_000112`, `estg_000283`), but each still contains a predicate; they affect exact boundary, not presence. |

**Upgrade:** `Definition clauses still receive an action span representing the definitional predicate.`

Status: **`STABLE_ANNOTATION_PRINCIPLE`** (presence only; exact boundary remains unresolved).

## 9. Gold inconsistency findings

| Case | Finding | Status |
| --- | --- | --- |
| `estg_000505 c2` vs `estg_000509 c2` | Near-identical deeming/computational fiction; Gold labels obligation vs definition with no sufficient contextual semantic difference. | `POTENTIAL_GOLD_INCONSISTENCY` |
| apply family | Same active predicate (`apply/applies`) receives both definition and obligation labels; `the following applies` is mixed across near-identical clauses. | `GOLD_SEMANTICS_UNCLEAR` / `NEEDS_GOLD_ADJUDICATION` |
| `estg_000136` vs `estg_000812` | Same `shall be determined` surface; argument structure supports a context-based distinction (`by` identity vs `in accordance with` method). | Contextually explainable; no inconsistency marked |
| Other definition-like lexical candidates | 14 broad candidates were previously surfaced, but not asserted to be missed definitions. | Not treated as Gold inconsistency in this round |

No new confirmed Gold inconsistency beyond the previously suspected `estg_000505 c2` / `estg_000509 c2` pair was found. The apply family remains an adjudication issue, not an automatically corrected annotation.

## 10. Preserved limitations

- Exact action complement/subordinate-clause boundaries are not solved.
- Condition/constraint boundary semantics are only summarized, not adjudicated.
- No Prompt wording, example wording, schema, Gold annotation, or experiment arm is changed.
- The analysis remains zero-API.
