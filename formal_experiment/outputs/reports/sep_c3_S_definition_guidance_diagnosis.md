# SEP-C3 S Definition-Guidance Diagnosis

- New API / LLM calls: **0**
- S rules were **not modified**.
- This is an evidence diagnosis, not a rewrite.

| Rule | Diagnosis | Supporting samples / evidence | Counterexamples | Confidence | Details |
| --- | --- | --- | --- | --- | --- |
| S2 | MISSING_DEFINITION_MODALITY_GUIDANCE | 20/29 first-definition samples and 25/39 definition clauses are non-definition in all four arms; 15/15 shall-definition clauses fail all four arms; two-arm confusions are definition -> obligation/prohibition. | None direct: S2 does list definition as a label, but it supplies no class semantics or shall ambiguity guidance. | high | The failure is not absence of the word definition but absence of annotation-level semantics for legal fiction, classification, and scope application. |
| S11 | MISLEADING_PERMISSIVE_GUIDANCE | 39/39 definition clauses have action; 0 empty-action clauses. Aligned predicted empty-action counts over 39 definitions are A=10, B=13, C=12, D=12. | If 'may' is read only as logical possibility, no direct Gold contradiction exists; as a design cue it is unsupported and locally misleading because every Gold definition has a definitional predicate action. | high | The problem is permissiveness relative to the observed Gold distribution, not a strict logical impossibility. |
| S8 | LOCALLY_CONFLICTING_ACTION_BOUNDARY_GUIDANCE | 44/46 definition action spans do not overlap any Gold condition/constraint/exception span. | estg_000020 c1: one Gold action span contains two separately annotated Gold condition spans. | high (local conflict); medium for any generalized boundary repair | Only a local direct counterexample is established; exact complement/subordinate boundary remains unresolved and is intentionally not solved in this round. |

## Status summary

- **S2:** `MISSING_DEFINITION_MODALITY_GUIDANCE` — confirmed.
- **S11:** `MISLEADING_PERMISSIVE_GUIDANCE` — confirmed as an unsupported permissive design cue, while noting the logical-possibility caveat.
- **S8:** `LOCALLY_CONFLICTING_ACTION_BOUNDARY_GUIDANCE` — confirmed locally by `estg_000020 c1`; exact boundary repair remains unresolved.
