# R15 GDPR-50 Three-Way Comparison Report

**Stage**: R15  
**Sample count**: 50  
**Comparison timestamp**: 2026-06-23T21:00:00Z  
**Honesty**: This is a local GDPR-50 study, not a benchmark. Results are not comparable to published work.

---

## 1. Results Summary

| Variant | Strict F1 | Lenient F1 | Exact Accuracy | Macro Strict F1 | LLM Used |
|---------|-----------|------------|----------------|-----------------|----------|
| Sun-style Rule-Only | 0.2706 | 0.4456 | 0.2464 | 0.1866 | No |
| spaCy-Enhanced | 0.2827 | 0.3787 | 0.2598 | 0.1924 | No |
| Rule+LLM (qwen3.7-max) | 0.2675 | 0.3779 | 0.2669 | 0.2132 | Yes (49 calls) |

---

## 2. Field Coverage (Rule+LLM)

| Field | Non-empty Count | Coverage |
|-------|----------------|----------|
| modality | 50 | 100% |
| actor | 49 | 98% |
| action | 50 | 100% |
| condition | 36 | 72% |
| constraint | 43 | 86% |
| exception | 7 | 14% |

---

## 3. Observations

1. **Strict F1 range**: 0.2675-0.2827 (all variants close)
2. **Lenient F1 range**: 0.3779-0.4456 (sun_style highest)
3. **Rule+LLM had higher non-empty field coverage** in this local GDPR-50 run
4. **All three variants have low F1** on this local dataset — not comparable to published benchmarks
5. **Exact accuracy**: 0.2464-0.2669 (all below 30%)

---

## 4. Assertions

| Assertion | Value |
|-----------|-------|
| benchmark | ❌ false |
| method_validation | ❌ false |
| sun_reproduction | ❌ false |
| llm_superiority_claim | ❌ false |

---

## 5. Recommended Claims

✅ **Can claim**:
- "Local GDPR-50 semantic extraction study"
- "Three-way comparison of rule-based, spaCy-enhanced, and rule+LLM approaches"
- "Rule+LLM showed higher non-empty field coverage in this local GDPR-50 run"

❌ **Cannot claim**:
- "Benchmark results"
- "Sun method validated"
- "Exact Sun reproduction"
- "LLM superiority"
- "Best method"
