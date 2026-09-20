# SEP-C3 S Modality / Action Audit

`S_MODALITY_ACTION_AUDIT`

- Scope: `semantic_rules_S.md`, rules 2, 4, 8, and 11 (modality/action-relevant rules).
- S is not restored or modified.
- API calls: **0**.

| S rule | Current wording / behavior | Gold compatibility | Conflict / risk | Evidence |
| --- | --- | --- | --- | --- |
| S2 | label each clause obligation, prohibition, permission, or definition; smallest sufficient surface trigger | Label inventory matches Gold. Partial semantic coverage only. | **MISSING_GUIDANCE**: no semantics for `definition`; no warning that `shall` can occur in definition/legal-fiction clauses. | 15/15 definition clauses with `shall` are non-definition in all four arms. |
| S4 | smallest verb-centred phrase that identifies the act, including necessary object, complement, or particle | Core verb-centred principle matches 46/46 Gold definition actions. | **AMBIGUOUS_GUIDANCE** / boundary risk: Gold sometimes keeps only the predicate and places complements in conditions/constraints (e.g. `leaves`, `works`, `shall include`, `be determined`). | Examples: estg_000283, estg_000037, estg_000136, estg_000112. |
| S8 | never fold condition/constraint/exception content into action; action ends where such a phrase begins | Compatible with 44/46 Gold definition action spans (no measured overlap with conditions/constraints/exceptions). | **CONFLICTING_GUIDANCE** for at least one Gold clause: estg_000020 action contains two separately annotated condition spans. | estg_000020 c1: action span [37,177) contains condition spans; overlap count 2. |
| S11 | a definition clause may have no actions | Logically permissive, but unsupported as a positive definition pattern. | **POTENTIALLY_MISLEADING / CONFLICT-ADJACENT**: Gold has 39/39 definition clauses with actions; E4 explicitly takes the empty-action branch. No definition clause has an empty action. | Gold definition action-empty count = 0. |

## S modality/action conclusions

- S2 is missing the semantic definition needed for the definition class. It cannot distinguish `shall` as a deontic modal from `shall` as a legal-fiction/definition trigger.
- S11 is technically permissive rather than contradictory, but it is indistinguishable from a positive empty-action instruction when paired with E4.
- S4 and S8 are mostly compatible with Gold's predicate-centred boundaries; S8 has one direct Gold counterexample (estg_000020).
- S does not repeat R_A/R_C, but it repeats E's action-empty concept in rule 11 and therefore compounds the E4 risk if S were used.
