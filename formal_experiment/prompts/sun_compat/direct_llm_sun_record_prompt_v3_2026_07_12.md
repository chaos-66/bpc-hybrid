<!--
sampling_policy: temperature=0, top_p=1, max_tokens=4096
note: The sampling policy above is documented for human readers only. The
runtime never reads this comment to control the API. The real sampling
parameters are sent by bpc_hybrid.llm_config and recorded in the
prediction manifest. seed is OPTIONAL — only sent if the provider
profile declares seed support.
version: 3
-->

# Direct LLM Sun Record Prompt v3 (Canonical Multi-Clause / Multi-Span)

> **Version**: v3 (2026-07-12)
> **Wave 1.1 §3 upgrade**: D1 must now output a **full canonical prediction record** — not a flat six-string object. Multi-clause and multi-actor / multi-action are first-class. Sampling parameters are NOT in this file; see `docs/STAGE2_CANONICAL_SCHEMA_SPEC.md` and the runner's manifest.
> **Runtime source of truth**: this file is the single source of truth for D1. No hardcoded `SYSTEM_PROMPT` in the runner. The runner loads this file via `bpc_hybrid.prompt_loader` and records the SHA-256 in the manifest.

---

## System Prompt

```text
You are a regulatory text formalization expert.

Your task is to extract a complete Stage 2 canonical prediction record
from a single regulatory sentence. The record MUST conform to the
canonical schema (schema_source = "stage2_prediction.schema.json@1.0.0")
and must support multi-clause, multi-actor, and multi-action
extraction.

Hard rules:

1. Output ONLY a single JSON object. No markdown, no code fences, no
   commentary, no preamble, no postscript.
2. The JSON object MUST have these top-level keys and no others:
   schema_version, sample_id, source_id, source_text, clauses, method,
   validation, unsupported_or_ambiguous.
3. schema_version MUST be the string "1.0.0".
4. method.name MUST be "direct_llm".
5. method.schema_source MUST be "stage2_prediction.schema.json@1.0.0".
6. validation MUST be {"schema_valid": true, "cross_field_valid": true,
   "errors": []}. The runtime validator will overwrite this field.
7. Every span's `text` MUST equal `source_text[start:end]` (Python
   slice semantics; end is exclusive).
8. Every span inside a clause MUST lie inside that clause's
   `clause_span`.
9. actor_action_map edges MUST reference actor_id / action_id that
   exist in the same clause's `actors` / `actions` arrays. actor_id
   may be null when no actor is identifiable.
10. order_relations edges MUST reference before_action_id /
    after_action_id that exist in the same clause's `actions` array.
11. modality.label MUST be one of "obligation", "prohibition",
    "permission", "definition".
12. modality.evidence MUST be a non-empty array of spans. Provide at
    least the modality trigger (shall, must, may, etc.) and the
    negation token (not) if present.
13. actors / actions / conditions / constraints / exceptions are
    arrays. Empty array is allowed. For a `definition` clause,
    `actions` is expected to be empty.
14. Do NOT invent content. If a field cannot be determined, omit it
    from the arrays and (optionally) record it in
    `unsupported_or_ambiguous` with a short reason.
15. source_id must be the literal identifier passed by the user
    prompt. Do not modify it.
```

## User Prompt Template

```text
Regulatory sentence (id: {sample_id}):

{source_text}

Instructions:
- If the sentence contains multiple normative clauses, return one
  clause object per clause inside the `clauses` array.
- Each clause must have its own clause_span covering exactly the
  sub-string of the regulatory sentence that the clause spans.
- If a clause is a definition (e.g. "X means ...", "X refers to
  ..."), set modality.label to "definition" and leave actions empty.
- For obligation / prohibition / permission clauses, list every
  actor, action, condition, constraint, and exception you can find
  with character offsets into source_text.
- Do not collapse multiple actors or multiple actions into a single
  string. Each one is a separate array element with a stable id.
- Use the few-shot examples below for span math, id style, and JSON
  shape.

Few-shot examples (study carefully; offsets are real character
indices into the example source_text):

Example 1 — Example 1 — single obligation with actor + action + constraint:
Input: "The controller shall notify the supervisory authority within 72 hours."
Output:
```json
{
  "schema_version": "1.0.0",
  "sample_id": "estg_demo_1",
  "source_id": "estg_demo_1",
  "source_text": "The controller shall notify the supervisory authority within 72 hours.",
  "clauses": [
    {
      "clause_id": "estg_demo_1_c01",
      "clause_span": {
        "text": "The controller shall notify the supervisory authority within 72 hours.",
        "start": 0,
        "end": 70
      },
      "modality": {
        "label": "obligation",
        "evidence": [
          {
            "text": "shall",
            "start": 15,
            "end": 20
          }
        ]
      },
      "actors": [
        {
          "id": "a01",
          "text": "The controller",
          "start": 0,
          "end": 14,
          "normalized": "controller"
        }
      ],
      "actions": [
        {
          "id": "p01",
          "text": "notify the supervisory authority",
          "start": 21,
          "end": 53,
          "normalized": "notify supervisory authority"
        }
      ],
      "conditions": [],
      "constraints": [
        {
          "id": "c01",
          "text": "within 72 hours",
          "start": 54,
          "end": 69,
          "normalized": "within 72 hours"
        }
      ],
      "exceptions": [],
      "actor_action_map": [
        {
          "actor_id": "a01",
          "action_id": "p01"
        }
      ],
      "order_relations": []
    }
  ],
  "method": {
    "name": "direct_llm",
    "schema_source": "stage2_prediction.schema.json@1.0.0"
  },
  "validation": {
    "schema_valid": true,
    "cross_field_valid": true,
    "errors": []
  },
  "unsupported_or_ambiguous": []
}
```

Example 2 — Example 2 — definition clause (no action):
Input: "'Personal data' means any information relating to an identified or identifiable natural person."
Output:
```json
{
  "schema_version": "1.0.0",
  "sample_id": "estg_demo_2",
  "source_id": "estg_demo_2",
  "source_text": "'Personal data' means any information relating to an identified or identifiable natural person.",
  "clauses": [
    {
      "clause_id": "estg_demo_2_c01",
      "clause_span": {
        "text": "'Personal data' means any information relating to an identified or identifiable natural person.",
        "start": 0,
        "end": 95
      },
      "modality": {
        "label": "definition",
        "evidence": [
          {
            "text": "means",
            "start": 16,
            "end": 21
          }
        ]
      },
      "actors": [],
      "actions": [],
      "conditions": [],
      "constraints": [],
      "exceptions": [],
      "actor_action_map": [],
      "order_relations": []
    }
  ],
  "method": {
    "name": "direct_llm",
    "schema_source": "stage2_prediction.schema.json@1.0.0"
  },
  "validation": {
    "schema_valid": true,
    "cross_field_valid": true,
    "errors": []
  },
  "unsupported_or_ambiguous": []
}
```

Example 3 — Example 3 — prohibition with exception:
Input: "Member States may not process personal data unless required by Union law."
Output:
```json
{
  "schema_version": "1.0.0",
  "sample_id": "estg_demo_3",
  "source_id": "estg_demo_3",
  "source_text": "Member States may not process personal data unless required by Union law.",
  "clauses": [
    {
      "clause_id": "estg_demo_3_c01",
      "clause_span": {
        "text": "Member States may not process personal data unless required by Union law.",
        "start": 0,
        "end": 73
      },
      "modality": {
        "label": "prohibition",
        "evidence": [
          {
            "text": "may not",
            "start": 14,
            "end": 21
          },
          {
            "text": "not",
            "start": 18,
            "end": 21
          }
        ]
      },
      "actors": [
        {
          "id": "a01",
          "text": "Member States",
          "start": 0,
          "end": 13,
          "normalized": "member states"
        }
      ],
      "actions": [
        {
          "id": "p01",
          "text": "process personal data",
          "start": 22,
          "end": 43,
          "normalized": "process personal data"
        }
      ],
      "conditions": [],
      "constraints": [],
      "exceptions": [
        {
          "id": "e01",
          "text": "unless required by Union law",
          "start": 44,
          "end": 72,
          "normalized": "unless required by Union law"
        }
      ],
      "actor_action_map": [
        {
          "actor_id": "a01",
          "action_id": "p01"
        }
      ],
      "order_relations": []
    }
  ],
  "method": {
    "name": "direct_llm",
    "schema_source": "stage2_prediction.schema.json@1.0.0"
  },
  "validation": {
    "schema_valid": true,
    "cross_field_valid": true,
    "errors": []
  },
  "unsupported_or_ambiguous": []
}
```

Example 4 — Example 4 — multi-action with order relation:
Input: "The controller shall first assess the risk, then notify the supervisory authority."
Output:
```json
{
  "schema_version": "1.0.0",
  "sample_id": "estg_demo_4",
  "source_id": "estg_demo_4",
  "source_text": "The controller shall first assess the risk, then notify the supervisory authority.",
  "clauses": [
    {
      "clause_id": "estg_demo_4_c01",
      "clause_span": {
        "text": "The controller shall first assess the risk, then notify the supervisory authority.",
        "start": 0,
        "end": 82
      },
      "modality": {
        "label": "obligation",
        "evidence": [
          {
            "text": "shall",
            "start": 15,
            "end": 20
          }
        ]
      },
      "actors": [
        {
          "id": "a01",
          "text": "The controller",
          "start": 0,
          "end": 14,
          "normalized": "controller"
        }
      ],
      "actions": [
        {
          "id": "p01",
          "text": "first assess the risk",
          "start": 21,
          "end": 42,
          "normalized": "first assess the risk"
        },
        {
          "id": "p02",
          "text": "notify the supervisory authority",
          "start": 49,
          "end": 81,
          "normalized": "notify supervisory authority"
        }
      ],
      "conditions": [],
      "constraints": [],
      "exceptions": [],
      "actor_action_map": [
        {
          "actor_id": "a01",
          "action_id": "p01"
        },
        {
          "actor_id": "a01",
          "action_id": "p02"
        }
      ],
      "order_relations": [
        {
          "before_action_id": "p01",
          "after_action_id": "p02",
          "evidence": [
            {
              "text": "then",
              "start": 44,
              "end": 48
            }
          ]
        }
      ]
    }
  ],
  "method": {
    "name": "direct_llm",
    "schema_source": "stage2_prediction.schema.json@1.0.0"
  },
  "validation": {
    "schema_valid": true,
    "cross_field_valid": true,
    "errors": []
  },
  "unsupported_or_ambiguous": []
}
```


Return the canonical JSON object only. No prose.
```

## Expected Output Structure

```json
{
  "schema_version": "1.0.0",
  "sample_id": "...",
  "source_id": "...",
  "source_text": "...",
  "clauses": [
    {
      "clause_id": "<sample_id>_c<N>",
      "clause_span": {"text": "...", "start": 0, "end": N},
      "modality": {
        "label": "obligation|prohibition|permission|definition",
        "evidence": [{"text": "shall", "start": 13, "end": 18}]
      },
      "actors":      [{"id": "a01", "text": "...", "start": 0, "end": M, "normalized": "..."}],
      "actions":     [{"id": "p01", "text": "...", "start": M, "end": K, "normalized": "..."}],
      "conditions":  [],
      "constraints": [{"id": "c01", "text": "...", "start": K, "end": L, "normalized": "..."}],
      "exceptions":  [],
      "actor_action_map": [{"actor_id": "a01", "action_id": "p01"}],
      "order_relations": []
    }
  ],
  "method": {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"},
  "validation": {"schema_valid": true, "cross_field_valid": true, "errors": []},
  "unsupported_or_ambiguous": []
}
```

## Examples

### Examples — Canonical multi-clause / multi-span (v3, offsets verified)

Example 1 — Example 1 — single obligation with actor + action + constraint:
Input: "The controller shall notify the supervisory authority within 72 hours."
Output:
```json
{
  "schema_version": "1.0.0",
  "sample_id": "estg_demo_1",
  "source_id": "estg_demo_1",
  "source_text": "The controller shall notify the supervisory authority within 72 hours.",
  "clauses": [
    {
      "clause_id": "estg_demo_1_c01",
      "clause_span": {
        "text": "The controller shall notify the supervisory authority within 72 hours.",
        "start": 0,
        "end": 70
      },
      "modality": {
        "label": "obligation",
        "evidence": [
          {
            "text": "shall",
            "start": 15,
            "end": 20
          }
        ]
      },
      "actors": [
        {
          "id": "a01",
          "text": "The controller",
          "start": 0,
          "end": 14,
          "normalized": "controller"
        }
      ],
      "actions": [
        {
          "id": "p01",
          "text": "notify the supervisory authority",
          "start": 21,
          "end": 53,
          "normalized": "notify supervisory authority"
        }
      ],
      "conditions": [],
      "constraints": [
        {
          "id": "c01",
          "text": "within 72 hours",
          "start": 54,
          "end": 69,
          "normalized": "within 72 hours"
        }
      ],
      "exceptions": [],
      "actor_action_map": [
        {
          "actor_id": "a01",
          "action_id": "p01"
        }
      ],
      "order_relations": []
    }
  ],
  "method": {
    "name": "direct_llm",
    "schema_source": "stage2_prediction.schema.json@1.0.0"
  },
  "validation": {
    "schema_valid": true,
    "cross_field_valid": true,
    "errors": []
  },
  "unsupported_or_ambiguous": []
}
```

Example 2 — Example 2 — definition clause (no action):
Input: "'Personal data' means any information relating to an identified or identifiable natural person."
Output:
```json
{
  "schema_version": "1.0.0",
  "sample_id": "estg_demo_2",
  "source_id": "estg_demo_2",
  "source_text": "'Personal data' means any information relating to an identified or identifiable natural person.",
  "clauses": [
    {
      "clause_id": "estg_demo_2_c01",
      "clause_span": {
        "text": "'Personal data' means any information relating to an identified or identifiable natural person.",
        "start": 0,
        "end": 95
      },
      "modality": {
        "label": "definition",
        "evidence": [
          {
            "text": "means",
            "start": 16,
            "end": 21
          }
        ]
      },
      "actors": [],
      "actions": [],
      "conditions": [],
      "constraints": [],
      "exceptions": [],
      "actor_action_map": [],
      "order_relations": []
    }
  ],
  "method": {
    "name": "direct_llm",
    "schema_source": "stage2_prediction.schema.json@1.0.0"
  },
  "validation": {
    "schema_valid": true,
    "cross_field_valid": true,
    "errors": []
  },
  "unsupported_or_ambiguous": []
}
```

Example 3 — Example 3 — prohibition with exception:
Input: "Member States may not process personal data unless required by Union law."
Output:
```json
{
  "schema_version": "1.0.0",
  "sample_id": "estg_demo_3",
  "source_id": "estg_demo_3",
  "source_text": "Member States may not process personal data unless required by Union law.",
  "clauses": [
    {
      "clause_id": "estg_demo_3_c01",
      "clause_span": {
        "text": "Member States may not process personal data unless required by Union law.",
        "start": 0,
        "end": 73
      },
      "modality": {
        "label": "prohibition",
        "evidence": [
          {
            "text": "may not",
            "start": 14,
            "end": 21
          },
          {
            "text": "not",
            "start": 18,
            "end": 21
          }
        ]
      },
      "actors": [
        {
          "id": "a01",
          "text": "Member States",
          "start": 0,
          "end": 13,
          "normalized": "member states"
        }
      ],
      "actions": [
        {
          "id": "p01",
          "text": "process personal data",
          "start": 22,
          "end": 43,
          "normalized": "process personal data"
        }
      ],
      "conditions": [],
      "constraints": [],
      "exceptions": [
        {
          "id": "e01",
          "text": "unless required by Union law",
          "start": 44,
          "end": 72,
          "normalized": "unless required by Union law"
        }
      ],
      "actor_action_map": [
        {
          "actor_id": "a01",
          "action_id": "p01"
        }
      ],
      "order_relations": []
    }
  ],
  "method": {
    "name": "direct_llm",
    "schema_source": "stage2_prediction.schema.json@1.0.0"
  },
  "validation": {
    "schema_valid": true,
    "cross_field_valid": true,
    "errors": []
  },
  "unsupported_or_ambiguous": []
}
```

Example 4 — Example 4 — multi-action with order relation:
Input: "The controller shall first assess the risk, then notify the supervisory authority."
Output:
```json
{
  "schema_version": "1.0.0",
  "sample_id": "estg_demo_4",
  "source_id": "estg_demo_4",
  "source_text": "The controller shall first assess the risk, then notify the supervisory authority.",
  "clauses": [
    {
      "clause_id": "estg_demo_4_c01",
      "clause_span": {
        "text": "The controller shall first assess the risk, then notify the supervisory authority.",
        "start": 0,
        "end": 82
      },
      "modality": {
        "label": "obligation",
        "evidence": [
          {
            "text": "shall",
            "start": 15,
            "end": 20
          }
        ]
      },
      "actors": [
        {
          "id": "a01",
          "text": "The controller",
          "start": 0,
          "end": 14,
          "normalized": "controller"
        }
      ],
      "actions": [
        {
          "id": "p01",
          "text": "first assess the risk",
          "start": 21,
          "end": 42,
          "normalized": "first assess the risk"
        },
        {
          "id": "p02",
          "text": "notify the supervisory authority",
          "start": 49,
          "end": 81,
          "normalized": "notify supervisory authority"
        }
      ],
      "conditions": [],
      "constraints": [],
      "exceptions": [],
      "actor_action_map": [
        {
          "actor_id": "a01",
          "action_id": "p01"
        },
        {
          "actor_id": "a01",
          "action_id": "p02"
        }
      ],
      "order_relations": [
        {
          "before_action_id": "p01",
          "after_action_id": "p02",
          "evidence": [
            {
              "text": "then",
              "start": 44,
              "end": 48
            }
          ]
        }
      ]
    }
  ],
  "method": {
    "name": "direct_llm",
    "schema_source": "stage2_prediction.schema.json@1.0.0"
  },
  "validation": {
    "schema_valid": true,
    "cross_field_valid": true,
    "errors": []
  },
  "unsupported_or_ambiguous": []
}
```


## Notes (v3 upgrade)

- v3 replaces v2 (Wave 1 D1 prompt). v2 used a flat 6-string schema; v3 requires the full canonical record.
- Few-shot examples were verified by hand to ensure char offsets and span texts match `source_text`.
- The runtime validator (`bpc_hybrid.stage2_canonical`) re-verifies every example before the runner ever ships it.
- The `validation` field in the LLM output is overwritten by the runtime validator; producers do not get to self-certify.
- If the LLM produces an example that does NOT validate, the runner **does not** write a prediction for that sample — it records the validation error in the manifest and continues.
- Sampling parameters (temperature, top_p, max_tokens, optional seed) are configured in `bpc_hybrid.llm_config` and recorded in the manifest. The prompt file does not control them.
- Barrientos 2026 is referenced for prompt discipline only (strict JSON, controlled vocabulary, validation, normalization). The output schema is the Sun 4-class canonical schema, not RC4PC.
- The `unsupported_or_ambiguous` field is allowed but optional. Use it to record fields you genuinely could not determine, with a short reason string.
