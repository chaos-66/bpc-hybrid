# R14.5 Descriptive Comparison Report

**Date:** 2026-06-23  
**Stage:** R14.5  
**Type:** Descriptive comparison of already accepted bounded pilot outputs  
**Comparison:** `rule_only` (R14.2) vs `rule_plus_llm_assisted` (R14.4)

---

## 1. Scope

R14.5 compares the already accepted R14.2 rule-only baseline and R14.4 Rule+LLM-assisted pilot outputs on the same 24 draft mini-gold samples from R14.1.

This stage:

- Reads existing R14.2 and R14.4 evaluation summaries and per-sample details
- Computes descriptive metric deltas (R14.4 − R14.2)
- Reports observed descriptive differences
- Does **not** re-run any predictor, runner, or evaluator
- Does **not** call any API or LLM
- Does **not** recompute any metrics

---

## 2. Source Artifacts

| Artifact | Path | Stage |
|----------|------|-------|
| Rule-only evaluation summary | `data/formal/results/r14_2_rule_only_evaluation_summary.json` | R14.2 |
| Rule-only evaluation details | `data/formal/results/r14_2_rule_only_evaluation_details.jsonl` | R14.2 |
| Rule+LLM evaluation summary | `data/formal/results/r14_4_rule_plus_llm_evaluation_summary.json` | R14.4 |
| Rule+LLM evaluation details | `data/formal/results/r14_4_rule_plus_llm_evaluation_details.jsonl` | R14.4 |
| Mini-gold (reference) | `data/formal/r14_controlled/r14_1_mini_gold.jsonl` | R14.1 |
| Candidate samples (reference) | `data/formal/r14_controlled/r14_1_candidate_samples.jsonl` | R14.1 |

All source artifacts were produced in prior stages and accepted via Codex audit. None were modified in R14.5.

---

## 3. Comparison Method

The comparison script (`scripts/compare_r14_rule_only_vs_rule_plus_llm.py`) reads the existing evaluation summaries and computes descriptive deltas:

```
delta = R14.4_value − R14.2_value
```

The script calls NO API, NO LLM, NO predictor, NO evaluator, and NO runner. It only performs arithmetic on already-computed numbers.

---

## 4. Overall Metrics

| Metric | Rule-only (R14.2) | Rule+LLM (R14.4) | Descriptive Delta |
|---|---:|---:|---:|
| Overall field exact accuracy | 0.1491 | 0.513 | +0.3639 |
| Macro strict F1 | 0.1405 | 0.5774 | +0.4369 |
| Micro strict F1 | 0.2138 | 0.5221 | +0.3083 |
| Macro lenient F1 | 0.2212 | 0.8405 | +0.6193 |
| Micro lenient F1 | 0.3145 | 0.8142 | +0.4997 |

All five overall metrics show a positive observed delta in this bounded pilot. The largest observed descriptive differences are in macro lenient F1 (+0.6193) and macro strict F1 (+0.4369).

---

## 5. Field-level Metrics

| Field | Rule-only exact | Rule+LLM exact | Rule-only strict F1 | Rule+LLM strict F1 | Rule-only lenient F1 | Rule+LLM lenient F1 | Descriptive Delta (exact) | Descriptive Delta (strict F1) | Descriptive Delta (lenient F1) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| modality | 0.6667 | 0.875 | 0.7805 | 0.875 | 0.7805 | 0.875 | +0.2083 | +0.0945 | +0.0945 |
| actor | 0.0417 | 0.7083 | 0.0625 | 0.7391 | 0.375 | 0.8261 | +0.6666 | +0.6766 | +0.4511 |
| action | 0.0 | 0.4167 | 0.0 | 0.4167 | 0.0976 | 0.7917 | +0.4167 | +0.4167 | +0.6941 |
| condition | 0.0 | 0.25 | 0.0 | 0.2667 | 0.0 | 0.8 | +0.25 | +0.2667 | +0.8 |
| constraint | 0.0 | 0.1667 | 0.0 | 0.1667 | 0.0741 | 0.75 | +0.1667 | +0.1667 | +0.6759 |
| exception | 0.0 | 1.0 | 0.0 | 1.0 | 0.0 | 1.0 | +1.0 | +1.0 | +1.0 |

---

## 6. Observed Descriptive Differences

On the same 24 draft mini-gold samples, the following descriptive differences were observed:

- **Modality**: The rule-only baseline already had a reasonably high observed value (0.6667 exact accuracy). The Rule+LLM side showed a higher observed value (0.875). This is the smallest observed delta among all fields.

- **Actor**: The Rule+LLM side showed a substantially higher observed value in exact accuracy (0.7083 vs 0.0417) and strict F1 (0.7391 vs 0.0625). Actor identification was difficult for the rule-only baseline because rules alone struggled with semantic entity recognition.

- **Action**: The rule-only baseline produced zero exact matches and very low lenient F1 (0.0976). The Rule+LLM side showed a higher observed value across all metrics (exact 0.4167, lenient F1 0.7917). This is a semantic field where rule-based extraction was weakest.

- **Condition**: The rule-only baseline could not identify any condition values. The Rule+LLM side showed modest exact accuracy (0.25) but substantially higher lenient F1 (0.8), suggesting partial overlap with multi-word spans.

- **Constraint**: Similar to condition — rule-only baseline had zero exact matches and very low lenient F1 (0.0741). The Rule+LLM side showed observed improvement (exact 0.1667, lenient F1 0.75).

- **Exception**: Only 3 of 24 samples had gold exceptions. The rule-only baseline missed all three; the Rule+LLM side captured all three (exact accuracy 1.0). This is a very small n (3) so no generalization is implied.

**Key observation**: The largest observed descriptive differences are concentrated in semantic fields (actor, action, condition, constraint) where deterministic rule templates alone had the most difficulty. The surface-level field (modality) showed the smallest delta.

---

## 7. PPT-safe Summary

On the same 24 draft mini-gold samples, the deterministic rule-only baseline and the separately authorized Rule+LLM-assisted run showed different field-level extraction behavior. The Rule+LLM side showed higher observed values on several extraction metrics in this bounded pilot, especially on semantic fields that were difficult for rules alone. This is a descriptive small-scale observation, not a formal benchmark or proof of generalized LLM advantage.

---

## 8. Limitations

1. **Sample size**: Only 24 draft mini-gold samples. No statistical significance is claimed.
2. **Single LLM**: Only one LLM model (`qwen3.7-max`) was used; no multi-model comparison.
3. **Single prompt**: Only Prompt B (`r13_6_prompt_B`) was used.
4. **Draft gold labels**: The mini-gold was constructed as a draft, not independently verified by multiple annotators.
5. **No ablation**: The Rule+LLM side combined rules and LLM assistance; individual component contributions are not isolated.
6. **Not a benchmark**: This comparison is descriptive only. It does not constitute a formal benchmark result.
7. **Not method validation**: This comparison does not validate the hybrid method as performing well in general.
8. **Not Sun reproduction**: This is a different dataset, different metrics, and different scope from Sun et al.

---

## 9. Claim Boundary

R14.5 is a **descriptive comparison** of two already accepted bounded pilot outputs on the same 24 draft mini-gold samples.

**Allowed claims**:
- Descriptive small-scale observation
- Observed descriptive differences
- Field-level metric delta reporting
- PPT-safe summary for internal presentation

**Disallowed claims**:
- Benchmark conclusion
- Method validation
- Sun reproduction
- Proof of generalized LLM advantage over rules
- Production GDPR compliance claim
- Formal generalization claim

---

## 10. Next Stage Recommendation

Return to Codex for R14.5 local-only audit. Do not use R14.5 as a benchmark, method validation, or Sun reproduction.
