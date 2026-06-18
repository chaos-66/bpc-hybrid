# R12.1 Synthetic Prototype Pilot Report

## 1. Status

```
R12_1_STATUS: PARTIAL
```

**Reason**: Pilot executed successfully with 14 real API calls. 4/14 produced
schema-valid output; 10/14 timed out (API transport error). No config_blocked,
no schema_invalid, no retry, no repair, no raw response saved.

## 2. Input Dataset

| Field | Value |
|-------|-------|
| File | `data/prototype/legal_sentences.jsonl` |
| Sample count | 14 synthetic prototype sentences |
| Source IDs | d01-d08, d12-d13, d27-d28, d34-d35 |
| Dataset type | `synthetic_prototype` |
| Gold annotations | `data/prototype/gold_multiclause.jsonl` (14 gold) |

## 3. Safety Boundary

| Constraint | Held |
|------------|------|
| Real API calls | 14 (1 per sample) |
| Calls ≤ sample count | ✅ (14 = 14) |
| Retry | ❌ (none) |
| Repair call | ❌ (none) |
| Raw response saved | ❌ (none) |
| Batch endpoint | ❌ (none) |
| Batch field on results | `false` |
| Formal benchmark | ❌ (none) |
| Method-validation claim | ❌ (none) |
| Accuracy/f1/metrics claim | ❌ (none) |
| `.env` read | ❌ (redacted config only) |
| Secrets leaked in output | ❌ (all `secret_redacted: true`) |
| API keys in output | ❌ (none) |
| `raw_response` field in results.jsonl | ❌ (none) |

## 4. API Call Budget

| Metric | Count |
|--------|-------|
| Max permitted | 14 |
| Attempted | 14 |
| Successful (schema_valid) | 4 |
| Failed (api_error) | 10 |
| Schema invalid | 0 |
| Config blocked | 0 |

## 5. Execution Summary

| Field | Value |
|-------|-------|
| Stage | R12.1 |
| Entrypoint | `scripts/run_synthetic_prototype_pilot.py` |
| Provider | `openai_compatible` |
| Model | `qwen3.7-max` |
| Started at | 2026-06-18T04:12:20 UTC |
| Ended at | 2026-06-18T04:18:24 UTC |
| Duration | ~6 minutes |
| Output dir | `outputs/r12_1_synthetic_prototype_pilot/` |

## 6. Per-sample Metadata Summary

| source_id | status | schema_valid | attempted | successful | error |
|-----------|--------|-------------|-----------|------------|-------|
| d01 | api_error | false | 1 | 0 | Real API timeout (details redacted) |
| d02 | api_error | false | 1 | 0 | Real API timeout (details redacted) |
| d03 | schema_valid | true | 1 | 1 | — |
| d04 | schema_valid | true | 1 | 1 | — |
| d05 | api_error | false | 1 | 0 | Real API timeout (details redacted) |
| d06 | api_error | false | 1 | 0 | Real API timeout (details redacted) |
| d07 | schema_valid | true | 1 | 1 | — |
| d08 | api_error | false | 1 | 0 | Real API timeout (details redacted) |
| d12 | api_error | false | 1 | 0 | Real API timeout (details redacted) |
| d13 | api_error | false | 1 | 0 | Real API timeout (details redacted) |
| d27 | api_error | false | 1 | 0 | Real API timeout (details redacted) |
| d28 | api_error | false | 1 | 0 | Real API timeout (details redacted) |
| d34 | schema_valid | true | 1 | 1 | — |
| d35 | api_error | false | 1 | 0 | Real API timeout (details redacted) |

### Schema-valid outputs (4/14)

| source_id | Sentence | Modality | Notes |
|-----------|----------|----------|-------|
| d03 | A service provider must retain the log. | must | single-clause, normal |
| d04 | A user shall not disclose the token. | shall not | negated modality |
| d07 | A controller may disclose the record only if authorized. | may | with condition |
| d34 | The provider warrants that the service is available. | (null) | hard — modality=null in output |

All 4 schema-valid outputs were produced by single-clause sentences.
Hard sentences (d27, d34 partial) and multi-clause sentences (d06, d13) all
timed out.

### Failure cases summary (10/14)

All 10 failures are `api_error` with redacted message: "Real API timeout
(details redacted)". No schema_invalid and no config_blocked. The pattern
suggests the API endpoint has a low timeout threshold — longer or more complex
sentences (multi-clause, hard, condition-bearing) consistently timed out.

## 7. Claim Boundary

This pilot is **NOT** a formal dataset experiment. It reports **descriptive
statistics only**:

- `schema_valid`: 4 (pipeline produced schema-conformant JSON)
- `schema_invalid`: 0 (no malformed output reached the schema gate)
- `api_error`: 10 (API timed out before producing output)
- `config_blocked`: 0 (real API was enabled throughout)

**No** claim is made about:
- Accuracy, precision, recall, or F1 of the LLM output
- Method superiority or comparison to any baseline
- Generalizability to real GDPR/BPMN/Sun datasets
- Production readiness

## 8. Next Step

R12.2 or later: investigate timeout root cause (API endpoint timeout threshold,
request payload size, network latency). The 4/14 schema-valid results confirm
the pipeline works end-to-end; the 10/14 timeout rate indicates the current API
endpoint is not suitable for a full dataset experiment without adjustment.

No further real API calls are authorized under R12.1.
