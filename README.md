# bpc-hybrid

## Current Status

**R0 ✅ | R1 ✅ | R1.5 ✅ | R1.6 ✅ | R2 ✅ | R3 ✅ | R4 ✅ | R5 ✅ | R5.1 ✅**

## Research Positioning

`bpc-hybrid` is a **rule-first LLM-assisted hybrid framework** for design-time business process compliance assessment.

The framework keeps Sun-style rule-template / marker-based regulatory semantic extraction as the **primary path** because it provides consistency, low cost, interpretability, and deterministic traceability. LLMs are planned only as a **controlled fallback** for cases such as multi-modality, missing actor/action, parser failure, or low-confidence matching.

LLM outputs must be constrained by strict JSON schemas and then processed through span normalization and deterministic post-processing to reduce hallucination and representation inconsistency.

A planned **multi-clause schema** will allow compound regulatory sentences with multiple modalities to be decomposed into individual normative clauses, each carrying its own modality, actor, action, condition, constraint, and exception.

## Important Declarations

- ⚠️ This is NOT a formal benchmark.
- ⚠️ No GDPR / BPMN / Sun dataset data is fabricated or included.
- ⚠️ Only a successful GitHub push marks the completion of a stage.
- ⚠️ No claims about surpassing Sun or any prior work are made.
- ⚠️ The current repository is a runnable MVP skeleton, not a validated system.

## R0 Artifacts

| File | Description |
|------|-------------|
| `.gitignore` | Git ignore rules for Python, secrets, outputs, OS/IDE files |
| `README.md` | Project overview and current status (this file) |
| `docs/research_idea.md` | Research concept and methodology outline |
| `docs/experiment_log.md` | Experiment progress log |
| `docs/safety_rules.md` | Safety constraints for this project |

## Current Stage

- R0 ✅: Safe GitHub-backed bootstrap completed.
- R1 ✅: Minimal Python project scaffold completed.
- R1.5 ✅: Research framing integrated into project documentation.
- R1.6 ✅: Codex local-only audit report persisted.
- R2 ✅: Core multi-clause schema completed.
- R3 ✅: Rule-first extractor completed.
- R4 ✅: Multi-clause splitter completed.
- R5 ✅: Prototype evaluation loop completed.
- R5.1 ✅: R5 CLI direct execution and prototype dataset ID mapping fixed after Codex audit.

## R2 Scope

R2 implements the core schema objects for multi-clause regulatory extraction:

- `FieldSpan`
- `ClauseExtraction`
- `MultiClauseExtractionResponse`

The schema supports object-or-null fields for modality, actor, action, condition, constraint, and exception, with span offsets and confidence scores. Schema validation is enforced via `SchemaValidationError`.

R2 does not implement rule extraction, multi-clause splitting, LLM fallback, evaluation, BPMN checking, real datasets, or benchmark results.

## R3 Scope

R3 implements a rule-first extractor (`RuleFirstExtractor`) that parses
single-clause regulatory sentences and populates all six semantic fields
(modality, actor, action, condition, constraint, exception) using
deterministic marker-based heuristics:

- **Modality**: priority-ordered markers (shall, shall not, must, must not, may)
- **Actor**: active-voice subject before marker, "no person" prohibition,
  by-agent passive detection
- **Action**: text after modality, truncated at constraint/exception/by-agent/
  recipient boundaries
- **Condition**: initial "Unless X" clause
- **Exception**: mid-sentence "unless X" clause
- **Constraint**: markers (within, before, after, only if, provided that)

Non-normative sentences (definitions, warranties, legal consequences,
descriptive statements) are detected and return null semantic fields.
Passive voice is detected via "be + past-participle" pattern; the actor
is extracted from "by the X" phrases while recipients ("to the X") are
excluded. Multi-clause splitting is deferred to R4.

## R4 Scope

R4 implements a deterministic, rule-based multi-clause splitter
(`RuleBasedClauseSplitter`) that decomposes compound normative sentences
with multiple modality markers into individual `ClauseSegment` objects:

- **Modality detection**: priority-ordered markers (shall/shall not/must not/shall/must/may)
- **Clause-boundary "and"**: splits on "and" between modality markers
- **Initial-unless**: detected as inherited condition, stripped from segment text
- **Mid-unless**: prevents splitting across unless clauses
- **Constraint regions**: within/before/after/only if/provided that
- **Integration**: Extractor `extract()` calls splitter first, then extracts each segment

R4 does not implement LLM fallback, evaluation, BPMN checking, or real datasets.

## R5 Scope

R5 implements a synthetic prototype evaluation loop for pipeline sanity checking:

- **Synthetic dataset**: 14 toy legal sentences at `data/prototype/legal_sentences.jsonl`
- **Gold multi-clause extractions**: `data/prototype/gold_multiclause.jsonl` with exact spans
- **Evaluator** (`bpc_hybrid.evaluator`): deterministic clause/field-level metrics with `EvaluationReport`
- **Rule baseline script**: `scripts/run_rule_baseline.py` runs the rule-first extractor on all sentences
- **Evaluation script**: `scripts/evaluate_multi_clause.py` loads gold + predictions, prints JSON report
- **Tests**: `tests/test_evaluator.py` — 30 tests covering FieldMetrics, perfect prediction, field errors, clause mismatch, perf-field/micro metrics, subprocess integration, and data safety

R5 does not implement LLM fallback, BPMN checking, formal benchmarks, or real (GDPR/Sun) datasets. All data is synthetic and used for sanity checks only.

## Dataset and Claim Boundary

The future formal evaluation target is a **Sun-aligned GDPR + BPMN dataset**, compared against Sun-style rule baseline and Winter-style textual baseline on precision / recall / F1 / AP / MAP.

**EStG / Austrian Income Tax Act** may only be used later as an optional generalization corpus and cannot replace the Sun-aligned main benchmark.

This project currently does **not** claim to outperform Sun-style baselines, Winter-style textual baselines, or any LLM baseline. Synthetic prototype data, if introduced later, is used for pipeline sanity checks only — not for benchmark claims.

## Next Stage

R6 — LLM Fallback — will only proceed after R5.1 is fully tested,
committed, pushed, and user authorization is granted.
