# R13.6 Prompt-refinement Design

## 1. Purpose

This document describes the design of three candidate prompts for a possible
R13.7 bounded real API mini-pilot. The prompts are based on the error analysis
from R13.5 (`docs/r13_5_post_pilot_error_analysis.md`) and the refinement
directions from `docs/r13_5_prompt_refinement_plan.md`.

This is a **design-only** stage. No real API call, no LLM call, and no
evaluator rerun occur in R13.6.

## 2. Evidence From R13.5

The R13.5 post-pilot analysis of the R13.4.2 8-sample mini-pilot identified
these error patterns (ranked by pervasiveness):

| Rank | Error | Samples Affected | Prompt Cause Hypothesis |
|------|-------|-----------------|------------------------|
| 1 | Action verbatim fragment extraction | 8/8 | No normalization instruction in prompt |
| 2 | Constraint as adverbial fragment | 8/8 | No full-proposition requirement in prompt |
| 3 | Passive-voice actor omission | 4/8 | No inference-from-passive instruction |
| 4 | German text not normalized to English | 3/8 | No output-language constraint |
| 5 | Subject complement confused with action | 1/8 | No "regulated activity" concept in prompt |
| 6 | Definition misclassified as obligation | 1/8 | No definition-vs-obligation boundary guidance |

All patterns are attributable to **prompt underspecification** rather than
demonstrated model incapability. The R13.4.2 prompt was minimal (schema-only,
no field definitions, no examples).

## 3. Error Patterns Being Targeted

The three candidate prompts target these error categories from R13.5
(`data/formal/metadata/r13_5_error_taxonomy.json`):

| Error Category | Prompt A | Prompt B | Prompt C |
|---------------|----------|----------|----------|
| actor_missing | ✅ inference rule | ✅ Example 1 | ✅ internal step |
| actor_wrong_granularity | ✅ canonical form rule | ✅ example demo | ✅ internal step |
| action_wrong_granularity | ✅ norm rule | ✅ all examples | ✅ internal step |
| action_subject_complement_confusion | — | — | ✅ internal step |
| condition_boundary_error | ✅ definition | ✅ example | ✅ internal step |
| constraint_boundary_error | ✅ definition | ✅ examples | ✅ definition |
| constraint_as_adverbial_fragment | ✅ definition | ✅ examples | ✅ definition |
| definition_as_obligation_error | ✅ definition text | ✅ Example 3 | ✅ internal step |
| passive_voice_actor_error | ✅ inference rule | ✅ Example 1 | ✅ internal step |
| field_normalization_error | ✅ English rule | ✅ all examples | ✅ English rule |
| german_text_normalization_failure | ✅ English rule | ✅ Example 3 | ✅ English rule |

## 4. Prompt A — Field Definitions

**File**: `prompts/r13_6/field_definition_strengthened_prompt.md`

**Strategy**: Declarative. Adds detailed per-field semantic definitions
and normalization rules directly into the prompt text. No examples.

**Key additions over R13.4.2 prompt**:
- modality: 5-type classification with keywords and a definition-vs-obligation boundary note
- actor: explicit passive-voice inference instruction, canonical form rule
- action: explicit [verb] [object] normalization rule, anti-verbatim warning
- condition: trigger-condition definition with "where/if/when" keywords
- constraint: full-proposition rule, anti-fragment warning
- exception: explicit carve-out definition
- Language constraint: all output in English
- Stronger format enforcement: "Output ONLY the JSON object. No markdown fences."

**Expected effect**: Moderate improvement on actor (passive-voice inference)
and action (normalization). Some improvement on constraint (full proposition).
Limited effect on definition-vs-obligation (text only, no example).

**Risk**: Without examples, model may still default to verbatim extraction
despite definitions. The definition of "normalized action phrase" may be
interpreted differently.

## 5. Prompt B — Few-shot Extraction

**File**: `prompts/r13_6/few_shot_extraction_prompt.md`

**Strategy**: In-context learning. Provides 3 annotated examples showing
expected field granularity.

**Examples**:
1. GDPR Art 5(1)(a)-style obligation with passive voice → demonstrates inferred actor + normalized action + full constraint
2. GDPR Art 9(1)-style prohibition with condition → demonstrates condition/constraint separation + normalized action
3. Austrian §1 Abs 1-style definition clause (German) → demonstrates definition-vs-obligation + German-to-English normalization

**Key design decisions**:
- Examples are **synthetic** — not copied from the R13.4.2 real 8 samples. They mirror the patterns without data contamination.
- Example 3 is deliberately in German to demonstrate the translation/normalization expected for non-English input.
- All 3 examples show the correct [verb] [object] action normalization.
- All 3 examples show full propositional constraint statements.

**Expected effect**: Stronger improvement on action normalization (concrete
demonstration). Better passive-voice actor inference (Example 1). Better
definition-vs-obligation classification for German input (Example 3).

**Risk**: Examples may overfit model output to the specific patterns shown.
Synthetic examples may not fully match real input distribution. 3 examples
may not cover all legal sentence patterns.

## 6. Prompt C — Two-step Hidden Extraction

**File**: `prompts/r13_6/two_step_hidden_extraction_prompt.md`

**Strategy**: Cognitive. Instructs the model to internally decompose the
sentence (modality → regulated activity → actor → condition → constraint →
exception) before producing the JSON output. Reasoning is explicitly
forbidden from appearing in the output.

**Key design decisions**:
- Internal steps are numbered 1-6 for clarity.
- Each step has a specific determination task.
- The "regulated activity" step (step 2) is designed to prevent subject
  complement confusion (R13.4.2 sample 003).
- The modality-first step (step 1) is designed to prevent definition-vs-
  obligation errors (R13.4.2 sample 006).
- Strong anti-reasoning-output language: "Do NOT include any of this
  internal analysis in your output. Do NOT write chain-of-thought."

**Expected effect**: May resolve the subject-complement confusion
(sample 003) by forcing internal separation of the regulated activity
from quality predicates. May improve definition-vs-obligation
classification.

**Risk**: Model may ignore the hidden-reasoning instruction and still
produce surface extraction. No concrete output examples to guide format.
Effectiveness depends on model's instruction-following for internal
reasoning tasks.

## 7. Prompt Comparison

See `data/formal/metadata/r13_6_prompt_selection_matrix.json` for the
full structured comparison.

Summary:

| Dimension | Prompt A | Prompt B | Prompt C |
|-----------|----------|----------|----------|
| Strategy | Declarative | In-context | Cognitive |
| Examples | 0 | 3 synthetic | 0 |
| Length | ~550 words | ~750 words | ~600 words |
| Action norm coverage | Rule only | Rule + demo | Internal step |
| Actor inference coverage | Rule only | Rule + demo | Internal step |
| Def-vs-oblig coverage | Text note | Example 3 | Internal step 1 |
| Subject-complement fix | — | — | Internal step 2 |
| Debuggability | High | Medium | Low |
| Overfitting risk | None | Medium | Low |
| Priority | 2 | **1** | 2 |

## 8. Recommended Next Prompt

**Primary recommendation**: **Prompt B (few_shot_extraction)** for R13.7.

**Rationale**:
1. Action normalization is the most pervasive error (8/8 samples wrong in
   R13.4.2). Prompt B provides concrete demonstrations of the expected form.
2. Passive-voice actor omission (4/8 samples missing) is directly addressed
   by Example 1.
3. Definition-vs-obligation confusion (sample 006) is addressed by Example 3.
4. The synthetic examples avoid data contamination with the real 8 samples.
5. Few-shot learning is a well-established technique for aligning LLM output
   format and granularity.

**Alternative**: Prompt C if few-shot examples are not desired.

**Caveat**: This recommendation is a hypothesis based on 8 samples from one
mini-pilot with one model (qwen3.7-max). Only a real API test can validate
effectiveness.

## 9. Risks

- **All prompts untested**: No prompt has been tested against a real API.
  All expected effects are hypotheses.
- **Single model**: qwen3.7-max behavior may not generalize to other models.
- **8-sample basis**: Error patterns observed in 8 samples may not be
  representative.
- **Gold subjectivity**: Improvements are measured against human-annotated
  gold that involves judgment calls (especially actor inference).
- **Prompt interaction effects**: Adding field definitions may interact
  with few-shot examples in unexpected ways.
- **Overfitting**: Prompt B examples may constrain model behavior more than
  intended.

## 10. Claim Boundary

This is a prompt-refinement design document based on one bounded 8-sample
mini-pilot (R13.4.2) and its post-hoc error analysis (R13.5). No prompt
has been tested against a real API. No benchmark, method validation, or
Sun reproduction claims are made.
