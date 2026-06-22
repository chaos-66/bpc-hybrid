# R13.6 Next Bounded Run Plan

## 1. Purpose

This document defines the plan for a possible R13.7 bounded real API
mini-pilot using one of the R13.6 refined prompts. This is a **planning-only**
document — no real API call occurs in R13.6.

## 2. Recommended Next Stage

**Stage**: R13.7 — Single-prompt bounded 8-sample real API mini-pilot
with refined prompt.

**Recommended prompt**: `r13_6_prompt_B` (few_shot_extraction).

## 3. Candidate Prompt

**Primary**: Prompt B — Few-shot Extraction
- File: `prompts/r13_6/few_shot_extraction_prompt.md`
- 3 synthetic examples covering passive voice, prohibition, and definition patterns
- Expected to address: action normalization, actor inference, constraint form

**Alternative**: Prompt C — Two-step Hidden Extraction
- File: `prompts/r13_6/two_step_hidden_extraction_prompt.md`
- Internal reasoning without output
- May better address subject-complement confusion

**Fallback**: Prompt A — Field Definition Strengthened
- File: `prompts/r13_6/field_definition_strengthened_prompt.md`
- Minimal change, lowest risk

## 4. Input Samples

Same 8 samples from the R13.3 mini-gold set:

| Sample ID | Source | Reference |
|-----------|--------|-----------|
| r13_3_candidate_001 | gdpr_eurlex | Article 5(1)(a) |
| r13_3_candidate_002 | gdpr_eurlex | Article 5(1)(b) |
| r13_3_candidate_003 | gdpr_eurlex | Article 5(1)(c) |
| r13_3_candidate_004 | gdpr_eurlex | Article 7(1) |
| r13_3_candidate_005 | gdpr_eurlex | Article 9(1) |
| r13_3_candidate_006 | austrian_income_tax_code | § 1 Abs 1 |
| r13_3_candidate_007 | austrian_income_tax_code | § 1 Abs 2 |
| r13_3_candidate_008 | austrian_income_tax_code | § 1 Abs 3 |

Source: `data/formal/processed/r13_3_candidate_samples.jsonl`

## 5. API Boundary

For any R13.7 real API execution:

| Constraint | Value |
|------------|-------|
| Max calls | 8 |
| Attempts per sample | 1 |
| Retry allowed | No |
| Repair call allowed | No |
| Batch allowed | No |
| Raw response saved | No |
| Provider | openai_compatible (qwen3.7-max) |
| Authorization required | Fresh explicit user authorization |

The R13.4.2 authorization is **consumed** and does not carry forward.

## 6. Output Paths

If R13.7 is authorized and executed, output files should follow the
established pattern:

- Predictions: `data/formal/predictions/r13_7_real_predictions.jsonl`
- Evaluation summary: `data/formal/results/r13_7_real_evaluation_summary.json`
- Evaluation details: `data/formal/results/r13_7_real_evaluation_details.jsonl`
- Metadata: `data/formal/metadata/r13_7_*.json`

## 7. Stop Conditions

The R13.7 run must stop immediately if:
1. Any API call returns a non-schema-valid response (same gate as R13.4.2)
2. Any API error (network, auth, timeout) occurs — no retry
3. The prompt is found to contain any material error before execution

## 8. Required User Authorization Statement

Before any R13.7 real API execution, the user must explicitly state
(in the conversation):

```
I authorize R13.7: one bounded 8-call real API mini-pilot using
[r13_6_prompt_B | r13_6_prompt_C].
I understand:
- R13.7 is NOT a benchmark, method validation, or Sun reproduction.
- Maximum 8 API calls, one attempt per sample, no retry, no batch,
  no raw response saved.
- This authorization is for R13.7 only and does not authorize any
  subsequent run.
```

The executing agent must refuse to proceed without this exact statement
or its equivalent.

## 9. Post-run Audit Requirement

After any R13.7 execution:
- A Codex local-only audit is required before accepting results.
- The audit must verify: call count, schema validity, no retry, no
  raw response storage, no data contamination with gold.
- Results must not be described as benchmark, method validation, or
  Sun reproduction.

## 10. Claim Boundary

R13.6 does not run any API. This document is a plan for a hypothetical
R13.7 stage. No benchmark, method validation, or Sun reproduction claims
are made. The recommended prompt (Prompt B) is a hypothesis that requires
real API testing to validate.
