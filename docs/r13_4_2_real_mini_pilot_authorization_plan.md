# R13.4.2 Real Mini-pilot Authorization Plan

## 1. Stage Purpose

R13.4.2-pre defines the authorization plan, execution contract, and safety rules
for a future bounded 8-sample real API mini-pilot. This stage does NOT run real
API — it is purely a planning and authorization gate.

R13.4.2-pre does not run real API.
R13.4.2 real execution requires explicit user authorization.

## 2. Current Accepted Inputs

| Input | Path | Status |
|-------|------|--------|
| Candidate samples | `data/formal/processed/r13_3_candidate_samples.jsonl` | Accepted |
| Mini-gold annotations | `data/formal/gold/r13_3_manual_gold_template.jsonl` | Accepted |
| Metric plan | `data/formal/metadata/r13_4_metric_plan.json` | Accepted |
| Result schema | `data/formal/metadata/r13_4_1_result_schema.json` | Accepted |
| Local evaluator | `src/bpc_hybrid/mini_pilot_evaluator.py` | Accepted (R13.4.1.1) |
| Evaluator tests | `tests/test_mini_pilot_evaluator.py` | Accepted (44 tests) |

## 3. Mini-gold Set

| Property | Value |
|----------|-------|
| Sample count | 8 |
| Obligation | 4 (r13_3_candidate_001–004) |
| Prohibition | 1 (r13_3_candidate_005) |
| Definition | 3 (r13_3_candidate_006–008) |
| Permission | 0 |
| Unknown | 0 |
| Sources | 5 GDPR (eurlex) + 3 Austrian (income tax code) |

## 4. Planned Real API Scope

| Constraint | Value |
|------------|-------|
| Maximum real API calls | 8 |
| One attempt per sample | Yes |
| Retry allowed | No |
| Repair call allowed | No |
| Batch allowed | No |
| Raw response saved | No |
| Benchmark claim | No |
| Method-validation claim | No |
| Sun reproduction claim | No |

Explicitly NOT allowed:

- Larger dataset beyond 8 samples
- Raw PDF extraction
- Sun reproduction
- BPMN matching experiment
- Benchmark comparison
- Accuracy improvement claim

## 5. Execution Contract

See `data/formal/metadata/r13_4_2_execution_contract.json` for the
machine-readable execution contract.

Key constraints:

```json
{
  "real_api_call_allowed_now": false,
  "requires_explicit_user_authorization": true,
  "max_real_api_calls": 8,
  "one_attempt_per_sample": true,
  "retry_allowed": false,
  "repair_call_allowed": false,
  "batch_allowed": false,
  "raw_response_saved": false,
  "benchmark": false,
  "method_validation": false,
  "sun_reproduction": false
}
```

## 6. Prediction Output Path

Real predictions will be written to:

```
data/formal/predictions/r13_4_2_real_predictions.jsonl
```

Each line must conform to the R13.4.1 prediction record schema:

```json
{
  "sample_id": "r13_3_candidate_001",
  "source_id": "gdpr_eurlex",
  "predicted": {
    "modality": "obligation",
    "actor": "...",
    "action": "...",
    "condition": null,
    "constraint": "...",
    "exception": null
  },
  "runtime": {
    "provider": "openai_compatible",
    "model": "configured_model_name",
    "real_api_call_performed": true,
    "raw_response_saved": false,
    "attempt_count": 1,
    "duration_ms": 0,
    "error_category": null
  },
  "schema_valid": true
}
```

On API error/timeout/schema-invalid, a structured error record must be written.
Raw response must NOT be saved in any case.

## 7. Evaluation Output Path

After real predictions are generated, the existing local evaluator will score them:

| Output | Path |
|--------|------|
| Summary | `data/formal/results/r13_4_2_real_evaluation_summary.json` |
| Details | `data/formal/results/r13_4_2_real_evaluation_details.jsonl` |
| Report | `docs/r13_4_2_real_mini_pilot_report.md` |

Summary must contain:

```json
{
  "real_api_call": true,
  "benchmark": false,
  "method_validation": false,
  "sun_reproduction": false,
  "sample_count": 8,
  "claim_boundary": "8-sample real mini-pilot only. No benchmark, no method validation, no Sun reproduction."
}
```

## 8. Runtime Safety Rules

1. Must not read `.env` content directly.
2. API config may only be loaded through existing safe project config logic.
3. Each sample max one attempt.
4. No retry.
5. No repair call.
6. No batch request.
7. No raw response saved.
8. Only structured predictions are written.
9. On timeout/API error, write structured error record.
10. Stop immediately if more than 8 attempted calls would occur.
11. Stop immediately if raw response saving is attempted.
12. Stop immediately if `.env` content is printed or read directly.

## 9. Failure Handling

| Failure Category | Trigger | Prediction Record |
|-----------------|---------|-------------------|
| `schema_invalid` | LLM output does not parse to valid prediction schema | Structured error record with null fields |
| `api_timeout` | API call exceeds configured timeout | Structured error record with `error_category: "api_timeout"` |
| `api_error` | API returns non-200 / network error | Structured error record with `error_category: "api_error"` |
| `config_blocked` | Required config keys missing / blocked | Stop immediately, no API call |
| `unsafe_output` | LLM output contains refused / harmful content | Structured error record with `error_category: "unsafe_output"` |
| `overclaim_detected` | Output implies benchmark/method-validation/Sun claims | Structured error record, escalate to review |

All failure records follow this template:

```json
{
  "sample_id": "r13_3_candidate_XXX",
  "source_id": "gdpr_eurlex",
  "predicted": {
    "modality": null,
    "actor": null,
    "action": null,
    "condition": null,
    "constraint": null,
    "exception": null
  },
  "runtime": {
    "provider": "openai_compatible",
    "model": "configured_model_name",
    "real_api_call_performed": true,
    "raw_response_saved": false,
    "attempt_count": 1,
    "duration_ms": 0,
    "error_category": "api_timeout"
  },
  "schema_valid": false
}
```

## 10. Claim Boundary

R13.4.2-pre does not run real API.
R13.4.2 real execution requires explicit user authorization.
The maximum real API calls will be 8.
Each sample may be called at most once.
No retry.
No repair call.
No batch.
No raw response saving.
No benchmark claim.
No method-validation claim.
No Sun reproduction claim.

Even after execution, R13.4.2 results may only be described as:

> 8-sample real mini-pilot — not a benchmark, not method validation, not Sun reproduction.

## 11. User Authorization Statement Required

Before R13.4.2 real execution begins, the user must explicitly issue an
authorization statement. Examples:

English:

> I authorize R13.4.2 to run a bounded real API mini-pilot with at most 8 calls,
> one attempt per sample, no retries, no repair calls, no batch requests,
> no raw response saving, and no benchmark/method-validation/Sun-reproduction
> claims.

Chinese:

> 我授权 R13.4.2 执行一次有界真实 API mini-pilot，最多 8 次调用，每条样本最多一次，
> 不重试，不 repair call，不 batch，不保存 raw response，不做 benchmark、
> 方法验证或 Sun 复现声明。

Without this statement, R13.4.2 real execution MUST NOT proceed.

## 12. Stop Conditions

The agent MUST refuse `--execute-real-api` / `--allow-llm` until authorization
is confirmed. Stop immediately if:

- Authorization statement not received
- Any safety rule would be violated
- `.env` content is read directly
- Raw response saving is attempted
- More than 8 calls would be made
- Any overclaim language detected in outputs

## 13. Post-run Audit Requirement

After any real execution (should one be authorized), a Codex audit of:

- `data/formal/predictions/r13_4_2_real_predictions.jsonl`
- `data/formal/results/r13_4_2_real_evaluation_summary.json`
- `data/formal/results/r13_4_2_real_evaluation_details.jsonl`
- `docs/r13_4_2_real_mini_pilot_report.md`

is mandatory. The audit must verify:

- No benchmark/method-validation/Sun-reproduction language
- No raw response content
- `real_api_call: true` but `benchmark: false`
- Exactly 8 samples scored
- All failure categories are valid
- No credential leakage
