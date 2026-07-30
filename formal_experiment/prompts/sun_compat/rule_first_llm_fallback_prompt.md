<!--
sampling_policy: temperature=0, top_p=1, max_tokens=2048
note: Sampling parameters are runtime-controlled, not prompt-controlled.
version: 4
-->

# Sun B0 + Selective LLM Repair Prompt v4

> **Version**: v4 (2026-07-30)
> **Contract**: H1 reads an immutable persisted B0 prediction. The LLM may
> replace only the canonical fields selected by the Gold-blind trigger. The
> runner applies the patch atomically and retains the exact B0 prediction if
> any contract or canonical validation check fails.
> **Schema**: `stage2_prediction.schema.json@1.0.0`.

---

## System Prompt

```text
You produce a repair patch for selected fields of an existing canonical
Stage 2 legal-rule prediction. You are not producing a complete prediction
and you must not change clause boundaries.

Return only one JSON object. Do not return Markdown, code fences,
explanations, or text outside the JSON object.

The object must have exactly these five keys:
sample_id, clause_id, repair_fields, patches, reason.

Canonical patch field names are exactly:
modality, actors, actions, conditions, constraints, exceptions,
actor_action_map, order_relations.

Hard requirements:

1. sample_id and clause_id must exactly match the request.
2. repair_fields must exactly reproduce the ordered list requested by the
   runner. Do not use singular aliases such as actor, action, condition,
   constraint, or exception.
3. patches must contain exactly one entry for every requested repair field
   and no other fields.
4. modality is a complete replacement object:
   {"label": one of obligation/prohibition/permission/definition,
    "evidence": [{"text": verbatim source text, "start": integer,
                  "end": integer}]}.
5. actors, actions, conditions, constraints, and exceptions are complete
   replacement arrays of:
   {"id": string, "text": verbatim source text, "start": integer,
    "end": integer, "normalized": non-empty string}.
6. actor_action_map and order_relations are complete replacement arrays in
   the canonical schema. If actions or actors change, all requested relation
   fields must reference IDs in the replacement arrays.
7. For a genuinely absent span or relation field, use {"absent": true}.
   Modality can never be absent.
8. Every span must be inside the existing clause_span and must satisfy
   text == source_text[start:end]. Do not paraphrase evidence or invent text.
9. IDs must be unique across semantic fields. An unchanged span may preserve
   its existing ID because its field is replaced atomically.
10. Do not return original_text/corrected_text, keep/correct/remove/add, or
    validation fields. The runner owns merge, validation, and fallback.

The runner rejects the entire patch if any requirement fails. It never
silently applies a partial patch.
```

## User Prompt Template

```text
Source text (sample_id: {sample_id}, source_id: {source_id}):

{source_text}

Immutable B0 clause (clause_id: {clause_id}):

{current_clause_json}

The Gold-blind trigger selected exactly these canonical fields:

repair_fields: {repair_fields_csv}
repair_reasons: {repair_reasons_csv}

Return exactly:

{{
  "sample_id": "{sample_id}",
  "clause_id": "{clause_id}",
  "repair_fields": [...the exact ordered list above...],
  "patches": {{
    "<every requested canonical field>": <complete replacement or {{"absent": true}}>
  }},
  "reason": "<short explanation based only on source text and B0>"
}}
```

## Expected Output Example

```json
{
  "sample_id": "estg_000001",
  "clause_id": "estg_000001.c1",
  "repair_fields": ["actors", "actions", "actor_action_map"],
  "patches": {
    "actors": [
      {
        "id": "estg_000001.c1.actor.1",
        "text": "The controller",
        "start": 0,
        "end": 14,
        "normalized": "controller"
      }
    ],
    "actions": [
      {
        "id": "estg_000001.c1.action.1",
        "text": "shall notify the authority",
        "start": 15,
        "end": 41,
        "normalized": "notify authority"
      }
    ],
    "actor_action_map": [
      {
        "actor_id": "estg_000001.c1.actor.1",
        "action_id": "estg_000001.c1.action.1"
      }
    ]
  },
  "reason": "B0 omitted the explicit actor and action."
}
```

## Runtime Semantics

- B0 is loaded from a persisted prediction artifact and bound by SHA-256.
- Trigger signals use only inference-visible B0 diagnostics and never Gold.
- A hard call budget ranks triggered clauses deterministically.
- Accepted patches, rejected patches, before/after field values, and
  prediction hashes are recorded in a telemetry sidecar.
- Invalid, unauthorized, incomplete, and no-op patches retain B0 exactly.
- This prompt and its dry/offline validation are development evidence until
  the formal B0, Gold, evaluator, model, and budget gates are locked.
