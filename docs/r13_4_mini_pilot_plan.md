# R13.4 Mini-pilot Evaluation Plan

## 1. Stage Purpose

R13.4 is **mini-pilot evaluation planning only**.

- Does NOT execute real API calls.
- Does NOT produce experimental results.
- Does NOT validate the method.
- Does NOT reproduce Sun et al.
- Does NOT serve as a benchmark.

The sole purpose of this plan is to define the evaluation protocol for a future bounded mini-pilot (R13.4.x) that will test whether the local pipeline can produce schema-aligned predictions on the 8 manually reviewed samples from R13.3.1.

## 2. Current Inputs

| Input | Path |
|-------|------|
| Candidate samples (unreviewed) | `data/formal/processed/r13_3_candidate_samples.jsonl` |
| Manually reviewed gold annotations | `data/formal/gold/r13_3_manual_gold_template.jsonl` |

Both files contain 8 samples (5 GDPR + 3 Austrian Income Tax Code).

> ⚠️ The 8 reviewed mini-gold entries are suitable only for a bounded mini-pilot, NOT for benchmark claims.

## 3. Mini-gold Summary

| Modality | Count | Sample IDs |
|----------|-------|-------------|
| obligation | 4 | 001, 002, 003, 004 |
| prohibition | 1 | 005 |
| definition | 3 | 006, 007, 008 |
| permission | 0 | — |
| unknown | 0 | — |
| **Total** | **8** | 001–008 |

### Per-sample Details

| ID | Source | Ref | Modality | Note |
|----|--------|-----|----------|------|
| 001 | GDPR | Article 5(1)(a) | obligation | Lawfulness, fairness, transparency |
| 002 | GDPR | Article 5(1)(b) | obligation | Purpose limitation with embedded negative constraint |
| 003 | GDPR | Article 5(1)(c) | obligation | Data minimisation |
| 004 | GDPR | Article 7(1) | obligation | Conditional obligation (consent-based) |
| 005 | GDPR | Article 9(1) | prohibition | Special categories of personal data |
| 006 | Austrian | §1 Abs 1 | definition | Unlimited tax liability classification |
| 007 | Austrian | §1 Abs 2 | definition | Unlimited tax liability with scope |
| 008 | Austrian | §1 Abs 3 | definition | Limited tax liability classification |

## 4. Prediction Output Schema

Future model output (JSONL, one object per line):

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

### Execution Constraints

- **raw response not saved** (`raw_response_saved: false`).
- **Exactly 1 attempt per sample** (`attempt_count: 1`).
- **No retry, no repair call, no batch.**
- Max 8 API calls total for the mini-pilot.

## 5. Evaluation Dimensions

| Dimension | Type | Description |
|-----------|------|-------------|
| `modality` | categorical | obligation / prohibition / permission / definition / unknown |
| `actor` | string | The entity on which the rule operates |
| `action` | string | The regulated activity |
| `condition` | string or null | Triggering condition for the rule |
| `constraint` | string | The normative constraint imposed |
| `exception` | string or null | Exceptions to the rule |
| `schema_validity` | boolean | Whether prediction passes schema validation |
| `runtime_safety` | categorical | Error category (null = no error) |

## 6. Scoring Rules

### Modality (exact match)

```
modality_exact: predicted.modality == gold.modality
```

### Field-level Labels

| Label | Meaning |
|-------|---------|
| `exact` | Predicted value matches gold exactly |
| `partial` | Predicted value captures part of the gold meaning |
| `missing` | Gold has a value, prediction is null/empty |
| `wrong` | Predicted value differs materially from gold |
| `not_applicable` | Both gold and prediction are null (correctly empty) |

### Per-dimension Application

| Dimension | Labels |
|-----------|--------|
| actor | exact / partial / missing / wrong |
| action | exact / partial / missing / wrong |
| condition | exact / partial / missing / wrong / not_applicable |
| constraint | exact / partial / missing / wrong |
| exception | exact / partial / missing / wrong / not_applicable |
| schema_valid | true / false |

### Allowed Outputs

The evaluation may produce **descriptive counts**:

- Modality exact match count
- Field-level exact / partial / missing / wrong counts per dimension
- Schema validity count
- Failure count by category

### FORBIDDEN Outputs

> ⚠️ 8 samples are too few for statistical claims. The following phrases are FORBIDDEN in R13.4.x reports:
>
> - "accuracy improved"
> - "method validated"
> - "outperformed Sun"
> - "benchmark completed"
> - "formal evaluation success"

## 7. Failure Categories

| Category | Description |
|----------|-------------|
| `schema_invalid` | Prediction fails schema validation |
| `modality_wrong` | Modality predicted incorrectly |
| `actor_missing` | Actor field null when gold has actor |
| `action_missing` | Action field null when gold has action |
| `condition_wrong` | Condition predicted incorrectly |
| `constraint_wrong` | Constraint predicted incorrectly |
| `exception_wrong` | Exception predicted incorrectly (false positive/negative) |
| `api_timeout` | API call timed out |
| `api_error` | API returned an error (non-timeout) |
| `config_blocked` | LLM config gate blocked the call |
| `unsafe_output` | Output contains disallowed content |
| `overclaim_detected` | Report contains forbidden overclaim phrase |

## 8. R13.4.x Execution Roadmap

| Stage | Description | Real API | Status |
|-------|-------------|----------|--------|
| **R13.4** | Planning only (this document) | no | Current |
| **R13.4.1** | Implement local evaluator and result schema; no real API | no | Planned |
| **R13.4.2** | User-authorized bounded real mini-pilot (max 8 calls) | yes | Planned |
| **R13.4.3** | Audit / report cleanup if needed | no | Planned |

### R13.4.1 Scope

- Create `scripts/evaluate_mini_pilot.py` or equivalent local evaluator.
- Load gold + prediction JSONL, compute per-sample field-level match labels.
- Produce `outputs/r13_4_2_mini_pilot_results.json` schema.
- Run mock-only (predictions from file, not API).
- No network, no `.env`, no real API.

### R13.4.2 Scope

- Requires **explicit user authorization** before any real API call.
- Max 8 calls (1 per sample), no retry, no batch, no raw response save.
- Run the local pipeline on all 8 gold samples.
- Produce `outputs/r13_4_2_mini_pilot_predictions.jsonl` and `outputs/r13_4_2_mini_pilot_results.json`.
- Descriptive counts only; no benchmark claims.

### R13.4.3 Scope

- Review R13.4.2 results for edge cases.
- Fix any documentation issues.
- No new API calls unless user explicitly authorizes additional samples.

## 9. Safety and Claim Boundary

> **This mini-pilot is NOT a benchmark.**
>
> **This mini-pilot does NOT validate the method.**
>
> **This mini-pilot does NOT reproduce Sun et al.**
>
> This mini-pilot only checks whether the local pipeline can produce schema-aligned predictions on 8 manually reviewed samples.

- No real API calls in R13.4 / R13.4.1.
- R13.4.2 requires explicit user authorization before any API call.
- No raw LLM responses are stored.
- No batch processing, no retry, no repair calls.
- All output files are JSONL with full runtime metadata.

## 10. Acceptance Criteria

| # | Criterion | Target |
|---|-----------|--------|
| 1 | Plan document exists | `docs/r13_4_mini_pilot_plan.md` |
| 2 | Metric plan JSON exists | `data/formal/metadata/r13_4_metric_plan.json` |
| 3 | Gold distribution correctly stated | 4 obligation / 1 prohibition / 3 definition |
| 4 | All 8 evaluation dimensions defined | yes |
| 5 | All 12 failure categories defined | yes |
| 6 | R13.4.x roadmap clear | 3 sub-stages defined |
| 7 | Claim boundary explicit | yes |
| 8 | No forbidden overclaims in any R13.4 doc | yes |
| 9 | README / logs updated | yes |
| 10 | Pytest + health + eval pass | yes |

## 11. User Authorization Required Before Real API

> ⚠️ **STOP**: R13.4.2 must not proceed until the user explicitly authorizes a bounded mini-pilot with real API calls.
>
> The agent must refuse `--execute-real-api` / `--allow-llm` until authorization is confirmed.
>
> R13.4.1 (local evaluator, mock-only) may proceed without API authorization.

## 12. Known Risks

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| 1 | 8 samples too few for meaningful evaluation | Statistical claims invalid | No statistical claims; descriptive counts only |
| 2 | Gold distribution skewed (no permission/unknown) | Some failure categories untested | Document the gap; do not interpolate |
| 3 | R13.3.1 used `Remove-Item` to delete a temporary script | Process violation recorded | I057 filed; use `python -c` or existing scripts in R13.4+ |
| 4 | Real API may timeout (cf. R12.1: 10/14 timeouts) | Mini-pilot may need timeout tuning | R13.4.2 `--timeout-seconds` flag from R12.3.0 |
| 5 | Austrian legal German may challenge the pipeline | Multi-lingual edge cases | Only 3 Austrian samples; treat as exploratory |
