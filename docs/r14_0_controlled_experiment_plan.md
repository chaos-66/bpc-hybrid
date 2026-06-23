# R14.0 Controlled Experiment Plan — Rule-only vs Rule+LLM Comparison

## 1. Purpose

R14.0 designs a controlled mini-experiment that compares a **Rule-only baseline**
against a **Rule+LLM-assisted** extraction path on the same set of 24 manually
annotated legal-text samples. This document defines the research question, sample
composition, gold annotation procedure, and evaluation framework.

**This is design-only.** No samples are created, no code is written, no APIs are
called, and no predictions are generated in this stage. All experimental execution
happens in downstream stages (R14.1 sample creation, R14.2 Rule-only baseline,
R14.3 Rule+LLM run, R14.4 comparison).

- Real API call: no
- LLM call: no
- Evaluator rerun: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- Prompt superiority claim: no

## 2. Research Question

> **Does an LLM-assisted structured extraction path show better field-level
> extraction behavior than a deterministic rule-only baseline on the same small
> manually annotated sample set?**

**Boundary note:** This is a small controlled mini-experiment (n=24), not a
formal benchmark or method validation. Results describe observed behavior on this
specific sample composition and do not generalize to arbitrary legal texts.

## 3. Compared Systems

| System | Description | Extraction Approach |
|--------|-------------|---------------------|
| **Rule-only baseline** | `RuleFirstExtractor` with `always_rule` fallback | Deterministic regex patterns only. No LLM call under any circumstance. |
| **Rule+LLM-assisted** | `RuleFirstExtractor` with `few_shot_extraction` Prompt B fallback | Rule-first extraction; LLM fallback invoked when rule confidence is below threshold or rule extraction fails schema validation. |

The Rule-only baseline is the control condition. The Rule+LLM-assisted path is
the treatment condition. Both systems share the same rule-first core; the only
difference is whether the LLM fallback is available for low-confidence or
schema-invalid extractions.

## 4. Sample Scale

**24 samples total**, organized as:

- **8 seed samples** from R13.3 (already have reviewed gold annotations)
- **16 new samples** to be created in R14.1

This is a deliberate doubling from the 8-sample mini-pilots (R13.4.2, R13.7).
The scale remains small enough for manual gold annotation while providing more
signal than the descriptive-comparison stage could offer.

## 5. Sample Composition

### 5.1 Source Distribution

| Source | Count | Language | Style |
|--------|-------|----------|-------|
| GDPR EurLex (Articles 5, 6, 7, 9, etc.) | 12 | English | EU legislative, passive-heavy |
| Austrian Income Tax Code (EStG) | 12 | German | National tax law, definition-heavy |

### 5.2 Modality and Structure Coverage

The 24 samples must cover the following categories (each category targets at
least 2 samples):

| Category | Target Count | Description |
|----------|-------------|-------------|
| Obligation clauses | 4 | "shall"/"must" deontic operators |
| Permission clauses | 2 | "may"/"is allowed to" operators |
| Prohibition clauses | 2 | "shall not"/"is prohibited" operators |
| Definition/classification clauses | 4 | Legal status definitions |
| Condition-heavy clauses | 3 | Multiple explicit conditions |
| Exception-heavy clauses | 3 | Contains explicit exception sub-clauses |
| Multi-clause paragraphs | 3 | 2+ independent normative clauses in one paragraph |
| Passive-voice clauses (no explicit actor) | 3 | Actor must be inferred |

### 5.3 Seed Samples (from R13.3)

| Sample ID | Source | Modality | Category |
|-----------|--------|----------|----------|
| r13_3_candidate_001 | GDPR Art 5(1)(a) | obligation | Passive-voice |
| r13_3_candidate_002 | GDPR Art 5(1)(b) | obligation | Multi-clause |
| r13_3_candidate_003 | GDPR Art 5(1)(c) | obligation | Passive-voice |
| r13_3_candidate_004 | GDPR Art 7(1) | obligation | Condition-heavy |
| r13_3_candidate_005 | GDPR Art 9(1) | prohibition | Prohibition |
| r13_3_candidate_006 | EStG §1 Abs 1 | definition | Definition |
| r13_3_candidate_007 | EStG §1 Abs 2 | definition | Multi-clause |
| r13_3_candidate_008 | EStG §1 Abs 3 | definition | Definition |

These 8 seed samples already have reviewed gold annotations (`annotation_status:
reviewed_gold`) and were used in both R13 mini-pilots. They carry known error
patterns (actor inference from passive voice, German→English normalization,
modality confusion with "pflichtig") that the controlled comparison can re-examine.

### 5.4 New Samples (to be created in R14.1)

The 16 new samples will be drawn from:

- **GDPR EurLex**: Articles 5(2), 6(1), 6(2), 6(3), 6(4), 7(2), 7(3), 7(4),
  9(2), 9(3), 9(4) — covering further processing, lawfulness grounds,
  consent conditions, prohibition exceptions.
- **Austrian Income Tax Code (EStG)**: §§ 2, 3, 4, 25, 26, 27, 28, 29 —
  covering income categories, tax-exempt income, profit determination methods,
  and specialized income types.

R14.0 does **not** create sample text. R14.1 will extract individual sentences
or short paragraphs from the above source sections, assign unique sample IDs
(`r14_1_new_001` through `r14_1_new_016`), and write them to
`data/formal/processed/r14_1_new_candidate_samples.jsonl`.

## 6. Gold Annotation Plan

### 6.1 Procedure

1. **R14.1**: Create 16 new candidate samples and write to
   `data/formal/processed/r14_1_new_candidate_samples.jsonl`.
2. **R14.1**: For each new sample, produce a gold annotation following the
   `ClauseExtraction` schema with `annotation_status: reviewed_gold`.
3. **R14.1**: Write the 16 new gold annotations to
   `data/formal/gold/r14_1_new_gold_annotations.jsonl`.
4. **R14.1**: Build the combined 24-sample gold by concatenating the 8 seed
   gold annotations with the 16 new annotations.

### 6.2 Annotation Guidelines

Same as R13.3 manual gold annotation procedure:

- **modality**: One of `obligation`, `prohibition`, `permission`, `definition`.
  Use the dominant deontic operator. If a sentence contains both obligation and
  prohibition elements, annotate the primary normative force.
- **actor**: English normalized form. For passive-voice GDPR clauses, infer the
  actor as the entity that performs the action (e.g., "entity processing personal
  data"). For German sources, translate to English.
- **action**: English normalized form, verb phrase without modality markers.
  Use the infinitive form.
- **condition**: Explicit trigger condition, if present. Null otherwise.
  Include the full condition text in English.
- **constraint**: The normative content (obligation content, prohibition content,
  definition scope). Full text in English.
- **exception**: Explicit exception sub-clause, if present. Null otherwise.
  Include the full exception text in English.

### 6.3 Annotation Quality

Each gold annotation must have `annotation_status: reviewed_gold` and include
`reviewer_notes` documenting annotation decisions (e.g., why a particular
modality was chosen, how actor inference was resolved).

### 6.4 Combined Gold File

The combined 24-sample gold will be written to:
`data/formal/gold/r14_combined_24_gold.jsonl`

This file is the single source of truth for evaluation in R14.2, R14.3, and
R14.4. It must be committed and immutable after R14.1 completes.

## 7. Rule-only Baseline Plan (R14.2)

### 7.1 Configuration

- Extractor: `RuleFirstExtractor`
- Fallback: `always_rule` — no LLM call permitted
- Splitter: `RuleBasedClauseSplitter`
- Input: 24 combined samples from `data/formal/processed/r14_combined_24_samples.jsonl`
- Output: `data/formal/predictions/r14_2_rule_only_predictions.jsonl`

### 7.2 Planned Observation Targets (Rule-only Baseline)

Based on R13.4.2 baseline observations:

- Modality extraction via regex keyword mapping (shall→obligation,
  shall not→prohibition, may→permission, is/are→definition).
- Actor extraction via regex subject pattern matching on active-voice
  clauses; passive-voice clauses likely return null or partial actor.
- Action extraction via regex verb-phrase matching; German verbs may be
  extracted in German rather than translated.
- Condition extraction via regex "where"/"if"/"when" pattern matching.
- Constraint extraction via regex main-clause capture.
- Exception extraction via regex "unless"/"except"/"provided that" patterns.

Based on R13.4.2 prior evidence, the Rule-only baseline may show higher
error rates than a human-annotated gold on:
- Passive-voice actor inference
- German→English field normalization
- Condition/exception boundary disambiguation
- Multi-clause paragraph splitting

R14.2 will measure whether these same patterns appear on the 24-sample set.
No comparison to R14.3 is predicted in advance.

### 7.3 Safety

- No API calls
- No LLM calls
- Deterministic, reproducible output
- No `.env` file read

## 8. Rule+LLM-assisted Plan (R14.3)

### 8.1 Configuration

- Extractor: `RuleFirstExtractor`
- Fallback: `few_shot_extraction` with Prompt B (4 few-shot examples)
- LLM config: same as R13.7 Prompt B configuration (qwen3.7-max, schema
  validation enabled, `max_tokens` per the R13.7 authorization contract)
- Splitter: `RuleBasedClauseSplitter`
- Input: same 24 combined samples as Rule-only baseline
- Output: `data/formal/predictions/r14_3_rule_plus_llm_predictions.jsonl`

### 8.2 Authorization Gate

Before executing R14.3, the user must explicitly authorize the LLM calls via the
same mechanism used in R13.7 (authorization contract + confirmation). R14.3
follows the rule-first principle: the LLM is invoked only when the rule
extraction falls below the confidence threshold or fails schema validation.

### 8.3 Planned Observation Targets (Comparison Questions)

R14.0 makes no outcome prediction. R14.0 does not claim LLM superiority.
The Rule+LLM run (R14.3) will produce field-level predictions that R14.4
will compare to the Rule-only baseline (R14.2). The comparison will report
whether the LLM-assisted path shows higher, lower, or similar field-level
scores on the same 24 samples. No outcome direction is assumed.

Based on R13.7 Prompt B observations on the 8 seed samples, the following
are comparison questions R14.4 can answer for the full 24-sample set:

- Modality: Does Rule+LLM match or differ from Rule-only on modality labels?
- Actor: Does Rule+LLM show different actor extraction behavior on
  passive-voice clauses and German→English normalization?
- Action: Does Rule+LLM show different action-field extraction behavior?
- Condition: Does Rule+LLM show different condition-boundary disambiguation?
- Constraint: Does Rule+LLM show different constraint content capture?
- Exception: Both systems are expected to produce mostly not_applicable for
  the selected source sections; R14.4 will confirm whether this holds.

### 8.4 Safety

- Real API call: yes (gated by authorization)
- LLM call: yes (gated by authorization)
- Secret redaction: active
- Schema validation: active
- No unsupervised batch execution
- Authorization contract required before execution

## 9. Evaluation Metrics

Evaluated per `docs/r14_0_metric_definition.md`. Summary:

| Metric | Definition | Use |
|--------|-----------|-----|
| Strict exact-F1 | exact matches / total fields (micro-averaged) | Primary comparison metric |
| Lenient partial-F1 | (exact + partial) / total fields | Secondary; captures near-miss behavior |
| Field-level accuracy | exact_count / total_applicable_fields per field | Per-field diagnostic |
| Macro-F1 | average of per-field exact-F1 | Complementary; weights all fields equally |

Comparison will be done descriptively — differences in observed counts between
Rule-only and Rule+LLM, not statistical significance testing.

## 10. Safety Boundary

### 10.1 Allowed Claims

- "On this 24-sample set, the Rule+LLM path showed [fewer/more] field-level
  errors than the Rule-only baseline for fields X, Y, Z."
- "The Rule+LLM path produced exact matches for actor in N/24 samples vs
  M/24 for Rule-only."
- "Observed error patterns in Rule-only included [patterns]; Rule+LLM
  [did/did not] show the same patterns."

### 10.2 Forbidden Claims

- Any claim of statistical significance (p-values, confidence intervals)
- Any claim of generalizability beyond these 24 samples
- Any claim that LLM-assisted extraction is "better" in absolute terms
- Any claim about the specific LLM model's capability
- Any comparison to published benchmarks or prior work
- Any claim of method validation
- Any claim of prompt superiority

### 10.3 Safety Flags

All metadata safety flags set to `false`:
- `benchmark`: false
- `method_validation`: false
- `sun_reproduction`: false
- `safe_to_claim_prompt_superiority`: false
- `safe_to_draw_benchmark_conclusion`: false

## 11. PPT/Report Format for R14.4

R14.4 will produce a comparison report with:

1. **Per-field count tables**: 6 fields × 2 systems, showing
   exact/partial/missing/wrong/NA counts.
2. **Per-sample notes**: For each of the 24 samples, note which system
   performed better on which fields (if any difference exists).
3. **Error-pattern analysis**: Categorize errors by type (actor inference
   failure, normalization failure, condition boundary error, etc.) and
   compare frequencies between systems.
4. **Aggregate comparison**: Strict exact-F1 and lenient partial-F1 for
   both systems, computed per `r14_0_metric_definition.md`.
5. **Claim boundary**: Explicit statement that results are descriptive
   observations on 24 samples only.

## 12. Claims (R14.0-specific)

- R14.0 defines the experimental design. No experimental claims are made in
  this stage.
- The research question is stated as a question, not a hypothesis.
- No prediction of outcomes is made.

## 13. Next Stage

**R14.1**: Create 16 new candidate samples with gold annotations, build the
combined 24-sample gold file, and prepare the combined sample input file.
R14.0 is a prerequisite for R14.1.
