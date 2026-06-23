# R15.0 vs R14.4 — Presentation Summary

## Slide 1: Title

- R15.0: Sun-style Rule-Template Baseline
- Comparison with R14.4 Rule+LLM

## Slide 2: What is R15.0?

- Rule-template extraction following Sun et al. (2024) method structure
- Uses modality classifier, domain marker lexicon, syntactic rules
- Includes BPMN process semantic parser and violation detector
- NO LLM, NO API, NO external downloads
- NOT an exact Sun reproduction (datasets/model unavailable)

## Slide 3: Key Numbers

- R15.0 Overall Field Exact Accuracy: 0.1667
- R14.4 Overall Field Exact Accuracy: 0.513
- R15.0 Strict F1: 0.2235
- R14.4 Strict F1: 0.5221
- R15.0 Macro Strict F1: 0.2268
- R14.4 Macro Strict F1: 0.5774

## Slide 4: Method Structural Comparison

R15.0 (Sun-style):
- Modality classification (obligation/prohibition/permission/definition)
- Domain marker lexicon (conditions, constraints, exceptions, actors)
- Syntactic span-based extraction (surrogate for tree patterns)
- BPMN process semantics (import/parse BPMN 2.0 XML)
- Violation detection (missing action, incorrect actor, out-of-order)

R14.2 (Lightweight):
- Regex-based keyword extraction
- Simple token-based field assignment
- No marker lexicon
- No BPMN support
- No violation detection

R14.4 (Rule+LLM):
- Same rule extraction as R14.2
- Plus LLM for additional field extraction

## Slide 5: Important Limitations

- R15.0 is rule-only and does NOT outperform rule+LLM
- No original Sun trained BERT model available
- No original syntactic parser available (deterministic fallback)
- No full GDPR BPMN benchmark dataset
- Hand-crafted marker lexicon (not learned from data)
- NOT an exact reproduction of Sun et al. (2024)

## Slide 6: What R15.0 Achieves

- Corrects methodological risk identified in R14.2
- Provides structurally aligned rule-template baseline
- Enables honest comparison: 'our best approximation of Sun'
- Documents all gaps between our implementation and original method
- Ready for future enhancement if BERT/parser/datasets become available

## Slide 7: Key Takeaway

"R15 Sun-style rule-template baseline is more method-aligned than
R14.2 lightweight baseline. Still not exact Sun reproduction."
