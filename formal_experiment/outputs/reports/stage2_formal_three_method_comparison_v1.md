# Formal Three-Method Stage 2 Comparison v1

- evaluation contract: sentence-level coarse FIVE span-bearing fields + separate four-class modality-label metrics
- modality evidence-span: unavailable (never zeroed, never aggregated)
- fine five fields: diagnostic / 对照
- historical six-field aggregate: development provenance only (NOT mixed in)

## Per-method main view (coarse five span fields, P/R/F1)
### Rules-Only (sun_rule_only, formal)
- actor: P 0.7076923076923077 / R 0.975609756097561 / F1 0.8203299152920196
- action: P 0.8729508196721312 / R 0.9133333333333333 / F1 0.8926856128973049
- condition: P 0.702928870292887 / R 0.860655737704918 / F1 0.7738369415016121
- constraint: P 0.5606060606060606 / R 0.6888888888888889 / F1 0.6181622204257612
- exception: P 0.7857142857142857 / R 1.0 / F1 0.88
- modality label accuracy: 0.74 | macro-F1: 0.712845542257307
  - obligation: P 0.7105263157894737 / R 0.9152542372881356 / F1 0.8
  - permission: P 0.8857142857142857 / R 0.7380952380952381 / F1 0.8051948051948051
  - prohibition: P 0.9285714285714286 / R 0.65 / F1 0.7647058823529412
  - definition: P 0.52 / R 0.4482758620689655 / F1 0.48148148148148145
- historical LLM calls: 0 | new calls: 0

### Direct-LLM (direct_llm, formal)
- actor: P 0.6666666666666666 / R 0.8780487804878049 / F1 0.7578947368421053
- action: P 0.9761904761904762 / R 0.9133333333333333 / F1 0.9437163978494625
- condition: P 0.9185185185185185 / R 0.7704918032786885 / F1 0.8380185491408441
- constraint: P 0.7771428571428571 / R 0.7111111111111111 / F1 0.7426621160409557
- exception: P 0.8 / R 0.7272727272727273 / F1 0.761904761904762
- modality label accuracy: 0.8333333333333334 | macro-F1: 0.7694506979014613
  - obligation: P 0.8656716417910447 / R 0.9830508474576272 / F1 0.9206349206349207
  - permission: P 0.9090909090909091 / R 0.9523809523809523 / F1 0.9302325581395349
  - prohibition: P 0.6538461538461539 / R 0.85 / F1 0.7391304347826088
  - definition: P 0.8333333333333334 / R 0.3448275862068966 / F1 0.4878048780487806
- historical LLM calls: 150 | new calls: 0

### Rules+LLM-Repair (sun_llm_fallback, formal)
- actor: P 0.2754491017964072 / R 0.975609756097561 / F1 0.42960541676395053
- action: P 0.8704453441295547 / R 0.92 / F1 0.8945369030390738
- condition: P 0.7088607594936709 / R 0.860655737704918 / F1 0.7774178621008793
- constraint: P 0.5636363636363636 / R 0.6888888888888889 / F1 0.6199999999999999
- exception: P 0.7857142857142857 / R 1.0 / F1 0.88
- modality label accuracy: 0.82 | macro-F1: 0.8123013565761656
  - obligation: P 0.7777777777777778 / R 0.9491525423728814 / F1 0.8549618320610687
  - permission: P 0.9428571428571428 / R 0.7857142857142857 / F1 0.8571428571428571
  - prohibition: P 1.0 / R 0.85 / F1 0.9189189189189189
  - definition: P 0.6538461538461539 / R 0.5862068965517241 / F1 0.6181818181818182
- historical LLM calls: 150 | new calls: 0

## Cross-method deltas (coarse five-field F1)
- sun_rule_only vs direct_llm: {'actor': 0.0624, 'action': -0.051, 'condition': -0.0642, 'constraint': -0.1245, 'exception': 0.1181}
- sun_rule_only vs sun_llm_fallback: {'actor': 0.3907, 'action': -0.0019, 'condition': -0.0036, 'constraint': -0.0018, 'exception': 0.0}
- direct_llm vs sun_rule_only: {'actor': -0.0624, 'action': 0.051, 'condition': 0.0642, 'constraint': 0.1245, 'exception': -0.1181}
- direct_llm vs sun_llm_fallback: {'actor': 0.3283, 'action': 0.0492, 'condition': 0.0606, 'constraint': 0.1227, 'exception': -0.1181}
- sun_llm_fallback vs sun_rule_only: {'actor': -0.3907, 'action': 0.0019, 'condition': 0.0036, 'constraint': 0.0018, 'exception': 0.0}
- sun_llm_fallback vs direct_llm: {'actor': -0.3283, 'action': -0.0492, 'condition': -0.0606, 'constraint': -0.1227, 'exception': 0.1181}

## Coarse five-field arithmetic mean F1 (descriptive)
- {'sun_rule_only': 0.797, 'direct_llm': 0.8088, 'sun_llm_fallback': 0.7203}

## Conclusions
- h1_net_negative_stop_optimizing: Rules+LLM-Repair (comparison-only) remains net-negative on the main coarse five-field view (esp. actor F1), consistent with the 2026-08-08 decision; no further optimization is intended
- d1_strength: Direct-LLM leads on action/condition/constraint coarse F1 with the highest modality-label accuracy; its actor extraction trails Rules-Only
- b0_strength: Rules-Only leads on actor and exception coarse F1 with higher recall; its constraint field is the weakest
- modality_label_separate: modality four-class label metrics are reported separately and must not be mixed into span metrics
- common_limitation: modality evidence-span metrics are unavailable for all three methods (published Gold stores modality as a plain string)
- three_method_ready_not_pipeline_complete: three-method formal comparison ready does NOT imply S2.13 / S1.7 / S3.7 completion

## Zero-API declaration
- new LLM/API calls: 0
- historical recorded calls: 300
