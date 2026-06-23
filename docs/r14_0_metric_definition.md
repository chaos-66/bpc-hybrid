# R14.0 Metric Definition — Field-level Evaluation Framework

## 1. Purpose

This document defines the evaluation metrics used in the R14 controlled
comparison (R14.2 Rule-only baseline vs R14.3 Rule+LLM-assisted). All metrics
are computed per-field against the combined 24-sample gold annotations in
`data/formal/gold/r14_combined_24_gold.jsonl`.

These definitions are consistent with the `FieldMetrics` class in
`src/bpc_hybrid/evaluator.py` and follow the same scoring taxonomy used in
R13.4.2, R13.7, and R13.8.

## 2. Field-level Score Taxonomy

For each field in each sample, the prediction receives exactly one of five
scores:

| Score | Definition | Example |
|-------|-----------|---------|
| **exact** | Predicted value matches gold value exactly after normalization (whitespace collapse, Unicode NFKC). For enum fields (modality), the label must match exactly. | Gold: `"obligation"`, Pred: `"obligation"` |
| **partial** | Predicted value shares substantial content with gold but is not an exact match. For text fields: token-overlap Jaccard >= 0.5 and < 1.0. For closed-set fields: not applicable (only exact/wrong). At exactly Jaccard = 0.5, the label is partial, not wrong. | Gold: `"the controller"`, Pred: `"controller"` (Jaccard = 0.5 → partial) |
| **missing** | Gold has a non-null value for this field, but prediction is `null` or empty string. | Gold: `"entity processing personal data"`, Pred: `null` |
| **wrong** | Predicted value is non-null but shares insufficient content with gold (token-overlap Jaccard < 0.5) or is semantically incorrect. | Gold: `"obligation"`, Pred: `"prohibition"` |
| **not_applicable (NA)** | Both gold and prediction have `null` for this field. The field is not relevant for this sample. | Gold: `null`, Pred: `null` |

## 3. Modality Scoring Rules

Modality is a closed-set enumeration: `obligation`, `prohibition`, `permission`,
`definition`.

- **exact**: Label matches gold exactly.
- **wrong**: Label differs from gold. Any non-matching label is wrong.
- **partial**: Not applicable for closed-set enums. Always treated as wrong.
- **missing**: Prediction is `null` but gold has a label.
- **NA**: Both null (should not occur for modality — every sentence has a modality).

## 4. Actor Scoring Rules

Actor is a free-text field normalized to English.

- **exact**: Full string match after normalization (whitespace collapse, Unicode
  NFKC, leading/trailing whitespace removal).
- **partial**: Case-insensitive token Jaccard similarity >= 0.5 AND < 1.0.
  At exactly Jaccard = 0.5, the label is partial, not wrong.
  Example: "the controller" vs "controller" → tokens {the,controller} ∩
  {controller} = 1, union = 2, Jaccard = 0.5 → partial.
- **missing**: Gold non-null, prediction null.
- **wrong**: Token Jaccard < 0.5 or semantically different entity.
- **NA**: Both null.

## 5. Action Scoring Rules

Action is a free-text field describing the action in English infinitive form.

- **exact**: Full string match after normalization.
- **partial**: Case-insensitive token Jaccard similarity >= 0.5 AND < 1.0.
  At exactly Jaccard = 0.5, the label is partial, not wrong.
  Example: "collect and further process personal data" vs "collect and process personal
  data" → tokens {collect,and,further,process,personal,data} ∩
  {collect,and,process,personal,data} = 5, union = 6, Jaccard ≈ 0.83 → partial.
- **missing**: Gold non-null, prediction null.
- **wrong**: Token Jaccard < 0.5.
- **NA**: Both null (should not occur — every clause has an action).

## 6. Condition Scoring Rules

Condition is a free-text field; may be null when no condition exists.

- **exact**: Both null, OR both non-null with full string match after
  normalization.
- **partial**: Both non-null, token Jaccard >= 0.5 AND < 1.0.
  At exactly Jaccard = 0.5, the label is partial, not wrong.
- **missing**: Gold non-null, prediction null.
- **wrong**: Both non-null, token Jaccard < 0.5. Also: gold null but prediction
  non-null (false positive condition).
- **NA**: Both null.

Note on false positives: If gold has `null` for condition but prediction
produces a non-null value, this is scored as `wrong` (not `NA`). The
not_applicable score is reserved for cases where both sides agree the field is
irrelevant.

## 7. Constraint Scoring Rules

Constraint is a free-text field capturing the normative content.

- **exact**: Full string match after normalization.
- **partial**: Token Jaccard >= 0.5 AND < 1.0.
  At exactly Jaccard = 0.5, the label is partial, not wrong.
- **missing**: Gold non-null, prediction null.
- **wrong**: Token Jaccard < 0.5, or gold null + prediction non-null.
- **NA**: Both null (should not occur — every clause has normative content).

## 8. Exception Scoring Rules

Exception is a free-text field; null when no exception exists.

- **exact**: Both null, OR both non-null with full string match after
  normalization.
- **partial**: Both non-null, token Jaccard >= 0.5 AND < 1.0.
  At exactly Jaccard = 0.5, the label is partial, not wrong.
- **missing**: Gold non-null, prediction null (false negative exception).
- **wrong**: Both non-null, token Jaccard < 0.5. Also: gold null but prediction
  non-null (false positive exception).
- **NA**: Both null (most common case — many clauses have no exception).

## 9. Aggregate Metrics

### 9.1 Strict Exact-F1 (Primary)

Computed per-field, then micro-averaged across all 6 fields × 24 samples.

For each field f:
- `exact_f = count(exact) for field f`
- `total_f = 24 − count(NA) for field f` (applicable samples only)
- `precision_f = exact_f / (exact_f + partial_f + wrong_f)`
- `recall_f = exact_f / total_f`
- `F1_f = 2 × precision_f × recall_f / (precision_f + recall_f)`

Micro-average across all fields:
- `exact_micro = sum(exact_f) over all f`
- `total_micro = sum(total_f) over all f`
- `precision_micro = exact_micro / (exact_micro + sum(partial_f) + sum(wrong_f))`
- `recall_micro = exact_micro / total_micro`
- **Strict exact-F1 =** `2 × precision_micro × recall_micro / (precision_micro + recall_micro)`

### 9.2 Lenient Partial-F1 (Secondary)

Same formula but treats both `exact` and `partial` as correct:

For each field f:
- `correct_f = count(exact) + count(partial) for field f`
- `precision_f = correct_f / (correct_f + count(wrong))`
- `recall_f = correct_f / total_f`
- `F1_f = 2 × precision_f × recall_f / (precision_f + recall_f)`

Micro-averaged across all fields to produce **lenient partial-F1**.

### 9.3 Field-level Accuracy

Simpler per-field metric:
- `accuracy_f = count(exact) for field f / total_f`
- Total applicable = 24 − count(NA) for that field

This is the proportion of applicable samples where the prediction matched gold
exactly. Used for per-field diagnostic comparisons.

### 9.4 Macro-F1

Average of per-field strict exact-F1:
- `macro_F1 = (1/6) × sum(F1_f over all 6 fields)`

This weights all fields equally regardless of how many samples have NA for a
given field. Complementary to micro-averaged metrics.

## 10. Comparison Framework

R14.4 will compare Rule-only vs Rule+LLM on:

| Metric | Comparison Type |
|--------|----------------|
| Strict exact-F1 (micro) | Direct difference: Rule+LLM − Rule-only |
| Lenient partial-F1 (micro) | Direct difference |
| Per-field accuracy (6 fields) | Side-by-side count table |
| Macro-F1 | Direct difference |
| Error category counts | Descriptive frequency comparison |

No statistical significance testing is performed. Results are reported as
observed count differences on this specific 24-sample set.

## 11. Implementation

The evaluation uses the existing `FieldMetrics` and `EvaluationReport` classes
in `src/bpc_hybrid/evaluator.py`. The scoring logic is already implemented and
tested (708 passing tests as of R13.9.1). No new evaluation code is needed for
R14.2/R14.3/R14.4.

## 12. Metric Boundary

- These metrics describe **field-level extraction behavior** on structured
  predictions vs structured gold annotations. They do not measure "legal
  correctness," "compliance validity," or "real-world utility."
- The evaluation is a string-matching exercise between two structured JSON
  representations. It is not a semantic evaluation and does not involve legal
  expert review of prediction quality.
- Strict exact-F1 is the primary metric by design: the project's rule-first
  architecture requires deterministic, reproducible extraction. Partial matches
  are diagnostically useful but do not satisfy the extraction contract.
