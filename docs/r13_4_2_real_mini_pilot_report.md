# R13.4.2 Real Mini-Pilot Report — Authorized Bounded Execution

**Date:** 2026-06-22
**Stage:** R13.4.2 (Authorized Real API Mini-Pilot)
**Commit:** 173d9c0
**Authorized by:** User ("我授权 R13.4.2 执行一次有界真实 API mini-pilot...")
**Status:** ✅ COMPLETE — 8/8 schema-valid, all safety constraints observed
**Post-run:** Pending Codex local-only audit (R13.4.2.1 checkpoint committed)

---

## 1. Stage Result

| Metric | Value |
|---|---|
| Samples processed | 8 |
| Real API calls attempted | 8 |
| Schema-valid predictions | 8 (100%) |
| Schema-invalid / errors | 0 |
| Raw responses saved | 0 (none) |
| Retry calls | 0 (none) |
| Batch calls | 0 (none) |
| Repair calls | 0 (none) |
| Total elapsed | 208.1 s |
| Avg per sample | ~26.0 s |

**Outcome:** All 8 gold-reviewed samples processed via real API (openai_compatible, qwen3.7-max). All returned schema-valid structured predictions. No errors, no timeouts, no CONFIG_BLOCKED.

---

## 2. User Authorization

User explicitly authorized this run on **2026-01-23**:

> "我授权 R13.4.2 执行一次有界真实 API mini-pilot，最多 8 次调用，每条样本最多一次，不重试，不 repair call，不 batch，不保存 raw response，不做 benchmark、方法验证或 Sun 复现声明。"

All constraints were observed. The `--execute-real-api` flag was required; the script rejects execution without it.

---

## 3. Scope

- **Samples:** 8 reviewed mini-gold samples from R13.3.1
- **Gold distribution:** obligation=4, prohibition=1, definition=3
- **Sources:** gdpr_eurlex=5, austrian_income_tax_code=3
- **API:** openai_compatible via `LLMConfig.from_env()`
- **Model:** qwen3.7-max
- **Not a benchmark.** Not method validation. Not Sun reproduction.

---

## 4. Input Samples

| sample_id | source_id | text (truncated) | gold_modality |
|---|---|---|---|
| r13_3_candidate_001 | gdpr_eurlex | Personal data shall be processed lawfully... | obligation |
| r13_3_candidate_002 | gdpr_eurlex | Personal data shall be collected for specified... | obligation |
| r13_3_candidate_003 | gdpr_eurlex | Personal data shall be adequate, relevant... | obligation |
| r13_3_candidate_004 | gdpr_eurlex | Where processing is based on consent... | obligation |
| r13_3_candidate_005 | gdpr_eurlex | Processing of personal data revealing racial... | prohibition |
| r13_3_candidate_006 | austrian_income_tax_code | Natürliche Personen... | definition |
| r13_3_candidate_007 | austrian_income_tax_code | Unbeschränkt steuerpflichtig... | definition |
| r13_3_candidate_008 | austrian_income_tax_code | Beschränkt steuerpflichtig... | definition |

---

## 5. Runtime Safety

- `BPC_HYBRID_DISABLE_PROJECT_ENV=0` (`.env` loaded)
- `--execute-real-api` flag present
- `--max-calls 8` (max enforced)
- API key in `Authorization` header only; never echoed, logged, or written to disk
- No raw responses saved (only structured predictions)
- Sequential execution, no concurrency
- 1 attempt per sample, no retry

---

## 6. API Call Summary

| sample_id | duration_ms | schema_valid | error_category |
|---|---|---|---|
| r13_3_candidate_001 | 20525.18 | true | — |
| r13_3_candidate_002 | 27696.58 | true | — |
| r13_3_candidate_003 | 26484.98 | true | — |
| r13_3_candidate_004 | 21384.60 | true | — |
| r13_3_candidate_005 | 27692.03 | true | — |
| r13_3_candidate_006 | 28442.69 | true | — |
| r13_3_candidate_007 | 29636.29 | true | — |
| r13_3_candidate_008 | 26197.76 | true | — |

No API errors, no timeouts, no transport failures.

---

## 7. Prediction Output

Stored in `data/formal/predictions/r13_4_2_real_predictions.jsonl`.

All 8 predictions are schema-valid. Each record contains:
- `sample_id`, `source_id`, `schema_valid: true`
- `predicted`: { modality, actor, action, condition, constraint, exception }
- `runtime`: { provider, model, real_api_call_performed, raw_response_saved, attempt_count, duration_ms, error_category }

---

## 8. Evaluation Summary

Stored in `data/formal/results/r13_4_2_real_evaluation_summary.json` and `data/formal/results/r13_4_2_real_evaluation_details.jsonl`.

| Field | Exact | Partial | Missing | Wrong | N/A |
|---|---|---|---|---|---|
| **modality** | 7 | 0 | 0 | 1 | 0 |
| **actor** | 0 | 1 | 4 | 3 | 0 |
| **action** | 0 | 0 | 0 | 8 | 0 |
| **condition** | 1 | 0 | 2 | 3 | 2 |
| **constraint** | 0 | 3 | 1 | 4 | 0 |
| **exception** | 0 | 0 | 0 | 0 | 8 |

**Modality accuracy:** 7/8 (87.5%). The single error is on sample r13_3_candidate_007 (predicted "definition", gold was "obligation" for the unbeschränkte Steuerpflicht clause).

**Key observation:** Actor and action fields show the most divergence from gold — the model tends to produce null actor for passive constructions and generates rephrased actions. Constraint extraction shows 3 partial matches.

---

## 9. Failure Cases

No API failures. The only schema-valid prediction with wrong modality was r13_3_candidate_007 — this is an Austrian tax code definition clause; the model classified it as "obligation" rather than "definition".

---

## 10. Claim Boundary (CRITICAL)

- **This is NOT a benchmark.** No benchmark claims are made.
- **This is NOT method validation.** 8 samples are insufficient for statistical validation.
- **This is NOT Sun reproduction.** Original Sun et al. dataset is not involved.
- **This is an internal mini-pilot** to verify that the real API transport, prompt engineering, and evaluation pipeline function correctly with 8 reviewed mini-gold samples.
- **No accuracy claims** beyond the descriptive counts in Section 8.
- **No cross-dataset generalization claims.**

---

## 11. Limitations

- **8 samples only** — insufficient for any statistical conclusion about the model, prompt, or task.
- **Single model** (qwen3.7-max) — no model comparison intended or performed.
- **Single pass** — no prompt engineering iteration, no few-shot examples.
- **Actor/action fields** show systematic divergence from gold — the extraction prompt may need refinement to better capture agentive structures in passive legal language.
- **Exception field** — all gold exceptions are null, so the "N/A" count is expected.

---

## 12. Next Step

**Pending Codex local-only audit** before any conclusion is drawn from the real mini-pilot.

Return to Codex for **R13.4.2 local-only audit.** The audit will:
1. Verify all safety constraints were observed.
2. Review per-sample prediction quality against gold.
3. Confirm no raw responses were saved.
4. Confirm no benchmark/method-validation/Sun-reproduction claims.
5. Assess whether the pipeline is ready for a larger formal evaluation.

After audit, proceed to R13.5 (formal evaluation planning) or R14 (scaling to the full reviewed-gold set).

---

## 13. R13.4.2.1 Post-run Checkpoint

This report was updated in R13.4.2.1 to align metadata, authorization state,
and documentation after the R13.4.2 real mini-pilot execution.

- No real API call in R13.4.2.1.
- No raw response saved.
- No retry, no repair, no batch.
- 8-sample mini-pilot only — not benchmark, not method validation, not Sun reproduction.

---

## 14. R13.4.2.2 — Codex Audit Blocker Fixes

**Date:** 2026-01-23
**Commit:** (this commit)

Three Codex audit blockers resolved:

### Blocker 1: Wrong summary metadata (stage/claim_boundary)

**Problem:** `r13_4_2_real_evaluation_summary.json` showed `"stage": "R13.4.1"`
and a mock `claim_boundary` string.

**Fix:**
- `evaluate_predictions()` in `src/bpc_hybrid/mini_pilot_evaluator.py` now
  accepts optional `stage` and `claim_boundary` parameters (defaults preserved
  for backward compat).
- `scripts/evaluate_mini_pilot_predictions.py` now accepts `--stage` and
  `--claim-boundary` CLI arguments.
- Summary re-generated with `--stage R13.4.2` and correct claim_boundary.

### Blocker 2: Runner had no authorization gate

**Problem:** `scripts/run_r13_4_2_real_mini_pilot.py` could be re-executed with
`--execute-real-api` even though authorization was consumed (both contract and
checklist have `real_api_call_allowed_now: false` / `authorized_now: false`).

**Fix:**
- Added `_check_authorization_gate()` function that reads both
  `execution_contract.json` and `authorization_checklist.json` and validates
  ALL conditions before loading `LLMConfig.from_env()` or making any API call.
- Added `--execution-contract` and `--authorization-checklist` CLI args with
  sensible defaults.
- Gate checks: `real_api_call_allowed_now`, `authorized_now`,
  `max_real_api_calls`, `retry_allowed`, `repair_call_allowed`,
  `batch_allowed`, `raw_response_saved`, `benchmark`, `method_validation`,
  `sun_reproduction`, fresh re-authorization requirements.
- No bypass flags exist.

### Blocker 3: No regression tests for authorization gates

**Problem:** Zero tests covering runner authorization enforcement.

**Fix:**
- Created `tests/test_r13_4_2_real_mini_pilot_safety.py` with 15 tests:
  closed-gate contract+checklist, contract-only closed, checklist-only closed,
  max-calls>8, missing --execute-real-api, candidate count>8, sample_id
  mismatch, non-reviewed_gold, duplicate IDs, no bypass flag, retry_allowed
  violation, benchmark violation, raw_response_saved violation, missing
  contract file, missing checklist file.
- All tests subprocess only — no network, no .env read, no real API.

### Verification
- Full pytest: 674 passed (44 evaluator + 15 safety + 615 others)
- Evaluator re-run with correct stage → summary fixed
- All 3 blockers resolved; ready for Codex re-audit

### Status
✅ R13.4.2.2 — All 3 Codex audit blockers fixed. Proceed to Codex R13.4.2.2
local-only re-audit.
