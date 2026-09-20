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
