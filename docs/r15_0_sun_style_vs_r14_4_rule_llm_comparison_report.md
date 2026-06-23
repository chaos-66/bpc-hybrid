# R15.0 Sun-style Rule-Template vs R14.4 Rule+LLM Comparison Report

**Generated**: 2026-06-23T09:27:41.797559+00:00

## Methods Compared

- **R15.0**: `sun_style_rule_template` (no LLM, no API, no external downloads)
- **R14.4**: `rule_plus_llm` (rule extraction + LLM for additional fields)

## Key Claim

R15.0 Sun-style rule-template baseline is structurally more aligned with Sun et al. (2024) method than R14.2 lightweight rule-only baseline.  R15.0 does NOT outperform R14.4 (rule+LLM) on numeric metrics because R15.0 uses no LLM.  Still, R15.0 is NOT an exact Sun reproduction — the original datasets, trained BERT model, full marker lexicon, and original BPMN benchmark are unavailable.

## Overall Metrics

| Metric | R15.0 | R14.4 | Delta (R15-R14) |
|--------|-------|-------|------------------|
| overall_field_exact_accuracy | 0.1667 | 0.513 | -0.3463 |
| strict_f1 | 0.2235 | 0.5221 | -0.2986 |
| macro_strict_f1 | 0.2268 | 0.5774 | -0.3506 |
| lenient_partial_f1 | 0.2824 | 0.8142 | -0.5318 |
| macro_lenient_f1 | 0.2959 | 0.8405 | -0.5446 |

## Field-Level Comparison

| Field | R15 Strict F1 | R14.4 Strict F1 | Delta |
|-------|--------------|-----------------|-------|
| action | 0.0 | 0.4167 | -0.4167 |
| actor | 0.0513 | 0.7391 | -0.6878 |
| condition | 0.0 | 0.2667 | -0.2667 |
| constraint | 0.0 | 0.1667 | -0.1667 |
| exception | 0.5 | 1.0 | -0.5 |
| modality | 0.8095 | 0.875 | -0.0655 |

## Important Context

- R15.0 is **rule-only** — NO LLM/API calls.
- R14.4 is **rule+LLM** — uses LLM for additional field extraction.
- R15.0 uses **Sun-style method structure** (modality classifier,
  domain marker lexicon, syntactic rules, BPMN/violation scaffold).
- R14.2 lightweight baseline did NOT use Sun-style method structure.
- R15.0 does NOT constitute exact Sun reproduction.
- The original Sun et al. datasets, trained BERT model, full marker
  lexicon, and original BPMN evaluation benchmark are UNAVAILABLE.

## Conclusion

R15.0 provides a **method-aligned but not equivalent** rule-template
baseline.  It is structurally closer to Sun et al. (2024) than the
R14.2 lightweight baseline.  However, it still does not match the
original Sun et al. numbers due to:

1. No original trained BERT model
2. No original syntactic parsing infrastructure
3. No full GDPR BPMN benchmark dataset
4. Deterministic fallback marker lexicon (hand-crafted, not learned)

This establishes the correct baseline for any future LLM-free
Sun-style comparison.
