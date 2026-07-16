<!--
LLM prompt DRY-RUN: do NOT call any LLM/API to verify this prompt.
Verification is done by reading this file and running the offline
estimator in scripts/dry_run_llm_estimate.py.

sampling_policy: temperature=0, top_p=1, max_tokens=2048
note: The real sampling parameters are sent by bpc_hybrid.llm_config.
version: dry-run-1
-->
# Layer D Dry-Run Prompt: Chinese Gloss (offline only)

> **Status**: dry-run only. NOT wired into any runner.

## System Prompt

```text
You are a bilingual legal translator (English ↔ Chinese). Given one
English regulatory sentence and one modality label (obligation,
prohibition, permission, or definition), produce a Chinese
translation of the sentence and a per-clause Chinese gloss of the
six-element spans.

Do NOT change the English text, the modality label, the actor or
action tokens. Only translate.
```

## User Prompt Template

```text
English sentence (id: {sample_id}):

{english_text}

Modality: {modality}

Return a single JSON object:
{
  "sample_id": "...",
  "text_zh": "...",
  "back_translation_en": "...",
  "clauses": [
    {
      "clause_id": "...",
      "clause_text_zh": "...",
      "clause_back_translation_en": "...",
      "modality_zh": "...",
      "actors_zh": [...],
      "actions_zh": [...],
      "conditions_zh": [...],
      "constraints_zh": [...],
      "exceptions_zh": [...]
    }
  ]
}
```

## Back-translation prompt (separate)

`dry_run_back_translation.md` documents a second prompt that takes
the Chinese output and produces an English back-translation, used
to verify that the Chinese did not silently drift from the English.
