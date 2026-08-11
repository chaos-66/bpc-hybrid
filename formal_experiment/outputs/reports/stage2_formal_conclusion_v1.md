# Stage 2 Formal Conclusion v1

- project date: 2026-08-11
- formal names: {'sun_rule_only': 'Rules-Only', 'direct_llm': 'Direct-LLM', 'sun_llm_fallback': 'Rules+LLM-Repair (comparison-only)'}
- reconstruction disclosure: paper-faithful independent reconstruction of the published Sun et al. (2024) Stage 2; NOT the authors' original implementation and NOT an exact reproduction
- data scale: 150 sentences (input v2 52a73aa1109970b6...)

## Conclusions (each references the formal report)
- Direct-LLM leads on action (coarse five-field F1) [{'sun_rule_only': 0.8927, 'direct_llm': 0.9437, 'sun_llm_fallback': 0.8945}] supported=True (stage2_formal_three_method_comparison_v1.json#methods.*.main_view_coarse_five_fields)
- Direct-LLM leads on condition (coarse five-field F1) [{'sun_rule_only': 0.7738, 'direct_llm': 0.838, 'sun_llm_fallback': 0.7774}] supported=True (stage2_formal_three_method_comparison_v1.json#methods.*.main_view_coarse_five_fields)
- Direct-LLM leads on constraint (coarse five-field F1) [{'sun_rule_only': 0.6182, 'direct_llm': 0.7427, 'sun_llm_fallback': 0.62}] supported=True (stage2_formal_three_method_comparison_v1.json#methods.*.main_view_coarse_five_fields)
- Direct-LLM leads on modality four-class label accuracy [{'sun_rule_only': 0.74, 'direct_llm': 0.8333, 'sun_llm_fallback': 0.82}] supported=True (stage2_formal_three_method_comparison_v1.json#methods.*.modality_labels.accuracy)
- Rules-Only leads on actor (coarse five-field F1) [{'sun_rule_only': 0.8203, 'direct_llm': 0.7579, 'sun_llm_fallback': 0.4296}] supported=True (stage2_formal_three_method_comparison_v1.json#methods.*.main_view_coarse_five_fields)
- Rules-Only leads on exception (coarse five-field F1) [{'sun_rule_only': 0.88, 'direct_llm': 0.7619, 'sun_llm_fallback': 0.88}] supported=True (stage2_formal_three_method_comparison_v1.json#methods.*.main_view_coarse_five_fields)
- Rules+LLM-Repair is net-negative as an overall scheme; kept as comparison-only and no longer optimized (2026-08-08 decision) [{'sun_rule_only': 0.8203, 'direct_llm': 0.7579, 'sun_llm_fallback': 0.4296}] supported=True (stage2_formal_three_method_comparison_v1.json#conclusions.h1_net_negative_stop_optimizing)

## Per-method summary
- Rules-Only (sun_rule_only): coarse five-field mean F1 0.797 | modality label acc 0.74
- Direct-LLM (direct_llm): coarse five-field mean F1 0.8088 | modality label acc 0.8333333333333334
- Rules+LLM-Repair (sun_llm_fallback): coarse five-field mean F1 0.7203 | modality label acc 0.82

## Disclosures
- historical_llm_calls: 300
- new_llm_api_calls: 0
- no_statistical_significance_inference: field differences are descriptive; no significance tests were run and none are claimed
- modality_evidence_span_metrics: unavailable (never zeroed/aggregated)
- historical_six_field_aggregate: development provenance only; NOT cited as formal conclusion

## Task status
- B0-R5: verified (paper conclusion formed; method-level independent reconstruction; result may be positive or negative and is reported descriptively)
- D1-R5: verified (paper conclusion formed; method-level independent reconstruction; disclosures recorded)
- H1: comparison-only conclusion (2026-08-08 decision; stop optimizing)
- not downgraded: the three-method formal comparison remains formal; S2.11/S2.13 incompleteness does not demote it to candidate
