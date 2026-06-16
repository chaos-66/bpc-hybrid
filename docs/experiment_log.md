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

## R3 — Rule-first Extractor

### Goal

Implement a deterministic rule-first extractor that parses single-clause
regulatory sentences and populates all six semantic fields defined by the
R2 schema.

### Scope

- Add `RuleFirstExtractor` class with `extract()` method
- Priority-ordered modality marker detection with word-boundary checks
- Active-voice actor extraction (text before marker)
- "no person shall" prohibition handling
- Passive-voice detection via "be + past-participle" heuristic
- By-agent passive actor extraction ("by the X")
- Recipient exclusion ("to the X" is NOT an actor)
- Initial unless → condition
- Mid-sentence unless → exception
- Constraint marker detection (within, before, after, only if, provided that)
- Action extraction truncated at constraint/exception/by-agent/recipient boundaries
- Definition / warranty / legal consequence / descriptive → null response
- Convenience function `extract_rule_first()`
- 34 unit tests covering positive, negative, edge, span integrity, and JSON/dict
  round-trip cases
- Export `ExtractionError`, `RuleFirstExtractor`, `extract_rule_first` from package

### Non-goals

- No multi-clause splitting (R4)
- No LLM fallback (R5+)
- No evaluator
- No real GDPR data
- No real BPMN models
- No Sun-aligned dataset
- No synthetic prototype dataset
- No benchmark result
- No compliance checking

### Status

Completed after 34 extractor tests + 35 prior tests all passed and
GitHub push succeeded.

## R3.1 — Fix R3 Package Import Blocking Issue

### Goal

Fix the package-level import failure found by Codex R3 local-only audit.

### Blocking Issue

Codex identified an `IndentationError` in `src/bpc_hybrid/__init__.py`,
which caused full pytest, extractor-specific pytest, and the health script
to fail before R3 behavior could be validated.

### Scope

- Fix malformed `__all__` / indentation in `src/bpc_hybrid/__init__.py`
- Re-run package compile check
- Re-run extractor tests
- Re-run full pytest
- Re-run health script
- Keep R3 scope limited to the rule-first extractor

### Non-goals

- No R4 multi-clause splitter
- No evaluator
- No LLM fallback
- No real GDPR data
- No real BPMN models
- No Sun-aligned dataset
- No synthetic prototype dataset
- No benchmark result
- No compliance checking

### Status

Completed after package import, tests, health script, commit, and GitHub
push succeeded.

## R4 — Multi-Clause Splitter

### Goal

Implement a deterministic, rule-based multi-clause sentence splitter that
decomposes compound normative sentences with multiple modality markers into
individual clause segments, and integrate it with the R3 extractor.

### Scope

- Create `src/bpc_hybrid/splitter.py` with `RuleBasedClauseSplitter`
- Implement `ClauseSegment` dataclass and `SplitError` exception
- Implement `split()` method with modality detection, clause-boundary "and",
  initial-unless stripping, mid-unless detection, constraint regions
- Implement `_find_all_modalities()`, `_find_clause_boundary_and()`,
  `_is_inside_constraint()`, `_has_modality_in_range()`,
  `_detect_initial_unless()`, `_detect_mid_unless()`
- Provide `split_normative_clauses()` convenience function
- Integrate splitter into extractor: `extract()` calls splitter first
- Fix action boundary bleeding: `_extract_action` accepts `end_bound` param
- Create `tests/test_splitter.py` (40 tests)
- Update `__init__.py` with splitter exports
- Update `README.md` and `experiment_log.md`

### Non-goals

- No LLM fallback
- No evaluator
- No BPMN checking
- No real datasets
- No benchmark results

### Key Design Decisions

- Splitter is purely deterministic (stdlib only, no ML)
- Modality priority mirrors R3 extractor for consistency
- Initial-unless is detected as inherited condition, stripped from segments
- Mid-unless prevents splitting across unless clauses
- Constraint markers (within/before/after/only if/provided that) are checked
- Multi-clause extraction: extractor calls splitter, then extracts each segment
- Action extraction respects `seg.span_end` boundary to prevent bleeding

### Test Coverage

40 splitter tests + 34 extractor tests = 74 total, all passing.

### Status

Completed — all 74 tests pass, committed and pushed.

## R5 — Prototype Evaluation Loop

### Goal

Implement a synthetic prototype evaluation loop that validates the full
pipeline (schema → extractor → splitter → evaluator) with deterministic
clause/field-level metrics on toy legal sentences only.

### Scope

- Create synthetic prototype sentences at `data/prototype/legal_sentences.jsonl`
  (14 entries: d01–d14)
- Create gold multi-clause extraction file at
  `data/prototype/gold_multiclause.jsonl` with exact spans
- Implement `src/bpc_hybrid/evaluator.py`:
  - `EvaluationError(ValueError)` — custom exception
  - `FieldMetrics` dataclass with tp/fp/fn and precision/recall/f1 properties
  - `EvaluationReport` dataclass with dataset_type, is_formal_benchmark,
    compares_against_sun, clause/field micro metrics, per_field breakdown,
    and source_details
  - `_normalize(text)` — lowercase, strip punctuation, collapse whitespace
  - `_compare_field(gold_fs, pred_fs, metrics)` — updates tp/fp/fn; TN not counted
  - `evaluate_responses(gold, predicted)` — aligns by source_id, clauses by position
  - `load_jsonl(path)`, `load_gold_responses(path)`, `load_predicted_responses(path)`
- Create `scripts/run_rule_baseline.py` — runs rule-first extractor on all
  sentences, outputs JSONL to stdout
- Create `scripts/evaluate_multi_clause.py` — loads gold + predictions (on-the-fly
  or pre-computed), runs evaluation, prints JSON report
- Create `tests/test_evaluator.py` — 30 tests:
  - TestFieldMetrics (perfect, zero, mixed, to_dict, zero-division)
  - TestEvaluationReport (defaults, to_dict)
  - TestNormalize (lowercase, punctuation, whitespace)
  - TestLoadJsonl (sentences, gold)
  - TestGoldValidation (all gold validate, IDs match sentences)
  - TestPerfectPrediction (all-fields F1=1.0, single-field F1=1.0)
  - TestFieldErrors (missing→FN, extra→FP, wrong text→FP+FN, both null→not counted)
  - TestClauseCountMismatch (more pred clauses, fewer pred clauses)
  - TestPerFieldAndMicro (6 fields present, micro sum)
  - TestDuplicateSourceId (raises EvaluationError)
  - TestRunRuleBaseline (subprocess, 14 output lines, valid JSONL)
  - TestEvaluateMultiClause (valid JSON output, synthetic_prototype flags,
    perfect-on-gold)
  - TestSyntheticOnly (no GDPR/ARTICLE/EU in any sentence or gold)
- Update `src/bpc_hybrid/__init__.py` with evaluator exports
- Update `README.md` with R5 status and scope
- Update `docs/experiment_log.md` (this section)

### Non-goals

- No LLM fallback (R6)
- No BPMN checking
- No formal benchmark
- No real (GDPR/Sun) datasets
- No benchmark claims
- All data is synthetic and used for pipeline sanity checks only

### Key Design Decisions

- Gold spans are exact source_text offsets from rule-first extractor output
- Clause alignment is positional (by index) within each source_id
- Field comparison uses normalized text (lowercase, stripped punctuation,
  collapsed whitespace)
- TN (both null) is not counted in any metric
- Extra gold clauses → FN on all non-null fields; extra pred clauses → FP
- Micro precision/recall/F1 are sums across all fields (not per-field averages)
- predict-on-the-fly mode writes compact JSONL (no indent) to tempfile

### Test Coverage

30 evaluator tests + 40 splitter tests + 34 extractor tests + 35 prior tests
+ check_project_health = 139 total (R5 initial run). NOTE: R5 was later found
to have blocking issues by Codex audit; see R5.1 below.

### Status

R5 initial commit and push succeeded, but R5 was found BLOCKED by Codex
local-only audit. See R5.1 for fixes.

## R5.1 — Fix R5 CLI Import and Dataset ID Mapping

### Goal

Fix the blocking issues found by Codex R5 local-only audit.

### Blocking Issues

Codex found that the R5 CLI scripts failed when executed directly because
`bpc_hybrid` was not importable from script execution. Codex also found that
the prototype dataset categories were present but did not match the required
source-id mapping.

### Scope

- Fix direct CLI imports for `scripts/run_rule_baseline.py`
- Fix direct CLI imports for `scripts/evaluate_multi_clause.py`
- Update prototype sample IDs to match the required R5 audit mapping
- Update gold annotations accordingly
- Strengthen evaluator tests for CLI execution and dataset ID mapping
- Re-run evaluator tests
- Re-run full pytest
- Re-run health script
- Re-run the evaluation command

### Dataset Boundary

The R5/R5.1 dataset remains synthetic prototype data only. It is not GDPR
data, not BPMN data, not Sun-aligned data, and not a formal benchmark.

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| CLI import failure | Direct execution of `scripts/run_rule_baseline.py` and `scripts/evaluate_multi_clause.py` failed with `ModuleNotFoundError: No module named 'bpc_hybrid'` | Direct script execution did not include the project `src/` directory in `sys.path` | Added project-local `src/` path insertion before importing `bpc_hybrid` | Direct CLI commands passed; evaluator tests passed; full pytest passed |
| Dataset ID mapping mismatch | Codex audit found required prototype categories under different source IDs | R5 synthetic prototype categories existed but did not follow the required audit mapping | Updated `legal_sentences.jsonl` and `gold_multiclause.jsonl` to match required IDs such as `d13`, `d12`, `d27`, `d34`, `d05`, `d28`, and `d35` | Dataset mapping tests passed; gold validation passed; evaluation command succeeded |
| Prior success claim became inaccurate after audit | R5 originally reported 139/139 tests passed, but Codex local audit found 136 passed / 3 failed | Direct CLI tests failed in Codex environment due import path behavior | Fixed CLI import behavior and strengthened tests | Re-ran py_compile, evaluator tests, full pytest, health script, direct CLI commands, and evaluation command |

### Non-goals

- No R6 LLM fallback
- No real GDPR data
- No real BPMN models
- No Sun-aligned dataset
- No formal benchmark
- No AP/MAP comparison
- No claim of outperforming Sun
- No compliance checking
- No over-compliance detection

### Status

Completed after direct CLI execution, evaluator tests, full pytest, health
script, evaluation command, commit, and GitHub push succeeded.
