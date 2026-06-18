# R12.2 API Error / Timeout Strategy

## 1. Current Status

```
R12_2_STATUS: PASSED (analysis only)
```

R12.2 analyzes the R12.1 timeout/API-error pattern and plans a bounded
next-step strategy.  R12.2 does NOT execute real API calls, does NOT
rerun the pilot, and does NOT modify R12.1 outputs.

## 2. R12.1 Result Summary

| Metric | Value |
|--------|-------|
| dataset_type | `synthetic_prototype` |
| sample_count | 14 |
| attempted_call_count_total | 14 |
| successful_call_count_total | 4 |
| schema_valid_count | 4 |
| schema_invalid_count | 0 |
| api_error_count | 10 |
| config_blocked_count | 0 |
| raw_response_saved | false |
| batch | false |
| retry | false |
| repair_call | false |
| pilot duration | ~6 min 4 sec |
| per-call avg | ~26.0 sec |

## 3. Successful Samples (4/14)

| source_id | Sentence | Len | Words | Modality | Features |
|-----------|----------|-----|-------|----------|----------|
| d03 | A service provider must retain the log. | 39 | 7 | must | simple |
| d04 | A user shall not disclose the token. | 36 | 7 | shall not | simple |
| d07 | A controller may disclose the record only if authorized. | 56 | 9 | may | condition |
| d34 | The provider warrants that the service is available. | 52 | 8 | null | simple |

Observations:
- All 4 are single-clause sentences.
- Lengths range from 36 to 56 chars — not consistently short.
- One has a condition (d07), one has null modality (d34).
- No obvious common property among successes.

## 4. API Error Samples (10/14)

| source_id | Sentence | Len | Words | Category (from `r12_pilot_plan.md`) |
|-----------|----------|-----|-------|--------------------------------------|
| d01 | A controller shall record the decision. | 39 | 6 | Simple single-clause |
| d02 | A reviewer may inspect the file. | 32 | 6 | Simple single-clause |
| d05 | Unless approved, a controller shall record the decision. | 56 | 8 | With condition |
| d06 | A reviewer may inspect the file and must not alter the record. | 62 | 12 | Multi-clause (2) |
| d08 | A controller shall respond within 30 days. | 42 | 7 | With constraint |
| d12 | The request shall be reviewed by the controller. | 48 | 8 | Passive voice |
| d13 | A reviewer may inspect the file and shall record the decision. | 62 | 11 | Multi-clause (2) |
| d27 | A violation results in a penalty. | 33 | 6 | No modality (hard) |
| d28 | No person shall alter the record unless an exception applies. | 61 | 10 | With exception |
| d35 | Unless authorized, no person shall disclose the record. | 55 | 8 | With condition |

**All 10 errors are `socket.timeout`** — each reported as:
`"LLM transport error: Real API timeout (details redacted)"`.

## 5. Error Pattern Analysis

### 5.1 Length Comparison

| Group | Count | Avg Len (chars) | Min | Max |
|-------|-------|-----------------|-----|-----|
| Success | 4 | 45.8 | 36 | 56 |
| Failure | 10 | 49.0 | 32 | 62 |

The length difference is negligible (45.8 vs 49.0).  The **shortest**
sentence (d02, 32 chars) failed.  The **joint longest** (d07, 56 chars)
succeeded.  There is **no clear length cutoff**.

### 5.2 Complexity Comparison

| Category | Success | Failure |
|----------|---------|---------|
| Simple single-clause | d03, d04 | d01, d02 |
| With condition | d07 | d05, d35 |
| With constraint | — | d08 |
| Multi-clause | — | d06, d13 |
| Passive voice | — | d12 |
| No modality (hard) | d34 | d27 |
| With exception | — | d28 |

- d01 and d02 are simple single-clause (same category as d03, d04) but failed.
- d27 (no modality, hard) failed, but d34 (also no modality, hard) succeeded.
- Multi-clause sentences (d06, d13) all failed, but sample size is too small
  to conclude a complexity effect.

### 5.3 Per-call Timing

Pilot duration: `04:12:20 → 04:18:24` UTC = ~6 min 4 sec (364 sec).
Per-call average: 364 / 14 ≈ **26.0 sec**.

Given that each timeout waits for the full `timeout_seconds` (30s default),
10×30s = 300s of waiting.  The remaining 64s covers 4 successful calls
(~16s each on average) plus overhead.

**Key insight**: The fail cases are all full-30s timeouts, not fast failures.
This suggests the API endpoint is intermittently unresponsive — some calls
complete under the timeout, some never complete.

### 5.4 Hypothesis

**Intermittent endpoint latency > 30s timeout**.  The API endpoint
(`qwen3.7-max` via `openai_compatible`) appears to have high latency
variability.  When a response arrives within 30s, it schema-validates;
when it doesn't, `socket.timeout` fires after 30s.  The current default
timeout of 30s may be too tight for this endpoint under certain load
conditions.

## 6. Current Timeout / Transport Behavior

### 6.1 Timeout Configuration

| Source | Variable | Default |
|--------|----------|---------|
| `.env` key | `BPC_HYBRID_LLM_TIMEOUT_SECONDS` | `30.0` |
| `LLMConfig.from_env()` | reads env var → `timeout_seconds` | `30.0` |
| `run_single_call()` | `RealAPITransport(config, timeout_seconds=config.timeout_seconds)` | passes through |
| `RealAPITransport.send()` | `urllib.request.urlopen(http_req, timeout=self._timeout)` | socket timeout |

The timeout is a **single value**: it applies to both TCP connect and
read (Python `urllib` timeout covers connection + first byte + read).

### 6.2 Error Classification (already implemented)

`RealAPITransport.send()` distinguishes 5 error types:

| Exception | Message |
|-----------|---------|
| `socket.timeout` | `Real API timeout (details redacted)` |
| `urllib.error.HTTPError` | `Real API HTTP status error (details redacted)` |
| `ssl.SSLError` | `Real API SSL error (details redacted)` |
| `urllib.error.URLError` | `Real API DNS/connection error (details redacted)` |
| `OSError` | `Real API network error (details redacted)` |
| Other `Exception` | `Real API unexpected error (details redacted)` |

All R12.1 failures are `socket.timeout` — the classification works.

### 6.3 Gaps

1. **No per-sample duration tracking** — the pilot runner does not record
   how long each call took (only aggregate start/end).
2. **No `connect_timeout` vs `read_timeout` separation** — Python's
   `urllib` timeout is a single value; cannot distinguish "server
   unreachable" from "server slow to generate response".
3. **No per-sample timeout configuration** — all 14 samples use the same
   `BPC_HYBRID_LLM_TIMEOUT_SECONDS` value.

## 7. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Increasing timeout may hit endpoint rate limits | Medium | R12.3 uses only 2 samples |
| Timeout not configurable per-endpoint | Low | Already configurable via `.env` |
| Longer timeout exposes API key longer in memory | Low | Already redacted, single-call, no raw storage |
| Same 30s timeout may be inherent to the endpoint | Medium | R12.3 is a controlled test, not full rerun |

## 8. R12.3 Candidate Strategies

### Option A: Increase timeout only (no code change)

- User changes `BPC_HYBRID_LLM_TIMEOUT_SECONDS=60` in `.env`
- Rerun 2 previously failed samples with `--execute-real-api`
- Code unchanged; pilot runner re-used as-is
- Risk: no per-sample duration data collected

### Option B: Add per-sample duration tracking + increase timeout

- **R12.3.0** (code/test only, no real API):
  - Add `duration_seconds` field to pilot runner per-sample metadata
  - Add `_TIMEOUT_SECONDS` override parameter to `run_pilot()`
  - Add tests for duration tracking
  - No real API call
- **R12.3.1** (real API, max 2 calls):
  - Run 2 previously failed samples (e.g., d01 + d06) with
    `BPC_HYBRID_LLM_TIMEOUT_SECONDS` increased to 60
  - Record per-sample durations in results.jsonl
  - If both succeed: recommend increasing timeout for future experiments
  - If still timeout: endpoint latency > 60s — investigate further

### Option C: Retry all 14 samples with increased timeout

- NOT recommended — too aggressive, 14 API calls without evidence
  that timeout increase will help.

## 9. Recommended Next Step

**Option B: R12.3 split into two safe sub-stages.**

### R12.3.0 — Add Per-Sample Duration Tracking (code/test only)

Scope:
- `scripts/run_synthetic_prototype_pilot.py`: add `duration_seconds` field
  to per-sample metadata; add `--timeout-seconds` CLI flag (default: from
  `LLMConfig.from_env()`)
- `tests/test_synthetic_prototype_pilot.py`: add tests for duration
  tracking
- No real API call
- No pilot rerun
- No `.env` modification

### R12.3.1 — 2-Sample Timeout Sanity Check (max 2 real API calls)

Scope:
- Select 2 previously failed samples: d01 (simple, 39 chars, failed)
  and d06 (multi-clause, 62 chars, failed)
- Run with `--execute-real-api --timeout-seconds 60 --max-samples 2`
- If both succeed: timeout hypothesis confirmed → recommend 60s for
  future experiments
- If one or both still timeout: endpoint latency > 60s → investigate
  before further experiments
- No retry, no repair, no batch, no raw response storage

### Safety guard for R12.3.1

| Constraint | Value |
|------------|-------|
| Max real API calls | 2 |
| Retry | 0 |
| Repair call | 0 |
| Raw response storage | 0 |
| Batch | false |
| Benchmark claim | false |
| Method-validation claim | false |

## 10. Claim Boundary

R12.2 is an analysis and planning phase.  R12.2 does not execute real
API calls.  R12.2 does not rerun the pilot.  R12.2 does not change
R12.1 outputs.  R12.2 is not a benchmark.  R12.2 is not method
validation.

R12.2 recommends a bounded R12.3 strategy: code-only changes first
(R12.3.0), then a 2-sample real API sanity check (R12.3.1).  R12.3.1
is conditional on R12.3.0 passing full pytest.
