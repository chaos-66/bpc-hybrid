# R13.4.1 Local Evaluator Report

## 1. Stage Result

```
R13_4_1_STATUS: PASSED
```

R13.4.1 implements a local evaluator, result schema, mock prediction fixture, and comprehensive tests for future 8-sample mini-pilot evaluation.

## 2. Scope

| Constraint | Value |
|------------|-------|
| Real API call | no |
| LLM call | no |
| Data download | no |
| Benchmark | no |
| Method validation | no |
| Sun reproduction | no |
| Temporary scripts | no |
| Remove-Item / delete | no |
| .env read | no |

## 3. Implemented Files

| File | Type | Description |
|------|------|-------------|
| `src/bpc_hybrid/mini_pilot_evaluator.py` | New | Core evaluator with scoring functions |
| `scripts/evaluate_mini_pilot_predictions.py` | New | CLI entrypoint for evaluation |
| `tests/test_mini_pilot_evaluator.py` | New | Comprehensive unit tests (44 as of R13.4.1.1) |
| `data/formal/metadata/r13_4_1_result_schema.json` | New | Result schema documentation |
| `data/formal/predictions/r13_4_1_mock_predictions.jsonl` | New | 8 mock predictions for testing |
| `data/formal/results/r13_4_1_mock_evaluation_summary.json` | New | Mock evaluation summary output |
| `data/formal/results/r13_4_1_mock_evaluation_details.jsonl` | New | Mock evaluation per-sample details |

## 4. Result Schema

See `data/formal/metadata/r13_4_1_result_schema.json` for the full machine-readable schema.

### Prediction Record (input)
- Required top-level: `sample_id`, `source_id`, `predicted`, `runtime`, `schema_valid`
- `predicted` contains: `modality`, `actor`, `action`, `condition`, `constraint`, `exception`
- `runtime` contains: `provider`, `model`, `real_api_call_performed`, `raw_response_saved`, `attempt_count`, `duration_ms`, `error_category`

### Evaluation Detail (output, per sample)
- `sample_id`, `source_id`, `schema_valid`
- `field_scores`: per-dimension match label (exact/partial/missing/wrong/not_applicable)
- `failure_categories`: list of triggered failure types
- `notes`: free-text

### Evaluation Summary (output)
- `stage`, `type`, `real_api_call`, `benchmark`, `method_validation`, `sun_reproduction`
- `sample_count`, `schema_valid_count`
- `field_score_counts`: per-dimension per-label counts
- `failure_category_counts`: per-category counts
- `claim_boundary`

## 5. Scoring Rules

### Modality (categorical, exact-only)
| Condition | Label |
|-----------|-------|
| `predicted.modality == gold.modality` | exact |
| `predicted.modality` null/empty, gold present | missing |
| Otherwise | wrong |

### Text fields (actor, action, condition, constraint, exception)
| Gold | Prediction | Label |
|------|-----------|-------|
| null/empty | null/empty | not_applicable |
| null/empty | non-empty | wrong |
| non-empty | null/empty | missing |
| non-empty | non-empty, normalized equal | exact |
| non-empty | one contains the other, or token overlap ≥ 0.5 | partial |
| non-empty | otherwise | wrong |

### Normalization
1. lowercase
2. strip whitespace
3. collapse internal whitespace to single spaces
4. remove simple punctuation `.,;:!?"'()-`

### Failure Category Mapping
- `schema_invalid`: record fails structural validation or has `schema_valid: false`
- `modality_wrong`: modality scored wrong or missing
- `actor_missing`: actor scored missing
- `action_missing`: action scored missing
- `condition_wrong`: condition scored wrong or missing
- `constraint_wrong`: constraint scored wrong or missing
- `exception_wrong`: exception scored wrong or missing
- `api_timeout` / `api_error` / `config_blocked`: from `runtime.error_category`

## 6. Mock Prediction Test

The 8 mock predictions exercise all five scoring labels:

| Label | Example fields |
|-------|---------------|
| exact | modality (6/8), actor (6/8), action (5/8), condition (4/8), constraint (3/8) |
| partial | constraint (001, 002, 003), action (002, 004), condition (005) |
| wrong | actor (002, 004), constraint (004) |
| missing | constraint (005) |
| not_applicable | condition (001, 002), exception (all 8) |

## 7. Verification

| Check | Result |
|-------|--------|
| `py_compile mini_pilot_evaluator.py` | PASS |
| `py_compile evaluate_mini_pilot_predictions.py` | PASS |
| CLI run with mock predictions | PASS — summary + details written |
| Unit tests (24 tests) | PASS |
| Full pytest | PASS |
| Health check | scaffold-ok |
| Synthetic eval | F1=1.0 |

## 8. Claim Boundary

> R13.4.1 uses mock predictions only.
>
> R13.4.1 does NOT run real API.
>
> R13.4.1 does NOT produce benchmark results.
>
> R13.4.1 does NOT validate the method.
>
> R13.4.1 does NOT reproduce Sun et al.
>
> R13.4.1 only validates local evaluator mechanics using hand-crafted mock predictions.

## 9. Readiness for R13.4.2

| Criterion | Status |
|-----------|--------|
| Evaluator can score all 8 dimensions | ✅ |
| CLI produces summary + details | ✅ |
| Result schema documented | ✅ |
| Mock predictions exercise all 5 labels | ✅ |
| Tests cover comprehensive scoring, schema, and boundary scenarios | ✅ |
| No real API in any code path | ✅ |
| No .env read in any code path | ✅ |

The evaluator is ready for R13.4.2. The only missing piece is real API-authorized predictions.

## 10. R13.4.1.1 — Codex Audit Blocker Fixes

### Fixes Applied

| # | Issue | Fix |
|---|-------|-----|
| 1 | Summary `real_api_call` and `type` hardcoded | Derive from `predictions[].runtime.real_api_call_performed` |
| 2 | `source_id` not in `_REQUIRED_TOP_FIELDS` | Added `source_id` to required top-level fields |
| 3 | `schema_valid` accepted non-bool values | Enforce `isinstance(schema_valid, bool)` in `validate_prediction_record` |
| 4 | No duplicate sample_id detection | Raise `ValueError` on duplicate sample_ids in gold, predictions, candidates |

### Updated Files

- `src/bpc_hybrid/mini_pilot_evaluator.py` — 4 fixes applied
- `tests/test_mini_pilot_evaluator.py` — 9 new regression tests (44 total)
- `docs/r13_4_1_local_evaluator_report.md` — this entry
- `README.md` — stage updated to R13.4.1.1
- `docs/experiment_log.md` — R13.4.1.1 entry
- `docs/issue_log.md` — I059 added

### Verification

- 659/659 full pytest pass
- 44/44 evaluator tests pass
- Mock results regenerated with derived `type: mock_local_evaluation`

---

## 11. User Authorization Required

> ⚠️ **STOP**: R13.4.2 must NOT proceed until the user explicitly authorizes a bounded mini-pilot with real API calls.
>
> The agent must refuse `--execute-real-api` / `--allow-llm` until authorization is confirmed.
>
> R13.4.2 will use the evaluator implemented here to score real predictions against the 8-sample mini-gold set.
>
> Maximum: 8 API calls (1 per sample), no retry, no batch, no raw response storage.
