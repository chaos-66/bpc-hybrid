# R13.5 Prompt-refinement Plan

## 1. Purpose

This document proposes prompt refinements for a possible R13.6 bounded
real API run, based on the error patterns observed in the R13.4.2
8-sample mini-pilot. The refinements are **design proposals only** —
no real API call, no LLM call, and no evaluator rerun occur in R13.5.

## 2. Observed Problems From R13.4.2

From `docs/r13_5_post_pilot_error_analysis.md`:

| Problem | Affected Fields | Samples |
|---------|----------------|---------|
| Verbatim fragment extraction instead of normalized phrases | action, constraint | All 8 |
| Passive-voice actor omission | actor | 001-005 |
| German text not normalized to English | actor, action, condition, constraint | 006-008 |
| Subject complement confused with regulated action | action | 003 |
| Definition misclassified as obligation | modality | 006 |
| Condition field not reliably detected | condition | 003, 005 |
| Constraint extracted as adverbial fragment | constraint | 001-003 |
| Special categories list conflated with constraint | constraint | 005 |

## 3. Prompt Design Hypotheses

1. **Normalization hypothesis**: The model defaults to verbatim span
   extraction because the prompt does not specify that fields should be
   normalized. Adding explicit normalization rules should improve
   action and constraint scores.

2. **Passive-voice hypothesis**: The model outputs null for actor in
   passive sentences because the prompt does not instruct it to infer
   implicit actors. Adding an inference instruction should reduce
   actor_missing errors.

3. **Language hypothesis**: The model outputs non-English text for
   non-English inputs because the prompt does not specify output
   language. Adding a language constraint should improve Austrian
   sample scores.

4. **Field definition hypothesis**: The model misunderstands what each
   field represents (e.g., action = regulated activity, not surface
   predicate) because the schema provides structural types but not
   semantic definitions. Adding per-field semantic definitions should
   improve field-level accuracy.

5. **Two-step hypothesis**: The model may benefit from internally
   classifying the clause type (obligation/prohibition/permission/
   definition) and identifying the regulated activity before
   extracting fields. A reasoning-hidden two-step instruction may
   improve coherence between fields.

## 4. Field Definitions To Add

The following per-field definitions should be added to the prompt
(in the system message or user instruction):

### modality
```
Already well-defined as enumeration: "obligation" | "prohibition" |
"permission" | "definition". Keep as-is. Add note:
"definition" = the sentence defines a legal status or classification
without prescribing or prohibiting behavior. Example: "X is subject to
Y" is a definition, not an obligation.
```

### actor
```
The entity that performs or is subject to the regulated activity.
- If the sentence uses active voice, extract the explicit subject.
- If the sentence uses passive voice, infer the implicit actor from
  context (e.g., "entity processing personal data").
- Normalize to English. For non-English input, translate the actor
  phrase to English.
- Use canonical form (e.g., "controller" not "the controller").
- If no actor can be reasonably inferred, output null.
```

### action
```
A normalized action phrase describing the regulated activity, in the
form [verb] [object]. Do NOT copy surface text verbatim.
- For "Personal data shall be processed" → action is "process personal
  data" (the regulated activity), NOT "processed" (the surface verb).
- For "X shall be adequate, relevant and limited" → action is "process
  personal data" (the regulated activity being constrained), NOT
  "be adequate, relevant and limited" (the quality constraint).
- Normalize to English. For non-English input, produce the English
  normalized action phrase.
- Use infinitive or base verb form.
- If the sentence defines a legal status (modality=definition), the
  action should describe what the entity is subject to
  (e.g., "be subject to unlimited income tax liability").
```

### condition
```
A trigger condition that must hold for the modality/action to apply.
- A condition is typically introduced by "where", "if", "when",
  "in case of", or a subordinate clause.
- Express as a complete propositional statement in English.
- If no condition is present, output null.
- Do NOT include the regulated action or constraint in the condition.
```

### constraint
```
A complete propositional statement describing how the action must
(or must not) be performed, or a restriction on the action.
- Express as a full sentence-like statement in English
  (e.g., "Personal data must be processed lawfully, fairly, and in
  a transparent manner").
- Do NOT output adverbial fragments, prepositional phrases, or lists
  of categories.
- For non-English input, produce the English normalized constraint.
- If the constraint is embedded in the main clause, extract it as a
  separate propositional statement.
```

### exception
```
Keep as-is (null in all samples). Definition: an explicit exception
or exemption from the modality/action/constraint.
```

## 5. Candidate Prompt Changes

### Direction A: Field-definition-strengthened prompt

Add the field definitions from Section 4 to the system message.
Keep the existing JSON schema skeleton. No few-shot examples.
This is the minimal change — purely declarative field definitions.

**Expected effect**: moderate improvement on actor (passive-voice
inference), moderate improvement on action (normalization
instruction), some improvement on constraint.

**Risk**: without examples, the model may still default to verbatim
extraction despite the definitions. The definition of "normalized
action phrase" may be interpreted differently by the model.

### Direction B: Few-shot example prompt

Add 2-3 few-shot examples showing: input sentence → expected JSON
output. Select examples that demonstrate:
1. Passive voice with inferred actor
2. Normalized action (not verbatim)
3. Full constraint statement (not fragment)

Example candidates from the mini-pilot (after prompt refinement):
- Sample 004 (GDPR Art 7(1)) — has explicit actor, condition, and
  demonstrates normalization
- Sample 001 (GDPR Art 5(1)(a)) — demonstrates passive-voice actor
  inference

**Expected effect**: stronger improvement due to in-context learning.
The model can see the expected normalization level directly.

**Risk**: few-shot examples may overfit to GDPR style and not help
with Austrian tax code samples. Examples may also constrain the model
to specific patterns that don't generalize.

### Direction C: Two-step reasoning-hidden extraction prompt

Instruct the model to internally determine (without outputting):
1. What is the clause type (modality)?
2. What is the regulated activity?
3. Who performs or is subject to it?
4. What conditions trigger it?
5. What constraints apply?

Then output the JSON. The reasoning must remain hidden — no
chain-of-thought in the output.

Add a system instruction like:
```
Before producing the JSON output, internally determine:
(1) The clause type: obligation, prohibition, permission, or definition.
(2) The regulated activity: what action is being regulated?
(3) The actor: who performs or is subject to this activity?
(4) Any trigger conditions.
(5) Any constraints or restrictions.

Then produce the JSON using these determinations. Do NOT include your
internal reasoning in the output.
```

**Expected effect**: the two-step approach may help with the subject
complement confusion (sample 003) by forcing the model to separate
"what is being regulated" from "how it should be done."

**Risk**: the model may still produce surface-level extraction in the
output even if internal reasoning is correct. The "hidden reasoning"
instruction may be ignored by some models.

## 6. Few-shot Example Plan

If Direction B is selected, use these examples:

### Example 1: Passive voice + normalization (GDPR Art 5(1)(a))

Input:
```
Personal data shall be processed lawfully, fairly and in a transparent
manner in relation to the data subject.
```

Output:
```json
{
  "modality": "obligation",
  "actor": "entity processing personal data",
  "action": "process personal data",
  "condition": null,
  "constraint": "Personal data must be processed lawfully, fairly, and in a transparent manner in relation to the data subject.",
  "exception": null
}
```

### Example 2: Explicit actor + condition (GDPR Art 7(1))

Input:
```
Where processing is based on consent, the controller shall be able to
demonstrate that the data subject has consented to processing of his or
her personal data.
```

Output:
```json
{
  "modality": "obligation",
  "actor": "controller",
  "action": "demonstrate consent to processing",
  "condition": "Processing is based on consent.",
  "constraint": "The controller must be able to demonstrate that the data subject has consented to processing of his or her personal data.",
  "exception": null
}
```

### Example 3: Definition clause with German input

Input:
```
Natürliche Personen, die im Inland einen Wohnsitz oder ihren
gewöhnlichen Aufenthalt haben, sind unbeschränkt
einkommensteuerpflichtig.
```

Output:
```json
{
  "modality": "definition",
  "actor": "natural persons",
  "action": "be subject to unlimited income tax liability",
  "condition": "The person has a residence or habitual abode in Austria.",
  "constraint": "The person is classified as subject to unlimited income tax liability.",
  "exception": null
}
```

## 7. Output Schema Rules

The JSON schema itself does not change. All fields remain:
- `modality`: `"obligation" | "prohibition" | "permission" | "definition"`
- `actor`: `string | null`
- `action`: `string`
- `condition`: `string | null`
- `constraint`: `string | null`
- `exception`: `string | null`

No new fields. No schema widening. The changes are purely in the
prompt text that precedes the schema.

## 8. Safety / API Boundary

**R13.5 does not execute any real API call.** The prompt refinements
described here are design proposals. They must NOT be sent to any
API in R13.5.

Before any R13.6 real API run:
- The user must provide fresh explicit authorization
- The refined prompt must be reviewed
- The same safety gates apply: max 8 calls, no retry, no batch,
  no raw response storage, one attempt per sample

## 9. Evaluation Plan For Next Stage

When R13.6 is authorized, reuse the same evaluation pipeline:
- Same 8 samples from R13.3 mini-gold set
- Same evaluator (`scripts/evaluate_mini_pilot_predictions.py`)
- Same gold (`data/formal/gold/r13_3_manual_gold_template.jsonl`)
- Compare field-level scores against R13.4.2 baseline
- Focus on whether action normalization and actor inference improve

No new evaluation methodology. No benchmark comparison.

## 10. Claim Boundary

This is a prompt-refinement design document based on one bounded
8-sample mini-pilot (R13.4.2). It does not validate the method,
establish a benchmark, or reproduce any paper result. The proposed
prompt changes are hypotheses that require testing in a future
authorized run (R13.6). No real API call occurs in R13.5.
