# R13.4.2 Real Mini-Pilot Report — Authorized Bounded Execution

**Date:** 2026-01-23
**Stage:** R13.4.2 (Authorized Real API Mini-Pilot)
**Commit:** (to be committed)
**Authorized by:** User ("我授权 R13.4.2 执行一次有界真实 API mini-pilot...")
**Status:** ✅ COMPLETE — 8/8 schema-valid, all safety constraints observed

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

Return to Codex for **R13.4.2 local-only audit.** The audit will:
1. Verify all safety constraints were observed.
2. Review per-sample prediction quality against gold.
3. Confirm no raw responses were saved.
4. Confirm no benchmark/method-validation/Sun-reproduction claims.
5. Assess whether the pipeline is ready for a larger formal evaluation.

After audit, proceed to R13.5 (formal evaluation planning) or R14 (scaling to the full reviewed-gold set).
