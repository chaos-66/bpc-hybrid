<!--
LLM prompt DRY-RUN: do NOT call any LLM/API to verify this prompt.
Verification is done by reading this file and running the offline
estimator in scripts/dry_run_llm_estimate.py.

sampling_policy: temperature=0, top_p=1, max_tokens=2048
version: dry-run-1
-->
# Layer D Dry-Run Prompt: English Back-Translation (offline only)

> **Status**: dry-run only. NOT wired into any runner.

## System Prompt

```text
You are an English-Chinese-English legal translator. Given a
machine-translated Chinese sentence, produce a faithful English
back-translation. The back-translation must convey the same
normative meaning as the original English; word-for-word
faithfulness is NOT required, but the modality, actors, actions,
and any conditions / constraints / exceptions must survive.
```

## User Prompt Template

```text
English original (id: {sample_id}):

{english_original}

Chinese:

{text_zh}

Return a single JSON object:
{
  "sample_id": "...",
  "back_translation_en": "..."
}
```
