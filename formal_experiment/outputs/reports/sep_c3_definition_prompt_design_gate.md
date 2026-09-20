# SEP-C3 Definition Prompt Design Gate

- New API / LLM calls: **0**
- Prompt changes: **none**
- Gold changes: **none**
- This is a gate, not a Prompt design.

## Gate matrix

| Candidate issue | Evidence stable? | Gold clear? | Existing guidance conflict/missing? | Ready for GPT design? |
| --- | --- | --- | --- | --- |
| definition modality missing guidance | Stable: 20/29 first-def and 25/39 clauses all-four-arm wrong; 15/15 shall definitions wrong. | Mostly clear for semantic coverage; not clear at apply-family boundary. | S2 missing definition semantics; E4 only explicit means. | READY_FOR_PROMPT_DESIGN (core semantic coverage only; not apply-family boundary) |
| E4 empty-action conflict | Stable: 0/39 Gold definitions have empty action. | Clear. | E4 explicitly says actions empty; direct conflict. | READY_FOR_PROMPT_DESIGN (design must not teach empty definition action) |
| S11 action-empty permissiveness | Stable: 39/39 Gold definitions have action; aligned predicted empty-action counts A=10, B=13, C=12, D=12. | Clear. | S11 says a definition clause may have no actions; unsupported as a design cue. | READY_FOR_PROMPT_DESIGN (remove/repair permissive cue) |
| S8 action-boundary conflict | Locally stable: 44/46 spans no condition/constraint/exception overlap; one direct counterexample. | Not clear at exact boundary; estg_000020 is an outlier. | S8 says action ends where condition/constraint begins; direct local conflict at estg_000020 c1. | NEEDS_GOLD_ADJUDICATION (preserve outlier; do not redesign boundary now) |
| apply-family modality ambiguity | Stable as an ambiguity: 7 definition vs 5 non-definition active apply/applies clauses. | No stable Gold discriminator; near-identical `the following applies` mixed. | S2 has no definition semantics; same surface receives both labels. | NEEDS_GOLD_ADJUDICATION |
| condition/constraint boundary | Partial: 28/39 definitions have each; E4 empty fields are under-representative. | Exact boundary not clear in this round. | Separate S5/S6/R_C boundary work exists but is not adjudicated here. | DO_NOT_TOUCH (out of scope; no boundary conclusion) |
| actor R_A | Stable for ordinary definitions: 37/39 definitions have empty actors; only 2 relational definitions name an actor. | Mostly clear; exception pattern visible. | E4 empty-actor pattern is mostly compatible; no new conflict. | DO_NOT_TOUCH (R_A not modified this round) |
| exception | Partial: 5/39 definitions have an exception; 34/39 empty. | No definition-specific exception conflict established. | E3/E4 not directly contradicted by the definition corpus. | DO_NOT_TOUCH (no new evidence requiring prompt change) |

## Interpretation of statuses

- `READY_FOR_PROMPT_DESIGN`: the evidence is stable and clear enough for a later Prompt design review. It does **not** authorize wording in this round.
- `NEEDS_GOLD_ADJUDICATION`: Prompt design should not resolve the boundary; Gold/annotation semantics need a separate human decision first.
- `DO_NOT_TOUCH`: no Prompt change should be made from the current evidence; this is not a judgment that current wording is perfect.
- `INSUFFICIENT_EVIDENCE`: not used in this matrix.

## Gate conclusions

- The definition modality *coverage* problem is ready for a later design review at the semantic level: legal fiction, classification, and scope/application are genuine definition patterns, and 15/15 `shall` definitions fail all four arms.
- The action-presence problem is ready: E4 and S11 both mislead toward empty definition actions while Gold has 39/39 non-empty actions.
- The apply-family and exact-boundary issues are not ready. In particular, `estg_000505 c2` / `estg_000509 c2` remains a `POTENTIAL_GOLD_INCONSISTENCY`, and `the following applies` is mixed across near-identical clauses.
- This gate deliberately leaves condition/constraint boundary, actor R_A, and exception untouched.
