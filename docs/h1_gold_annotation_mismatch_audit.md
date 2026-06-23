# H1-E — Gold Annotation Mismatch Audit

**Audit ID**: H1-GOLD  
**Commit**: d7f83ff  
**Audit timestamp**: 2026-06-23T21:00:00Z  

---

## 1. Mismatch Summary

| Metric | Value |
|--------|-------|
| Total samples | 50 |
| Exact matches | 0 |
| Mismatched | 50 |

---

## 2. Mismatch Classification

| Classification | Count | Description |
|----------------|-------|-------------|
| pred_too_verbose | 44 | Predictions contain much more text than gold values |
| semantic_mismatch | 3 | Predictions and gold disagree on meaning |
| mixed_errors | 2 | Combination of verbose and wrong fields |
| partial_match_or_format_diff | 1 | Close match but format or minor text difference |

---

## 3. Root Cause Analysis

### 3.1 Gold annotations are precise

Gold annotations provide **concise, exact field values** — e.g.:
- `actor`: `"data subject"` 
- `action`: `"carried out only under the control of official authority"`
- `condition`: null (when no condition applies)

### 3.2 Predictions are verbose

The rule-based extraction engine captures **full sentence fragments** instead of precise semantic values — e.g.:
- `actor`: `"Article 10 Processing"` (wrong — article heading captured instead of actor)
- `condition`: entire sentence repeated (wrong — no extraction performed)
- `constraint`: `"only under the control of official authority or when the processing is authorised by Union or Member State law..."` (too long — should be just `"only under the control of official authority"`)

### 3.3 Extraction engine limitations

The keyword-based rule engine:
1. **Does not distinguish actors from article headings** — captures "Article 10 Processing" as actor
2. **Falls back to full-sentence for missing fields** — when no pattern matches, the entire sentence is used
3. **Does not perform clause-level segmentation** — fails to split compound sentences
4. **Misses null annotations** — where gold says null, predictions provide text

---

## 4. Impact on Metrics

This mismatch pattern explains the low strict F1 (0.27) and higher lenient F1 (0.45):
- **Strict**: exact string match fails when predictions are verbose
- **Lenient**: partial overlap exists when predictions contain the gold text as substring

---

## 5. Recommendations

1. **Post-processing**: Add truncation/normalization to extract first clause only
2. **Null detection**: Add explicit null-value detection rules
3. **Actor extraction**: Use NER-based approach instead of keyword matching
4. **Sentence segmentation**: Pre-segment compound sentences before extraction

---

## 6. Verdict

**PASS_WITH_WARNINGS**

All 50 samples show mismatches, primarily due to prediction verbosity. This is an extraction quality issue, not a data integrity issue. The gold annotations are correct; the extraction engine needs improvement.
