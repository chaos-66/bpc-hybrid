# Transferability Matrix

This matrix does not recommend a new final prompt, a new R_C v2, a new E, or a new experimental arm. It only classifies evidence by compatibility with the current BPC Stage 2 schema, Gold, and prompt.

Current prompt assets referenced:
- Common system/user skeleton: `formal_experiment/prompts/sun_compat/modular_v1/common_system.md`, `user_envelope.md`.
- S semantic rules: `formal_experiment/prompts/sun_compat/modular_v1/semantic_rules_S.md`.
- E examples: `formal_experiment/prompts/sun_compat/modular_v1/examples_E.md`.
- R_A: `formal_experiment/src/bpc_hybrid/modular_refinement_prompt.py`.
- Current structured-output schema/canonicalizer already exists; it is not re-designed here.

---

## Directly compatible

| Evidence | Source | Why compatible | Current coverage | Can it be borrowed? |
|---|---|---|---|---|
| `exception` = cases where the regulation does not apply | LegalDiscourse EXCEPTION; LegalChanges4BPC exception | Semantics match current `exception` | Current S rule 7 defines exception; current schema has `exceptions` array | Conceptually compatible, but no new instruction needed |
| `actor` = role responsible for executing the action | LegalChanges4BPC exact prompt | Close to R_A's "responsible for performing/refraining/being subject to the action" | Already covered by R_A | No new instruction needed |
| `action` = activity that is mandatory/prohibited/permitted | LegalChanges4BPC exact prompt; common skeleton | Matches current `action` field | Already covered by common/S | No new instruction needed |
| Strict JSON/schema discipline improves structural consistency | RC4PC; LegalChanges4BPC | Current project already has shared structured-output baseline and canonicalizer | Already covered | Do not restore J solely because these papers use JSON |
| Controlled vocabulary prevents invalid labels | RC4PC; LegalChanges4BPC | Current schema already constrains fields and labels | Already covered | No new prompt text needed |

---

## Potentially useful but needs mapping

| Evidence | Source | Why useful | Mapping problem | Transfer risk |
|---|---|---|---|---|
| Recursive / lowest-level parsing | LegalDiscourse Section 2.3/10.1 | Highlights that span granularity is inherently ambiguous and context-dependent | LegalDiscourse favors lowest-level parse and does not allow co-reporting parent+child roles; our Gold can retain full condition and nested constraint | High: could re-open condition/constraint boundary and reduce complete-condition recall |
| `precondition` (factual) vs `norms` (deontic) | RC4PC | Cleanly separates applicability facts from regulated actions | RC4PC works with formal action objects, not text spans; restrictions are typed patterns/nested temporal constraints, not a separate `constraint` field | High: structural idea does not translate directly to span labels |
| Threshold as `constraint`, disclosure as `condition` | LegalChanges4BPC one-shot example | Closest terminology and an example that treats threshold/limit as constraint | No span boundary rule; `concepts_modified` is a list of changed concept types, not overlapping spans | Medium-high: could be over-mapped into a rigid "threshold=constraint" rule without Gold support |
| Broad agent/subject definitions | LegalDiscourse, Haque & Singh, COLING 2025 | Provide actor-like semantics and error reports | A permits passive implied subjects; B has counterparty `object`; C emphasizes completeness | High for empty-Gold actor; only R_A-compatible subset is useful, and that subset is already covered |
| Modular prompt composition | Kölbel et al. | Useful experimental-design reference for component ablations and control experiments | It is a BPMN/standard question-answering framework, not Stage 2 field extraction | Medium if used as experiment-design only; no direct prompt migration |
| One-shot example for output-format correction | LegalChanges4BPC | Verified: round 2 added a one-shot input/output example after JSON schema mismatch | Current E already provides synthetic worked examples; no contrastive example or condition/constraint boundary rule | Low-medium: already covered by E; no new example should be designed here |

---

## Already covered

| Literature practice | Where in current project | Action |
|---|---|---|
| Condition = antecedent state/event that activates or determines whether/when the norm applies | S rule 5 | Already covered; do not duplicate |
| Constraint = limitation on how/how much/where/by when an applicable action is performed; includes legal references, time/duration, quantity, purpose, exclusivity | S rule 6; R_C wording | Already covered; do not duplicate |
| Exception = case removed from/narrowing an otherwise applicable rule | S rule 7 | Already covered |
| Field partition between condition/constraint/exception; never fold into action | S rule 8 | Already covered |
| Constraint nested inside a condition reported in both arrays | S rule 8; E5 worked example "within two years" | Already covered in current prompt + examples |
| Actor explicit-only and no-actor behavior | R_A | Already covered and stricter than literature |
| Synthetic worked examples | E examples, including E5 nested condition/constraint | Already covered; E has strong positive evidence |
| Structured output validation and canonicalization | Shared structured-output baseline and canonicalizer | Already covered; literature JSON practice does not justify restoring J |

---

## Incompatible

| Literature rule/definition | Source | Conflict with our schema/Gold |
|---|---|---|
| `"passive voice entity"` when no explicit subject is mentioned | LegalDiscourse SUBJECT prompt | Conflicts with R_A's explicit-only rule and empty-Gold actor |
| Enumerate all instances / no omission for subject extraction | LegalDiscourse; COLING 2025 | Can over-extract objects/resources/amounts and worsen empty-Gold actor false positives |
| Empty subject may mean "all parties" | Haque & Singh | Conflicts with our empty-Gold actor semantics (absence means no actor) |
| `object` = counterparty party | Haque & Singh | Not our action object; renaming it would corrupt actor/action semantics |
| Same entity in both SUBJECT and OBJECT -> annotate as OBJECT | LegalDiscourse | Conflicts with our multi-role/nested span possibility; our schema has separate arrays and does not have B's party-object role |
| `[MASK]` prompt learning and verbalizer | DPLACC (G) | Conceptually different from instruction-based LLM prompting; not a prompt-design reference for Stage 2 |
| BPMN/external-standard question answering | Kölbel et al. (F) | Different task and unit; no condition/constraint role extraction |

---

## Insufficient evidence

| Question | Status |
|---|---|
| Explicit inclusion/exclusion criteria for condition vs constraint | not publicly specified in any source |
| Overlap/nesting annotation policy for condition and constraint spans | not specified; LegalDiscourse discusses recursion but not a co-labeling rule; RC4PC uses formal nesting only |
| Complete span vs minimal span rule for condition/constraint | not specified |
| Contrastive examples between condition and constraint | not found in A-G |
| Positive + negative examples for field boundary | only positive 1-shot/few-shot examples found; no contrastive boundary examples |
| Exact first-round LegalChanges4BPC prompt (pre-one-shot) | not publicly committed; only paper description verified |
| Haque & Singh published Figure 1 | public preprint prompt verified; publisher full text not accessible |
| LegalDiscourse public code/annotation package | not found; paper promises release but gives no URL |
| COLING 2025 public code/supplement | not found |
| Sun X. et al. 2024 full text (source cited by LegalChanges4BPC for six concepts) | closed access; not publicly found |

---

## "Less is more" test for candidate borrowings

Every candidate that looked potentially borrowable was checked against the six required questions.

### Candidate 1: LegalChanges4BPC condition/constraint definitions

1. **Already in current prompt?** Yes: S rules 5-7, and S rule 8 is more operational.
2. **Which observed failure would adding it solve?** None; it would duplicate existing definitions and could broaden `constraint` to "when applicable," worsening condition-to-constraint leakage.
3. **Only a repeat of E/R_A/common?** Repeat of common/S, with E already showing the nested case.
4. **Adds complexity?** Yes, without a boundary rule.
5. **Could recreate broad S?** Yes: `constraint` defined as "how or when applicable" risks folding even more condition text into constraints.
6. **Positive/negative evidence?** Positive example only; no negative/contrastive evidence.

Verdict: **not a high-value borrowing.**

### Candidate 2: LegalDiscourse lowest-level parse principle

1. **Already in current prompt?** Partially: S rules define complete spans and nested dual reporting; E5 demonstrates it.
2. **Which observed failure would it solve?** It may reduce disagreement on granularity, but it directly conflicts with the observed need to preserve a full condition while separately marking an inner constraint.
3. **Only a repeat?** Not a repeat; it is a different policy.
4. **Adds complexity/conflict?** Yes, strong conflict.
5. **Could recreate broad S or span fragmentation?** Fragmentation, and it could cut conditions into small spans.
6. **Evidence?** The paper describes the ambiguity and advises lowest-level parse, but does not validate it against a nested condition/constraint Gold.

Verdict: **not compatible.**

### Candidate 3: RC4PC strict schema + controlled pattern vocabulary

1. **Already in current prompt?** Current project already has a shared schema and canonicalizer; J is mainly raw serialization.
2. **Which observed failure would it solve?** Not the condition/constraint semantic boundary; only output structure.
3. **Repeat of common/J?** Yes at the structural level.
4. **Adds complexity?** Yes, large controlled vocabulary would be a poor fit for our six fields.
5. **Could recreate broad S?** Not directly, but it would distract from the semantic boundary and add a large pattern list.
6. **Evidence?** Verified for RC4PC's own task; not evidence for our Gold.

Verdict: **do not transfer.**

### Candidate 4: Kölbel modular prompt composition / control experiments

1. **Already in current prompt?** No; current project has its own modular E/S/J design.
2. **Which observed failure would it solve?** None directly; it could help design future component ablations, but it is outside this task's scope.
3. **Repeat?** Different domain.
4. **Adds complexity?** It is an experiment-design reference, not a Stage 2 prompt.
5. **Could recreate broad S?** Not relevant.
6. **Evidence?** Verified for BPMN/standard question answering; not for our field boundary.

Verdict: **experimental-design reference only; no migration.**

### Candidate 5: LegalChanges4BPC one-shot example

1. **Already in current prompt?** Yes: E already has synthetic worked examples, including nested condition/constraint.
2. **Which observed failure would it solve?** It could improve output format, but current canonicalizer already handles structured output; E is already stronger for our schema.
3. **Repeat?** Yes, E.
4. **Adds complexity?** A new example would duplicate E.
5. **Could recreate broad S?** Not necessarily, but it risks overfitting to a gluten example unrelated to our Gold.
6. **Evidence?** Positive one-shot only; no contrastive example.

Verdict: **no new E or example should be designed.**

---

## Final classification

- **Directly compatible:** terminology-level alignment with exception/actor/action and structured output; already covered.
- **Potentially useful but needs mapping:** recursive span granularity (A), formal precondition/norm structure (D), threshold/condition example (E), modular experiment design (F).
- **Already covered:** condition/constraint/exception definitions, field partition, nested condition/constraint in S/E5, explicit-only R_A, E, structured output.
- **Incompatible:** passive implied subjects, no-omission actor extraction, empty subject = all parties, counterparty `object`, `[MASK]` prompt learning, BPMN question-answering.
- **Insufficient evidence:** no public span overlap/nesting rule; no contrastive boundary example; no complete/minimal span rule; exact round-1 LegalChanges4BPC prompt not public.
