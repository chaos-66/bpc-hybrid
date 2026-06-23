# R14.4 Rule+LLM-assisted Real API Pilot Report

**Date:** 2025-12-18  
**Stage:** R14.4  
**Method:** `rule_plus_llm_assisted`  
**Prompt:** `r13_6_prompt_B` (few-shot extraction, SHA256=`d390ad51e...`)  
**LLM:** `openai_compatible` / `qwen3.7-max` (Alibaba MaaS)  
**Authorization:** Explicit user authorization for single bounded run with 24-sample draft mini-gold.

---

## 1. Execution Summary

| Metric | Value |
|--------|-------|
| Samples processed | 24 / 24 |
| API calls attempted | 24 |
| Schema-valid responses | 24 (100%) |
| Errors | 0 |
| Raw responses saved | None (as required) |
| Retries | 0 |
| Repair calls | 0 |
| Batch | No |
| Benchmark | No |
| Method validation | No |
| Sun reproduction | No |
| LLM superiority claim | No |

All 24 samples received schema-valid JSON responses from the LLM. No network errors, timeouts, or schema-invalid responses occurred.

---

## 2. Evaluation Results (Jaccard-based field-level)

| Metric | Value |
|--------|-------|
| **overall_field_exact_accuracy** | **0.513** |
| strict_f1 (micro) | 0.5221 |
| **macro_strict_f1** | **0.5774** |
| lenient_f1 (micro) | 0.8142 |
| **macro_lenient_f1** | **0.8405** |

### Per-Field Exact Accuracy

| Field | Exact Accuracy |
|-------|---------------|
| modality | 0.875 (21/24) |
| actor | 0.7083 (17/24) |
| action | 0.4167 (10/24) |
| condition | 0.2500 (4/16 applicable) |
| constraint | 0.1667 (4/24) |
| exception | 1.0000 (3/3 applicable) |

---

## 3. Context: R14.2 Rule-Only Baseline (for reference)

| Metric | R14.2 (Rule-Only) |
|--------|-------------------|
| overall_field_exact_accuracy | 0.1491 |
| macro_strict_f1 | 0.1405 |
| macro_lenient_f1 | 0.6173 |

**R14.4 does NOT make comparative claims vs R14.2.** R14.5 will present the descriptive comparison. This section is purely informational context.

---

## 4. Artifacts

| Artifact | Path |
|----------|------|
| Predictions | `data/formal/predictions/r14_4_rule_plus_llm_predictions.jsonl` |
| Evaluation Summary | `data/formal/evaluations/r14_4_rule_plus_llm_summary.json` |
| Evaluation Details | `data/formal/evaluations/r14_4_rule_plus_llm_details.jsonl` |
| Manifest | `data/formal/metadata/r14_4_manifest.json` |
| Runner Script | `scripts/run_r14_4_rule_plus_llm_real_pilot.py` |
| Safety Tests | `tests/test_r14_4_rule_plus_llm_safety.py` (15 test items, all passing) |
| Evaluator (modified) | `scripts/evaluate_r14_field_metrics.py` (added CLI boundary flags) |

---

## 5. Constraint Compliance

All constraints from R14.3 execution contract satisfied:
- ✅ max_api_calls = 24 (used exactly 24)
- ✅ one_attempt_per_sample = true
- ✅ retry_allowed = false
- ✅ repair_call_allowed = false
- ✅ batch_allowed = false
- ✅ raw_response_saved = false
- ✅ benchmark = false
- ✅ method_validation = false
- ✅ sun_reproduction = false
- ✅ llm_superiority_claim = false

---

## 6. Files Created / Modified

| File | Action |
|------|--------|
| `scripts/run_r14_4_rule_plus_llm_real_pilot.py` | Created |
| `scripts/evaluate_r14_field_metrics.py` | Modified (added CLI boundary flags) |
| `tests/test_r14_4_rule_plus_llm_safety.py` | Created (15 test items) |
| `data/formal/predictions/r14_4_rule_plus_llm_predictions.jsonl` | Created (24 records) |
| `data/formal/evaluations/r14_4_rule_plus_llm_summary.json` | Created |
| `data/formal/evaluations/r14_4_rule_plus_llm_details.jsonl` | Created (24 records) |
| `data/formal/metadata/r14_4_manifest.json` | Created |
| `data/formal/reports/r14_4_rule_plus_llm_real_pilot_report.md` | Created |

---

## 7. Conclusion

R14.4 successfully executed a bounded Rule+LLM-assisted real API pilot over 24 draft mini-gold samples using qwen3.7-max (Alibaba MaaS) with Prompt B. All 24 API calls returned schema-valid predictions. The overall field exact accuracy was 0.513, with macro_strict_f1 of 0.5774 and macro_lenient_f1 of 0.8405.

No comparative claims are made against the R14.2 rule-only baseline at this stage (deferred to R14.5).
