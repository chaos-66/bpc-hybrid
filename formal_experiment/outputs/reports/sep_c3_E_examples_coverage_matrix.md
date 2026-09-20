# SEP-C3 E Examples Coverage Matrix

- Scope: `examples_E.md`, Examples E1-E5.
- API calls: **0**.
- Gold coverage numbers below are strict structural counts, not fuzzy semantic recalls.

| Example | Main concept taught | Gold coverage | Potential overgeneralization | Potential conflict |
| --- | --- | --- | --- | --- |
| E1 | permission; unresolved pronoun actor; condition | permission clauses: 62; permission with condition: 46; pronoun actor: 1 | May suggest pronoun actors are common; only 1 Gold permission clause has a bare pronoun actor under the strict count. | No direct modality conflict; actor scope was not re-studied this round. |
| E2 | passive no-actor obligation; coordinated actions; constraints | strict exact pattern (obligation, no actor, >=2 actions, >=1 constraint): 1 | A very rare exact Gold pattern; concept-level passive no-actor rule is supported by S rule 10. | E2 does not show by-phrase actors; no direct definition-clause conflict. |
| E3 | prohibition with exception | prohibition clauses with exception: 2 | Exceptions are rare in Gold; E3 may make exception extraction look more typical than it is. | No direct conflict; aligns with S rule 7. |
| E4 | definition clause with empty actor/action, followed by obligation | definition clauses: 39; with action: 39; fully semantic-empty: 0 | Explicitly overgeneralizes action emptiness to all definition clauses. | Direct conflict with Gold action presence; also omits condition/constraint coverage. |
| E5 | condition containing nested constraint | actual condition-contains-constraint pairs: 7; clauses: 6; obligation pairs: 3 | Actual nesting is less frequent than merged-hull diagnostics; E5 is still an actual Gold pattern. | No direct conflict; aligns with S rule 8. |

## Overall E assessment

- E is not wholly wrong: E1/E3/E5 are structurally aligned with Gold, and E2 follows the explicit passive rule.
- E4 is the local example that conflicts with Gold on definition actions and under-covers definition conditions/constraints.
- Therefore the evidence favours **E is broadly useful but E4 is a local, high-impact mismatch**, rather than an E-wide definition problem.
