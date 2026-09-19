# Condition / Constraint Boundary Review

Core question: did any reviewed paper provide a public, transferable rule for distinguishing an applicability condition from a restriction, especially when a complete condition contains a quantity/time/threshold/limit and an inner span may separately be a constraint?

Short answer: **No reviewed paper directly resolves our nested condition/constraint annotation boundary.** Several papers provide related structural ideas, but none provides a public span-level rule that would justify a new Stage 2 prompt instruction. The current project already has stronger operational rules and a worked nested example than anything found in the literature.

Evidence labels: **Verified** = direct source quote; **Strongly suggested** = consistent evidence without one explicit rule; **Interpretation** = our mapping.

---

## A. LegalDiscourse (NAACL 2024)

### Q1. Does it distinguish applicability conditions from restrictions on behavior?

**Partial.** The schema has:
- `TEST`: "an explicit condition applied to an entity ... that determines when a SUBJECT-CONSEQUENCE-OBJECT relation holds" (Verified).
- `EXCEPTION`: "a corollary to a TEST; it specifies when a law does NOT apply" (Verified).
- `CONSEQUENCE`: "the specific power or restriction conferred by the law" (Verified).

So it distinguishes applicability (`TEST`/`EXCEPTION`) from consequences/restrictions (`CONSEQUENCE`). It does **not** have a separate `constraint` role.

### Q2. Overlapping spans / nested roles / multi-role spans / parent-child spans?

**Partially discussed, not specified as an annotation rule.** The paper states that the task is recursive and "most of the error and ambiguity ... derived from when to split spans into sub-spans"; annotators were advised to "parse to the lowest-level" (Verified). It also states that a single entity can be both `SUBJECT` and `OBJECT`, and in those cases it was annotated as `OBJECT` (Verified). Section 10.1 says there is "no correct parse" without a use-case and suggests a future tree-like parse structure (Verified). This does not provide a rule for reporting the same span under both `condition` and `constraint`.

### Q3. Complete applicability condition contains quantity/time/threshold/limit phrases?

**Conceptually yes, but no inner constraint label.** The `TEST` prompt asks "Under what conditions does this law apply?" and its examples include population thresholds and census/date conditions (Verified). Those phrases are kept inside the `TEST` span; no separate inner label is extracted. This is compatible with preserving the full condition, but it does not say whether an inner threshold is also a `constraint`.

### Q4. Inclusion/exclusion criteria, contrastive examples, positive/negative examples, minimal/complete span, role relation?

- Positive 1-shot examples: yes.
- Negative examples: no; the prompts use `"none"` / `"no entity"` answers instead.
- Minimal span: no explicit rule; the paper instead advises "parse to the lowest-level" for annotation, which can conflict with our complete-condition rule.
- Complete span: no explicit rule for condition/constraint.
- Role relation: relation prompts exist for identification/classification, but no `condition`-`constraint` relation.
- Inclusion/exclusion criteria: only general "restrict your answer to text in the law."

### Q5. Can it explain "full condition kept, inner span separately constraint"?

**No.** Its schema has no separate `constraint` role, and its annotation practice favored a lowest-level parse rather than co-reporting a parent condition and child restriction. It supports the first half ("keep the TEST/condition"), not the nested dual-role annotation.

Evidence: Verified definitions and prompt text; Interpretation for mapping TEST -> condition.

---

## B. Haque & Singh (COINE 2024 / arXiv 2404.02269)

### Q1. Applicability condition vs behavioral restriction?

**No separate distinction.** The norm model has `antecedent` ("the condition on which the action of the subject depends") and `consequent` ("the outcomes of the action") (Verified). Restrictions are not a separate field; a restrictive phrase can land in the antecedent or consequent.

### Q2. Overlapping/nested roles?

**Not specified.**

### Q3. Complete applicability condition containing quantity/time/threshold?

**Not addressed as a span problem.** The prompt operates at the sentence/norm level and returns normalized elements, not exact source spans. The authors report that conjunctions often lead to incorrect antecedent/consequent parsing and that long complex antecedents/consequents are a problem (Verified), which is consistent with our boundary difficulty but does not solve it.

### Q4. Inclusion/exclusion criteria, contrastive/minimal/complete spans?

- Positive worked examples in the paper: yes.
- Prompt examples: no; zero-shot only.
- Negative/contrastive examples: no.
- Minimal/complete span rules: no.
- Role relation: subject/object directionality definitions are explicit for norm types (Verified).

### Q5. Can it explain nested condition/constraint?

**No.** `object` is a counterparty, `antecedent`/`consequent` are event-level elements. There is no span-level parent/child rule.

Evidence: Verified prompt and reported error analysis.

---

## C. Jingyun Sun, Luo & Li (COLING 2025)

### Q1. Applicability condition vs behavioral restriction?

**No.** The templates extract constrained subjects and deontic words only. There is no condition, constraint, exception, or applicability extraction in the public Appendix C templates (Verified).

### Q2. Overlapping/nested roles?

**Not specified.**

### Q3. Full applicability condition with nested quantity/time/threshold?

**Not addressed.**

### Q4. Inclusion/exclusion criteria, contrastive/minimal/complete spans?

- It uses one positive illustrative example in each template (Verified).
- It gives an accuracy/completeness instruction (Verified).
- No negative/contrastive examples, no span-boundary rule, no minimal/complete span rule.

### Q5. Can it explain nested condition/constraint?

**No.** It is not a condition/constraint extraction method; it provides no evidence on the boundary.

Evidence: Verified Chinese templates.

---

## D. RC4PC (IST 2026)

### Q1. Applicability condition vs behavioral restriction?

**Yes at the formal-structure level, not at the text-span level.** The paper states: "Preconditions are treated as factual conditions and do not carry deontic meaning; deontic modalities are defined only over actions in norms." The exact prompt schema separates `precondition` from `norms` (Verified). Restrictions are encoded inside action objects via `dimension`, `compliance_pattern`, and optional nested `temporal_constraints`, not as a top-level `constraint` role.

### Q2. Overlapping/nested roles?

**Not specified for spans.** The JSON schema permits nested data structures (`temporal_constraints` inside an action object, action objects inside precondition or norm). That is a parent-child formal structure, not a rule that two text spans may carry two semantic roles.

### Q3. Complete applicability condition containing quantity/time/threshold?

**Strongly suggested structural treatment.** Such content can be represented as an action object with `dimension` + `compliance_pattern` (e.g., data/time patterns) and nested `temporal_constraints` in either `precondition` or `norms` (Verified prompt schema). The prompt does not say how to decide whether a phrase belongs to `precondition` or to a norm action, and it does not preserve text spans.

### Q4. Inclusion/exclusion criteria, contrastive/minimal/complete spans?

- Controlled vocabulary: yes.
- Strict schema: yes.
- Exclusivity rule: yes (`A_precedes_B`/`A_followed_by_B` excludes `existence_of_X` for same activities).
- Negative constraints: yes ("do NOT invent new patterns").
- Contrastive examples: no.
- Few-shot examples: no (zero-shot).
- Minimal/complete text-span rules: no.

### Q5. Can it explain nested condition/constraint?

**Partially, but not directly.** It supports the general idea that a condition may contain nested restrictions (e.g., temporal constraints inside an action object), but its unit is a formal action object, not a pair of text spans. It cannot tell us whether `within two years` is merely inside a condition span or also a separate `constraint` span.

Evidence: Verified prompt schema and paper Section 5.1; structural mapping is Interpretation.

---

## E. LegalChanges4BPC (BISE 2026)

### Q1. Applicability condition vs behavioral restriction?

**Yes, terminologically.** The exact prompt defines:
- `condition`: "Specifies when the statement applies."
- `constraint`: "A restriction limiting how or when the regulation is applicable."
- `exception`: "Conditions under which the regulation does not apply."

This is the closest terminology to our schema (Verified).

### Q2. Overlapping/nested roles?

**Not specified.** The prompt asks for a comma-separated `concepts_modified` list. The one-shot example can mention more than one concept type for the same modified statement, but it does not define overlapping text spans, nested roles, or a single span with multiple labels. No such rule was found in the paper or repository.

### Q3. Complete applicability condition containing quantity/time/threshold?

**Some illustrative evidence, no boundary rule.** In the one-shot example, a threshold change ("less than 10ppm") is listed under `constraint`, while a new disclosure condition is listed under `condition`; the same modified statement lists `"concept_modified": "constraint, condition, action_object"` (Verified). This suggests the authors see threshold/limit and applicability condition as distinct concept categories, but it does **not** state their span boundaries or whether one can be nested inside the other.

### Q4. Inclusion/exclusion criteria, contrastive/minimal/complete spans?

- Controlled vocabulary ("Only the following six concept types are allowed"): yes.
- One-shot positive example: yes (second round; final prompt).
- Negative/contrastive examples: no.
- Minimal/complete span rules: no.
- Role relation: no explicit condition/constraint relation beyond the definitions.
- The prompt uses a strong JSON schema and "Return only a JSON array" rule, verified from the repo and paper.

### Q5. Can it explain nested condition/constraint?

**No direct rule.** It is the best terminological source, but its public prompt does not define overlap/nesting. Its example suggests separate changed concept categories, not a parent/child span rule. Treating its definitions as the new boundary rule would over-interpret the paper.

Evidence: Verified prompt text and one-shot example; no span rule found.

---

## F. Kölbel, Poss & Schönig (2026, optional)

### Q1-Q5.

**Not applicable / cannot resolve.** The paper does not extract condition, constraint, or exception roles. It uses a modular prompt builder to answer questions about BPMN process models against external standards. It offers useful experimental design patterns (modular components, zero-shot/few-shot/CoT/role/context/format controls, missing-information handling, error typology), but no condition/constraint annotation boundary. Do not transfer it to Stage 2.

---

## G. DPLACC (2026, optional)

### Q1-Q5.

**Not applicable / conceptually different.** DPLACC is prompt learning with a `[MASK]` template, first-order-logic vectors, and a verbalizer (`yes`/`no`). It performs sentence-pair compliance classification. It does not extract semantic roles or spans and is not an instruction-based LLM prompting method. It cannot resolve our condition/constraint boundary.

---

## Cross-paper synthesis

| Question | Best evidence found | Does it resolve our boundary? |
|---|---|---|
| Separate condition vs restriction | LegalDiscourse TEST/CONSEQUENCE; RC4PC precondition/norm; LegalChanges4BPC condition/constraint | Terminology yes; span policy no |
| Overlapping/nested spans | LegalDiscourse recursive sub-span discussion; RC4PC nested formal action objects | No public span-level overlap rule |
| Full condition containing threshold/quantity/time | LegalDiscourse TEST examples; RC4PC nested temporal/data patterns; LegalChanges4BPC threshold example | Suggestive only |
| Inclusion/exclusion/contrastive examples | No paper has contrastive examples for similar labels | No |
| Minimal vs complete span | LegalDiscourse discusses lowest-level parsing, but as ambiguity, not a rule; no paper gives a complete-condition + inner-constraint rule | No |
| Can explain "full condition kept + inner constraint" | Current project's S rule 8 and E5 example explicitly do this | Literature does not add a better rule |

**Verified finding:** none of Papers A-G contains a public annotation principle that explicitly permits and bounds overlapping condition/constraint spans in the way our current project already does.

**Interpretation:** the closest cross-paper idea is nested structure (RC4PC) or recursive parsing (LegalDiscourse), but neither is a safe textual annotation rule for our Gold.

**Conclusion:** mark condition/constraint boundary evidence as **insufficient evidence** for a new prompt instruction. No literature-grounded rule should be added solely from this review.
