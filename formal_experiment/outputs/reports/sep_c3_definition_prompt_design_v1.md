# SEP-C3 Definition Prompt Design v1

- Task: design the smallest defensible prompt refinement for definition clauses
- Role: strict design review only
- New API / LLM calls: **0**
- Active prompt modifications: **none**
- Gold modifications: **none**
- Prediction modifications: **none**
- Patch status: **not applied**

This report is a design-review gate. It separates frozen evidence, candidate
wording, safety review, and unresolved issues. It does not claim a measured
improvement and does not run an experiment.

## 0. Evidence read and scope

The following checkpoint reports were read completely before this design:

- `formal_experiment/outputs/reports/sep_c3_definition_adjudication_v1.md`
- `formal_experiment/outputs/reports/sep_c3_definition_adjudication_cases.jsonl`
- `formal_experiment/outputs/reports/sep_c3_definition_modality_contrastive_matrix.csv`
- `formal_experiment/outputs/reports/sep_c3_definition_prompt_design_gate.md`
- `formal_experiment/outputs/reports/sep_c3_E4_final_diagnosis.md`
- `formal_experiment/outputs/reports/sep_c3_S_definition_guidance_diagnosis.md`

Only the three gate-approved issues are designed here:

1. `MISSING_DEFINITION_MODALITY_GUIDANCE` (S2)
2. definition clauses incorrectly being allowed to have empty action spans (S11/E4)
3. `E4` conflict with Gold because its definition example has no action (E4)

The following remain out of scope and untouched:

- actor `R_A`
- constraint `R_C`
- condition/constraint boundary
- exception guidance
- exact action complement boundary
- `S8` boundary logic
- `estg_000505` / `estg_000509` Gold
- ambiguous apply-family modality labels

## 1. Task 1 - current prompt components and assembly

### 1.1 Component map

| Component | Exact file | Current text | Active in current SEP-C3 A/B/C/D? |
|---|---|---|---|
| S2 | `formal_experiment/prompts/sun_compat/modular_v1/semantic_rules_S.md` | `2. Modality: label each clause obligation, prohibition, permission, or definition. Use the smallest sufficient surface trigger as evidence; include negation evidence when it changes the class.` | No. Current A/B/C/D arms are common + E + optional R_A/R_C; S is absent. |
| S11 | `formal_experiment/prompts/sun_compat/modular_v1/semantic_rules_S.md` | `11. Definition and empty records: a definition clause may have no actions. A fragment with no defensible normative clause may have clauses=[] and must report the missing semantic field with a controlled reason.` | No. Current A/B/C/D arms do not include S. |
| S8 | `formal_experiment/prompts/sun_compat/modular_v1/semantic_rules_S.md` | `8. Field partition: condition, constraint, and exception are separate arrays. Never fold their content into the action span; the action ends where such a phrase begins. A constraint nested inside a condition is reported in both arrays.` | No. S8 is explicitly not ready for repair and is untouched. |
| E4 | `formal_experiment/prompts/sun_compat/modular_v1/examples_E.md` | `Example E4 — definition clause followed by an obligation clause:` with input `"'Personal data' means information about a person; the controller must protect it."`; clause 1 is `definition; evidence "means"; actors and actions empty` | Yes. E is included in current A/B/C/D user prompts, so E4 is active. |
| Other definition wording | `common_system.md`, `user_envelope.md`, `output_format_J.md` | No definition-specific semantic guidance. | Common/J may be active depending on family; none contains definition guidance. |

### 1.1a Exact current E4 text

Source: `formal_experiment/prompts/sun_compat/modular_v1/examples_E.md`

```text
Example E4 — definition clause followed by an obligation clause:
Input: "'Personal data' means information about a person; the controller must protect it."
- clause 1 span [0,48): definition; evidence "means" [16,21); actors and actions empty
- clause 2 span [50,81): obligation; evidence "must" [65,69); actor "the controller" [50,64), normalized "controller"; action "protect it" [70,80)
- conditions, constraints, exceptions: empty in both clauses
```

### 1.2 Few-shot example construction

- The E module is `formal_experiment/prompts/sun_compat/modular_v1/examples_E.md`.
- It contains prose/numbered synthetic examples E1-E5, not JSON `## Examples` blocks.
- The composer places the whole E module into the user prompt; the system prompt is common + S + J according to the E/S/J flags.
- `prompt_loader.py` can extract JSON few-shot examples from `## Examples` blocks, but the modular E examples are not loaded through that JSON path. They are part of the rendered user prompt. Therefore the replacement must be written as an `Example E4` block in the same E-module style.

### 1.3 Final active prompt assembly path

There are two relevant assemblies:

1. **Frozen modular E/S/J family**
   - Source modules: `common_system.md`, `user_envelope.md`, `semantic_rules_S.md`, `examples_E.md`, `output_format_J.md`.
   - Composer: `formal_experiment/src/bpc_hybrid/modular_prompt.py`.
   - Builder: `formal_experiment/scripts/build_modular_prompt_v1.py --write`.
   - Generated outputs: `formal_experiment/prompts/sun_compat/modular_v1/generated/direct_llm_modular_<ESJ>_v1.md`.
   - This family is rejected for default use by its own README, but it remains the source of the S/E modules.

2. **Current SEP-C3 targeted-refinement A/B/C/D family**
   - Composer: `formal_experiment/src/bpc_hybrid/modular_refinement_prompt.py`.
   - It reuses frozen modular arm `100` (`E=1, S=0, J=0`) and appends optional `R_A` and/or `R_C`.
   - Runner/path: `formal_experiment/scripts/run_sep_c3_targeted_refinement_v1.py` loads `prompts/sun_compat/modular_refinement_v1/generated/direct_llm_refinement_{A,B,C,D}_v1.md`.
   - `S2`, `S11`, and `S8` are not in the current sent system prompt. `E4` is in the current user prompt for all four arms.
   - Consequently, a future S2/S11 patch would affect S-enabled prompts only; an E4 patch would affect the E block in all current arms after regeneration.

Current active prompt hashes at the start of this design review:

| Artifact | SHA-256 |
|---|---|
| `modular_v1/common_system.md` | `b8cfc32b87f446ced89da83fd0ad5aef69ee418a116c6ede534816c5204ac2d7` |
| `modular_v1/user_envelope.md` | `e8f18096d7260ccd23a6a1ed562b15c861f4e6caf2e5bc7de96a8a23d4e98728` |
| `modular_v1/semantic_rules_S.md` | `113037b73485adb071dbfeabc54dfe6906514279c3dd065f72b4eb019d3a0025` |
| `modular_v1/examples_E.md` | `fa04d454914fd85ad422ed40b3e4d3f71027ad87e9a46b1f4808f0cb4e21aebd` |
| `modular_v1/output_format_J.md` | `aa4ed3db8c8b55090a719467802cc878847b436fab9ec8af4d730dce9e899879` |
| `modular_refinement_v1/generated/direct_llm_refinement_A_v1.md` | `d24c0c0d5150dd6382260f91614cc6d475ecdb68efb2cfe8d48347272d74a580` |
| `modular_refinement_v1/generated/direct_llm_refinement_B_v1.md` | `c468c631b6e454522994d6839f6a4021a259daedea7f3a2852b7b4343cd22849` |
| `modular_refinement_v1/generated/direct_llm_refinement_C_v1.md` | `d58163b677c6a7bda06f4de3ea8de743d8568e0d5e2c740bdea8af48ccfa4479` |
| `modular_refinement_v1/generated/direct_llm_refinement_D_v1.md` | `b241126dcb04001872e3bfd60deb330ed884ccad50537cc2031017a66835c091` |

No prompt file is modified by this review.

## 2. Task 2 - minimal S2 refinement

### S2_CURRENT

```text
2. Modality: label each clause obligation, prohibition, permission, or definition. Use the smallest sufficient surface trigger as evidence; include negation evidence when it changes the class.
```

### S2_PROPOSED

```text
2. Modality: label each clause obligation, prohibition, permission, or definition. Use the smallest sufficient surface trigger as evidence; include negation evidence when it changes the class. Definition is semantic rather than lexical: a clause may define by establishing legal status, identity, classification or membership, legal fiction, or a scope/applicability characterization, even without an explicit definition marker. The word "shall" does not by itself make a clause an obligation, and "shall" plus a verb does not by itself determine modality; classify from what the clause does in context. An obligation instead imposes required conduct or a required method on a duty bearer or regulated subject, whereas a definition characterizes what something is or how it is treated.
```

### S2_DIFF

```diff
 2. Modality: label each clause obligation, prohibition, permission, or definition. Use the smallest sufficient surface trigger as evidence; include negation evidence when it changes the class.
+Definition is semantic rather than lexical: a clause may define by establishing legal status, identity, classification or membership, legal fiction, or a scope/applicability characterization, even without an explicit definition marker.
+The word "shall" does not by itself make a clause an obligation, and "shall" plus a verb does not by itself determine modality; classify from what the clause does in context.
+An obligation instead imposes required conduct or a required method on a duty bearer or regulated subject, whereas a definition characterizes what something is or how it is treated.
```

### RATIONALE

- The current S2 names `definition` as a label but gives no semantic coverage for legal fiction, classification, status, or scope/applicability.
- The proposal makes the distinction functional and contextual.
- It explicitly prevents the most visible shortcut in the current failures: treating `shall` as an obligation trigger.
- It preserves `definition` as a semantic category rather than a phrase list.
- It keeps the contrast with genuine deontic obligation, but does not claim that every obligation must have an explicit extracted actor.

### SUPPORTED_BY

- 39 Gold definition clauses, including 15 containing `shall`.
- 25/39 definition clauses and 15/15 shall-definition clauses were predicted as non-definition in all four arms.
- The gate report marks missing definition semantics as `READY_FOR_PROMPT_DESIGN` for core semantic coverage.
- `sep_c3_S_definition_guidance_diagnosis.md` confirms `MISSING_DEFINITION_MODALITY_GUIDANCE`.
- Gold definition families include legal status, identity, classification/membership, legal fiction, and scope/applicability.

### KNOWN_LIMITATIONS

- The apply/applies family remains mixed (`7 definition` vs `5 non-definition` in core cases), and near-identical `the following applies` clauses receive different Gold labels.
- `estg_000505 c2` vs `estg_000509 c2` remains a `POTENTIAL_GOLD_INCONSISTENCY`.
- `shall be determined` remains contextually explainable only from argument structure, not from a surface rule.
- The wording still has to choose a label in genuinely ambiguous cases; it does not create an unresolved output label.
- The proposal must not be strengthened into an exception-free rule and must not be treated as a lexical classifier.
- No measured improvement is claimed.

## 3. Task 3 - minimal S11 refinement

### S11_CURRENT

```text
11. Definition and empty records: a definition clause may have no actions. A fragment with no defensible normative clause may have clauses=[] and must report the missing semantic field with a controlled reason.
```

### S11_PROPOSED

```text
11. Definition and empty records: a definition clause normally contains an action span representing the definitional predicate. Do not omit the action merely because the clause is classificatory, stative, relational, or copular; give the predicate span that the sentence supports. Exact action boundaries still follow the evidence in the sentence. A fragment with no defensible normative clause may have clauses=[] and must report the missing semantic field with a controlled reason.
```

### S11_DIFF

```diff
-11. Definition and empty records: a definition clause may have no actions. A fragment with no defensible normative clause may have clauses=[] and must report the missing semantic field with a controlled reason.
+11. Definition and empty records: a definition clause normally contains an action span representing the definitional predicate. Do not omit the action merely because the clause is classificatory, stative, relational, or copular; give the predicate span that the sentence supports. Exact action boundaries still follow the evidence in the sentence. A fragment with no defensible normative clause may have clauses=[] and must report the missing semantic field with a controlled reason.
```

### RATIONALE

- Gold has 39 definition clauses with 39/39 containing at least one action span; 0/39 are empty.
- The old S11 explicitly says a definition clause may have no actions and therefore licenses the exact error observed in the aligned predictions.
- The new wording replaces permission with a presence expectation while avoiding a universal exact-boundary rule.
- It explicitly covers classification/static/copular clauses, where models currently tend to omit an action.

### SUPPORTED_BY

- Gate matrix: S11 action-empty permissiveness is `READY_FOR_PROMPT_DESIGN`.
- S diagnosis: `MISLEADING_PERMISSIVE_GUIDANCE`.
- 46 Gold definition action spans across 39 clauses; aligned predicted empty-action counts A=10, B=13, C=12, D=12.
- E4 final diagnosis: `actions empty` has `0/39` compatibility with Gold.

### KNOWN_LIMITATIONS

- Exact action boundaries remain unresolved; this proposal does not introduce or repair a boundary rule.
- `S8` remains locally conflicting at `estg_000020 c1` and is untouched.
- The wording says `normally` because the evidence is a stable presence principle, not a universal formal proof over all future texts.
- It does not tell the model how to choose the exact complement; that remains evidence-bound.
- No measured improvement is claimed.

## 4. Task 4 - replacement E4 (synthetic)

Full JSON: `formal_experiment/outputs/reports/sep_c3_definition_synthetic_E4_candidate_v1.json`.

Synthetic candidate sentence:

```text
A jointly operated community library is classified as a single service unit for the purposes of this bylaw; 'service unit' means a facility open to the public.
```

Expected Rule Record (summary; exact offsets are in the JSON):

| Clause | clause_span | modality / evidence | actors | actions | conditions | constraints | exceptions |
|---|---|---|---|---|---|---|---|
| c1 | `[0,106)` | definition; `classified as` `[40,53)` | `[]` | `is classified as a single service unit` `[37,75)` | `[]` | `for the purposes of this bylaw` `[76,106)` | `[]` |
| c2 | `[108,159)` | definition; `means` `[123,128)` | `[]` | `means a facility open to the public` `[123,158)` | `[]` | `[]` | `[]` |

Field-by-field justification:

- **c1 modality=definition:** establishes a classification/characterization, not required conduct.
- **c1 evidence=`classified as`:** the smallest sufficient definitional-classification predicate in the sentence.
- **c1 actors=[]:** the library is the topic of classification, not a duty bearer.
- **c1 action non-empty:** directly fixes the old E4 conflict with the 39/39 Gold action-presence evidence.
- **c1 constraint=`for the purposes of this bylaw`:** a natural purpose/scope limit, not artificial field filling.
- **c2 modality=definition and evidence=`means`:** preserves the narrow but valid explicit-definition signal from the old E4.
- **c2 action non-empty:** `means a facility open to the public` includes the necessary complement.
- **empty fields:** conditions and exceptions are empty in c1; c2 has only action/evidence. The candidate does not fill every field.

Why it improves over old E4:

- Old E4 taught an empty definition action; the replacement has a non-empty definitional action in every definition clause.
- Old E4 demonstrated only `means`; the replacement adds a non-`means` classification definition.
- The replacement still contains one explicit `means` clause, so the valid narrow means evidence is not abandoned.
- It adds a natural purpose constraint while leaving several fields empty.
- It is synthetic and does not use an EStG sentence or sample ID.

What it intentionally does **not** teach:

- It does not turn `classified as`, `means`, or any other phrase into a deterministic lookup rule.
- It does not resolve the apply/applies family, `shall be assumed`, or `shall be determined` ambiguities.
- It does not say that every stative/copular/relational clause is a definition.
- It does not teach a universal exact action-complement or condition/constraint boundary rule.
- It does not teach actor-action-map or order-relation behavior.
- It does not add a deontic clause; E1-E3 and E5 continue to cover other modalities.

## 5. Task 5 - contrastive safety review

Full review: `formal_experiment/outputs/reports/sep_c3_definition_prompt_safety_review_v1.md`.

Summary:

| Category | S2 proposal | S11 proposal | E4 replacement | Overall |
|---|---|---|---|---|
| A. explicit definition using `means` | helps (definition remains available) | helps (action required) | helps (keeps a `means` clause with action) | helps |
| B. legal-fiction definition using `shall` | helps (shall is not automatic obligation) | helps (action presence) | neutral (synthetic example has no `shall`) | helps, with overgeneralization caveat |
| C. applicability/scope statement | risks over-labeling definition unless context is required | neutral | neutral | remains `NEEDS_GOLD_ADJUDICATION`; do not infer resolved |
| D. normal actor-directed obligation using `shall` | helps via duty-conduct/method contrast | neutral | neutral | helps |
| E. permission using `may` | neutral | neutral | neutral | neutral |
| F. prohibition using `may not` / `shall not` | neutral | neutral | neutral | neutral |
| G. ambiguous apply-family clause | risk if read as a rule; not a rule | neutral | neutral | remains explicitly unresolved |
| H. `shall be determined` contextual pair | helps with caution (`shall` not decisive; context decides) | helps action presence | neutral | partially helps; context pair remains unresolved |

The candidate does **not** turn all `shall + stative verb` clauses into definitions. It says `shall` plus a verb does not determine modality and requires functional/contextual interpretation. The apply-family and `shall be determined` ambiguities remain unresolved.

## 6. Task 6 - overfitting / test-leakage review

| Risk | Inspection result | Decision |
|---|---|---|
| Specific EStG wording | Prompt candidate text contains no EStG sentence. Synthetic example uses `community library` and `bylaw`. | No leakage. |
| Sample IDs | No sample ID appears in proposed prompt wording. Reports may cite IDs only as evidence. | No leakage. |
| Memorized predicates as deterministic rules | S2 does not enumerate predicates. E4 uses `classified as` and `means` as illustrative examples, not as rules. | No deterministic lookup rule. |
| Gold labels of ambiguous test cases | `estg_000505` / `estg_000509` and apply-family labels are not encoded. They remain marked unresolved. | No label leakage. |
| Narrow patterns from one or two examples | S2 is corpus-level; S11 is 39/39 presence evidence; E4 is one synthetic illustration of classification and means, explicitly not a rule. | No overfitting; keep as design candidate. |
| Test-specific lexical shortcut | The replacement avoids `shall + stative` as a definition trigger and avoids apply-family surfaces as decision rules. | Portable semantic wording. |

Conclusion: the proposal passes the leakage/overfitting review. It is semantic and portable. The E4 candidate's `classified as` predicate is illustrative only; no prompt text says that phrase always means definition.

## 7. Task 7 - decision gate

| Proposed change | Status | Reason |
|---|---|---|
| S2 definition semantic guidance | `READY_FOR_OFFLINE_PATCH` | Core semantic coverage is stable and gate-approved. Apply-family and `shall be determined` boundaries remain unresolved and are not resolved by the wording. |
| S11 definition action-presence guidance | `READY_FOR_OFFLINE_PATCH` | 39/39 Gold definitions have actions; 0/39 are empty. The wording removes the permissive cue without inventing an exact-boundary rule. |
| E4 replacement | `READY_FOR_OFFLINE_PATCH` | Synthetic; all definition clauses carry non-empty definitional actions; retains means coverage; no deontic ambiguity; exact boundary is not universalized. |

No patch is applied in this task. The statuses are design-gate statuses only.

## 8. Unresolved issues preserved

- apply/applies modality boundary: `NEEDS_GOLD_ADJUDICATION`
- `estg_000505 c2` vs `estg_000509 c2`: `POTENTIAL_GOLD_INCONSISTENCY`
- `shall be determined`: contextually explainable, not surface-decidable
- `S8` exact action boundary: locally conflicting; untouched
- condition/constraint boundary: out of scope and unresolved
- actor `R_A`, constraint `R_C`, exception guidance: untouched
- no result is presented as a measured improvement

## 9. Verification and no-op checks

- New API / LLM calls: 0.
- Active prompt files: byte-identical at review time; no prompt file was written.
- Gold: byte-identical at review time; no Gold file was written.
- Predictions: byte-identical at review time; no prediction file was written.
- Only design reports and one candidate JSON were created by this task, plus focused report/invariant tests if present.
