# R14.3 Rule+LLM Experiment Plan

## 1. Scope

This document defines the Rule+LLM-assisted experiment plan for a possible future
R14.4 execution. R14.3 itself is planning-only — it does NOT call LLM, does NOT
call real API, and does NOT produce any prediction or evaluation outputs.

The plan covers:
- Future Rule+LLM method (same `RuleFirstExtractor` + `few_shot_extraction` Prompt B)
- Same 24 R14.1 draft mini-gold samples as the R14.2 rule-only baseline
- Maximum 24 API calls, one per sample, no retry, no repair, no batch
- Same R14 field-level evaluator (Jaccard-based) as R14.2

## 2. Current Baseline (R14.2)

The deterministic rule-only baseline has been established on the 24-sample
mini-gold:

| Metric | Value |
|--------|-------|
| overall_field_exact_accuracy | 0.1491 |
| micro_strict_f1 | 0.2138 |
| macro_strict_f1 | 0.1405 |
| micro_lenient_f1 | 0.3145 |
| macro_lenient_f1 | 0.2212 |

Strongest field: **modality** (strict_f1 = 0.7805).
Weakest fields: **action** (strict_f1 = 0.0000), **condition** (strict_f1 = 0.0000),
**constraint** (strict_f1 = 0.0000), **exception** (strict_f1 = 0.0000).
**actor** is low (strict_f1 = 0.0625).

The rule-only baseline does NOT use LLM, API, or network. It is the control
condition for any future comparison.

## 3. Future Rule+LLM Method (R14.4)

```
method = rule_plus_llm_assisted
input_samples = data/formal/r14_controlled/r14_1_candidate_samples.jsonl
input_gold = data/formal/r14_controlled/r14_1_mini_gold.jsonl
baseline_reference = data/formal/results/r14_2_rule_only_evaluation_summary.json
```

The Rule+LLM-assisted path will use:
- `RuleFirstExtractor` with `few_shot_extraction` Prompt B fallback
- One LLM extraction call per sample
- Schema-constrained JSON output (6-field format)
- Same deterministic rule-first core as the baseline
- LLM fallback invoked when rule confidence is below threshold or rule extraction fails schema validation

Execution boundaries:
- max_api_calls = 24
- one attempt per sample: yes
- retry allowed: no
- repair call allowed: no
- batch allowed: no
- raw response saved: no

## 4. Input Dataset

Same as R14.2 rule-only baseline:
- 24 samples from `data/formal/r14_controlled/r14_1_candidate_samples.jsonl`
- Gold annotations from `data/formal/r14_controlled/r14_1_mini_gold.jsonl`
- 8 seed samples from R13.3 + 16 new samples from R14.1
- 12 GDPR EurLex (English) + 12 Austrian Income Tax Code (German)
- Covers: obligation, prohibition, permission, definition, condition-heavy,
  exception-heavy, multi-clause, passive-voice clauses

## 5. Prompt and Schema

Selected prompt: **R13.6 Prompt B** (`few_shot_extraction_prompt.md`)

- Prompt type: few-shot extraction with 3 examples (obligation/passive, prohibition/condition, definition/German)
- Output schema: 6-field JSON (modality, actor, action, condition, constraint, exception)
- Schema-constrained: yes
- Language normalization: English canonical form
- Prompt snapshot: `data/formal/metadata/r14_3_prompt_snapshot.json`

A frozen prompt snapshot (SHA256 + size) is recorded for auditability. If Prompt B
is modified after R14.3, the snapshot will detect the drift.

## 6. Execution Contract

The full execution contract is at:
`data/formal/metadata/r14_3_rule_plus_llm_execution_contract.json`

Key constraints:
- `requires_fresh_user_authorization = true`
- R14.3 does NOT authorize or execute the run
- R14.4 future run requires the exact authorization text from the authorization
  request document

## 7. Evaluation Plan

Same evaluator as R14.2: `scripts/evaluate_r14_field_metrics.py`

Evaluation will produce:
- `data/formal/results/r14_4_rule_plus_llm_evaluation_summary.json`
- `data/formal/results/r14_4_rule_plus_llm_evaluation_details.jsonl`

Metrics computed:
- Field-level exact/partial/missing/wrong/NA counts
- Strict precision/recall/F1 per field
- Lenient partial precision/recall/F1 per field
- Macro/micro averages
- Overall field-exact accuracy

Thresholds (from `docs/r14_0_metric_definition.md`):
- Jaccard = 1.0 → exact
- Jaccard ≥ 0.5 → partial
- Jaccard < 0.5 → wrong

## 8. Comparison Plan After R14.4

R14.3 does not run Rule+LLM. R14.4, if authorized later, will produce the
Rule+LLM side. Only after R14.4 and audit can a descriptive comparison be made.

Comparison will be:
- Field-level delta tables (exact/partial count shift per field)
- F1 comparison (strict and lenient)
- Error pattern analysis (does LLM help most on actor inference, constraint extraction, etc.?)
- Same evaluator, same gold, same metric definitions

This is a small controlled mini-experiment (n=24), NOT a formal benchmark.

## 9. Safety Controls

- `.env` must contain `BPC_HYBRID_LLM_ENABLED=true` before any API call
- `$env:BPC_HYBRID_DISABLE_PROJECT_ENV = "1"` must be set
- No raw response persistence (`raw_response_saved = false`)
- No retry, no repair call, no batch execution
- All API calls exit through `LLMFallbackAdapter` → `RealAPITransport`
- Secret redaction active at all times (`redact_secret()`, `redact_mapping()`)
- Maximum 24 API calls, enforced by counter in execution harness

## 10. PPT-safe Reporting Language

> We first established a deterministic no-LLM rule-only baseline. The next planned
> step is a separately authorized Rule+LLM-assisted run on the same 24 draft
> mini-gold samples. Any comparison will be descriptive and small-scale, not a
> formal benchmark.

This language does not claim:
- LLM superiority
- Method validation
- Benchmark completion
- Sun reproduction
- Production readiness
- Benchmark-level accuracy

## 11. Limitations

- n=24 is a small exploratory sample; results do not generalize
- Only two legal domains (GDPR, Austrian tax code) — domain-specific behavior may vary
- Prompt B has only 3 few-shot examples — may not cover all modality/structure combinations
- German→English normalization quality depends on LLM's multilingual capability
- No retry, no repair means single-attempt failures are counted as-is
- The evaluator is field-level Jaccard-based and does not measure semantic equivalence

## 12. Claim Boundary

R14.3 does not run Rule+LLM.
R14.3 only prepares the future R14.4 run.
R14.2 rule-only baseline can be used as the no-LLM side.
R14.4, if authorized later, will produce the Rule+LLM side.
Only after R14.4 and audit can a descriptive comparison be made.

This stage does not claim, imply, or suggest:
- LLM superiority
- Method validation
- Benchmark completion
- Sun reproduction
- Production GDPR compliance checker
- Any real API was called in R14.3
- Any LLM was called in R14.3
