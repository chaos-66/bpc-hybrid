# SEP-C3 E4 Coverage Audit

- Task: Definition-Clause Semantics & Prompt Coverage Study
- Scope: `prompts/sun_compat/modular_v1/examples_E.md`, Example E4 only.
- API calls: **0**.

## 1. Exact E4 text

```text
Example E4 — definition clause followed by an obligation clause:
Input: "'Personal data' means information about a person; the controller must protect it."
- clause 1 span [0,48): definition; evidence "means" [16,21); actors and actions empty
- clause 2 span [50,81): obligation; evidence "must" [65,69); actor "the controller" [50,64), normalized "controller"; action "protect it" [70,80)
- conditions, constraints, exceptions: empty in both clauses
```

## 2. What E4 wants to teach

E4 teaches (a) a definition clause can be labeled `definition`, (b) the trigger `means` is sufficient modality evidence, and (c) a definition clause has empty actors and actions. It also demonstrates splitting a definition clause from a following obligation clause.

## 3. Audit against Gold definition clauses

| Question | Result | Evidence |
| --- | --- | --- |
| Gold definition clauses | 39 | clauses with Gold modality == definition |
| Gold definition samples (any clause) | 34 | distinct sample_ids |
| First-clause definition samples (record-level evaluator view) | 29 | first Gold clause is definition |
| Gold definition clauses with non-empty action | 39 | 46 action spans |
| E4 explicit action-empty pattern compatible with Gold | 0 | E4 says actions empty; Gold has 0/39 empty actions |
| E4 actor-empty pattern compatible with Gold | 37 | Gold definition clauses with actor: 2 |
| E4 all-condition/constraint/exception-empty pattern compatible with Gold | 0 | Gold clauses with no condition, constraint, and exception |
| Gold clauses matching E4's explicit `means` trigger | 1 | exact token `means` |
| Gold definition clauses with `shall` | 15 | legal-fiction/definition uses of shall |
| Gold shall-definition clauses all four arms non-definition | 15 | A/B/C/D predictions |

## 4. Coverage judgement

- **Modality**: E4's label `definition` is compatible with Gold's label inventory, but E4 covers only an explicit `means` definition. It does not cover the dominant `shall`-based legal-fiction patterns (15 definition clauses), classification/status predicates, or scope-application definitions.
- **Action**: E4 explicitly says `actors and actions empty`. This conflicts with Gold: 39/39 definition clauses have at least one action span; E4-compatible action-empty count is 0.
- **Actor**: E4's empty actor pattern is broadly compatible (37/39 Gold definition clauses have no actor), but it is not universal (2 clauses have actors).
- **Condition / constraint / exception**: E4 shows all three empty. No Gold definition clause has all three empty; 28/39 have conditions and 28/39 have constraints.
- **Joint pattern**: E4's full joint pattern (definition + no actor/action/condition/constraint/exception) occurs in 0/39 Gold definition clauses.

## 5. E4 status

**`CONFLICTS_WITH_GOLD`**

The conflict is concentrated in action emptiness. The status is not caused by the modality label itself.

## 6. E4 + S interaction risk

S rule 11 says a definition clause *may* have no actions. That is permissive, not a direct contradiction of Gold, but combined with E4's explicit empty action it removes any positive signal that definition clauses normally have action spans. The joint guidance is therefore a high-risk explanation for empty definition actions, even though this A/B/C/D run includes E4 and not S.
