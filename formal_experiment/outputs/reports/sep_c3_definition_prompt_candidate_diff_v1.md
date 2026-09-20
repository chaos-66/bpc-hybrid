# SEP-C3 Definition Prompt Candidate Diff v1

- Status: **candidate-only; not applied**
- New API / LLM calls: **0**
- Active prompt changes: **none**
- Gold changes: **none**
- Prediction changes: **none**

This file records the exact candidate text changes for offline review. It does
not modify `semantic_rules_S.md` or `examples_E.md`.

## 1. S2 modality candidate

### Current (source unchanged)

Source: `formal_experiment/prompts/sun_compat/modular_v1/semantic_rules_S.md`

```text
2. Modality: label each clause obligation, prohibition, permission, or definition. Use the smallest sufficient surface trigger as evidence; include negation evidence when it changes the class.
```

### Proposed candidate

```text
2. Modality: label each clause obligation, prohibition, permission, or definition. Use the smallest sufficient surface trigger as evidence; include negation evidence when it changes the class. Definition is semantic rather than lexical: a clause may define by establishing legal status, identity, classification or membership, legal fiction, or a scope/applicability characterization, even without an explicit definition marker. The word "shall" does not by itself make a clause an obligation, and "shall" plus a verb does not by itself determine modality; classify from what the clause does in context. An obligation instead imposes required conduct or a required method on a duty bearer or regulated subject, whereas a definition characterizes what something is or how it is treated.
```

### Candidate diff

```diff
 2. Modality: label each clause obligation, prohibition, permission, or definition. Use the smallest sufficient surface trigger as evidence; include negation evidence when it changes the class.
+Definition is semantic rather than lexical: a clause may define by establishing legal status, identity, classification or membership, legal fiction, or a scope/applicability characterization, even without an explicit definition marker.
+The word "shall" does not by itself make a clause an obligation, and "shall" plus a verb does not by itself determine modality; classify from what the clause does in context.
+An obligation instead imposes required conduct or a required method on a duty bearer or regulated subject, whereas a definition characterizes what something is or how it is treated.
```

## 2. S11 definition-action candidate

### Current (source unchanged)

Source: `formal_experiment/prompts/sun_compat/modular_v1/semantic_rules_S.md`

```text
11. Definition and empty records: a definition clause may have no actions. A fragment with no defensible normative clause may have clauses=[] and must report the missing semantic field with a controlled reason.
```

### Proposed candidate

```text
11. Definition and empty records: a definition clause normally contains an action span representing the definitional predicate. Do not omit the action merely because the clause is classificatory, stative, relational, or copular; give the predicate span that the sentence supports. Exact action boundaries still follow the evidence in the sentence. A fragment with no defensible normative clause may have clauses=[] and must report the missing semantic field with a controlled reason.
```

### Candidate diff

```diff
-11. Definition and empty records: a definition clause may have no actions. A fragment with no defensible normative clause may have clauses=[] and must report the missing semantic field with a controlled reason.
+11. Definition and empty records: a definition clause normally contains an action span representing the definitional predicate. Do not omit the action merely because the clause is classificatory, stative, relational, or copular; give the predicate span that the sentence supports. Exact action boundaries still follow the evidence in the sentence. A fragment with no defensible normative clause may have clauses=[] and must report the missing semantic field with a controlled reason.
```

## 3. E4 replacement candidate

Full JSON: `formal_experiment/outputs/reports/sep_c3_definition_synthetic_E4_candidate_v1.json`

### Current (source unchanged)

Source: `formal_experiment/prompts/sun_compat/modular_v1/examples_E.md`

```text
Example E4 — definition clause followed by an obligation clause:
Input: "'Personal data' means information about a person; the controller must protect it."
- clause 1 span [0,48): definition; evidence "means" [16,21); actors and actions empty
- clause 2 span [50,81): obligation; evidence "must" [65,69); actor "the controller" [50,64), normalized "controller"; action "protect it" [70,80)
- conditions, constraints, exceptions: empty in both clauses
```

### Proposed synthetic E4 candidate

```text
Example E4 — classification definition and explicit means definition:
Input: "A jointly operated community library is classified as a single service unit for the purposes of this bylaw; 'service unit' means a facility open to the public."
- clause 1 span [0,106): definition; evidence "classified as" [40,53); actors empty; action "is classified as a single service unit" [37,75); constraint "for the purposes of this bylaw" [76,106); exceptions empty
- clause 2 span [108,159): definition; evidence "means" [123,128); actors empty; action "means a facility open to the public" [123,158); conditions, constraints, exceptions empty
```

### Candidate diff (conceptual block replacement)

```diff
-Example E4 — definition clause followed by an obligation clause:
-Input: "'Personal data' means information about a person; the controller must protect it."
-- clause 1 span [0,48): definition; evidence "means" [16,21); actors and actions empty
-- clause 2 span [50,81): obligation; evidence "must" [65,69); actor "the controller" [50,64), normalized "controller"; action "protect it" [70,80)
-- conditions, constraints, exceptions: empty in both clauses
+Example E4 — classification definition and explicit means definition:
+Input: "A jointly operated community library is classified as a single service unit for the purposes of this bylaw; 'service unit' means a facility open to the public."
+- clause 1 span [0,106): definition; evidence "classified as" [40,53); actors empty; action "is classified as a single service unit" [37,75); constraint "for the purposes of this bylaw" [76,106); exceptions empty
+- clause 2 span [108,159): definition; evidence "means" [123,128); actors empty; action "means a facility open to the public" [123,158); conditions, constraints, exceptions empty
```

## 4. Scope guard

The candidate diff does **not** modify:

- `R_A`
- `R_C`
- `S8`
- condition/constraint boundary guidance
- exception guidance
- exact action complement guidance
- Gold
- predictions
- ambiguous apply-family modality labels
- `estg_000505` / `estg_000509` Gold

## 5. Assembly impact if later applied

- S2/S11 candidate text lives in `semantic_rules_S.md`; it only affects prompts with `S=1` after the modular prompt generator is rerun.
- Current SEP-C3 targeted-refinement A/B/C/D prompts do not include S, so they would remain unchanged unless the arm design changes.
- E4 candidate text lives in `examples_E.md`; it would affect every E-enabled prompt after regeneration, including current A/B/C/D.
- No generated prompt file in this task was regenerated.
