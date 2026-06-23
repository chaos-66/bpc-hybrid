# R13.9 Final Package Plan

## 1. Scope

R13.9 packages the accepted R13 experiment chain into a project-level final
package suitable for internal documentation, resume description, and interview
explanation. This stage creates documentation only — no experiments, no API
calls, no data modifications.

- Real API call: no
- LLM call: no
- Evaluator rerun: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- Prompt superiority claim: no

## 2. Accepted Stage Chain

| Stage | Name | Type | Status |
|-------|------|------|--------|
| R13.4.2 | Baseline Bounded Real Mini-pilot | 8-sample real API baseline (qwen3.7-max, no few-shot) | Accepted |
| R13.5 | Post-pilot Error Analysis | Analysis-only | Accepted |
| R13.6 | Prompt-refinement Design | Design-only, 3 prompt variants | Accepted |
| R13.7-pre | Prompt B Authorization Plan | Authorization-only | Accepted |
| R13.7 | Prompt B Bounded Real Mini-pilot | 8-sample real API Prompt B (few_shot_extraction) | Accepted |
| R13.7.1 | Audit-blocker Fixes | Code fix (gate logic, test hardening) | Accepted |
| R13.7.2 | Gate Test Coverage Fix | 7 negative gate tests | Accepted |
| R13.8 | Descriptive Comparison | Post-run comparison R13.4.2 vs R13.7 | Accepted |
| R13.8.1 | GDPR Typo Fix | Documentation polish | Accepted |
| R13.9 | Final Package Planning | Documentation-only | Current |

## 3. Key Artifacts

### Core Pipeline Code

- `src/bpc_hybrid/schema.py` — `ClauseExtraction`, `MultiClauseExtractionResponse` (R2)
- `src/bpc_hybrid/extractor.py` — `RuleFirstExtractor` (R3)
- `src/bpc_hybrid/splitter.py` — `RuleBasedClauseSplitter` (R4)
- `src/bpc_hybrid/evaluator.py` — `FieldMetrics`, `EvaluationReport` (R5)
- `src/bpc_hybrid/fallback.py` — `MockLLMFallbackClient`, fallback decision (R6)
- `src/bpc_hybrid/normalization.py` — Span repair, field normalization (R6)
- `src/bpc_hybrid/llm_config.py` — `LLMConfig`, safety gates, `.env` loading (R7-R9)
- `src/bpc_hybrid/schema_alignment.py` — Real LLM output normalizer (R11.2)
- `src/bpc_hybrid/transport.py` — `RealAPITransport`, secret redaction (R9-R11)

### Real API Pilot Scripts

- `scripts/run_r13_4_2_real_mini_pilot.py` — Baseline 8-sample runner
- `scripts/run_r13_7_prompt_b_real_mini_pilot.py` — Prompt B 8-sample runner with authorization gate
- `scripts/evaluate_mini_pilot_predictions.py` — Field-level mini-gold evaluator

### Prompts

- `prompts/r13_6/few_shot_extraction_prompt.md` — Prompt B (4 few-shot examples)
- `prompts/r13_6/` — Prompt A (instruction-only) and Prompt C (chain-of-thought)

### Documentation

- `docs/r13_4_mini_pilot_plan.md` — Mini-pilot evaluation plan
- `docs/r13_4_2_real_mini_pilot_report.md` — Baseline mini-pilot report
- `docs/r13_5_post_pilot_error_analysis.md` — Error analysis
- `docs/r13_5_prompt_refinement_plan.md` — Prompt refinement strategy
- `docs/r13_6_prompt_refinement_design.md` — Prompt design details
- `docs/r13_6_next_run_plan.md` — Next-run planning
- `docs/r13_7_pre_prompt_b_authorization_plan.md` — Authorization contract
- `docs/r13_7_prompt_b_real_mini_pilot_report.md` — Prompt B pilot report
- `docs/r13_8_descriptive_comparison.md` — R13.4.2 vs R13.7 comparison
- `docs/r13_9_final_package_plan.md` — This document
- `docs/r13_9_project_stage_summary.md` — Project stage summary
- `docs/r13_9_resume_and_interview_talking_points.md` — Resume/interview points

### Data

- `data/formal/gold/r13_3_manual_gold_template.jsonl` — 8-sample reviewed mini-gold
- `data/formal/processed/r13_3_candidate_samples.jsonl` — 8 input samples
- `data/formal/predictions/r13_4_2_real_predictions.jsonl` — Baseline predictions
- `data/formal/predictions/r13_7_prompt_b_real_predictions.jsonl` — Prompt B predictions
- `data/formal/results/r13_4_2_real_evaluation_summary.json` — Baseline evaluation
- `data/formal/results/r13_4_2_real_evaluation_details.jsonl` — Baseline details
- `data/formal/results/r13_7_prompt_b_real_evaluation_summary.json` — Prompt B evaluation
- `data/formal/results/r13_7_prompt_b_real_evaluation_details.jsonl` — Prompt B details
- `data/formal/metadata/` — Execution contracts, authorization checklists, snapshots

## 4. What This Project Demonstrates

1. **Audit-gated real API execution**: Every real API call required an explicit
   user authorization, a pre-defined safety contract, and before/after Codex
   audit checkpoints. No unsupervised batch execution was allowed.

2. **Rule-first architecture**: Deterministic regex-based extraction as the
   primary path, with LLM used only as a controlled fallback for structured
   extraction — not as an autonomous reasoning engine.

3. **Schema-constrained LLM fallback**: LLM outputs must pass JSON Schema
   validation against the project's `ClauseExtraction` / `MultiClauseExtractionResponse`
   schemas. Schema-invalid responses are rejected.

4. **Field-level mini-gold evaluation**: 6-field evaluation (modality, actor,
   action, condition, constraint, exception) with exact/partial/wrong/missing/
   not_applicable scoring — more granular than end-to-end accuracy.

5. **Bounded prompt-iteration experiment chain**: Baseline → Error Analysis →
   Prompt Design → Refined Prompt Pilot → Descriptive Comparison — a full
   mini-pilot lifecycle without overclaiming.

6. **Safety-by-design engineering**: Secret redaction, `.env` isolation, raw
   response suppression, call-count tracking, authorization consumption, and
   `BPC_HYBRID_DISABLE_PROJECT_ENV` audit controls.

## 5. What This Project Does Not Demonstrate

- **Benchmark performance**: 8 samples. No statistical significance. No held-out
  test set. No cross-validation. No comparison against published baselines.
- **Method validation**: The pipeline was tested on 2 legal domains (GDPR EUR-Lex
  and Austrian Income Tax Code) with 8 total samples. This is not sufficient
  for method validation.
- **Sun reproduction**: No attempt was made to replicate the Sun et al. benchmark
  dataset, metrics (AP/MAP), or experimental protocol.
- **Prompt B superiority**: R13.8 describes count differences between 8-sample
  runs. The differences may be attributable to the few-shot design, model-internal
  variability, or sample-specific factors. No causal claim is made.
- **Production readiness**: This is a research prototype. No deployment pipeline,
  no scalability testing, no adversarial evaluation, no compliance certification.

## 6. Safe Claim Boundary

### Allowed Claims

- Built an audit-gated prototype workflow for structured regulatory semantic extraction
- Combined rule-first design with schema-constrained LLM fallback
- Implemented field-level mini-gold evaluation
- Completed a bounded 8-sample real API mini-pilot chain (R13.4.2 → R13.7)
- Produced a descriptive comparison of two 8-sample mini-pilot runs
- Engineered safety controls: authorization gates, secret redaction, raw response
  suppression, and audit-safe env isolation

### Forbidden Claims

- Validated a method for regulatory compliance extraction
- Achieved benchmark-level accuracy
- Reproduced or improved upon Sun et al.
- Proved that Prompt B is superior to the baseline
- Built a production-ready GDPR compliance checker
- Established formal BPMN compliance checking capability

## 7. Suggested Final Package Structure

```
bpc-hybrid/
├── README.md                         # Project overview, status, claim boundary
├── docs/
│   ├── experiment_log.md             # Full stage-by-stage log
│   ├── issue_log.md                  # All issues and resolutions
│   ├── r13_4_mini_pilot_plan.md
│   ├── r13_4_2_real_mini_pilot_report.md
│   ├── r13_5_post_pilot_error_analysis.md
│   ├── r13_5_prompt_refinement_plan.md
│   ├── r13_6_prompt_refinement_design.md
│   ├── r13_6_next_run_plan.md
│   ├── r13_7_pre_prompt_b_authorization_plan.md
│   ├── r13_7_prompt_b_real_mini_pilot_report.md
│   ├── r13_8_descriptive_comparison.md
│   ├── r13_9_final_package_plan.md       # This document
│   ├── r13_9_project_stage_summary.md    # Project summary
│   └── r13_9_resume_and_interview_talking_points.md
├── data/formal/
│   ├── gold/r13_3_manual_gold_template.jsonl
│   ├── processed/r13_3_candidate_samples.jsonl
│   ├── predictions/
│   │   ├── r13_4_2_real_predictions.jsonl
│   │   └── r13_7_prompt_b_real_predictions.jsonl
│   ├── results/
│   │   ├── r13_4_2_real_evaluation_summary.json
│   │   ├── r13_4_2_real_evaluation_details.jsonl
│   │   ├── r13_7_prompt_b_real_evaluation_summary.json
│   │   └── r13_7_prompt_b_real_evaluation_details.jsonl
│   └── metadata/                     # Contracts, checklists, manifests
├── prompts/r13_6/                    # Prompt A, B, C
├── scripts/                          # Pilot runners, evaluator
├── src/bpc_hybrid/                   # Core library
└── tests/                            # 708 tests
```

## 8. Next Development Options

These are possible next directions but require new authorization, planning,
and audit before any implementation:

1. **R14: Another bounded prompt variant pilot** — Test Prompt A or Prompt C
   from R13.6 on the same 8-sample set to gather more descriptive evidence.

2. **R15: Expanded sample set** — Add more annotated legal samples (requires
   new data intake, gold annotation, and user authorization).

3. **R16: Multi-model comparison** — Test the same prompt on a different
   model (e.g., a different provider or model family).

4. **R17: Exception-bearing samples** — Collect and annotate samples that
   contain exception clauses to enable exception-field evaluation.

5. **R18: Statistical experimental design** — Move from manual pilot runs to
   a formal experimental protocol with sample-size justification, held-out
   sets, and statistical tests (requires methodology upgrade).

None of these is authorized now. Each requires a fresh planning stage,
explicit user authorization, and new Codex audit checkpoints.

## 9. Audit and Safety Notes

- R13.9 is documentation-only — no code, data, or configuration was changed
  beyond R13.8.1.
- All prediction and evaluation files remain at their R13.4.2/R13.7 committed
  states.
- The only `.env`-related content in committed files is `.env.example` (public
  template with placeholder values).
- Raw API responses were never saved at any stage.
- The audit boundary from R13.8 applies: descriptive project evidence only.
