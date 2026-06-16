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
