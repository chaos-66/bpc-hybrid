# SEP-C3 Definition Contrastive Pairs

- API calls: **0**.
- Pairs are evidence contrasts, not Prompt rules.

## Pair A: definition clause vs superficially similar obligation clause

| Case | Gold modality | Gold action | A/B/C/D predicted modality | Why it matters |
| --- | --- | --- | --- | --- |
| estg_000071 c1: `For registered traders, Item 13 applies` | definition | `applies` | obligation / obligation / obligation / obligation | Same `applies` lexeme as `estg_000128 c2`, but Gold separates definition from legal-reference application. |
| estg_000128 c2: `Section 10(2) last sentence shall apply.` | obligation | `apply` | permission / permission / permission / permission in aligned records | Same lexeme, different Gold role; model does not use the distinction. |

## Pair B: definition action span vs non-definition action span

| Case | Gold modality | Gold action | Predicted action behaviour | Boundary lesson |
| --- | --- | --- | --- | --- |
| estg_000136 c1: `... shall be determined ...` | definition | `be determined` | obligation; actions `be determined` / `determined` / `be determined` / `be determined` | Definition action can be a passive predicate; model still labels modality obligation. |
| estg_000812 c1: `... profit shall be determined ...` | obligation | `be determined` | obligation; action includes subject + modal in all arms | Same lexical verb, different Gold modality. |
| estg_000080 c4: `... shall be deemed as the acquisition cost` | definition | `shall be deemed as the acquisition cost` | obligation; action variants add/remove `be`, `shall`, and parenthetical material | Gold action includes `shall` here, unlike most bare-infinitive deeming actions. |

## Pair C: same lexical trigger, different Gold modality

| Trigger | Definition example | Non-definition example | Gold contrast |
| --- | --- | --- | --- |
| `shall be assumed` / `be assumed` | estg_000509 c2 `a monthly wage payment period shall be assumed` | estg_000505 c2 same construction | definition vs obligation; strongest apparent inconsistency |
| `applies` / `apply` | estg_000071 c1 `Item 13 applies` | estg_000128 c2 `Section 10(2) last sentence shall apply` | definition vs obligation |
| `shall be determined` | estg_000136 c1 | estg_000812 c1 | definition vs obligation |
| `does not apply` | estg_000083 c1 | no non-definition match found in this Gold | definition-only family |

## Pair D: definition action with condition vs E4 empty-action definition

| Signal | Gold | E4 | Contrast |
| --- | --- | --- | --- |
| Definition action | 39/39 clauses have >=1 action | actions empty | direct conflict |
| Condition coverage | 28/39 clauses have conditions | empty | E4 under-covers |
| Constraint coverage | 28/39 clauses have constraints | empty | E4 under-covers |
| Legal fiction / shall | 15 definition clauses use `shall` | no shall-based definition example | missing coverage |
