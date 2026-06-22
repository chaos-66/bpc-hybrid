# R13.7-pre Prompt B Authorization Plan

## 1. Purpose

This document defines the authorization plan for a possible R13.7 bounded
real API mini-pilot using Prompt B (`r13_6_prompt_B`, few_shot_extraction).
This is a **planning-only** stage — no real API call, no LLM call, and no
evaluator rerun occur in R13.7-pre.

The plan bridges R13.6 (prompt design) with R13.7 (potential execution) by
establishing the exact execution contract, safety rules, and user
authorization requirements.

## 2. Selected Prompt

| Property | Value |
|----------|-------|
| Prompt ID | `r13_6_prompt_B` |
| Prompt Name | few_shot_extraction |
| Prompt Path | `prompts/r13_6/few_shot_extraction_prompt.md` |
| Source Stage | R13.6 |
| Strategy | 3 synthetic few-shot examples with in-context learning |
| Snapshot | `data/formal/metadata/r13_7_prompt_b_selected_prompt_snapshot.json` |

**Selection rationale**:
1. R13.4.2 showed 0/8 actor exact and 0/8 action exact — primary failure is
   verbatim fragment extraction instead of normalized field values.
2. R13.5 identified passive voice, field normalization, and definition-vs-
   obligation as the dominant error patterns.
3. Prompt B uses synthetic few-shot examples that directly demonstrate the
   expected normalization level for each field, without data contamination.
4. This is only a candidate for the next bounded test — it does not imply
   that Prompt B is already effective. Only a real API test can validate.

## 3. Evidence From R13.5 / R13.6

- **R13.5 post-pilot error analysis** (`docs/r13_5_post_pilot_error_analysis.md`)
  identified action verbatim extraction (8/8 wrong) and passive-voice actor
  omission (4/8 missing) as the most pervasive failures.
- **R13.6 prompt selection matrix** (`data/formal/metadata/r13_6_prompt_selection_matrix.json`)
  ranked Prompt B priority 1 based on direct coverage of these error patterns.
- The selection matrix explicitly cautions that the recommendation is a
  hypothesis from 8 samples with one model (qwen3.7-max).

## 4. Input Samples

Same 8 samples from the R13.3 mini-gold set (unchanged since R13.3.1):

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

- Input: `data/formal/processed/r13_3_candidate_samples.jsonl`
- Gold: `data/formal/gold/r13_3_manual_gold_template.jsonl`

## 5. Planned Real API Scope

| Constraint | Value |
|------------|-------|
| Max API calls | 8 |
| Attempts per sample | 1 |
| Retry allowed | No |
| Repair call allowed | No |
| Batch allowed | No |
| Raw response saved | No |
| Provider | openai_compatible (qwen3.7-max) |
| Model | qwen3.7-max |
| Authorization required | Fresh explicit user authorization |

Note: The R13.4.2 authorization is consumed and does not carry forward.

## 6. Execution Contract

The full execution contract is defined in:
`data/formal/metadata/r13_7_prompt_b_execution_contract.json`

Key terms:
- `status`: `authorization_required` — execution is blocked until user
  explicitly authorizes.
- `real_api_call_allowed_now`: `false` — R13.7-pre does NOT execute.
- `requires_explicit_user_authorization`: `true` — fresh authorization
  is mandatory.
- All safety limits (max 8 calls, no retry, no batch, no raw saving)
  are locked in the contract.

## 7. Prediction Output Path

R13.7 prediction output must use a **new** path — do NOT overwrite
R13.4.2 outputs:

```
data/formal/predictions/r13_7_prompt_b_real_predictions.jsonl
```

This file does not yet exist and must NOT be created in R13.7-pre.

## 8. Evaluation Output Path

R13.7 evaluation outputs must use **new** paths:

```
data/formal/results/r13_7_prompt_b_real_evaluation_summary.json
data/formal/results/r13_7_prompt_b_real_evaluation_details.jsonl
docs/r13_7_prompt_b_real_mini_pilot_report.md
```

These files do not yet exist and must NOT be created in R13.7-pre.

The existing R13.4.2 evaluation files must NOT be modified or overwritten:
- `data/formal/results/r13_4_2_real_evaluation_summary.json`
- `data/formal/results/r13_4_2_real_evaluation_details.jsonl`

## 9. Runtime Safety Rules

The R13.7 runner must enforce:
1. `--execute-real-api` flag required — no execution without explicit flag.
2. `--allow-llm` flag required — no LLM call without explicit gate.
3. `--max-calls 8 --one-attempt-per-sample` — enforced programmatically.
4. No retry logic — first API failure stops the run.
5. No repair call — schema-invalid responses are logged but not retried.
6. No batch execution — samples are processed sequentially, one at a time.
7. No raw response storage — `raw_response_saved` is always `false`.
8. No `.env` content logged or stored.

## 10. Stop Conditions

The R13.7 run must stop immediately if:
1. Any API call returns a non-schema-valid response.
2. Any API error (network, auth, timeout) occurs — no retry.
3. The selected prompt is found to contain a material error before execution.
4. Any safety gate is bypassed or violated.
5. The executing agent cannot confirm the safety flags are properly set.

## 11. Required User Authorization Statement

Before R13.7 can execute, the user must explicitly state:

```
I authorize R13.7 to execute one bounded real API mini-pilot using
Prompt B, with a maximum of 8 API calls, one attempt per sample, no
retries, no repair calls, no batch execution, and no raw response
saving. I understand this is NOT a benchmark, method validation, or
Sun reproduction.
```

The executing agent must refuse to proceed without this statement
or its equivalent. No implicit authorization is accepted.

## 12. Post-run Audit Requirement

After any R13.7 execution:
- A Codex local-only audit is required before accepting results.
- The audit must verify: call count (≤8), schema validity, no retry,
  no raw response storage, no data contamination with gold, no
  unauthorized file modifications, no `.env` exposure.
- Results must not be described as benchmark, method validation, or
  Sun reproduction.

## 13. Claim Boundary

R13.7-pre does not run any API. This document is an authorization plan
for a hypothetical R13.7 stage. No benchmark, method validation, or
Sun reproduction claims are made. Prompt B is a candidate only — its
effectiveness has not been validated.
