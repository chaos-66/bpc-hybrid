# S2.12 Formal Descriptive Error Analysis v1 (retrospective/exploratory)

- retrospective: True | preregistered: False
- note: stratification/analysis formed AFTER seeing the results; explicitly retrospective/exploratory, NOT preregistered; S2.12 full DoD remains blocked on S2.11 (complex legal corpus + G0.5)

## Methodology
- error_taxonomy: per-field ground_truth/extracted/matched/misclassified/missed (Sun literal-overlap contract)
- denominator: same formal input v2 (150 records) and same published Gold views for all methods
- input_set: estg150_formal_inference_input_v2.json (150)
- view: coarse five span fields (main) + separate modality labels
- modality_evidence_span: unavailable (never zeroed/aggregated)

### Rules-Only (sun_rule_only)
- actor: gt=41 ext=65 matched_ap=40 misclass_ap=19 missed_ap=1
- action: gt=150 ext=244 matched_ap=137 misclass_ap=31 missed_ap=13
- condition: gt=122 ext=239 matched_ap=105 misclass_ap=71 missed_ap=17
- constraint: gt=135 ext=330 matched_ap=93 misclass_ap=145 missed_ap=42
- exception: gt=11 ext=14 matched_ap=11 misclass_ap=3 missed_ap=0
- modality label acc: 0.74

### Direct-LLM (direct_llm)
- actor: gt=41 ext=60 matched_ap=36 misclass_ap=20 missed_ap=5
- action: gt=150 ext=210 matched_ap=137 misclass_ap=5 missed_ap=13
- condition: gt=122 ext=135 matched_ap=94 misclass_ap=11 missed_ap=28
- constraint: gt=135 ext=175 matched_ap=96 misclass_ap=39 missed_ap=39
- exception: gt=11 ext=10 matched_ap=8 misclass_ap=2 missed_ap=3
- modality label acc: 0.8333333333333334

### Rules+LLM-Repair (sun_llm_fallback)
- actor: gt=41 ext=167 matched_ap=40 misclass_ap=121 missed_ap=1
- action: gt=150 ext=247 matched_ap=138 misclass_ap=32 missed_ap=12
- condition: gt=122 ext=237 matched_ap=105 misclass_ap=69 missed_ap=17
- constraint: gt=135 ext=330 matched_ap=93 misclass_ap=144 missed_ap=42
- exception: gt=11 ext=14 matched_ap=11 misclass_ap=3 missed_ap=0
- modality label acc: 0.82

## Complementarity
- actor: missed_ap {'sun_rule_only': 1, 'direct_llm': 5, 'sun_llm_fallback': 1} | lowest sun_rule_only | highest direct_llm
- action: missed_ap {'sun_rule_only': 13, 'direct_llm': 13, 'sun_llm_fallback': 12} | lowest sun_llm_fallback | highest sun_rule_only
- condition: missed_ap {'sun_rule_only': 17, 'direct_llm': 28, 'sun_llm_fallback': 17} | lowest sun_rule_only | highest direct_llm
- constraint: missed_ap {'sun_rule_only': 42, 'direct_llm': 39, 'sun_llm_fallback': 42} | lowest direct_llm | highest sun_rule_only
- exception: missed_ap {'sun_rule_only': 0, 'direct_llm': 3, 'sun_llm_fallback': 0} | lowest sun_rule_only | highest direct_llm

## Weakest field per method
- {'sun_rule_only': 'constraint', 'direct_llm': 'constraint', 'sun_llm_fallback': 'constraint'}

## Observations
- constraint is the weakest field for Rules-Only (lowest recall) and among the weakest for the other methods
- Direct-LLM has the highest recall on action/condition/constraint; Rules-Only has the highest recall on actor (approx missed counts derived from recall)
- Rules+LLM-Repair consistently underperforms its own Rules-Only base on actor (net-negative), matching the 2026-08-08 stop-optimizing decision
- all three methods share the modality evidence-span limitation (structural, from the published Gold)
- misclassified vs missed trade-off differs per method per field (see complementarity)

## Dependency
- S2.11 (complex legal corpus freeze + G0.5 complexity rules frozen before results) + Barrientos adapter
