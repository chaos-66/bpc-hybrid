<!--
LLM prompt: Layer D, Call A (Chinese translation + per-clause / six-element
Chinese explanation).

This is the AUTHORITATIVE prompt for Call A of the Layer D
real-LLM run. The runner loads it via
scripts/run_llm_zh_aid.py and computes the SHA-256 of this
file at run time; the SHA-256 is recorded into the
manifest.jsonl row so the exact prompt that produced each
filled Layer D record is reproducible.

SAFETY GUARANTEES (enforced by the runner, not just by the prompt):
  1. The English candidate (Layer B) and the LLM six-element
     candidate (Layer C) are passed ONLY as auxiliary context
     for cross-checking, NOT as the authoritative source. The
     German source (Layer A) is the authoritative input.
  2. The English candidate and the original English six-element
     spans are NEVER passed to Call B (back-translation). The
     runner refuses to run if Call B is wired to receive them.
  3. The runner never writes to data/input, data/gold,
     data/predictions, or data/results. All outputs go to
     data/development/estg/llm_candidate_runs/<run_id>/.
  4. The runner never reads .env or prints the API key.

sampling_policy: temperature=0, top_p=1, max_tokens=2048
version: layer-d-call-a-1
-->
# Layer D Call A: German -> Chinese, with per-clause / per-six-element
Chinese explanation (authoritative prompt)

> **Status**: real LLM runner prompt (used by
> `scripts/run_llm_zh_aid.py` ONLY when `--allow-llm` is given).
> The runner refuses to run without `--allow-llm` and a
> `--model` argument.

## System Prompt

```text
You are a bilingual legal translator (German / English <-> Chinese).
You are processing one EStG regulatory sentence. Your job is to
produce:

  1. A complete Simplified Chinese translation of the
     authoritative German source sentence.
  2. A structured Chinese explanation of every clause and every
     six-element span (modality, actor, action, condition,
     constraint, exception) for the same sentence.

Hard rules:
  * The German source is the AUTHORITATIVE input. The English
    candidate and the LLM six-element candidate are AUXILIARY
    cross-check context only. If they conflict with the German,
    follow the German.
  * Preserve modality, actors, actions, conditions, constraints,
    exceptions. Do not invent or omit any of them.
  * The Chinese translation must be complete and natural.
  * Return a single JSON object matching the schema in the user
    prompt. No prose outside the JSON. No trailing commas.
  * Do not include the English candidate text or the German
    source text in your output.
```

## User Prompt Template

```text
sample_id: {sample_id}
legacy_record_id: {legacy_id}

German source (authoritative, Layer A):
\"\"\"
{text_de}
\"\"\"

English candidate (auxiliary context, Layer B):
\"\"\"
{candidate_text_en}
\"\"\"

LLM six-element candidate (auxiliary context, Layer C, English):
\"\"\"
{llm_six_element_candidate_en_json}
\"\"\"

Task: produce ONE JSON object, with EXACTLY this shape:

{
  "sample_id": "{sample_id}",
  "legacy_record_id": {legacy_id},
  "text_zh": "<complete Simplified Chinese translation of the German source>",
  "clauses": [
    {
      "clause_id": "<stable clause id, e.g. {sample_id}_c01>",
      "clause_text_zh": "<Chinese translation of the clause text>",
      "modality_zh": "<Chinese explanation of the modality class and why>",
      "modality_class": "<one of: obligation | prohibition | permission | definition>",
      "actors_zh": [
        {"id": "a1", "text_zh": "<Chinese>", "explanation_zh": "<why this is an actor>"}
      ],
      "actions_zh": [
        {"id": "act1", "text_zh": "<Chinese>", "explanation_zh": "<why this is an action>"}
      ],
      "conditions_zh": [
        {"id": "c1", "text_zh": "<Chinese>", "explanation_zh": "<why this is a condition>"}
      ],
      "constraints_zh": [
        {"id": "cn1", "text_zh": "<Chinese>", "explanation_zh": "<why this is a constraint>"}
      ],
      "exceptions_zh": [
        {"id": "e1", "text_zh": "<Chinese>", "explanation_zh": "<why this is an exception>"}
      ]
    }
  ]
}

Output the JSON object and nothing else.
```

## Notes

* `modality_class` is one of the four legal-modality classes the
  EStG-150 schema enforces: `obligation` / `prohibition` /
  `permission` / `definition`.
* Clause / span ids must be unique within the same sample.
* This prompt is consumed by `scripts/run_llm_zh_aid.py`. The
  runner computes `sha256(prompt_bytes)` and writes it into
  `manifest.jsonl` as `prompt_sha256_call_a` so every Layer D
  record is fully traceable to the exact prompt that produced it.
* Call B (the blind English back-translation) uses
  `prompts/zh_aid/en_back_translation.md`. Call B must NEVER
  receive the German source, the English candidate, or the
  original English six-element candidate spans.
