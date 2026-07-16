<!--
LLM prompt DRY-RUN: do NOT call any LLM/API to verify this prompt.
Verification is done by reading this file and running the offline
estimator in scripts/dry_run_llm_estimate.py.

sampling_policy: temperature=0, top_p=1, max_tokens=4096
note: The real sampling parameters are sent by bpc_hybrid.llm_config
and recorded in the prediction manifest.
version: dry-run-1
-->
# Layer C Dry-Run Prompt: Six-Element Extraction (offline only)

> **Status**: dry-run only. This file documents the prompt that WILL
> be used if/when the user authorizes a real LLM call to (re)generate
> layer C (`estg_150_llm_six_element_candidates_v1.jsonl`). It is NOT
> wired into any runner. Any real call requires explicit user
> authorization + a recorded call budget.

## System Prompt (proposed)

```text
You are a regulatory text formalization expert. Given a single
regulatory sentence in English, extract a Stage 2 canonical
prediction record with the modality / actor / action / condition /
constraint / exception spans.

Hard rules:
  1. Output ONLY a single JSON object. No prose.
  2. Use one of: obligation, prohibition, permission, definition.
  3. For obligation / prohibition / permission clauses, list every
     actor / action / condition / constraint / exception span as
     {id, text, start, end, normalized}. spans must lie inside the
     clause text. IDs unique within a clause.
  4. For "X means ..." or "X refers to ..." definition clauses,
     set modality.label to "definition" and leave actions empty.
  5. Do NOT invent content. If a field cannot be determined, omit it
     from the array and record the reason in unsupported_or_ambiguous.
```

## User Prompt Template

```text
Regulatory sentence (id: {sample_id}):

{source_text}

Return a single JSON object with the keys:
schema_version, sample_id, source_id, source_text, clauses, method,
validation, unsupported_or_ambiguous.
```

## Few-shot examples (4)

Same as the D1 prompt in `direct_llm_sun_record_prompt.md` v3, but
**without the v3 sampling-policy comment**, since the LLM does not
read this comment.

## Required call-budget manifest

Each call writes to
`data/development/estg/llm_candidate_runs/<run_id>/manifest.jsonl`
with:
  - timestamp
  - model
  - prompt_sha256
  - response_sha256
  - sample_id
  - input_tokens
  - output_tokens
  - elapsed_ms
  - error (if any)

The manifest is part of the formal capsule; deletion requires an
audit event.
