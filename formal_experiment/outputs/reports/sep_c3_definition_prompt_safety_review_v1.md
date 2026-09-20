# SEP-C3 Definition Prompt Safety Review v1

- Status: **conceptual safety review only; no patch applied**
- New API / LLM calls: **0**
- Gold modifications: **none**
- Prediction modifications: **none**
- Active prompt modifications: **none**

Reviewed candidates:

- S2 proposed semantic definition guidance
- S11 proposed definition action-presence guidance
- Synthetic E4 replacement in `sep_c3_definition_synthetic_E4_candidate_v1.json`

This review tests whether the candidate wording biases classification beyond
the evidence, overfits to stored phrases, or resolves issues that were
explicitly left unresolved.

## 1. Contrastive category review

Legend:

- **helps:** guidance supports the correct semantic direction.
- **neutral:** guidance does not directly affect this category.
- **risks:** guidance could misclassify if read as a surface rule or if the
  category is inherently ambiguous.

| Category | S2 candidate | S11 candidate | E4 candidate | Overall conclusion |
|---|---|---|---|---|
| A. explicit definition using `means` | Helps. Definition remains a semantic label and explicit definition is not displaced. | Helps. Requires the definitional predicate action instead of leaving it empty. | Helps. The replacement keeps one explicit `means` clause and gives it a non-empty action. | Correct direction. |
| B. legal-fiction definition using `shall` | Helps. States that `shall` does not automatically mean obligation and that legal fiction can be definition. | Helps. Requires the definitional predicate action for stative/legal-fictional clauses. | Neutral. The synthetic E4 has no `shall`. | Helps, but must not become "all `shall + stative verb` is definition." |
| C. applicability/scope statement | Risks over-labeling if `scope/applicability` is read as a trigger. The wording says semantic function, not surface phrase, but the apply family is genuinely mixed. | Neutral. It addresses action presence only. | Neutral. The synthetic example is classification, not an applicability predicate. | Remains `NEEDS_GOLD_ADJUDICATION`; no resolution claimed. |
| D. normal actor-directed obligation using `shall` | Helps. Contrasts required conduct/method on a duty bearer or regulated subject with definitional characterization. | Neutral. Obligations already need actions and are outside this repair. | Neutral. The replacement has no deontic clause. | Correct direction, with the caveat that unexpressed duty bearers remain possible. |
| E. permission using `may` | Neutral. Permission is not redefined. | Neutral. | Neutral. Existing E1 continues to cover permission. | No new risk. |
| F. prohibition using `may not` / `shall not` | Neutral. Prohibition is not redefined. | Neutral. | Neutral. Existing E3 continues to cover prohibition. | No new risk. |
| G. ambiguous apply-family clause | Risks misclassification because the same surface occurs as definition and obligation. The candidate says context decides, but context-only guidance is not a stable discriminator in the observed Gold. | Neutral. | Neutral. | Explicitly unresolved; no Gold decision is encoded. |
| H. `shall be determined` contextual pair | Helps only with caution. It supports a contextual/argument-structure reading, not a surface rule. | Helps action presence; the action exists in both Gold sides of the pair. | Neutral. | Partially helps; the pair remains context-dependent and unresolved as a rule. |

## 2. Does the candidate turn all `shall + stative verb` into definition?

**No.** The proposed S2 wording says:

- `shall` alone does not make a clause an obligation.
- `shall` plus a verb does not determine modality.
- classification is based on what the clause does in context.

The S11 wording only says not to omit an action when a clause is a definition.
It does not say that any stative or copular clause is a definition.

The only remaining risk is interpretive: a model may still over-label an
ambiguous applicability clause as definition. That risk is why the apply
family remains `NEEDS_GOLD_ADJUDICATION` and why the candidate is not presented
as a measured fix.

## 3. Boundary safety

- The S11 candidate explicitly says exact action boundaries still follow the
  evidence in the sentence.
- It does not introduce a new rule that excludes conditions, constraints, or
  exceptions from the action span.
- The E4 candidate's `for the purposes of this bylaw` constraint is illustrative
  of one natural boundary; it is not proposed as a universal boundary rule.
- `S8` is untouched.
- Condition/constraint boundary guidance is untouched.

## 4. Gold-consistency safety

- The candidate does not modify Gold.
- The candidate does not encode the obligation/definition labels of the
  `estg_000505 c2` / `estg_000509 c2` pair.
- The candidate does not resolve the apply-family labels.
- The candidate does not promote the explicit `means` example into a general
  phrase rule; it remains one example.
- The E4 replacement adds an action to every definition clause, consistent with
  39/39 Gold action presence.

## 5. Test-leakage and overfitting review

| Risk | Result |
|---|---|
| Specific EStG wording in candidate prompt text | None. The E4 sentence is synthetic and uses `community library` / `bylaw`. |
| Sample IDs in candidate prompt text | None. |
| Memorized predicate list as a deterministic rule | None in S2/S11. E4 uses `classified as` and `means` as examples, not as rules. |
| Gold labels of ambiguous test cases | None. Apply-family and 505/509 remain unresolved. |
| One/two-example narrow pattern | S2 uses 39-definition / 15-shall evidence; S11 uses 39/39 presence evidence; E4 is explicitly one synthetic illustration. |
| Exact-boundary overreach | None; S11 defers to evidence and S8 remains untouched. |

Conclusion: the candidate passes the safety and leakage review for a design
gate. It is not a performance claim and should not be applied until the
offline patch step is authorized.

## 6. Decision-gate summary

| Candidate | Status |
|---|---|
| S2 semantic definition guidance | `READY_FOR_OFFLINE_PATCH` |
| S11 definition action-presence guidance | `READY_FOR_OFFLINE_PATCH` |
| E4 replacement | `READY_FOR_OFFLINE_PATCH` |

Unresolved issue policy: `READY_FOR_OFFLINE_PATCH` does not change the statuses
of the apply-family ambiguity, the 505/509 potential Gold inconsistency, the
`shall be determined` contextual pair, or `S8`.
