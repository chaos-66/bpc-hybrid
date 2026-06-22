# R13.2 Annotation Guideline

## 1. Annotation Goal

Produce consistent, auditable **gold annotations** for regulatory sentences collected
from public sources. Annotations follow Sun et al. (2024) paper-visible categories
(modality classification + phrase-level semantic extraction) but are created independently
by this project.

## 2. Unit of Annotation

A **single regulatory sentence or clause** from a legal/regulatory text. If a sentence
contains multiple normative clauses (e.g., one obligation + one exception), annotate
each clause as a separate sample.

## 3. Modality Labels

| Label | Definition | Example Trigger Words |
|-------|------------|----------------------|
| `obligation` | A mandatory requirement that MUST be fulfilled | "shall", "must", "is required to", "has the duty to" |
| `prohibition` | An action that MUST NOT be performed | "shall not", "must not", "is prohibited", "may not" |
| `permission` | An action that MAY be performed but is not required | "may", "is allowed to", "has the right to", "can" |
| `definition` | A statement that defines a term, scope, or concept | "means", "refers to", "shall include", "is defined as" |
| `unknown` | Cannot confidently assign any of the above | — |

**Rule**: If multiple modalities are present in one sentence, split into separate clause
samples. If uncertain between two labels, use `unknown` and document the ambiguity.

## 4. Phrase-level Concepts

Based on Sun et al. (2024) 6-concept phrase-level annotation (Table 8):

| Concept | Description | Example |
|---------|-------------|---------|
| `actor` | The entity that performs or is subject to the action | "data controller", "processor", "supervisory authority" |
| `action` | The verb phrase describing what must/must not/may be done | "process personal data", "implement appropriate measures" |
| `condition` | A prerequisite or triggering condition | "where processing is based on consent", "if the data subject is a child" |
| `constraint` | A limitation, scope, or boundary on the action | "for specified, explicit and legitimate purposes", "no longer than necessary" |
| `exception` | An exclusion or carve-out from the rule | "unless the data subject has given consent", "except where Union or Member State law provide" |
| `modality` | The deontic type from §3 above | "obligation", "prohibition", etc. |

**Rule**: Not all concepts are present in every sentence. Use `null` when a concept is
not applicable. Do NOT invent concepts that are not present in the text.

## 5. Clause Fields

```json
{
  "sample_id": "formal_mini_001",
  "source_id": "gdpr_eurlex",
  "source_ref": "Article 5(1)(a)",
  "text": "Personal data shall be processed lawfully, fairly and in a transparent manner in relation to the data subject.",
  "modality": "obligation",
  "actor": "data controller",
  "action": "process personal data lawfully, fairly and in a transparent manner",
  "condition": null,
  "constraint": "in relation to the data subject",
  "exception": null,
  "notes": "",
  "annotation_status": "manual_gold_candidate"
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sample_id` | string | yes | Unique identifier, format `formal_mini_NNN` |
| `source_id` | string | yes | Source identifier from collection plan |
| `source_ref` | string | yes | Article/paragraph/section reference |
| `text` | string | yes | The exact regulatory sentence text |
| `modality` | enum | yes | One of: obligation, prohibition, permission, definition, unknown |
| `actor` | string\|null | no | The entity performing or subject to the action |
| `action` | string\|null | no | The verb phrase describing the normative action |
| `condition` | string\|null | no | Prerequisite or triggering condition |
| `constraint` | string\|null | no | Limitation, scope, or boundary |
| `exception` | string\|null | no | Exclusion or carve-out |
| `notes` | string | no | Free-text annotation notes |
| `annotation_status` | enum | yes | One of: manual_gold_candidate, reviewed_gold, uncertain |

## 6. Violation-related Fields

For process-model samples (if BPMN sources are acquired), additional fields apply:

| Field | Type | Description |
|-------|------|-------------|
| `violation_type` | string\|null | missing_action, incorrect_actor, out_of_order_execution, or null |
| `violation_status` | string\|null | violation_detected, no_violation, or null (if not applicable) |
| `bpmn_model_ref` | string\|null | Reference to the BPMN model file or ID |

These fields are **optional** and only populated if process-model sources are available.

## 7. Annotation Rules

### R1: Text Fidelity
Copy the source text **exactly** — no corrections, no normalization, no paraphrasing.
Preserve original punctuation, capitalization, and whitespace.

### R2: Minimum Span
Extract the **shortest meaningful span** for each concept. For example, extract
`"data controller"` not `"the data controller who is responsible for"`.

### R3: Non-overlapping Spans
Actor, action, condition, constraint, and exception spans should not overlap within
a single clause. If they naturally overlap, prefer the most specific span.

### R4: Null vs Empty
- Use `null` when a concept is not present in the text.
- Do NOT use empty string `""` for missing concepts.
- Use `""` for `notes` when there are no notes.

### R5: Implicit Actors
If the actor is grammatically implicit (e.g., passive voice without "by X"), infer
the most likely actor from context and note the inference in `notes`. If the actor
cannot be reasonably inferred, set `actor: null`.

### R6: Multi-clause Sentences
If a sentence contains multiple normative clauses:
- Split into separate samples (`formal_mini_001a`, `formal_mini_001b`).
- Each sample gets its own `modality`, `actor`, `action`, etc.
- Note the split in `notes`.

## 8. Ambiguity Handling

| Situation | Action |
|-----------|--------|
| Unclear modality | Set `modality: "unknown"`, explain in `notes` |
| Multiple possible actors | Choose the most likely, list alternatives in `notes` |
| Boundary unclear (where action ends) | Choose the narrower span, document the ambiguity |
| Two annotators disagree | Mark `annotation_status: "uncertain"`, record both views in `notes` |

## 9. Reviewer Notes

The reviewer should check:

1. ✅ Modality label matches the deontic meaning of the sentence.
2. ✅ Actor, action, condition, constraint, exception spans are accurate and minimal.
3. ✅ No fabricated concepts (null where absent).
4. ✅ Source text is copied exactly.
5. ✅ Annotation status is correctly set.
6. ✅ Ambiguities are documented.

## 10. Examples

### Example 1: Clear Obligation (GDPR Article 5)

```json
{
  "sample_id": "formal_mini_001",
  "source_id": "gdpr_eurlex",
  "source_ref": "Article 5(1)(a)",
  "text": "Personal data shall be processed lawfully, fairly and in a transparent manner in relation to the data subject.",
  "modality": "obligation",
  "actor": "controller",
  "action": "process personal data lawfully, fairly and in a transparent manner",
  "condition": null,
  "constraint": "in relation to the data subject",
  "exception": null,
  "notes": "Actor 'controller' inferred from Article 4(7) definition. 'Shall' = obligation.",
  "annotation_status": "manual_gold_candidate"
}
```

### Example 2: Prohibition (GDPR Article 9)

```json
{
  "sample_id": "formal_mini_002",
  "source_id": "gdpr_eurlex",
  "source_ref": "Article 9(1)",
  "text": "Processing of personal data revealing racial or ethnic origin, political opinions, religious or philosophical beliefs, or trade union membership, and the processing of genetic data, biometric data for the purpose of uniquely identifying a natural person, data concerning health or data concerning a natural person's sex life or sexual orientation shall be prohibited.",
  "modality": "prohibition",
  "actor": null,
  "action": "processing of special categories of personal data",
  "condition": null,
  "constraint": null,
  "exception": null,
  "notes": "Passive construction. Actor is any data controller/processor. 'Shall be prohibited' = prohibition.",
  "annotation_status": "manual_gold_candidate"
}
```

### Example 3: Permission (GDPR Article 6)

```json
{
  "sample_id": "formal_mini_003",
  "source_id": "gdpr_eurlex",
  "source_ref": "Article 6(1)(a)",
  "text": "The data subject has given consent to the processing of his or her personal data for one or more specific purposes.",
  "modality": "permission",
  "actor": "data subject",
  "action": "give consent to processing of personal data for specific purposes",
  "condition": null,
  "constraint": "for one or more specific purposes",
  "exception": null,
  "notes": "Consent as lawful basis = permission. 'Has given' = completed action enabling permission.",
  "annotation_status": "manual_gold_candidate"
}
```

### Example 4: Definition

```json
{
  "sample_id": "formal_mini_004",
  "source_id": "gdpr_eurlex",
  "source_ref": "Article 4(1)",
  "text": "'Personal data' means any information relating to an identified or identifiable natural person ('data subject').",
  "modality": "definition",
  "actor": null,
  "action": "define personal data",
  "condition": null,
  "constraint": "relating to an identified or identifiable natural person",
  "exception": null,
  "notes": "Clear definition. 'Means' = definition signal.",
  "annotation_status": "manual_gold_candidate"
}
```

### Example 5: Unknown / Ambiguous

```json
{
  "sample_id": "formal_mini_005",
  "source_id": "austrian_income_tax_code",
  "source_ref": "§ 1 Abs 1",
  "text": "Natürliche Personen, die im Inland einen Wohnsitz oder ihren gewöhnlichen Aufenthalt haben, sind unbeschränkt einkommensteuerpflichtig.",
  "modality": "obligation",
  "actor": "natürliche Personen mit Wohnsitz oder gewöhnlichem Aufenthalt im Inland",
  "action": "sind unbeschränkt einkommensteuerpflichtig",
  "condition": "im Inland einen Wohnsitz oder ihren gewöhnlichen Aufenthalt haben",
  "constraint": null,
  "exception": null,
  "notes": "German text. 'Sind ... pflichtig' = obligation (tax liability). Condition embedded in subject description.",
  "annotation_status": "manual_gold_candidate"
}
```

## 11. Do-not-claim Boundary

- These annotations are **project-created**, not from Sun's original dataset.
- They are NOT a benchmark.
- They are NOT method validation.
- They do NOT constitute formal evaluation results.
- They are for **pipeline sanity and paper-aligned reconstruction only**.
- Annotation quality is the sole responsibility of this project's author.
