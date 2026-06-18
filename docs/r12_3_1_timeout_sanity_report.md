# R12.3.1 — Two-sample Timeout Sanity Check Report

## Status

```
R12_3_1_STATUS: PASSED
```

## Context

R12.1 ran 14 real API calls with default 30s timeout.  10/14 calls
produced `socket.timeout` errors.  R12.2 analyzed the pattern and
recommended a bounded 2-sample sanity check at 60s timeout.

R12.3.0 / R12.3.0.1 added per-sample `duration_ms`, `error_category`,
and `timeout_seconds_configured` metadata, plus a `--timeout-seconds`
CLI flag that correctly propagates to dry-run metadata.

R12.3.1 executes the 2-sample sanity check: pick the first 2
api_error/timeout samples from R12.1 by source_id sort order, re-run
with `--timeout-seconds 60`, and record results without retry/batch.

## Selected Samples

| source_id | text |
|-----------|------|
| d01 | A controller shall record the decision. |
| d02 | A reviewer may inspect the file. |

Selection rule: deterministic — sort all `status=api_error` records
from R12.1 by `source_id`, take first 2.

## Results

| # | source_id | R12.1 (30s) | R12.3.1 (60s) | duration_ms |
|---|-----------|-------------|---------------|-------------|
| 1 | d01 | socket.timeout | schema_valid | 10589.607 |
| 2 | d02 | socket.timeout | schema_valid | 10397.139 |

## Summary

```json
{
  "sample_count": 2,
  "attempted_call_count_total": 2,
  "successful_call_count_total": 2,
  "schema_valid_count": 2,
  "api_error_count": 0,
  "timeout_error_count": 0,
  "timeout_seconds_configured": 60.0,
  "duration_ms_total": 20986.746,
  "duration_ms_avg": 10493.373,
  "raw_response_saved": false,
  "batch": false,
  "retry": false,
  "repair_call": false,
  "formal_benchmark": false,
  "method_validation": false
}
```

## Interpretation

With `timeout_seconds=60`, both previously-timed-out samples returned
schema-valid responses in ~10.5s each.  This supports the R12.2
hypothesis that the R12.1 failures were caused by the 30s default
timeout being too short for this provider/model combination.

**This is NOT**:
- A benchmark
- A formal dataset experiment
- Method validation
- A claim that 60s is "optimal"

**This IS**:
- A bounded (n=2) sanity check confirming that increasing timeout
  allows these specific samples to complete

## Safety Boundary

- Real API calls: 2 (exactly as authorized)
- Retry: 0
- Repair call: 0
- Batch: 0
- Raw response saved: no
- `.env` read: no (LLMConfig.from_env() only, no direct file read)
- R12.1 outputs modified: no
- R12.1 pilot rerun: no
- Benchmark claim: no
- Method-validation claim: no

## Files

| File | Created/Modified |
|------|-----------------|
| `outputs/r12_3_1_timeout_sanity/selected_samples.jsonl` | NEW |
| `outputs/r12_3_1_timeout_sanity/results.jsonl` | NEW |
| `outputs/r12_3_1_timeout_sanity/summary.json` | NEW |
| `docs/r12_3_1_timeout_sanity_report.md` | NEW |

## Next Step

Codex audit R12.3.1.  If accepted, R12 is complete.
