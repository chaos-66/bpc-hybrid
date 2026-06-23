# R15 GDPR-50 — PPT-Safe Result Table

**NOTE**: This table is H1-audited and claim-safe. All assertions verified.

---

## Variant Comparison

| Variant | Strict F1 | Lenient F1 | Exact Accuracy | Macro Strict F1 |
|---------|-----------|------------|----------------|-----------------|
| Rule-Only | 0.2706 | 0.4456 | 0.2464 | 0.1866 |
| spaCy-Enhanced | 0.2827 | 0.3787 | 0.2598 | 0.1924 |
| Rule+LLM | 0.2675 | 0.3779 | 0.2669 | 0.2132 |

---

## Field Coverage (Rule+LLM)

| Field | Coverage |
|-------|----------|
| modality | 100% (50/50) |
| actor | 98% (49/50) |
| action | 100% (50/50) |
| condition | 72% (36/50) |
| constraint | 86% (43/50) |
| exception | 14% (7/50) |

---

## PPT-Safe Claims

✅ "Local GDPR-50 semantic extraction study with 50 samples"  
✅ "Three-way comparison of rule-based, spaCy-enhanced, and rule+LLM approaches"  
✅ "Rule+LLM showed higher non-empty field coverage in this local GDPR-50 run"  
✅ "All variants had strict F1 below 0.29 on this local dataset"  

❌ DO NOT claim: "benchmark", "validated", "outperforms", "best method", "Sun reproduction"
