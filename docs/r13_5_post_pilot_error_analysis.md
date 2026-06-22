# R13.5 Post-pilot Error Analysis

## 1. Scope

This document analyzes the R13.4.2 bounded 8-sample real API mini-pilot
results. The analysis is post-hoc and read-only:

- Real API call: no
- LLM call: no
- Evaluator rerun: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no

The evidence is the committed R13.4.2 prediction JSONL, evaluation summary,
and evaluation details. No new data is generated in this stage.

## 2. Input Evidence

| File | Role |
|------|------|
| `data/formal/predictions/r13_4_2_real_predictions.jsonl` | Model predictions (8 samples) |
| `data/formal/results/r13_4_2_real_evaluation_summary.json` | Field-level score counts |
| `data/formal/results/r13_4_2_real_evaluation_details.jsonl` | Sample-level field scores |
| `data/formal/processed/r13_3_candidate_samples.jsonl` | Candidate texts |
| `data/formal/gold/r13_3_manual_gold_template.jsonl` | Gold annotations |

## 3. Overall Observations

In this 8-sample mini-pilot (5 GDPR EurLex + 3 Austrian Income Tax Code):

- **8/8 schema-valid** — all predictions passed JSON schema validation.
- **7/8 modality exact** — the model generally distinguishes obligation,
  prohibition, and definition correctly.
- **0/8 actor exact** — the model never produced an actor field that
  matched gold exactly.
- **0/8 action exact** — the model never produced an action field that
  matched gold exactly.
- **0/8 constraint exact** — the model never produced a constraint field
  that matched gold exactly.
- **Exception field**: all 8 samples had `not_applicable` for exception
  (both gold and predicted). This field was irrelevant in this mini-pilot.

The stark asymmetry between modality (7/8 exact) and the other fields
(0/8 actor, 0/8 action, 0/8 constraint) suggests the current prompt
adequately conveys the modality concept but fails to communicate the
expected format, normalization level, and content boundaries for the
other fields.

## 4. Field-level Error Pattern

### 4.1 Modality

| Score | Count |
|-------|-------|
| exact | 7 |
| wrong | 1 (sample 006: definition → obligation) |

The model correctly outputs one of the four modality labels
(`obligation`, `prohibition`, `permission`, `definition`) in 7/8 cases.
The single error (sample 006) is an Austrian tax code §1 Abs 1
definition clause ("Natürliche Personen... sind unbeschränkt
einkommensteuerpflichtig") that the model classified as an obligation.
The German word "pflichtig" may have triggered an obligation heuristic
even though the sentence is a legal status classification.

**Why modality works relatively well**: modality is a closed-set
enumeration with well-understood legal semantics. The model maps
deontic keywords ("shall", "shall be prohibited", "sind...pflichtig")
to labels reliably. The taxonomy is simple and the model's pre-training
likely covers legal deontic classification.

### 4.2 Actor

| Score | Count |
|-------|-------|
| exact | 0 |
| partial | 1 (sample 004: "the controller" vs gold "controller") |
| missing | 4 (samples 001, 002, 003, 005 — all GDPR passive sentences) |
| wrong | 3 (samples 006, 007, 008 — German phrases not normalized) |

Two distinct error sub-patterns:

**Sub-pattern A — Passive-voice null actor (GDPR samples 001-005):**
The GDPR sentences use passive voice ("shall be processed", "shall be
collected"). The model outputs `null` for actor instead of inferring
"entity processing personal data" as the gold does. This suggests the
prompt does not instruct the model to infer or impute an actor from
passive constructions.

**Sub-pattern B — Non-normalized German actor (Austrian samples 006-008):**
The model outputs German phrases verbatim ("Natürliche Personen",
"natürliche Personen") instead of the English normalized form
("natural persons"). The gold is in English. This suggests the prompt
does not specify that output fields should be in English regardless of
source language.

### 4.3 Action

| Score | Count |
|-------|-------|
| exact | 0 |
| wrong | 8 |

This is the most pervasive failure in the mini-pilot. Every sample has
a wrong action. The pattern is consistent: the model extracts verbatim
text fragments while the gold expects normalized action phrases.

| Sample | Predicted (verbatim) | Gold (normalized) |
|--------|---------------------|-------------------|
| 001 | "processed" | "process personal data" |
| 002 | "collected" | "collect and further process personal data" |
| 003 | "be adequate, relevant and limited" | "process personal data" |
| 004 | "be able to demonstrate that the data subject has consented..." | "demonstrate consent to processing" |
| 005 | "Processing" | "process special categories of personal data" |
| 006 | "einkommensteuerpflichtig" | "be subject to unlimited income tax liability" |
| 007 | "unbeschränkt steuerpflichtig" | "be subject to unlimited income tax liability" |
| 008 | "beschränkt steuerpflichtig" | "be subject to limited income tax liability" |

**Why action is so bad**: the prompt apparently does not tell the model
that the action field should be a **normalized action phrase** in
`[verb] [object]` form. The model treats action as "extract the main
verb or predicate from the sentence" instead of "produce a normalized
action description." This is a prompt design issue, not a model
capability issue.

Sample 003 is especially instructive: the gold action is "process
personal data" (the actual regulated activity), but the model extracted
"be adequate, relevant and limited" (the subject complement describing
how data should be). The model confused the **quality constraint**
with the **regulated action**.

### 4.4 Condition

| Score | Count |
|-------|-------|
| exact | 1 (sample 004) |
| missing | 2 (samples 003, 005) |
| wrong | 3 (samples 006-008) |
| not_applicable | 2 (samples 001, 002) |

Mixed performance. The model correctly identified the condition in
sample 004 ("processing is based on consent") but missed conditions in
003 and 005. For the Austrian samples (006-008), conditions were marked
wrong — the model output fragments of conditions but not the complete
propositional form the gold expects.

### 4.5 Constraint

| Score | Count |
|-------|-------|
| exact | 0 |
| partial | 3 (samples 001-003: adverbial fragments) |
| missing | 1 (sample 004) |
| wrong | 4 (samples 005-008) |

The model consistently fails to produce full constraint statements.
For GDPR samples 001-003, it outputs adverbial/prepositional phrases
("lawfully, fairly and in a transparent manner...") instead of the
gold's full propositional form ("Personal data must be processed
lawfully..."). For sample 005, it outputs the list of special
categories as the constraint instead of the prohibition statement.

### 4.6 Exception

All 8 samples: `not_applicable` for both gold and predicted. No
error to analyze. This field was not exercised by the mini-pilot
sample set.

## 5. Sample-level Notes

### r13_3_candidate_001 — GDPR Art 5(1)(a)
- **Text**: "Personal data shall be processed lawfully, fairly and in a
  transparent manner in relation to the data subject."
- **Modality**: exact (obligation)
- **Actor**: missing — passive voice, model output null
- **Action**: wrong — "processed" instead of "process personal data"
- **Constraint**: partial — adverbial phrase instead of full statement
- **Primary error**: verbatim fragment extraction + passive actor omission

### r13_3_candidate_002 — GDPR Art 5(1)(b)
- **Text**: "Personal data shall be collected for specified, explicit and
  legitimate purposes and not further processed in a manner that is
  incompatible with those purposes."
- **Modality**: exact (obligation)
- **Actor**: missing — passive voice
- **Action**: wrong — "collected" instead of "collect and further process
  personal data"
- **Constraint**: partial — "for specified, explicit and legitimate
  purposes..." instead of full statement
- **Primary error**: same verbatim fragment pattern as 001

### r13_3_candidate_003 — GDPR Art 5(1)(c)
- **Text**: "Personal data shall be adequate, relevant and limited to
  what is necessary in relation to the purposes for which they are
  processed."
- **Modality**: exact (obligation)
- **Actor**: missing — passive voice
- **Action**: wrong — "be adequate, relevant and limited" (subject
  complement) instead of "process personal data" (regulated action)
- **Condition**: missing — gold has "Processing is carried out in
  relation to specified purposes"
- **Primary error**: **subject complement confusion** — the model
  extracted the quality predicate as the action instead of the
  regulated activity; this is a fundamental misreading of what
  "action" means in the schema

### r13_3_candidate_004 — GDPR Art 7(1)
- **Text**: "Where processing is based on consent, the controller shall
  be able to demonstrate that the data subject has consented to
  processing of his or her personal data."
- **Modality**: exact (obligation)
- **Actor**: partial — "the controller" vs gold "controller"
- **Action**: wrong — verbatim long phrase vs normalized
  "demonstrate consent to processing"
- **Condition**: exact — "processing is based on consent"
- **Constraint**: missing — model output null, gold has full statement
- **Primary error**: verbatim extraction + constraint omission;
  note that condition was exact (best-performing sample for condition)

### r13_3_candidate_005 — GDPR Art 9(1)
- **Text**: "Processing of personal data revealing racial or ethnic
  origin... shall be prohibited."
- **Modality**: exact (prohibition)
- **Actor**: missing — passive voice
- **Action**: wrong — "Processing" (gerund) instead of
  "process special categories of personal data"
- **Condition**: missing — gold has complex condition about data categories
- **Constraint**: wrong — model output the list of special categories
  as constraint; gold has prohibition statement
- **Primary error**: the model conflated the **trigger condition**
  (what kind of data) with the **constraint** (that processing is
  prohibited) and extracted neither correctly

### r13_3_candidate_006 — Austrian §1 Abs 1
- **Text**: "Natürliche Personen, die im Inland einen Wohnsitz oder
  ihren gewöhnlichen Aufenthalt haben, sind unbeschränkt
  einkommensteuerpflichtig."
- **Modality**: wrong — "obligation" instead of "definition"
- **Actor**: wrong — "Natürliche Personen" (German) vs "natural persons"
- **Action**: wrong — "einkommensteuerpflichtig" (adjective) vs
  "be subject to unlimited income tax liability"
- **Condition**: wrong
- **Constraint**: wrong
- **Primary error**: **definition-as-obligation** misclassification +
  German text not normalized to English +
  adjective extracted as action

Note: This is the only modality error in the mini-pilot.
Corrected in R13.4.2.4 (report narrative fix).

### r13_3_candidate_007 — Austrian §1 Abs 2
- **Text**: "Unbeschränkt steuerpflichtig sind jene natürlichen Personen,
  die im Inland einen Wohnsitz oder ihren gewöhnlichen Aufenthalt haben.
  Die unbeschränkte Steuerpflicht erstreckt sich auf alle in- und
  ausländischen Einkünfte."
- **Modality**: exact (definition)
- **Actor**: wrong — "natürliche Personen" vs "natural persons"
- **Action**: wrong — "unbeschränkt steuerpflichtig" vs
  "be subject to unlimited income tax liability"
- **Condition**: wrong
- **Constraint**: wrong — "alle in- und ausländischen Einkünfte" vs
  "Unlimited tax liability extends to all domestic and foreign income"
- **Primary error**: German text not normalized + adjective as action
- Note: modality exact — model correctly identified this as definition
  despite the same "-pflichtig" suffix as 006

### r13_3_candidate_008 — Austrian §1 Abs 3
- **Text**: "Beschränkt steuerpflichtig sind jene natürlichen Personen,
  die im Inland weder einen Wohnsitz noch ihren gewöhnlichen Aufenthalt
  haben. Die beschränkte Steuerpflicht erstreckt sich nur auf die im
  § 98 aufgezählten Einkünfte."
- **Modality**: exact (definition)
- **Actor**: wrong — "natürliche Personen" vs "natural persons"
- **Action**: wrong — "beschränkt steuerpflichtig" vs
  "be subject to limited income tax liability"
- **Condition**: wrong
- **Constraint**: wrong
- **Primary error**: same pattern as 007 — German normalization failure

## 6. Actor / Action Error Diagnosis

### 6.1 Why modality works but actor/action don't

Modality is a **closed-set classification task** with 4 labels. The
model maps surface deontic cues to labels. This is a task at which LLMs
excel — few-shot classification with small label sets — and the schema
definition is clear: pick one of four.

Actor and action are **open-ended extraction tasks** with no
enumeration. The model must understand:
1. What counts as an "actor" in this schema
2. At what granularity to express the actor
3. That passive-voice sentences have implicit actors
4. That output should be normalized, not verbatim
5. That output should be in English regardless of source language

None of this was in the R13.4.2 prompt. The model defaulted to
verbatim text extraction, which matches general instruction-following
behavior when no explicit normalization constraint is provided.

### 6.2 Passive voice effect

All 5 GDPR samples use passive voice ("shall be processed", "shall be
collected"). The gold infers an actor ("entity processing personal
data") from context. The model does not — it outputs null. This is a
**prompt gap**, not a model limitation. The prompt never tells the
model to infer actors from passive constructions.

### 6.3 Phrase extraction vs field normalization

The action field shows the clearest normalization failure. The model
consistently extracts surface text:
- "processed" (past participle) instead of "process personal data"
- "Processing" (gerund) instead of "process special categories..."
- "einkommensteuerpflichtig" (German adjective) instead of
  "be subject to unlimited income tax liability"

This suggests the model treats the extraction task as **span
highlighting** (find the relevant words in the text) rather than
**field normalization** (express the concept in a canonical form).

### 6.4 Subject complement confusion (sample 003)

Sample 003 is the most diagnostic error. The sentence is:
"Personal data shall be adequate, relevant and limited to what is
necessary..."

The model extracted "be adequate, relevant and limited" as the action.
The gold action is "process personal data" — the **regulated
activity**, not the **quality predicate**. This means:
- The model doesn't understand that "action" means "the regulated
  activity being constrained"
- The model may benefit from a two-step approach: first determine
  what is being regulated, then extract the fields

### 6.5 Gold schema definition clarity

The gold definitions for actor/action are implicit rather than explicit.
The annotator inferred "entity processing personal data" from context.
A prompt that makes these definitions explicit could improve extraction:

For actor: "the entity that performs or is subject to the regulated
activity — infer from passive voice when needed"

For action: "a normalized [verb] [object] phrase describing the
regulated activity — do not copy surface text verbatim"

### 6.6 Few-shot examples

The R13.4.2 prompt had zero examples. Given the field granularity
mismatch (verbatim vs normalized), 2-3 few-shot examples showing the
expected normalization level for each field could help align model
output with gold expectations.

## 7. Prompt-refinement Implications

See `docs/r13_5_prompt_refinement_plan.md` for the full plan.

Key directions:
- **Direction A**: Field definition strengthening — add explicit
  normalization rules, passive-voice handling, language specification
- **Direction B**: Few-shot examples — 2-3 annotated examples showing
  expected field granularity
- **Direction C**: Two-step reasoning-hidden extraction — instruct model
  to internally determine clause type and regulated activity before
  extracting fields, without outputting reasoning

## 8. Risks and Limitations

- **8 samples only**: all observations are from 8 samples across 2
  sources (GDPR EurLex, Austrian tax code). Error patterns may not
  generalize.
- **Single model**: qwen3.7-max only. Other models may exhibit
  different error patterns.
- **No retry data**: each sample had exactly 1 attempt. No data on
  output variability.
- **Gold subjectivity**: actor/action gold annotations involve
  annotator judgment (especially inferred actors from passive voice).
  Inter-annotator agreement is not measured.
- **Prompt was minimal**: R13.4.2 used a schema-only prompt with no
  examples, no normalization instructions, no field-level definitions.
  The observed errors may be largely attributable to prompt
  underspecification rather than model incapability.

## 9. Next Stage Recommendation

Proceed to R13.6 prompt-refinement design. The error analysis in this
document provides the evidence base. A refined prompt (incorporating
field definitions, normalization rules, few-shot examples, and/or
two-step extraction) should be designed and reviewed before any new
real API mini-pilot.

**Do not run another real API mini-pilot without fresh explicit user
authorization.** The R13.4.2 authorization was consumed.

## 10. Claim Boundary

This is a post-hoc error analysis of one bounded 8-sample real API
mini-pilot (R13.4.2). It does not constitute a benchmark, method
validation, or Sun reproduction. All error patterns described are
observations from 8 samples only. Generalization to other samples,
models, or legal domains requires further testing.
