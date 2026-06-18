# R12 Closure Report

## 1. Executive Summary

R12 is **closed as a synthetic prototype API-pipeline sanity milestone**.
It is **not** closed as a benchmark, not closed as formal dataset evaluation,
and not closed as method validation.

The R12 stages demonstrated a complete, safe, auditable real-API path from
planning through bounded execution to evidence-based closure.  Key result:
two previously-timeout synthetic samples succeeded under a 60-second timeout,
confirming the R12.2 hypothesis that the default 30-second timeout was too
short.

## 2. Stage Timeline

| Stage | Description | Real API? | Status |
|-------|-------------|-----------|--------|
| R12.0 | Staged plan creation | No | ACCEPTED |
| R12.0.1 | Pilot planning verification | No | ACCEPTED |
| R12.1 | Synthetic prototype pilot (14 calls) | Yes | ACCEPTED (PARTIAL) |
| R12.1.1 | Pilot output safety regression fix | No | ACCEPTED |
| R12.2 | Timeout analysis and strategy | No | ACCEPTED |
| R12.3.0 | Add duration/timeout metadata | No | ACCEPTED |
| R12.3.0.1 | Fix --timeout-seconds metadata propagation | No | ACCEPTED |
| R12.3.1 | 2-sample timeout sanity check | Yes (2 calls) | ACCEPTED |
| R12.3.1.1 | Commit sanitized outputs, restore test gate | No | ACCEPTED |
| R12.4 | Closure and next-stage planning | No | CURRENT |

## 3. Accepted Results

R12.1 through R12.3.1.1 are Codex-accepted.  The key evidence:

- **R12.1** produced a 14-sample synthetic prototype pilot with partial
  success under the 30-second default timeout.
- **R12.2** identified timeout/socket.timeout as the dominant failure mode
  (10/14 cases) and recommended a conservative 2-sample sanity check at
  60 seconds.
- **R12.3.0 / R12.3.0.1** added per-sample duration, timeout metadata,
  and error-category classification without real API calls.
- **R12.3.1** confirmed that two selected prior-timeout samples (d01, d02)
  both succeed under a 60-second timeout, with no batch, no retry, no
  repair call, and no raw-response storage.

## 4. R12.1 Synthetic Pilot Result

```json
{
  "sample_count": 14,
  "attempted_call_count_total": 14,
  "successful_call_count_total": 4,
  "schema_valid_count": 4,
  "api_error_count": 10,
  "timeout_seconds_configured": 30.0,
  "formal_benchmark": false,
  "method_validation": false,
  "raw_response_saved": false
}
```

## 5. R12.2 Timeout Analysis

- 10/14 api_error samples matched timeout/socket.timeout keyword patterns.
- Hypothesis: default 30-second timeout shorter than provider response time
  for many samples.
- Recommendation: bounded 2-sample sanity check at 60 seconds, no retry,
  no batch.

## 6. R12.3.0 Metadata Improvements

- Added per-sample `duration_ms`, `timeout_seconds_configured`,
  `error_category` fields.
- Added summary aggregates: `duration_ms_total`, `duration_ms_avg`,
  `timeout_error_count`, `transport_error_count`.
- Added `--timeout-seconds` CLI flag.
- R12.3.0.1: fixed timeout metadata propagation when `--execute-real-api`
  is not set.
- Code/test only; no real API calls.

## 7. R12.3.1 Two-sample Timeout Sanity

```json
{
  "sample_count": 2,
  "attempted_call_count_total": 2,
  "successful_call_count_total": 2,
  "schema_valid_count": 2,
  "api_error_count": 0,
  "timeout_seconds_configured": 60.0,
  "raw_response_saved": false,
  "batch": false,
  "retry": false,
  "repair_call": false,
  "d01_status": "schema_valid",
  "d01_duration_ms": 10589.607,
  "d02_status": "schema_valid",
  "d02_duration_ms": 10397.139
}
```

## 8. Safety and Artifact Status

| Artifact | Status |
|----------|--------|
| `outputs/r12_1_synthetic_prototype_pilot/` | Committed, sanitized, whitelisted |
| `outputs/r12_3_1_timeout_sanity/` | Committed (R12.3.1.1), sanitized, whitelisted |
| `docs/r12_3_1_timeout_sanity_report.md` | Committed |
| Test whitelists (2 files) | Updated with R12.3.1 paths |
| Full pytest (615 tests) | All passing |

## 9. Claim Boundary

R12.3.1 supports a **narrow hypothesis**: a 60-second timeout helped
two selected synthetic timeout samples (d01, d02) that previously
failed at 30 seconds.

R12 does **NOT** prove or claim:

- Benchmark completion
- Formal dataset performance
- Method validation
- Accuracy improvement
- Sun baseline outperformance
- Formal GDPR/BPMN evaluation success

R12 is closed as a synthetic prototype API-pipeline sanity milestone.
R12 is not closed as a benchmark.
R12 is not closed as formal dataset evaluation.
R12 is not method validation.

## 10. Remaining Limitations

- Only 2 of 10 prior-timeout samples were retested.
- The remaining 8 R12.1 timeout samples were not retested.
- The 4 R12.1 schema-valid samples (at 30s) were not cross-validated at 60s.
- Synthetic prototype data only — no formal GDPR/BPMN/Sun dataset.
- Single provider (openai_compatible, qwen3.7-max).
- No inter-annotator agreement evaluation.
- No statistical significance analysis.

## 11. Recommended Next Stage

### R13.0 — Formal Dataset Acquisition and Evaluation Design

R13.0 is a **planning and data-acquisition stage only**.  No real API
calls until the dataset plan is separately accepted by Codex audit.

Recommended R13.0 objectives:

1. Identify formal GDPR/BPMN/Sun dataset requirements.
2. Decide dataset source and licensing.
3. Define sample schema and evaluation protocol.
4. Define baseline / gold annotation assumptions.
5. Produce a staged R13.1-R13.x evaluation plan for separate audit.
6. No real API until dataset plan is accepted.

## 12. Exit Decision

```
R12_4_DECISION: CLOSED_AS_SYNTHETIC_PROTOTYPE_MILESTONE
R12_4_CLAIM: NOT_BENCHMARK | NOT_FORMAL_DATASET | NOT_METHOD_VALIDATION
R12_4_NEXT: R13.0 — Formal Dataset Acquisition and Evaluation Design
```
