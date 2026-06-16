# Experiment Log

## R0 — Safe GitHub-backed Bootstrap

### Goal

Establish a GitHub-backed safe project root before any code implementation.

### Safety Requirements

- Project root is fixed to `D:\Paper\experiment\bpc-hybrid`.
- No operation is allowed outside the project root.
- No recursive deletion or cleanup commands are allowed.
- Local commit is not considered completion.
- Only successful GitHub push marks the stage as complete.

### Artifacts Created

- `.gitignore`
- `README.md`
- `docs/research_idea.md`
- `docs/experiment_log.md`
- `docs/safety_rules.md`

### Status

Completed after successful GitHub push.

## R1 — Minimal Python Project Scaffold

### Goal

Create the minimal Python package structure required for later schema, extractor, splitter, evaluator, and LLM mock stages.

### Scope

- Create `src/bpc_hybrid/`
- Create `tests/`
- Create `scripts/`
- Create `data/prototype/`
- Configure pytest through `pyproject.toml`
- Add a minimal smoke test
- Add a local project health script

### Non-goals

- No real GDPR data
- No real BPMN models
- No Sun-aligned benchmark
- No LLM API call
- No extraction algorithm
- No compliance checking

### Status

Completed after tests passed and GitHub push succeeded.

## R1.5 — Research Framing Integration

### Goal

Integrate a safer and clearer research framing into the project documentation after the R1 scaffold.

### Scope

- Update `README.md` with concise research positioning, dataset boundary, and claim boundary.
- Update `docs/research_idea.md` with prior-work relation, multi-clause schema rationale, deterministic normalization rationale, dataset boundary, and forbidden claims.
- Keep the current project status limited to a runnable scaffold / MVP skeleton.

### Non-goals

- No schema implementation.
- No extractor implementation.
- No LLM fallback implementation.
- No real GDPR data.
- No real BPMN model.
- No Sun-aligned benchmark.
- No synthetic prototype dataset.
- No benchmark result.
- No claim of outperforming Sun or any baseline.
- No method validation claim (requires R5+).

### Status

Completed after documentation update and GitHub push succeeded.

## R2 — Core Multi-Clause Schema

### Goal

Implement the core schema objects required for later rule-first extraction, multi-clause splitting, LLM fallback validation, and evaluation.

### Scope

- Add `FieldSpan`
- Add `ClauseExtraction`
- Add `MultiClauseExtractionResponse`
- Support object-or-null fields for modality, actor, action, condition, constraint, and exception
- Support span offsets and confidence scores
- Add schema validation tests
- Add JSON/dict round-trip tests

### Non-goals

- No rule extractor
- No multi-clause splitter
- No evaluator
- No LLM fallback
- No real GDPR data
- No real BPMN models
- No Sun-aligned dataset
- No synthetic prototype dataset
- No benchmark result
- No compliance checking

### Status

Completed after schema tests passed and GitHub push succeeded.
