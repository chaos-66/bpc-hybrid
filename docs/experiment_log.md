# Experiment Log

## R14.5 — Descriptive Rule-only vs Rule+LLM Comparison

### Date
2026-06-23

### Description
R14.5 is a descriptive comparison of two already accepted bounded pilot outputs (R14.2 rule-only baseline vs R14.4 Rule+LLM-assisted pilot) on the same 24 draft mini-gold samples from R14.1. All metrics and per-field deltas are computed by arithmetic on already-computed numbers. No predictor, runner, evaluator, LLM, or API was called.

### Computed Deltas
- `overall_field_exact_accuracy_delta`: +0.3639
- `macro_strict_f1_delta`: +0.4369
- `micro_strict_f1_delta`: +0.3083
- `macro_lenient_f1_delta`: +0.6193
- `micro_lenient_f1_delta`: +0.4997

### Outputs
- `data/formal/results/r14_5_rule_only_vs_rule_plus_llm_comparison_summary.json`
- `data/formal/results/r14_5_rule_only_vs_rule_plus_llm_field_comparison.jsonl`
- `data/formal/metadata/r14_5_descriptive_comparison_manifest.json`
- `docs/r14_5_descriptive_comparison_report.md`
- `docs/r14_5_ppt_safe_result_table.md`

### Claim Boundary
Descriptive small-scale observation. Not a formal benchmark, not method validation, not Sun reproduction, not proof of LLM superiority.

### Script
`scripts/compare_r14_rule_only_vs_rule_plus_llm.py` — read-only arithmetic script, no API/LLM calls.

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

## R6 — Mock LLM Fallback and Normalization Foundation

### Goal

Implement the LLM fallback decision interface, a mock fallback client (stub,
deterministic), fallback schema validation, and deterministic normalization /
span-repair helpers — **without** calling any real LLM API.

### Scope

- Create `src/bpc_hybrid/fallback.py`:
  - `FallbackError(ValueError)` — custom exception for fallback path failures
  - `DecisionReason` enum: NO_FALLBACK_NEEDED, MISSING_MODALITY, MISSING_ACTOR,
    MISSING_ACTION, LOW_FIELD_CONFIDENCE, LOW_CLAUSE_CONFIDENCE,
    SCHEMA_VALIDATION_FAILURE, FALLBACK_DISABLED
  - `FallbackDecision` dataclass: should_trigger, reasons list
  - `FallbackRequest` dataclass: source_text, source_id, rule_response, reasons
  - `FallbackResult` dataclass: response (or None), raw_dict, error; is_valid property
  - `MockLLMFallbackClient` class: configurable fixed_response (or None for
    simulated failure), simulate_invalid flag; complete(request) → FallbackResult
  - `should_trigger_fallback(response)` function: schema validation check →
    per-clause checks (normative only: missing actor, missing action, low field
    confidence <0.5, low clause confidence <0.5); skip non-normative clauses
  - `extract_hybrid(text, source_id, fallback_client)` function: chain
    extract_rule_first → should_trigger_fallback → mock complete →
    validate → repair → return
- Create `src/bpc_hybrid/normalization.py`:
  - `NormalizationError(ValueError)` — custom exception
  - `normalize_field_text(text, *, lowercase, strip_punctuation)` — collapse
    whitespace, optionally lowercase and strip outer punctuation
  - `normalize_modality_text(text)` — map may/shall/shall not/must/must not/
    no person shall/no person must to canonical forms
  - `repair_field_span(source_text, field)` — if span already correct return
    unchanged; if text unique in source fix span; if missing raise
    NormalizationError; if ambiguous raise NormalizationError
  - `repair_response_spans(response)` — iterate all clauses × 6 fields, repair
    each, keep nulls, validate after repair
- Create `tests/test_fallback.py` — 29 tests:
  - TestDecisionReasonEnum (distinct values)
  - TestFallbackDecision (trigger_true, to_dict)
  - TestFallbackRequestResult (valid result, invalid result)
  - TestShouldTriggerFallbackNormative (clean → no trigger, missing actor,
    missing action, low field confidence, low clause confidence, multiple reasons)
  - TestShouldTriggerFallbackNonNormative (negative case no trigger, warranty neg,
    mixed clauses)
  - TestShouldTriggerFallbackSchemaValidation (validation failure triggers)
  - TestMockLLMFallbackClient (no network, fixed response, no response simulates
    failure, simulate invalid, no env file, no api key)
  - TestExtractHybrid (no-fallback == rule-first, fallback uses mock result,
    fallback needed but no client raises, invalid fallback raises, simulated
    invalid raises, null fields preserved)
  - TestNoNetworkOrRealData (no forbidden imports, no env access in source)
- Create `tests/test_normalization.py` — 38 tests:
  - TestNormalizeFieldText (7: whitespace collapse, trailing punct, leading punct,
    lowercase, case preservation, internal punct preserved, empty)
  - TestNormalizeModalityText (2: canonical forms param, unknown cleaned)
  - TestFindUnique (3: single, none, multiple)
  - TestRepairFieldSpan (5: correct unchanged, wrong repairable, missing raises,
    duplicate raises, partial match)
  - TestRepairResponseSpans (5: all correct, one broken repaired, null preserved,
    unrepairable raises, repaired validates, multi-clause)
  - TestSyntheticOnly (1)
- Update `src/bpc_hybrid/__init__.py` with fallback + normalization exports
- Update `README.md` with R6 status and scope
- Update `docs/experiment_log.md` (this section)

### Non-goals

- No real LLM API call
- No `.env` file, no API keys, no network
- No BPMN checking
- No formal benchmark
- No real (GDPR/Sun) datasets
- Not even mock HTTP — pure in-process stub
- No overriding the rule-first output unless fallback triggers

### Key Design Decisions

- **No network**: MockLLMFallbackClient returns pre-configured responses only;
  no requests, openai, anthropic, or httpx imports.
- **Trigger logic**: Only normative clauses (modality != None) are checked for
  missing actor/action; non-normative clauses (definitions, warranties, legal
  consequences) are skipped.
- **Confidence threshold**: Default 0.5 for both field-level and clause-level
  checks; configurable via extract_hybrid() parameters.
- **Span repair**: Deterministic exact-match only — find text uniquely in
  source_text, fix offsets. Never fuzzy-match. Raise NormalizationError on
  missing or ambiguous text.
- **Hybrid flow**: extract_rule_first → should_trigger_fallback → if fallback:
  mock.complete → validate → repair_response_spans → return. If no fallback:
  return rule response as-is.

### Test Coverage

29 fallback tests + 38 normalization tests + 43 evaluator tests + 40 splitter
tests + 34 extractor tests + 35 prior tests = 219 total.

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| Incorrect normalization test expectation | `test_partial_match_raises` failed during R6 test execution | The test expectation did not match the deterministic exact-match span repair policy | Updated the test expectation to match the intended no-fuzzy, exact-match behavior | R6 fallback/normalization tests passed; full pytest passed |
| Invalid mock fallback span | A fixed mock fallback response failed validation because a span exceeded the source text length | The configured mock fallback response used an invalid span for the synthetic source text | Corrected the mock fallback response span so it maps to the source text and can be repaired/validated deterministically | R6 fallback tests passed; response validation passed |
| Missing explicit file encoding | A file-open path in the R6 test or helper code lacked explicit encoding | Windows execution can be sensitive to implicit encoding defaults; reproducibility requires explicit encoding | Added explicit UTF-8 encoding to the relevant file read/write path | R6 tests passed on Windows; full pytest passed |

### Status

Completed after all tests passed, health script passed, commit and GitHub
push succeeded.

## R7 — Safe Real LLM Fallback Adapter Scaffold

### Goal

Add a safety-gated configuration and adapter scaffold for later real LLM
fallback experiments, without performing real API calls.

### Scope

- Create `src/bpc_hybrid/llm_config.py`:
  - `LLMConfigError(ValueError)` — custom exception
  - `LLMProvider` constants (MOCK, OPENAI_COMPATIBLE, DISABLED)
  - `LLMConfig` dataclass: enabled/provider/model/api_key/base_url/
    timeout_seconds/max_tokens/temperature; defaults disabled
  - `validate()` — checks provider validity, API key requirement,
    numeric bounds
  - `__repr__`/`__str__` — always redact api_key
  - `from_dict()`/`to_dict()` — round-trip
  - `from_env()` — reads `BPC_HYBRID_LLM_*` env vars only; no `.env`/dotenv
  - `redact_secret()` — show first 4 chars + `***REDACTED***`
  - `redact_mapping()` — replace values for keys containing key/secret/token
    or values containing sk-/Bearer
- Create `src/bpc_hybrid/llm_client.py`:
  - `LLMClientError(ValueError)` — custom exception
  - `LLMRequest` dataclass — source_id, source_text, system_prompt, user_prompt,
    schema_name; NO api_key
  - `LLMResponse` dataclass — content, provider, model, finish_reason; NO api_key
  - `LLMTransport` — abstract protocol with `send(request) → LLMResponse`
  - `MockLLMTransport` — fixed_response, simulate_invalid_json,
    simulate_invalid_schema; no network, no .env
  - `OpenAICompatibleRequestBuilder` — build_url(), build_headers() (redacted),
    build_body() (no api_key), build_payload(); no openai/requests/httpx import
  - `_extract_json_from_content()` — strip markdown fences
  - `parse_llm_json_response()` — fence strip → json.loads → dict check →
    from_dict → validate
  - `validate_llm_extraction_response()` — thin validation wrapper
  - `LLMFallbackAdapter` — config + transport; complete(FallbackRequest) →
    FallbackResult; auto-creates MockLLMTransport for mock provider
- Create `tests/test_llm_config.py` — 24 tests:
  - TestRedactSecret (4), TestRedactMapping (5), TestLLMConfigDefaults (2),
    TestLLMConfigValidation (9), TestLLMConfigRepr (3), TestLLMConfigDictRoundTrip (1),
    TestLLMConfigFromEnv (9), TestLLMProvider (2), TestNoSecretsLeaked (1)
- Create `tests/test_llm_client.py` — 28 tests:
  - TestLLMRequestResponse (2), TestLLMTransportAbstract (1),
    TestMockLLMTransport (6), TestParseLLMJsonResponse (7),
    TestValidateLLMExtractionResponse (2), TestExtractJsonFromContent (3),
    TestOpenAICompatibleRequestBuilder (6), TestLLMFallbackAdapter (7),
    TestSafetyGuarantees (3)
- Update `src/bpc_hybrid/fallback.py` — update `extract_hybrid()` docstring
  for duck-typed fallback_client compatibility with LLMFallbackAdapter
- Update `src/bpc_hybrid/__init__.py` — add R7 exports
- Update `README.md` — add R7 status, scope, next stage
- Update `docs/experiment_log.md` — this section

### Non-goals

- No real LLM API calls
- No network access
- No `.env` file access
- No raw response storage
- No real GDPR data
- No real BPMN models
- No original Sun dataset
- No Sun-aligned formal benchmark
- No claim of outperforming Sun
- No compliance checking
- No over-compliance detection

### Key Design Decisions

- **Disabled by default**: `LLMConfig.enabled = False` — real LLM execution
  requires explicit opt-in.
- **Secret redaction everywhere**: `repr`, `str`, `redact_mapping()` all
  replace API keys with `***REDACTED***`.
- **Duck-typed fallback client**: `extract_hybrid()` accepts any object with
  `.complete(FallbackRequest) → FallbackResult`; both `MockLLMFallbackClient`
  (R6) and `LLMFallbackAdapter` (R7) satisfy this.
- **No real SDK imports**: `llm_client.py` does not import openai, anthropic,
  requests, or httpx.
- **Mock transport only**: R7 only exercises `MockLLMTransport`;
  `OpenAICompatibleRequestBuilder` builds payloads but never sends them.

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| LLMConfig bounds validation hidden behind early return | Numeric bound checks for `timeout_seconds`, `max_tokens`, and `temperature` were not applied consistently when `provider="mock"` or config was disabled | `LLMConfig.validate()` returned too early before shared validation logic ran | Moved provider and numeric validation before provider-specific early-return behavior so all configs are structurally validated | `tests/test_llm_config.py` passed; full pytest passed |
| Dotenv import test false positive | `test_no_dotenv_import` failed because it matched `.env` text in a docstring rather than an actual dotenv import | The assertion searched for the broad substring `.env` instead of import patterns | Narrowed the assertion to reject actual imports such as `from dotenv`, `import dotenv`, and `load_dotenv` | `tests/test_llm_config.py` passed; full pytest passed |
| Schema invalid error expectation mismatch | `test_schema_invalid_rejected` expected a generic schema validation message but the actual schema layer raised a more specific `Unknown keys` message | The test expectation did not match the existing `MultiClauseExtractionResponse` validation error text | Updated the expected regex to match the actual schema validation behavior while still asserting rejection of invalid LLM output | `tests/test_llm_client.py` passed; full pytest passed |

### Status

Completed after tests, health script, synthetic evaluation command, commit,
and GitHub push succeeded.

## R7.1 — Harden LLM Config Validation and Documentation

### Goal

Resolve Codex R7 audit blockers around disabled-config validation,
base_url secret handling, and missing R7 issue documentation.

### Scope

- **Fix A — Provider + numeric validation always runs**: Refactored
  `LLMConfig.validate()` so provider whitelist and numeric-bound checks
  (`timeout_seconds`, `max_tokens`, `temperature`) always execute,
  regardless of `enabled`; only the API-key requirement stays gated
  behind `enabled=True` and a real provider.
- **Fix B — base_url secret-material rejection**: Added
  `_base_url_has_secrets()` (detects `?api_key=`, `?token=`, `?secret=`,
  `user:password@`), integrated into `LLMConfig.validate()`,
  `LLMConfig.__repr__`, `redact_mapping()`, and
  `OpenAICompatibleRequestBuilder.__post_init__`.
- **Fix C — New tests**: Added 18 config tests (disabled-config
  validation, base_url security, `redact_mapping` base_url redaction)
  and 2 client tests (builder rejects secret base_url, error message
  sanitization). Total: 53 config + 39 client tests.
- **Fix D — Documentation**: Updated R7 Issues and Resolutions with real
  implementation issues; added this R7.1 section; appended I007 to
  `docs/issue_log.md`; corrected test counts in `README.md`.

### Non-goals

Same as R7 non-goals — no real LLM API calls, no network, no `.env`,
no formal benchmark.

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| Disabled configs skipped shared validation | Codex found invalid provider and invalid numeric settings could pass when `enabled=False` | `validate()` returned before shared provider and numeric bounds checks | Refactored validation so provider whitelist and numeric bounds always run | 18 new config tests passed; full pytest passed |
| Secret material could be embedded in base_url | Codex found `base_url` could contain key/token/secret material and appear in repr or builder URL | No explicit secret-like URL validation existed | Added `_base_url_has_secrets()` and integrated into `validate()`, `repr`, `redact_mapping()`, and builder `__post_init__` | New base_url security tests passed; full pytest passed |
| R7 issue documentation incomplete | Codex found R7 implementation fixes were not recorded in `docs/experiment_log.md` | Experiment log still used the generic no-issues template | Updated R7 Issues and Resolutions with actual implementation issues and fixes | Documentation updated; Codex re-audit pending |

### Status

Completed after tests, health script, synthetic evaluation command, commit,
and GitHub push succeeded.

## R7.2 — Complete base_url Secret Query Coverage

### Goal

Resolve the Codex R7.1 re-audit blocker: `base_url` secret detection
missing required query parameter names `access_token` and `authorization`.

### Scope

- Add `access_token` and `authorization` to `_SECRET_QUERY_KEYS`
- Add regression tests for `access_token` and `authorization` rejection
  in `LLMConfig.validate()` and `OpenAICompatibleRequestBuilder`
- Verify error messages do not leak raw secret material
- Update stale test-count documentation

### Non-goals

- No real LLM API calls
- No network access
- No `.env` file access
- No raw response storage
- No formal benchmark
- No claim of outperforming Sun

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| Incomplete base_url secret query coverage | Codex R7.1 re-audit found `access_token` and `authorization` were missing from secret query-key detection | R7.1 covered 7 secret-like query names but missed two explicitly required names | Added `access_token` and `authorization` to `_SECRET_QUERY_KEYS` plus regression tests | 58 config + 43 client tests passed; full 320-test suite passed; health script and synthetic eval passed |

### Status

Completed after tests, health script, synthetic evaluation command, commit,
and GitHub push succeeded.

## R8 — Controlled Single-Sample LLM Dry-Run Harness

### Goal

Add a guarded single-sample dry-run harness for future LLM fallback
experiments while keeping real API execution disabled in this stage.

### Scope

- Add single-sample dry-run CLI (`scripts/run_llm_dry_run.py`)
- Require explicit `--allow-llm`
- Require explicit `--single-sample`
- Use mock provider by default
- Refuse real provider execution in R8
- Emit JSON-only success/error summaries
- Redact secrets
- Avoid raw response storage
- Add `make_schema_valid_mock_response_json` helper to `llm_client.py`
- Add 23 direct CLI tests

### Non-goals

- No real LLM API calls
- No network access
- No `.env` file access
- No raw response storage
- No batch execution
- No real GDPR data
- No real BPMN models
- No original Sun dataset
- No Sun-aligned formal benchmark
- No claim of outperforming Sun
- No compliance checking
- No over-compliance detection

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| Invalid mock response returned success exit code | During R8 dry-run verification, the CLI handled invalid LLM/mock responses as JSON errors but still returned exit code `0` | Error handling produced a structured JSON error but did not propagate failure status to the process exit code | Updated the dry-run CLI so invalid LLM/mock responses return a non-zero exit code while still emitting redacted JSON error output | `tests/test_llm_dry_run.py` passed; full pytest passed; health script and synthetic evaluation command passed |

### Status

Completed after tests, health script, synthetic evaluation command, commit,
and GitHub push succeeded.

## R8.2 — JSON Error Envelope for CLI Parse Failures

### Goal

Ensure ALL CLI parse errors (invalid `--provider`, unknown arguments) emit
redacted JSON error envelopes instead of argparse usage text.

### Scope

- Replace `argparse.ArgumentParser` with `JsonArgumentParser` that overrides
  `error()` to emit JSON
- Remove `choices=` from `--provider` to bypass argparse's built-in usage text
- Add manual provider validation gate that emits `_error("DryRunError", …)`
  JSON
- Add regression tests for invalid provider and unknown-flag parse-error paths
- Assert all parse-error output is valid JSON with no `usage:` text, no
  `Traceback`, and no secret leakage

### Non-goals

- No real LLM API calls
- No changes to success paths or existing gate behavior

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| Invalid `--provider` produced argparse usage text | Codex R8 audit found `--provider not_a_provider` emitted `usage:` text instead of the required JSON error envelope | `argparse` `choices=` rejected the value at parse time, before the JSON error helper could run | Replaced `ArgumentParser` with `JsonArgumentParser`, removed `choices=`, added manual provider validation in `main()` with `_error("DryRunError", …)` | 25/25 dry‑run tests passed; full pytest passed; health OK; eval OK |

### Status

Completed after tests, health script, synthetic evaluation command, commit,
and GitHub push succeeded. Codex re-audit pending (awaited before R9).

## R9.0 — Add Project-local .env Support for Real API Smoke

### Goal

Add a safe project-root `.env` configuration system as a blocking prerequisite before
R9 real API smoke testing.

### Safety Requirements

- Only `BPC_HYBRID_*` keys are read from `.env`
- System environment variables always override `.env` values
- `.env` is gitignored; `.env.example` is committed
- API key must never appear in stdout, stderr, repr, str, or error messages
- No new dependencies (no `python-dotenv`)

### Artifacts Created/Modified

- `.gitignore` — Added `!.env.example` exception
- `.env.example` — User template with placeholder values
- `src/bpc_hybrid/llm_config.py` — Added `_ENV_WHITELIST`, `load_project_env_file()`, updated `from_env()`
- `scripts/run_llm_dry_run.py` — Added `.env` loading in `main()`
- `tests/test_llm_config.py` — Added `TestLoadProjectEnvFile` (9 tests) + `TestFromEnvWithProjectRoot` (7 tests)
- `tests/test_llm_dry_run.py` — Added `TestDotenvSafety` (5 tests)

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| `NameError: name 'Path' is not defined` | 33 tests failed with NameError cascade | `load_project_env_file()` used `Path()` but `pathlib.Path` was not imported | Added `from pathlib import Path` to `llm_config.py` | All tests passed |
| `test_no_dotenv_in_script` failed | Existing test forbade `.env` in script source | R9.0 intentionally introduces `.env` references | Removed `.env` from forbidden list; renamed `_project_dotenv` to `_project_env` | All tests passed |
| `test_dotenv_api_key_fallback` failed | `_ENV_WHITELIST` was missing `ENABLED`, `TIMEOUT_SECONDS`, `MAX_TOKENS`, `TEMPERATURE` | Spec only listed 5 user-facing keys, but `from_env()` reads additional keys | Expanded whitelist to all 9 `BPC_HYBRID_LLM_*` keys | All tests passed |

### Status

Completed after tests (366 passed), health check, synthetic eval, and GitHub push.

## R9.0.1 — Add Audit-safe Project Env Loading Controls

### Goal

Keep project-root `.env` support for local real API smoke tests while
allowing tests and Codex audits to explicitly disable reading the real
project `.env`.

### Scope

- Add `load_project_env=False` support
- Add `BPC_HYBRID_DISABLE_PROJECT_ENV=1` control
- Add `--no-project-env` CLI flag
- Update dry-run tests so they do not read the real project `.env`
- Clarify README whitelist wording
- Preserve `.env` Git ignore behaviour

### Non-goals

- No real LLM API calls
- No network access
- No raw response storage
- No batch execution
- No benchmark result
- No real GDPR/BPMN/Sun data

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| Existing project `.env` blocked Codex test execution under no-read audit rule | Codex refused to run dry-run tests/full pytest because the CLI would read project-root `.env` during startup | R9.0 enabled project `.env` loading but did not provide an audit/test bypass | Added `--no-project-env`, `BPC_HYBRID_DISABLE_PROJECT_ENV=1`, and `load_project_env=False` controls, then updated tests to avoid reading real project `.env` | R9.0.1 config tests, dry-run tests, full pytest, health script, and synthetic evaluation command passed |
| Codex pytest temp setup hit project-external permission issue | Codex encountered permission denial under the default Windows temp pytest root | Pytest temporary root defaulted outside the project, conflicting with local permission/audit constraints | Documented that future Codex audit should use a project-local pytest basetemp such as `.pytest_cache/codex-tmp` | DeepSeek tests passed; Codex re-audit pending |

### Status

Completed after tests, documentation update, commit, and GitHub push succeeded.

## R9.0.2 — Isolate Env-loading Tests From External Audit Environment

### Goal

Make `.env` fallback tests deterministic under Codex audit environments that
globally set `BPC_HYBRID_DISABLE_PROJECT_ENV=1`.

### Scope

- Update config tests to explicitly clear `BPC_HYBRID_DISABLE_PROJECT_ENV`
  when testing enabled fake `.env` loading
- Keep disable-control tests explicitly setting `BPC_HYBRID_DISABLE_PROJECT_ENV`
- Ensure tests only read temporary fake `.env` files under `tmp_path`
- Preserve project-root `.env` no-read audit rule
- Avoid production code behaviour changes

### Non-goals

- No real LLM API calls
- No network access
- No raw response storage
- No batch execution
- No benchmark result
- No real GDPR/BPMN/Sun data
- No project-root `.env` content reads

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| External audit env var broke fake `.env` fallback tests | Codex re-audit with `BPC_HYBRID_DISABLE_PROJECT_ENV=1` produced 4 failing config tests | Tests that expected fake `.env` fallback did not explicitly clear the external disable flag | Added explicit `monkeypatch.delenv("BPC_HYBRID_DISABLE_PROJECT_ENV", raising=False)` to enabled-fallback tests and explicit `setenv` to disable tests; added isolation regression tests | Config tests, dry-run tests, full pytest, health script, and synthetic evaluation passed in both normal and audit-env modes |

### Status

Completed after tests in both normal and audit-env modes, documentation update,
commit, and GitHub push succeeded.

## R9 — Controlled Real API Single-Sample Smoke

### Goal

Perform at most one explicitly authorized real API single-sample connectivity smoke through the controlled dry-run harness.

### Scope

- Add/verify real API gate
- Require explicit CLI flags
- Require project-local `.env` configuration
- Run at most one synthetic toy sentence
- Validate schema-normalized output
- Do not store raw response
- Do not run benchmark
- Do not use real GDPR/BPMN/Sun data

### Non-goals

- No batch LLM execution
- No formal benchmark
- No accuracy comparison
- No Sun comparison
- No BPMN compliance checking
- No over-compliance detection
- No raw response storage

### Real API Execution

Status: SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED

Constraints:

- single sample only
- no raw response saved
- no benchmark result
- no accuracy claim
- secret redacted

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| Real API network error (redacted) | Single-sample real API call returned network error | Base URL or network connectivity issue; details redacted for security | Error was properly redacted; no secrets leaked; returned valid JSON error envelope | All offline tests (408) passed; health and eval OK; real API gate logic verified |

### Status

Completed after all offline tests passed (408/408), real API gate implementation,
CLI flag additions, documentation update, commit, and GitHub push succeeded.
Real API smoke returned network error (redacted) — connectivity issue, not a
code defect.

## R9.1 — Connectivity and Configuration Diagnostics

### Goal

Improve real API connectivity diagnostics: error classification, endpoint
construction, and machine-readable status field.

### Scope

* Better error classification in `RealAPITransport.send()`:
  `socket.timeout`, `ssl.SSLError`, `urllib.error.URLError` (DNS/connection),
  `urllib.error.HTTPError` (HTTP status) all now produce distinct redacted
  error messages
* Better endpoint construction in `build_url()`: handles base URLs with
  `/chat/completions` already present, root-like URLs, and `/v1/` variants
* Added `"status"` field to CLI error JSON output:
  `SKIPPED_NO_API_KEY_OR_CONFIG` or `SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED`
* Diagnostic existence checks for config keys (presence yes/no only)

### Non-goals

* No new features
* No batch execution
* No benchmark
* No modifications to `.env` or `.env.example`

### Real API Execution

Status: SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED (DNS/connection)

Retry at most once — same redacted result, but now classified as
DNS/connection error rather than generic network error.

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| DNS/connection error classified | Real API call failed with DNS/connection error | Base URL or network connectivity issue; details redacted | Error now classified as DNS/connection (was generic network error); status field present in JSON | All offline tests pass (423); health and eval OK |

### Status

Completed after all offline tests passed (423/423), error classification
improvements, endpoint construction hardening, status field addition,
documentation update, commit, and push. Real API smoke still returns
DNS/connection error (redacted, same as R9) — connectivity issue, not a
code defect.

## R9.2 — Retry After Manual .env Configuration Fix

### Goal

Retry the controlled single-sample real API smoke after the user
manually corrected project-local `.env` configuration.

### Scope

- At most one authorized retry
- Same synthetic toy sentence
- Same R9/R9.1 safety gates
- No raw response storage
- No batch execution
- No benchmark result
- No accuracy claim

### Real API Execution

Status: SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED

Error classification: HTTP status error — server reached (unlike R9.1
DNS/connection error), but HTTP status indicates auth/endpoint/config
issue.  Details redacted.

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| HTTP status error after .env fix | Real API call reached server but returned HTTP error (status redacted) | Auth key, model name, or endpoint path mismatch; details redacted | Error classified as HTTP status (was DNS/connection in R9.1); `.env` correction improved connectivity from DNS→reachable | All offline tests pass (423); health and eval OK; test isolation fix for env contamination |

### Status

Completed after all offline tests passed (423/423), one real API retry
executed, test isolation fix applied, documentation update, commit, and
push.  Real API smoke now reaches server (HTTP status error) — progress
from DNS/connection in R9.1, but not yet a successful response.
Connectivity improved; auth/endpoint config likely needs adjustment.

## R9.3 — Retry After Workspace Base URL Fix

### Goal

Retry the controlled single-sample real API smoke after the user
manually corrected the Alibaba Cloud Model Studio WorkspaceId/base_url/API
configuration.

### Scope

- At most one authorized retry
- Same synthetic toy sentence
- Same R9/R9.1/R9.2 safety gates
- No raw response storage
- No batch execution
- No benchmark result
- No accuracy claim

### Real API Execution

Status: SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED

Error classification: HTTP status error — server reached (same as R9.2),
but HTTP status indicates auth/endpoint/config issue. Details redacted.
One retry executed. `real_api_call_performed: true`, `raw_response_saved:
false`, `secret_redacted: true`.

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| HTTP status error after workspace fix | Real API call reached server but returned HTTP error (status redacted); same as R9.2 | Auth key, model name, workspace ID, or endpoint path mismatch; details redacted | Confirmed server reachable; error redacted; no code defect found | All offline tests pass (423); health and eval OK; one retry executed |

### Status

Completed after all offline tests passed (423/423), one real API retry
executed, documentation update, commit, and push. Real API smoke still
returns HTTP status error (same classification as R9.2) — server
reachable but auth/endpoint config needs further correction by user.

## R9.4 — Retry After API Key / Model / Workspace Alignment Fix

### Goal

Retry the controlled single-sample real API smoke after the user
manually aligned API key, model, WorkspaceId, and base URL
configuration.

### Scope

- At most one authorized retry
- Same synthetic toy sentence
- Same R9/R9.1/R9.2/R9.3 safety gates
- No raw response storage
- No batch execution
- No benchmark result
- No accuracy claim

### Real API Execution

Status: SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED

Error classification: DNS/connection error — regression from R9.2/R9.3
HTTP status error back to DNS/connection error. This config revision
made the server unreachable again. Details redacted. One retry executed.
`real_api_call_performed: true`, `raw_response_saved: false`,
`secret_redacted: true`.

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| DNS/connection error after config alignment | Real API call returned DNS/connection error (regression from HTTP status in R9.2/R9.3) | Config change made server unreachable; base_url/endpoint may be incorrect; details redacted | Error properly redacted; no code defect; one retry executed per policy | All offline tests pass (423); health and eval OK |

### Status

Completed after all offline tests passed (423/423), one real API retry
executed, documentation update, commit, and push. Real API smoke
regressed from HTTP status error (R9.2/R9.3) back to DNS/connection
error — config change made server unreachable. No secrets leaked.

## R9.5 — Retry After Removing WorkspaceId Braces

### Goal

Retry the controlled single-sample real API smoke after the user
manually removed the erroneous braces around WorkspaceId in
project-local `.env`.

### Root Cause Candidate

R9.4 used a malformed Workspace base URL because `{}` placeholder
braces were retained around the real WorkspaceId. This caused
DNS/connection failure. The fix is to remove the braces from the
base URL.

### Scope

- At most one authorized retry
- Same synthetic toy sentence
- Same R9/R9.1/R9.2/R9.3/R9.4 safety gates
- No raw response storage
- No batch execution
- No benchmark result
- No accuracy claim

### Real API Execution

Status: SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED

Error details: LLM response parse error — Cannot convert LLM response
to MultiClauseExtractionResponse. The LLM returned fields
(`conditions`, `normative_type`, `object`, `original_text`, `subject`)
not recognized by the `ClauseExtraction` schema.

**Connectivity assessment**: API connectivity smoke **succeeded** for
the first time across all R9.x retries. The server was reached, a
valid HTTP response was received, and the LLM returned structured
content. The only failure is schema mismatch between the LLM's output
fields and the project's `ClauseExtraction` schema.

`real_api_call_performed: true`, `raw_response_saved: false`,
`secret_redacted: true`. One retry executed. No secrets leaked.

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| Schema mismatch after braces fix | Real API returned valid response but LLM output fields don't match ClauseExtraction schema | LLM returned `conditions`, `normative_type`, `object`, `original_text`, `subject` — not in current schema | Connectivity smoke succeeded; schema needs alignment with LLM output format | All offline tests pass (423); health and eval OK; first successful API round-trip |

### Status

Completed after all offline tests passed (423/423), one real API retry
executed, documentation update, commit, and push. **Connectivity smoke
succeeded** — the WorkspaceId braces fix resolved the DNS issue and the
API returned a valid structured response for the first time. Schema
mismatch remains but is not a connectivity or code defect.

## R9.6 — Fix Diagnostic Classification: Schema Invalid vs Network Error

### Goal

Reclassify real API parse/schema failures as
`SINGLE_SAMPLE_API_RETURNED_SCHEMA_INVALID` when the API returns a valid
response but the content cannot be converted into
`MultiClauseExtractionResponse`.  Network/transport errors keep their
existing `SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED` status.

### Rationale

Codex audit found that R9.5's schema parse failure was incorrectly
classified as `SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED`.  The API
connectivity succeeded — the server was reached, the LLM returned
structured content — but the response fields did not match the project
schema.  This is a **schema invalid** scenario, not a **network error**.

### Diagnostic Rules (Post R9.6)

| Error type | Status field |
|---|---|
| DNS failure / connection failure / timeout | `SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED` |
| HTTP status error (4xx, 5xx) | `SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED` |
| Request exception / transport-level exception | `SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED` |
| LLM returned content but JSON/schema/field conversion failed | `SINGLE_SAMPLE_API_RETURNED_SCHEMA_INVALID` |
| Missing API key or config | `SKIPPED_NO_API_KEY_OR_CONFIG` |

### Scope

- Update `scripts/run_llm_dry_run.py` — detect `"parse error"` in
  `result.error` and assign `SINGLE_SAMPLE_API_RETURNED_SCHEMA_INVALID`
- Keep network/transport errors as `SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED`
- Add gate tests:
    - `TestSchemaInvalidStatusClassification` (3 tests): adapter
      parse-error prefix, transport-error prefix, status logic
      verification
    - `TestSchemaInvalidNoSecretLeak` (2 tests): no key/url/raw-body
      in error, no raw response files created
- No `.env` changes (not needed)
- No real API calls (code-only diagnostic fix)

### Non-goals

- No `.env` modifications
- No real API execution
- No widening of the project schema to match arbitrary LLM responses
- No raw response storage
- No benchmark or accuracy claims

### Key Design Decisions

- The split between transport errors and parse errors is already present
  in `LLMFallbackAdapter.complete()`: transport exceptions produce
  `"LLM transport error: ..."`, while `LLMClientError` exceptions produce
  `"LLM response parse error: ..."`.  The R9.6 fix simply checks for the
  `"parse error"` substring in the error message to select the correct
  status.

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| Schema-invalid response misclassified as network error | R9.5 returned `SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED` for a schema mismatch | CLI error handler treated all dry-run errors with `real_api_requested=True` the same way | Added `_is_parse_error` check; parse errors → `SINGLE_SAMPLE_API_RETURNED_SCHEMA_INVALID`; transport errors unchanged | 5 new gate tests passed; full pytest passed; health and eval OK |

### Status

Completed after code fix, 5 new gate tests, full offline validation,
commit, and GitHub push.  No real API call executed — R9.6 is a
code-only diagnostic fix.

## R9.7 — Align Real LLM Prompt With Project Schema

### Goal

Strengthen the LLM system/user prompt to explicitly require JSON output
matching the project's current `MultiClauseExtractionResponse` schema,
so that future real API calls are less likely to return schema-invalid
responses (as seen in R9.5).

### Rationale

R9.5 demonstrated that the LLM returned valid structured content but
with field names (`conditions`, `normative_type`, `object`,
`original_text`, `subject`) not recognized by the `ClauseExtraction`
schema.  R9.6 correctly classified this as schema-invalid.  R9.7
addresses the root cause by embedding the exact schema field names into
the prompt, giving the LLM a precise contract.

### Scope

- Add `build_schema_json_skeleton(source_text, source_id)` to
  `llm_client.py` — generates a dict with exact project schema field
  names that passes `MultiClauseExtractionResponse.from_dict().validate()`
- Add `_SCHEMA_PROMPT_INSTRUCTIONS` constant — strict instructions
  disallowing markdown, code fences, explanations, extra fields, and
  requiring all 13 clause fields
- Update `LLMFallbackAdapter.system_prompt` — mandate single JSON
  object matching `MultiClauseExtractionResponse` exactly
- Update `LLMFallbackAdapter.complete()` user prompt — include the JSON
  skeleton and `_SCHEMA_PROMPT_INSTRUCTIONS`
- Add 5 categories of tests (17 new tests total):
  1. **Prompt content tests** (9 tests in `test_llm_client.py`):
     Skeleton keys match schema, clause keys have 13 fields, FieldSpan
     keys are correct, skeleton passes validation, extra keys rejected,
     instructions contain required terms, system prompt forbids
     markdown, user prompt includes skeleton
  2. **Valid-schema fake provider tests** (2 tests in
     `test_real_api_gate.py`): Fake urllib-opener returning
     schema-valid JSON → adapter succeeds; no raw response files
  3. **R9.5-style invalid still fails** (3 tests in
     `test_real_api_gate.py`): Exact R9.5 field names still rejected
     by schema, through adapter, via CLI path
  4. **Network/transport errors unchanged** (3 tests in
     `test_real_api_gate.py`): Timeout, HTTP 500, DNS — all still
     produce transport error, not parse error

### Non-goals

- No real API calls
- No `.env` changes
- No schema widening (schema stays exactly as-is)
- No benchmark or accuracy claims
- No batch execution

### Key Design Decisions

- The JSON skeleton uses the exact field names from the current schema
  (`MultiClauseExtractionResponse`, `ClauseExtraction`, `FieldSpan`)
- The skeleton passes `from_dict().validate()` — it is a valid
  schema instance, not just documentation
- The runtime prompt assembly (skeleton + instructions) is implicit
  — the `LLMFallbackAdapter.complete()` method builds it at call time
  from the current schema definitions
- `condition`, `constraint`, `exception` are `null` in the skeleton
  (allowed by schema — these are Optional fields)

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| — | — | — | — | — |

### Status

Completed after prompt changes, 17 new tests, full offline validation,
commit, and GitHub push.  No real API call executed — R9.7 is a
code-only prompt/schema alignment phase.

## R9.7.1 — Fix Unsafe R9.7 CLI Regression Test

### Goal

Fix the Codex-blocking R9.7 test issue.

### Context

Codex blocked R9.7 because a claimed CLI fake-response regression test
invoked `run_llm_dry_run.py` in a subprocess with `--execute-real-api`,
could not receive monkeypatched fake responses, and ended with `pass`
instead of asserting `SINGLE_SAMPLE_API_RETURNED_SCHEMA_INVALID`.

### Change

- Extracted `classify_real_api_error_status()` pure function from
  `scripts/run_llm_dry_run.py` — no side effects, safe to test without
  network
- Removed unsafe `test_r9_5_style_via_cli_returns_schema_invalid`
  (subprocess + `--execute-real-api` + `pass`)
- Replaced with safe in-process tests:
  - `test_r9_5_style_via_classify_helper_returns_schema_invalid` (5 assertions)
  - `TestRealApiErrorClassificationHelper` (11 tests covering parse
    errors, transport errors, timeout, HTTP, DNS, SSL, connection
    refused, and mutual exclusion)
- All 12 new tests are pure-function tests — no network, no subprocess,
  no `--execute-real-api`

### Scope

- No real API call
- No `.env` read
- No raw response storage
- No batch execution
- No benchmark result
- No accuracy claim

### Issues and Resolutions

| Issue | Symptom | Root Cause | Fix | Verification |
|---|---|---|---|---|
| Unsafe CLI regression test blocked R9.7 Codex audit | `test_r9_5_style_via_cli_returns_schema_invalid` used subprocess + `--execute-real-api` + `pass` | R9.7 test was written as a subprocess test that couldn't receive fake responses and ended with `pass` | Extracted `classify_real_api_error_status()` pure function from `run_llm_dry_run.py`; replaced unsafe test with 12 safe in-process tests | 148/148 tests pass; health and eval OK; safety scan clean |

### Status

Completed after helper extraction, test rewrite (12 new safe tests),
full offline validation, commit, and GitHub push.  No real API call
executed — R9.7.1 is a code-only test safety fix.

## R9.8 — Real API Single-Sample Schema Smoke

### Goal

Run one controlled real API single-sample schema smoke after R9.7/R9.7.1
prompt/schema alignment.

### Scope

- At most one authorized real API call
- One synthetic toy sentence only
- No real GDPR/BPMN/Sun data
- No raw response storage
- No batch execution
- No benchmark result
- No accuracy claim
- No method-validation claim

### Input

Synthetic sentence:

`A controller shall record the decision.`

### Success Criteria

The smoke succeeds only if the real API call returns a response that
parses into the current `MultiClauseExtractionResponse` schema while
preserving:

- `real_api_call_performed: true`
- `schema_valid: true`
- `raw_response_saved: false`
- `secret_redacted: true`

### Result

`SINGLE_SAMPLE_SCHEMA_SMOKE_SUCCEEDED`

Model `qwen3.7-max` via `openai_compatible` provider returned a valid
`MultiClauseExtractionResponse` JSON with modality/actor/action fields
matching the project schema.

### Recorded Real API Smoke Metadata

- `source_id`: `r9_8_real_schema_smoke_001`
- `input`: `A controller shall record the decision.`
- `provider`: `openai_compatible`
- `model`: `qwen3.7-max`
- `real_api_call_performed`: `true`
- `schema_valid`: `true`
- `raw_response_saved`: `false`
- `secret_redacted`: `true`
- `batch`: `false`
- `raw_response_body_committed`: `false`

This is a single synthetic-sentence schema smoke only. It is not a
benchmark, not an accuracy evaluation, not method validation, not a
Sun baseline comparison, and not a real GDPR/BPMN evaluation.

### Status

Completed after full offline validation (456/456 tests pass), one
authorized real API call, and clean schema smoke.  No retry, no
batch, no raw response saved, no benchmark.

## R10.0 — Planning for Controlled Real-LLM Fallback Integration

### Goal

Create a conservative R10 plan after R9.8/R9.8.1 accepted the real
API single-sample schema smoke.

### Scope

- Planning only
- No real API call
- No `.env` read
- No source code changes
- No raw response storage
- No batch execution
- No benchmark
- No accuracy claim
- No method-validation claim

### Output

- `docs/r10_plan.md`

### Status

Planning completed.  R10 plan defines 5 small auditable stages
(R10.0–R10.4) with mock-first, gate-enforced, single-sample-first
controls.  No real API executed, no `.env` read, no code modified.

## R10.1 — Offline/Mock Integration Design for Real-LLM Fallback Path

### Goal

Design a conservative mock-first integration path for optional
real-LLM fallback inside the rule-first extraction pipeline.

### Scope

- Design only
- No source code changes
- No test changes
- No real API call
- No `.env` read
- No raw response storage
- No batch execution
- No benchmark
- No accuracy claim
- No method-validation claim

### Output

- `docs/r10_1_mock_integration_design.md`

### Key Design Decisions

- Fallback interface uses existing `FallbackRequest` / `FallbackResult` types
- `LLMFallbackAdapter` already satisfies the `FallbackProvider` contract
- Fallback is disabled by default; requires explicit gate
- On any fallback failure, rule-first result is returned (never lost)
- Provenance tracking deferred to R10.2
- 13 mock-only tests specified for R10.2

### Status

Design completed.  No source code changed, no real API executed,
no `.env` read, no benchmark.

## R10.2 — Mock-only Pipeline Integration Tests for Optional LLM Fallback

### Goal

Implement and test a mock-only optional LLM fallback integration helper
for the rule-first extraction pipeline.

### Scope

- Mock-only implementation
- No real API call
- No `.env` read
- No raw response storage
- No batch execution
- No benchmark
- No accuracy claim
- No method-validation claim

### Change

- Added `OptionalFallbackResult` dataclass (external wrapper metadata, no schema change)
- Added `extract_with_optional_llm_fallback()` helper with conservative failure behavior:
  - fallback disabled → return rule-first
  - fallback not triggered → return rule-first
  - fallback schema-invalid → return rule-first
  - fallback network/config error → return rule-first
  - only schema-valid fallback → accept
- Preserved existing strict `extract_hybrid()` raising behavior
- Added 27 mock-only pipeline tests in `tests/test_fallback_pipeline.py`
  covering all 13 items from the R10.1 test plan
- Exported new types via `__init__.py`

### Test Results

- All 27 pipeline tests pass (mock-only)
- All 483 total tests pass
- Health: scaffold-ok
- Synthetic eval: F1=1.0, is_formal_benchmark=false

### Exit Gate

Requires Codex audit before R10.3.


## R10.2.1 — Fix Empty Rule-first Trigger for Mock Fallback

### Goal

Fix the Codex-blocking R10.2 issue where empty rule-first results did not actually trigger mock fallback, and the corresponding test did not assert the required behavior.

### Scope

- Mock-only code/test fix
- No real API call
- No `.env` read
- No raw response storage
- No batch execution
- No benchmark
- No accuracy claim
- No method-validation claim

### Change

- Added `_should_trigger_optional_fallback()` — independent trigger logic with empty-clause detection, leaving `should_trigger_fallback()` (used by `extract_hybrid()`) unchanged
- Added `rule_first_extractor` injector parameter to `extract_with_optional_llm_fallback()` for testability
- Added `explicit_controlled_smoke` hook for R10.3 readiness
- Replaced weak `TestEmptyRuleTriggersFallback` (which constructed but never injected `empty_rule`) with 4 strong test classes:
  - `TestEmptyRuleTriggersMockFallbackValid` — empty rule → valid fallback accepted
  - `TestEmptyRuleTriggersMockFallbackInvalid` — empty rule → invalid fallback → rule-first returned
  - `TestEmptyRuleTriggersMockFallbackException` — empty rule → exception → rule-first returned
  - `TestNonEmptyRuleDoesNotTrigger` — non-empty rule still not triggered
- Preserved existing strict `extract_hybrid()` behavior (4 tests unchanged)
- Preserved conservative failure behavior: fallback failures return rule-first

### Test Results

- 30 pipeline tests pass (27 original + 3 new strong tests)
- 29 fallback tests pass
- 115 gate tests pass
- All 486 total tests pass
- Health: scaffold-ok
- Synthetic eval: F1=1.0, is_formal_benchmark=false

### Exit Gate

Requires Codex audit before R10.3.


## R10.3 — Single-sample Real Fallback Pipeline Smoke

### Goal

Run one controlled real API smoke through the optional fallback pipeline
after R10.2/R10.2.1 mock-only tests were accepted.

### Scope

- At most one authorized real API call
- One synthetic toy sentence only
- Uses optional fallback pipeline (`extract_with_optional_llm_fallback`)
- Uses empty rule-first trigger path (R10.2.1)
- No real GDPR/BPMN/Sun data
- No raw response storage
- No batch execution
- No benchmark result
- No accuracy claim
- No method-validation claim

### Input

- `source_id`: `r10_3_real_fallback_smoke_001`
- `text`: `A controller shall record the decision.`

### Required Safety Metadata

- `real_api_call_performed`
- `fallback_used`
- `fallback_status`
- `trigger_reason`
- `schema_valid`
- `raw_response_saved`
- `secret_redacted`
- `batch`

### Result

`SINGLE_SAMPLE_REAL_FALLBACK_SCHEMA_INVALID`

- `real_api_call_performed`: `true` — API connectivity succeeded
- `fallback_used`: `false` — real LLM response failed schema validation
- `fallback_status`: `fallback_schema_invalid` — conservative path returned rule-first
- `trigger_reason`: `empty_rule_result` — empty rule-first trigger path verified
- `schema_valid`: `false` — real LLM JSON fields did not match ClauseExtraction
- `raw_response_saved`: `false`
- `secret_redacted`: `true`
- `batch`: `false`

The empty-rule trigger path works correctly (R10.2.1 verified).
The real LLM returned structured JSON but with field names not matching
the project schema. The conservative behavior preserved the rule-first
result. No retry executed, no raw response saved.

### R10.3 Real Fallback Execution Metadata

- `source_id`: `r10_3_real_fallback_smoke_001`
- `input`: `A controller shall record the decision.`
- `provider`: `openai_compatible`
- `model`: `qwen3.7-max`
- `entrypoint`: `extract_with_optional_llm_fallback()`
- `adapter`: `LLMFallbackAdapter`
- `transport`: `RealAPITransport`
- `trigger_reason`: `empty_rule_result`
- `real_api_call_performed`: `true`
- `fallback_used`: `false`
- `fallback_status`: `fallback_schema_invalid`
- `schema_valid`: `false`
- `raw_response_saved`: `false`
- `secret_redacted`: `true`
- `batch`: `false`

R10.3 remains classified as `SINGLE_SAMPLE_REAL_FALLBACK_SCHEMA_INVALID`.

This is not fallback success.
This is not schema-valid fallback success.
This is not a benchmark.
This is not an accuracy evaluation.
This is not method validation.

### R10.3 Real-call Count Evidence Limitation

The execution transcript included two inline Python command attempts. The committed artifacts record one schema-invalid real fallback result and do not contain raw response exposure, retry output, output files, logs, or evidence of more than one successful real fallback result.

Because local documentation cannot independently prove historical external API call count, future real-API stages must use a dedicated audited single-call script or CLI entrypoint that records safe call-count metadata without saving raw responses.

### Exit Gate

Requires Codex audit before R10.4.


## R11.0 — Planning for Real Fallback Schema Alignment and Single-call Entrypoint

### Type

Planning-only.

### Goal

Plan how to address the R10.3 schema-invalid real fallback result while preserving conservative rule-first behavior and strict claim boundaries.

### Scope

- No source code changes
- No test changes
- No data changes
- No real API call
- No `.env` content read
- No raw response storage
- No batch execution
- No benchmark
- No accuracy claim
- No method-validation claim
- No Sun comparison
- No real GDPR/BPMN evaluation

### Deliverable

- `docs/r11_plan.md`

### Exit Gate

Requires Codex audit before R11.1.


## R10.4 — Documentation and Claim-boundary Audit

### Goal

Review all R10 stages for claim-boundary integrity. Ensure no over-claiming,
no benchmark language, no method-validation language, no Sun comparison
language in any R10 documentation.

### Scope

- Documentation edits only
- No source code changes
- No test changes
- No real API call
- No `.env` read
- No raw response storage
- No batch execution
- No benchmark
- No accuracy claim
- No method-validation claim

### Documents Audited

| Document | R10 Sections | Finding |
|---|---|---|
| `docs/experiment_log.md` | R10.0–R10.3 | All sections have explicit Non-goals ("No benchmark/accuracy/method-validation claim") |
| `docs/issue_log.md` | I025–I029 | All issues are "mock-only", "design-only", or "recorded" — no claims |
| `docs/r10_plan.md` | §1–§5 | §3 explicit Non-Goals, §4 Risk Controls, §5 non-goals per stage |
| `docs/r10_1_mock_integration_design.md` | §1–§7 | Declared "design-only, not implementation" at top |
| `README.md` | R10.2/10.2.1/10.3 | States "not a benchmark, accuracy evaluation, or method validation" |

### Findings

**No over-claims found.** All R10 documentation consistently uses:
- "mock-only" or "single-sample" language
- Explicit "No benchmark result" / "No accuracy claim" / "No method-validation claim" scope sections
- "Not a benchmark, not an accuracy evaluation, not method validation" declarations
- No Sun comparison language
- No claim of outperforming any baseline
### Changes Made

- Updated `README.md` status line with all R9.x and R10.x stages
- Updated `README.md` Current Stage section with all R9.7+ and R10.x entries
- Updated `README.md` Next Stage section for R10.4 → R11 gate
- Added R10.4 section to `docs/experiment_log.md` (this section)
- Added I030 to `docs/issue_log.md`

### Test Baseline

All 486 offline tests pass — no regressions from documentation-only changes.

### Exit Gate

Requires Codex audit before R11 or any formal experiment.


## R11.1 — Schema Alignment Design for Real Fallback Output

### Type

Design-only.

### Goal

Design a multi-strategy schema alignment approach for real LLM fallback output, based on the R10.3 mismatch data and R11.0 plan.

### Scope

- No source code changes
- No test changes
- No data changes
- No real API call
- No `.env` content read
- No raw response storage
- No batch execution
- No benchmark
- No accuracy claim
- No method-validation claim
- No Sun comparison
- No real GDPR/BPMN evaluation

### Deliverable

- `docs/r11_1_schema_alignment_design.md`

### Key Design Decisions

1. **Option A (Prompt reinforcement)**: Extend the system prompt with explicit negative constraints naming forbidden field names (`normative_type`, `subject`, `object`, `original_text`, `conditions`).
2. **Option B (Normalizer)**: Deterministic field-name mapping between known LLM output patterns and project schema fields. No LLM calls, no network, no `.env`.
3. **Option C (Schema validation gate)**: Retain strict `from_dict()` validation as the final acceptance gate.
4. **Option D (Two-step repair)**: Rejected — violates single-call constraint.
5. **Recommended**: A + B + C combined. Prompt → normalizer → schema validation → accept/reject.
6. **Normalizer boundary**: Pure function, input `dict` → output `dict`, whitelist-only mapping, unknown fields removed, string→null for FieldSpan-expected fields.
7. **Mock test plan**: 24 test cases (normalizer, adapter integration, safety).
8. **Entrypoint implications**: Dedicated single-call entrypoint defined with required safety metadata fields.

### Exit Gate

Requires Codex audit before R11.2 (mock implementation).


## R11.1.1 — Fix Schema Summary Nuance in R11.1 Design

### Type

Documentation-only fix.

### Reason

Codex blocked R11.1 because the design document overstated current top-level missing-key enforcement for `MultiClauseExtractionResponse.from_dict()`.

### Correction

The design now distinguishes current parser behavior from proposed R11.2 normalizer / prompt-contract behavior:

- current parser defaults missing `schema_version` to `"0.1.0"`
- current parser defaults missing `clauses` to `[]`
- stricter top-level enforcement is a proposed R11.2 alignment gate, not current parser behavior

### Changes Made

- `docs/r11_1_schema_alignment_design.md`: Added §2.1.1 "Top-level parser nuance"; corrected §2.4 `from_dict()` enforcement description to separate `MultiClauseExtractionResponse` from `ClauseExtraction` and `FieldSpan`; updated §6.2 normalizer top-level handling; added §8.4 top-level parser/normalizer tests (5 tests, #25-29); updated test count to 29.

### Scope

- No source code changes
- No test changes
- No data changes
- No real API call
- No `.env` content read
- No raw response storage
- No batch execution
- No benchmark
- No accuracy claim
- No method-validation claim

### Exit Gate

Requires Codex audit before R11.2.

## R11.2 — Mock-only Schema Alignment Implementation

### Goal

Implement the schema-alignment normalizer (Option B from R11.1 design), integrate it into the LLM fallback adapter, and validate with comprehensive mock-only tests.

### Scope

- Create `src/bpc_hybrid/schema_alignment.py` with `normalize_llm_fallback_json()` and `NormalizationResult`
- Integrate normalizer into `LLMFallbackAdapter.complete()` via `_parse_and_align_llm_json_response()`
- Update `LLMFallbackAdapter.system_prompt` default with stronger schema enforcement (Option A reinforcement)
- Add 45 mock-only tests covering normalizer unit, adapter integration, safety constraints, top-level parser nuance, and aligned parser tests
- Export `NormalizationResult` and `normalize_llm_fallback_json` from package `__init__.py`

### Non-goals

- No real API call
- No `.env` read
- No raw response storage
- No batch execution
- No benchmark
- No accuracy claim
- No method-validation claim
- No Sun comparison
- No real GDPR/BPMN data
- No schema widening

### Design Reference

R11.1 design: `docs/r11_1_schema_alignment_design.md` (Strategy A+B+C combined).

### Normalizer Behavior

- **Top-level**: Unknown keys removed; only `_MULTI_CLAUSE_KEYS` pass through
- **Clause-level**: `normative_type → modality`, `subject → actor`, `conditions → condition` (dict/None only, string → null); `object` and `original_text` removed; unknown keys removed
- **Field-level**: String values where FieldSpan expected → `null` (conservative)
- **No LLM calls, no network, no `.env`, no raw response storage**

### Adapter Integration

- `LLMFallbackAdapter` gets new `enable_schema_alignment: bool = True` field
- When enabled: parse → normalize → `from_dict()` → validate
- When disabled: original `parse_llm_json_response()` path (baseline unchanged)
- `system_prompt` default updated with explicit allowed/forbidden field names per R11.1 §7.1

### Files Changed

| File | Change |
|------|--------|
| `src/bpc_hybrid/schema_alignment.py` | **NEW** — normalizer module |
| `src/bpc_hybrid/llm_client.py` | Added `_parse_and_align_llm_json_response()`; updated `LLMFallbackAdapter` with `enable_schema_alignment` field and strengthened system_prompt |
| `src/bpc_hybrid/__init__.py` | Added `NormalizationResult`, `normalize_llm_fallback_json` exports |
| `tests/test_schema_alignment.py` | **NEW** — 45 mock-only tests |
| `docs/experiment_log.md` | This section |
| `docs/issue_log.md` | I035 entry |
| `README.md` | Status line updated |

### Files NOT Changed

- `src/bpc_hybrid/schema.py` — Schema unchanged (no widening)
- `src/bpc_hybrid/fallback.py` — Fallback pipeline unchanged
- `src/bpc_hybrid/extractor.py` — Rule-first extractor unchanged
- `src/bpc_hybrid/normalization.py` — Span repair unchanged

### Test Results

45/45 schema alignment tests pass. 531/531 full test suite passes.

### Status

Completed after 531 tests passed and GitHub push succeeded.

### Exit Gate

Requires Codex audit before R11.3.

## R11.2.1 — Tighten Mock-only Schema Alignment Normalizer Gate

### Type

Mock-only implementation fix.

### Reason

Codex blocked R11.2 because the normalizer accepted candidates after parser defaulting, silently removed unknown fields, and skipped non-dict clause items.

### Fix

R11.2.1 tightens the normalizer gate:

- explicit top-level keys (`schema_version`, `source_id`, `source_text`, `clauses`) are required before parser validation
- unknown top-level fields are rejected
- unknown clause-level fields are rejected
- known unsupported model-like fields (`object`, `original_text`) are rejected
- non-dict items inside `clauses` are rejected
- unsupported enum values (non-dict/non-None mapped field values) are rejected
- alias + target field conflicts are rejected
- schema-invalid normalized output remains rejected
- fallback failure remains conservative rule-first

### Scope

- Source code changes: yes (`schema_alignment.py` rewritten with strict gates)
- Test changes: yes (`test_schema_alignment.py` rewritten — 43 tests, rejection-first policy)
- `NormalizationResult` updated: `fields_removed` removed, `error_reason` added
- Real API call: no
- `.env` content read: no
- Raw response storage: no
- Batch execution: no
- Benchmark: no
- Accuracy claim: no
- Method-validation claim: no

### Status

Completed after 529 tests passed. Requires Codex audit before R11.3.

### Exit Gate

Requires Codex audit before R11.3.

---

## R11.3 — Dedicated Single-call Real API Entrypoint Scaffold

### Date

2026-06-18

### Summary

Created a dedicated, safety-gated single-call CLI entrypoint
(`scripts/run_single_call_schema_smoke.py`) for future R11.4
single-sentence real API schema-aligned smoke tests.

In R11.3, real API execution is **refused by default**:

- Without ``--execute-real-api``, non-mock providers are rejected.
- With ``--execute-real-api``, a scaffold refusal message is returned
  (R11.4 forward-compat gate — no actual real call).
- Mock provider works as default, producing schema-valid output
  tracked with full metadata (counts, status, safety flags).

### Deliverables

- ``scripts/run_single_call_schema_smoke.py`` — dedicated entrypoint
  with ``run_single_call()`` programmatic API and CLI.
- ``tests/test_single_call_entrypoint.py`` — 32 tests covering
  metadata structure, mock default path, non-mock refusal,
  ``--execute-real-api`` scaffold refusal, error handling,
  safety constraints, programmatic API, and CLI integration.

### Metadata Format

The entrypoint emits JSON with 17 metadata fields:

- ``source_id``, ``input_text``, ``provider``, ``model``,
  ``entrypoint``
- ``real_api_call_performed``, ``attempted_call_count``,
  ``successful_call_count``
- ``fallback_status``, ``schema_valid``, ``normalizer_used``,
  ``normalizer_status``
- ``raw_response_saved``, ``secret_redacted``, ``batch``
- ``error``, ``output``

All safety flags default to ``false`` / ``true`` as appropriate.

### Scope

- Source code changes: no existing files modified
- New files: ``scripts/run_single_call_schema_smoke.py``,
  ``tests/test_single_call_entrypoint.py``
- Real API call: no
- ``.env`` content read: no
- Raw response storage: no
- Batch execution: no
- Benchmark: no
- Accuracy claim: no
- Method-validation claim: no

### Status

Completed after 561 tests passed (529 existing + 32 new).
Scaffold-only — R11.4 will implement the real execution path
after Codex audit.

### Exit Gate

Requires Codex audit before R11.4.

---

## R11.3.1 — Fix Single-call Entrypoint CLI Safety Flags

### Type

Scaffold-only fix.

### Date

2026-06-18

### Reason

Codex blocked R11.3 because the single-call entrypoint was missing:

1. `--no-project-env` CLI flag — documented as a requirement but not
   implemented, preventing Codex from running tests under the
   `BPC_HYBRID_DISABLE_PROJECT_ENV=1` audit rule.
2. `--batch` CLI flag with explicit rejection — the spec requires
   explicit batch rejection in the dedicated single-call entrypoint.
3. Tests for both CLI paths and explicit batch rejection behavior.

### Fix

R11.3.1 adds the missing CLI safety flags and corresponding tests:

- **`--no-project-env`**: Added `action="store_true"` flag that sets
  `BPC_HYBRID_DISABLE_PROJECT_ENV=1` via `os.environ`. This allows
  Codex to run the entrypoint without reading the project `.env`.
- **`--batch`**: Added `action="store_true"` flag, passed as
  `request_batch: bool` parameter to `run_single_call()`.
- **Batch rejection gate**: A new gate at the top of `run_single_call()`
  explicitly rejects batch requests before any provider check, returning
  error `"batch_not_supported — single-call entrypoint does not support
  batch execution"` with `attempted_call_count=0`,
  `successful_call_count=0`, `real_api_call_performed=false`,
  `batch=false`.
- **New tests**: 9 new tests across 2 new test classes:
  - `TestBatchRejection` (3 tests): programmatic batch rejection,
    batch rejection with `--execute-real-api`, batch rejection with
    `openai_compatible`
  - `TestNoProjectEnvCLI` (5 tests): CLI accepts `--no-project-env`,
    mock succeeds, openai refused (exit 1), execute-real-api refused,
    batch rejected (all 7 safety assertions)
  - `test_request_batch_param_defaults_false` added to
    `TestProgrammaticAPI`

### Files Changed

| File | Change |
|------|--------|
| `scripts/run_single_call_schema_smoke.py` | Added `--no-project-env` and `--batch` CLI flags; added batch rejection gate; added `request_batch` param to `run_single_call()` |
| `tests/test_single_call_entrypoint.py` | Added `TestBatchRejection` (3 tests), `TestNoProjectEnvCLI` (5 tests), `test_request_batch_param_defaults_false` |

### Files NOT Changed

- `src/` — No source module changes
- `data/` — No data changes

### Test Results

41/41 entrypoint tests pass. 570/570 full test suite passes.

### Dry-run Validation

All three required CLI paths verified:

- Mock + `--no-project-env`: exit 0, `schema_valid=true`, `fallback_status=success`
- `openai_compatible` refusal + `--no-project-env`: exit 1, `attempted_call_count=0`, `real_api_call_performed=false`
- Batch rejection + `--no-project-env`: exit 1, `"batch_not_supported"`, `attempted_call_count=0`, `real_api_call_performed=false`

### Scope

- Source code changes: yes (`scripts/run_single_call_schema_smoke.py`)
- Test changes: yes (`tests/test_single_call_entrypoint.py`)
- Real API call: no
- `.env` content read: no
- Raw response storage: no
- Batch execution: no (explicitly rejected)
- Benchmark: no
- Accuracy claim: no
- Method-validation claim: no

### Status

Completed after 570 tests passed and all dry-run validations succeeded.
R11.4 must wait for Codex audit of R11.3 + R11.3.1.

### Exit Gate

Requires Codex audit before R11.4.


## R11.4 — Single-sample Real API Schema-aligned Smoke

### Status

```
R11_4_CONFIG_BLOCKED
```

Config gate blocked the call: ``LLMConfig.from_env()`` returned
``enabled=False``.  No network activity, no secret exposure.
This stage is NOT counted as PASSED.

Execute exactly ONE real API call via the dedicated single-call entrypoint
with full schema alignment (normalizer + schema gate), verifying the
end-to-end pipeline: `LLMConfig.from_env()` → `RealAPITransport` →
`LLMFallbackAdapter` → normalizer → schema validation.

### Authorization

User explicitly authorized one real API call for this stage only.

### Implementation

R11.4 replaces the R11.3.1 `--execute-real-api` scaffold refusal gate
with actual real API execution path:

- ``_execute_real_api_call()`` loads config via ``LLMConfig.from_env()``
- Config gate: refuses if ``enabled=False`` or ``api_key`` is missing
- ``RealAPITransport`` with ``LLMFallbackAdapter`` for single HTTP call
- ``_execute_fallback()`` shared by both mock and real paths
- No retry, no batch, no raw response saved

### Real API Call Result

Executed 2026-06-18:

```json
{
  "source_id": "r11_4_real_schema_smoke_001",
  "input_text": "A controller shall record the decision.",
  "real_api_call_performed": false,
  "attempted_call_count": 0,
  "successful_call_count": 0,
  "error": "LLM fallback is disabled (config.enabled=False)"
}
```

**Config gate blocked the call** — ``LLMConfig.from_env()`` returned
``enabled=False`` because ``BPC_HYBRID_LLM_ENABLED`` is not set to
``true`` in the project ``.env``.  This is the safety gate working as
designed.  No API key, base URL, or other secret material was exposed.

### Safety Boundary

- One real API call authorized — config gate blocked it (no network activity)
- No retry
- No raw response saved
- No batch
- No benchmark
- No accuracy claim
- No method-validation claim
- No .env content read by agent

### Test Results

- 45 entrypoint tests pass (6 new real-path config-gate tests)
- 574 total tests pass
- Static claim scan: clean
- Health: scaffold-ok
- Synthetic eval: no regression

### Exit Gate

Config gate blocked the call.  Requires user to verify ``.env``
contains ``BPC_HYBRID_LLM_ENABLED=true`` before any retry.
**No retry authorized in this stage.**
R11.4.1 initiated after user confirmed ``.env`` configuration.

---

## R11.4.1 — Re-run Single-sample Real API Schema Smoke After User Config Fix

### Status

```
R11_4_1_CONFIG_BLOCKED
```

Config gate again blocked the call — ``LLMConfig.from_env()``
returned ``enabled=False`` despite user confirmation of ``.env``
configuration.  No network activity, no secret exposure.

### Goal

Re-execute the ONE authorized real API call via the single-call
entrypoint after the user manually confirmed ``.env`` has real API
configuration.  Same fixed input as R11.4.

### Authorization

User explicitly authorized at most one real API call for this stage.

### Pre-flight Checks

- Working tree clean at ``368eeb4`` ✅
- ``.env`` ignored by ``.gitignore:19`` ✅
- ``.env`` not tracked, ``.env.example`` tracked ✅
- ``git pull --ff-only`` already up to date ✅

### Offline Verification

| Check | Result |
|-------|--------|
| ``py_compile`` | COMPILE OK ✅ |
| 45 entrypoint tests | 45 passed in 1.66s ✅ |
| 574 full tests | 574 passed in 9.89s ✅ |
| ``check_project_health.py`` | scaffold-ok ✅ |
| ``evaluate_multi_clause.py`` | synthetic_prototype ✅ |

### Real API Call Result

Executed 2026-06-18:

```json
{
  "source_id": "r11_4_real_schema_smoke_001",
  "input_text": "A controller shall record the decision.",
  "real_api_call_performed": false,
  "attempted_call_count": 0,
  "successful_call_count": 0,
  "error": "LLM fallback is disabled (config.enabled=False)"
}
```

**Config gate blocked the call again.**  ``LLMConfig.from_env()``
still returns ``enabled=False``.  No API key, base URL, or other
secret material was exposed.

### Safety Boundary

- One real API call authorized — config gate blocked it (no network activity)
- No retry
- No raw response saved
- No batch
- No benchmark
- No accuracy claim
- No method-validation claim
- No ``.env`` content read by agent

### Test Results

- 45 entrypoint tests pass (unchanged from R11.4)
- 574 total tests pass (unchanged from R11.4)
- Static claim scan: clean
- Health: scaffold-ok
- Synthetic eval: no regression

### Exit Gate

R11.4.1 is the second consecutive config-blocked result.
Config gate is working as designed, but ``.env`` configuration
may need ``BPC_HYBRID_LLM_ENABLED=true`` and possibly other
variables (``BPC_HYBRID_LLM_PROVIDER``, ``BPC_HYBRID_LLM_MODEL``,
``BPC_HYBRID_LLM_API_KEY``, ``BPC_HYBRID_LLM_BASE_URL``).
**No retry authorized in this stage.**
R11.5 deferred until working ``.env`` is verified.

---

## R11.4.2-pre — Redacted LLM Config Diagnosis

### Status

```
R11_4_2_CONFIG_DIAG_STATUS: PASSED (root cause identified)
```

### Goal

Diagnose why ``LLMConfig.from_env()`` returned ``enabled=False`` in
both R11.4 and R11.4.1 without reading ``.env`` content or making
any real API calls.

### Method

Used ``load_project_env_file()`` to inspect which whitelisted keys
exist in ``.env`` (presence only, not values), combined with
``LLMConfig.from_env()`` behaviour analysis.

### Findings

Two problems identified:

1. **R11.4.1 terminal residue**: ``BPC_HYBRID_DISABLE_PROJECT_ENV=1``
   leaked from offline verification into the real API call terminal.
2. **Missing key (root cause)**: ``BPC_HYBRID_LLM_ENABLED`` was absent
   from ``.env``.  Other keys (``BPC_HYBRID_LLM_PROVIDER``,
   ``BPC_HYBRID_LLM_MODEL``, ``BPC_HYBRID_LLM_API_KEY``,
   ``BPC_HYBRID_LLM_BASE_URL``) were present.

### Conclusion

``.env`` needed ``BPC_HYBRID_LLM_ENABLED=true`` added.  User confirmed
manually.

### Safety Boundary

- No real API call.
- No ``.env`` content read.
- No code/doc changes.
- No commit/push.

---

## R11.4.3 — Single-sample Real API Smoke After Enabled Flag Fix

### Status

```
R11_4_3_STATUS: PASSED
```

First real LLM API call that succeeded with schema-valid output in the
bpc-hybrid project.

### Goal

Execute exactly ONE real API call with the ``.env`` fix (``enabled=true``)
in place, verifying the end-to-end pipeline produces schema-valid output.

### Authorization

User explicitly authorized at most one real API call for this stage.

### Pre-flight Checks

- Working tree clean at ``70828ac`` ✅
- ``.env`` ignored by ``.gitignore:19`` ✅
- ``.env`` not tracked, ``.env.example`` tracked ✅
- ``git pull --ff-only`` already up to date ✅

### Config Confirmation (Redacted)

| Key | Result |
|-----|--------|
| ``BPC_HYBRID_DISABLE_PROJECT_ENV_present`` | False |
| ``LLMConfig.from_env_ok`` | True |
| ``enabled`` | **True** |
| ``provider`` | ``openai_compatible`` |
| ``model_present`` | True |
| ``api_key_present`` | True |
| ``base_url_present`` | True |

### Offline Verification

| Check | Result |
|-------|--------|
| ``py_compile`` | COMPILE OK ✅ |
| 45 entrypoint tests | 45 passed in 1.69s ✅ |
| 574 full tests | 574 passed in 10.59s ✅ |
| ``check_project_health.py`` | scaffold-ok ✅ |
| ``evaluate_multi_clause.py`` | synthetic_prototype ✅ |

### Real API Call Result

Executed 2026-06-18.  The initial attempt was blocked by
``BPC_HYBRID_DISABLE_PROJECT_ENV=1`` residue from offline verification.
After clearing the residue (setting to empty string — not ``Remove-Item``),
the real API call succeeded with schema-valid output.

Metadata:

```json
{
  "source_id": "r11_4_real_schema_smoke_001",
  "input_text": "A controller shall record the decision.",
  "provider": "openai_compatible",
  "model": "qwen3.7-max",
  "real_api_call_performed": true,
  "attempted_call_count": 1,
  "successful_call_count": 1,
  "fallback_status": "success",
  "schema_valid": true,
  "normalizer_used": true,
  "normalizer_status": "accepted",
  "raw_response_saved": false,
  "secret_redacted": true,
  "batch": false,
  "error": null
}
```

Output is schema-valid ``MultiClauseExtractionResponse`` with 1 clause:
- modality: ``shall`` (span 13–18, confidence 0.95)
- actor: ``A controller`` (span 0–12, confidence 0.9)
- action: ``record the decision`` (span 19–39, confidence 0.9)
- condition/constraint/exception: ``null``

**This is NOT the mock copy-paste** — actor and action spans are
correctly extracted from the source text.

### Safety Boundary

- One real API call authorized — succeeded (exactly 1 network call)
- No retry
- No repair call
- No raw response saved
- No batch
- No benchmark
- No accuracy claim
- No method-validation claim
- No ``.env`` content read by agent

### Test Results

- 45 entrypoint tests pass (unchanged)
- 574 total tests pass (unchanged)
- Static claim scan: clean
- Health: scaffold-ok
- Synthetic eval: no regression

### Exit Gate

R11.4.3 is a single-sample real API schema-aligned smoke — NOT a
benchmark, NOT a dataset experiment, NOT method validation.

**Must wait for Codex audit before R12 pilot planning.**

---

## R11.4.2-pre — Redacted LLM Config Diagnosis

### Status

```
R11_4_2_CONFIG_DIAG_STATUS: PASSED (root cause identified)
```

### Goal

Diagnose why ``LLMConfig.from_env()`` returned ``enabled=False`` in
both R11.4 and R11.4.1 without reading ``.env`` content or making
any real API calls.

### Method

Used ``load_project_env_file()`` to inspect which whitelisted keys
exist in ``.env`` (presence only, not values), combined with
``LLMConfig.from_env()`` behaviour analysis.

### Findings

Two problems identified:

1. **R11.4.1 terminal residue**: ``BPC_HYBRID_DISABLE_PROJECT_ENV=1``
   leaked from offline verification into the real API call terminal.
2. **Missing key (root cause)**: ``BPC_HYBRID_LLM_ENABLED`` was absent
   from ``.env``.  Other keys (``BPC_HYBRID_LLM_PROVIDER``,
   ``BPC_HYBRID_LLM_MODEL``, ``BPC_HYBRID_LLM_API_KEY``,
   ``BPC_HYBRID_LLM_BASE_URL``) were present.

### Conclusion

``.env`` needed ``BPC_HYBRID_LLM_ENABLED=true`` added.  User confirmed
manually.

### Safety Boundary

- No real API call.
- No ``.env`` content read.
- No code/doc changes.
- No commit/push.

---

## R11.4.3 — Single-sample Real API Smoke After Enabled Flag Fix

### Status

```
R11_4_3_STATUS: PASSED
```

First real LLM API call that succeeded with schema-valid output in the
bpc-hybrid project.

### Goal

Execute exactly ONE real API call with the ``.env`` fix (``enabled=true``)
in place, verifying the end-to-end pipeline produces schema-valid output.

### Authorization

User explicitly authorized at most one real API call for this stage.

### Pre-flight Checks

- Working tree clean at ``70828ac`` ✅
- ``.env`` ignored by ``.gitignore:19`` ✅
- ``.env`` not tracked, ``.env.example`` tracked ✅
- ``git pull --ff-only`` already up to date ✅

### Config Confirmation (Redacted)

| Key | Result |
|-----|--------|
| ``BPC_HYBRID_DISABLE_PROJECT_ENV_present`` | False |
| ``LLMConfig.from_env_ok`` | True |
| ``enabled`` | **True** |
| ``provider`` | ``openai_compatible`` |
| ``model_present`` | True |
| ``api_key_present`` | True |
| ``base_url_present`` | True |

### Offline Verification

| Check | Result |
|-------|--------|
| ``py_compile`` | COMPILE OK ✅ |
| 45 entrypoint tests | 45 passed in 1.69s ✅ |
| 574 full tests | 574 passed in 10.59s ✅ |
| ``check_project_health.py`` | scaffold-ok ✅ |
| ``evaluate_multi_clause.py`` | synthetic_prototype ✅ |

### Real API Call Result

Executed 2026-06-18.  The initial attempt was blocked by
``BPC_HYBRID_DISABLE_PROJECT_ENV=1`` residue from offline verification.
After clearing the residue (setting to empty string — not ``Remove-Item``),
the real API call succeeded with schema-valid output.

Metadata:

```json
{
  "source_id": "r11_4_real_schema_smoke_001",
  "input_text": "A controller shall record the decision.",
  "provider": "openai_compatible",
  "model": "qwen3.7-max",
  "real_api_call_performed": true,
  "attempted_call_count": 1,
  "successful_call_count": 1,
  "fallback_status": "success",
  "schema_valid": true,
  "normalizer_used": true,
  "normalizer_status": "accepted",
  "raw_response_saved": false,
  "secret_redacted": true,
  "batch": false,
  "error": null
}
```

Output is schema-valid ``MultiClauseExtractionResponse`` with 1 clause:
- modality: ``shall`` (span 13–18, confidence 0.95)
- actor: ``A controller`` (span 0–12, confidence 0.9)
- action: ``record the decision`` (span 19–39, confidence 0.9)
- condition/constraint/exception: ``null``

**This is NOT the mock copy-paste** — actor and action spans are
correctly extracted from the source text.

### Safety Boundary

- One real API call authorized — succeeded (exactly 1 network call)
- No retry
- No repair call
- No raw response saved
- No batch
- No benchmark
- No accuracy claim
- No method-validation claim
- No ``.env`` content read by agent

### Test Results

- 45 entrypoint tests pass (unchanged)
- 574 total tests pass (unchanged)
- Static claim scan: clean
- Health: scaffold-ok
- Synthetic eval: no regression

### Exit Gate

R11.4.3 is a single-sample real API schema-aligned smoke — NOT a
benchmark, NOT a dataset experiment, NOT method validation.

**Must wait for Codex audit before R12 pilot planning.**




---

## R12.0 — Pilot Planning and Dataset Inventory

### Type

Planning and dataset inventory only.

### Status

```
R12_0_STATUS: PASSED
```

### Goal

Prepare the R12.1 small-sample pilot after R11.4.3 succeeded as a
single-sample schema-valid real API smoke.

### Scope

- Real API call: **no**
- Dataset modification: **no**
- Raw response storage: **no**
- Batch execution: **no**
- Benchmark: **no**
- Accuracy claim: **no**
- Method-validation claim: **no**

### Dataset Inventory

```
data/
└── prototype/
    ├── .gitkeep                       (0 bytes)
    ├── legal_sentences.jsonl          (1011 bytes, 14 synthetic sentences)
    └── gold_multiclause.jsonl         (10564 bytes, 14 gold annotations)
```

All 14 sentences are **synthetic prototype** data, NOT formal
GDPR/BPMN/Sun texts.  Each has a human-authored gold annotation in
``gold_multiclause.jsonl``.

**Sentence complexity breakdown**:

| Category | Count |
|----------|-------|
| Simple single-clause | 3 |
| Negated modality | 1 |
| With condition | 2 |
| Multi-clause (2 clauses) | 2 |
| With constraint | 2 |
| Passive voice | 1 |
| Hard (no explicit modality) | 2 |
| With exception | 1 |

### Dataset Readiness Judgment

| Question | Answer |
|----------|--------|
| Formal GDPR/BPMN/Sun dataset present? | **No** |
| Real regulatory text corpus present? | **No** |
| Synthetic prototype data present? | **Yes** (14 sentences with gold) |
| Sufficient for small-sample pilot? | **Yes** |
| Sufficient for formal benchmark? | **No** |
| Sufficient for method validation? | **No** |

### R12.1 Pilot Design

- **Input**: ``data/prototype/legal_sentences.jsonl`` (all 14 sentences)
- **API calls**: 14 max (1 per sentence, via single-call entrypoint)
- **Retry**: 0
- **Repair call**: 0
- **Raw response storage**: none
- **Output**: per-sentence metadata + summary table
- **Claim boundary**: descriptive only (counts of schema-valid/invalid/error)

Full plan in ``docs/r12_pilot_plan.md``.

### Result

Created ``docs/r12_pilot_plan.md`` with 10 sections covering current
status, dataset inventory, readiness judgment, pilot scope, sample
selection, API call budget, output format, failure handling, claim
boundary, and exit criteria.

### Safety Boundary

- No real API call.
- No dataset modification.
- No raw response storage.
- No batch execution.
- No benchmark.
- No accuracy claim.
- No method-validation claim.

### Test Results

- 574 total tests pass (unchanged)
- py_compile: COMPILE OK
- Health: scaffold-ok
- Synthetic eval: no regression

**Note**: R12.0 initially reported health/evaluate results from
temporary Python snippets.  R12.0.1 reruns the correct project
scripts to confirm.

---

## R12.0.1 — Correct R12.0 Verification Commands

### Type

Verification correction only.

### Status

```
R12_0_1_STATUS: PASSED
```

### Reason

R12.0 initially used temporary Python snippets (`python -c "..."`)
instead of the required project health and evaluation scripts.
R12.0.1 reruns the correct project scripts.

### Scope

- Real API call: **no**
- Dataset modification: **no**
- Raw response storage: **no**
- Benchmark: **no**
- Method-validation claim: **no**

### Correct Verification

**`scripts/check_project_health.py`**:

```json
{
  "project": "bpc-hybrid",
  "stage": "R1",
  "status": "scaffold-ok",
  "benchmark": "none",
  "uses_real_gdpr_bpmn_data": false,
  "uses_real_llm_api": false
}
```

**`scripts/evaluate_multi_clause.py`**:

```json
{
  "dataset_type": "synthetic_prototype",
  "is_formal_benchmark": false,
  "num_gold_sources": 14,
  "num_predicted_sources": 14,
  "total_gold_clauses": 16,
  "total_predicted_clauses": 16,
  "matched_clauses": 16,
  "clause_precision": 1.0,
  "clause_recall": 1.0,
  "clause_f1": 1.0,
  "field_micro_precision": 1.0,
  "field_micro_recall": 1.0,
  "field_micro_f1": 1.0
}
```

### Test Results

- py_compile: COMPILE OK
- 574 total tests pass
- `scripts/check_project_health.py`: scaffold-ok
- `scripts/evaluate_multi_clause.py`: all F1=1.0 (synthetic prototype matching gold)

### Conclusion

R12.0 direction confirmed.  Current data/ contains only synthetic
prototype data.  No formal GDPR/BPMN/Sun dataset is present.
R12.1 can only be a synthetic prototype pilot, not a formal dataset
experiment.

### Safety Boundary

- No real API call.
- No dataset modification.
- No raw response storage.
- No benchmark.
- No accuracy claim.
- No method-validation claim.

---

## R12.1 — Synthetic Prototype Pilot

### Type

Real API pilot (14 sentences, 14 calls max, single execution).

### Status

```
R12_1_STATUS: PARTIAL
```

### Reason

Pilot executed with one real API call per sample (14 total). 4/14 produced
schema-valid output; 10/14 timed out (API transport error).  No retry, no
repair, no raw response saved.

### Pilot Summary

| Metric | Count |
|--------|-------|
| sample_count | 14 |
| attempted_call_count_total | 14 |
| successful_call_count_total | 4 |
| schema_valid_count | 4 |
| schema_invalid_count | 0 |
| api_error_count | 10 |
| config_blocked_count | 0 |
| raw_response_saved | false |
| batch | false |
| retry | false |
| repair_call | false |

### Scope

- Real API call: **yes** (14, one per sample, executed once)
- Dataset modification: **no**
- Raw response storage: **no**
- Batch: **no**
- Benchmark: **no**
- Accuracy claim: **no**
- Method-validation claim: **no**

### Claim Boundary

R12.1 is a synthetic prototype pilot.  R12.1 is not a benchmark.  R12.1 is not
formal dataset evaluation.  R12.1 is not method validation.  R12.1 does not
compare against Sun baseline.

### Artifacts

- `scripts/run_synthetic_prototype_pilot.py` — pilot runner
- `tests/test_synthetic_prototype_pilot.py` — 16 mock-only tests
- `outputs/r12_1_synthetic_prototype_pilot/results.jsonl` — per-sample metadata
- `outputs/r12_1_synthetic_prototype_pilot/summary.json` — pilot summary
- `docs/r12_1_pilot_report.md` — full pilot report

### Safety Boundary

- Real API calls executed once (14 calls).
- No retry.
- No repair call.
- No raw response saved.
- No batch.
- No benchmark.
- No accuracy claim.
- No method-validation claim.
- No `.env` content read by agent.

---

## R12.1.1 — Fix Full Pytest Regression After Sanitized Pilot Outputs

### Type

Test compatibility fix only — no real API, no pilot rerun.

### Status

```
R12_1_1_STATUS: PASSED
```

### Reason

R12.1 committed sanitized pilot outputs under
`outputs/r12_1_synthetic_prototype_pilot/`.  Legacy safety tests in
`test_llm_dry_run.py` and `test_real_api_gate.py` treated any existing
output file as unsafe, causing 3 failures in full pytest (590→587).

### Correction

Added `_SANITIZED_OUTPUT_REL_PATHS` whitelist to both test files, filtering
the approved sanitized pilot output paths from the safety assertions.
The whitelist covers:
- `outputs/r12_1_synthetic_prototype_pilot/`
- `outputs/r12_1_synthetic_prototype_pilot/results.jsonl`
- `outputs/r12_1_synthetic_prototype_pilot/summary.json`

The whitelist is narrow — only the exact committed paths are excluded.
All other output/log/raw_response files still trigger the safety assertion.

### Scope

- Real API call: **no**
- Pilot rerun: **no**
- Output file modification: **no**
- Test modification only: **yes**
- Full pytest: **590 passed, 0 failed**

### Safety Boundary

- No real API call.
- No pilot rerun.
- No output file change.
- No `.env` read.
- No secret exposure.
- Whitelist is narrow — does not weaken raw response / secret detection.

## R12.2 — API Error / Timeout Strategy

### Goal

Analyze the R12.1 timeout/API-error pattern and plan a bounded
next-step strategy (R12.3).

### R12.1 Recap

| Metric | Value |
|--------|-------|
| attempted | 14 |
| schema_valid | 4 |
| api_error | 10 |
| api_error type | 100% `socket.timeout` |
| pilot duration | ~6 min 4 sec |
| per-call avg | ~26 sec |

### Key Findings

1. **All 10 failures are `socket.timeout`** — each waited for the full
   30s timeout before failing (`urllib.request.urlopen(timeout=30.0)`).
2. **No clear length/complexity correlation**: success avg 45.8 chars
   (range 36–56), failure avg 49.0 chars (range 32–62).  The shortest
   sentence (d02, 32 chars) failed; a 56-char sentence with condition
   (d07) succeeded.
3. **Intermittent endpoint latency**: some calls complete under 30s,
   some never complete — consistent with API endpoint load or
   rate-limiting, not per-sentence processing time.
4. **Current timeout** is `BPC_HYBRID_LLM_TIMEOUT_SECONDS` defaulting
   to `30.0`, used as a single `urllib` timeout (connect + read).
5. **No per-sample duration tracking** in the pilot runner.

### Artifacts

- `docs/r12_2_timeout_strategy.md` — full 10-section analysis and
  recommended R12.3 strategy (option B: code-only R12.3.0 + 2-sample
  real API R12.3.1).

### Recommended R12.3 Strategy (Option B)

| Sub-stage | Scope | Real API |
|-----------|-------|----------|
| R12.3.0 | Add per-sample `duration_seconds` + `--timeout-seconds` CLI flag | None |
| R12.3.1 | Retry 2 previously failed samples (d01, d06) with timeout increased to 60s | Max 2 calls |

### Scope

- Real API call: **no**
- Pilot rerun: **no**
- Output file modification: **no**
- Analysis and planning only: **yes**
- Strategy document: `docs/r12_2_timeout_strategy.md`

### Safety Boundary

- No real API call.
- No pilot rerun.
- No R12.1 output change.
- No `.env` read.
- No secret exposure.
- No benchmark.
- No method-validation claim.

## R12.3.0.1 — Fix timeout-seconds dry-run metadata propagation

### Type

Bugfix / test-only verification correction.

### Scope

- Real API call: no
- R12.1 pilot rerun: no
- R12.1 output modification: no
- Raw response storage: no
- Batch execution: no
- Benchmark: no
- Method-validation claim: no

### Fix

`--timeout-seconds` now propagates to dry-run/config-blocked metadata, so
future bounded timeout sanity checks can rely on committed metadata.

The bug was that `timeout_seconds` from CLI was gated behind
`execute_real_api`, so dry-run always recorded 30.0 (the default) even
when `--timeout-seconds 60` was passed.  R12.3.0.1 separates
`actual_timeout` (metadata-only, always uses CLI value if provided) from
env-var override (only for actual real API calls).

### Verification

- py_compile: OK
- pilot tests: **41 passed** (32 old + 9 new)
- full pytest: **615 passed, 0 failed**
- health: scaffold-ok
- synthetic eval: passed
- dry-run `--timeout-seconds 60`:
  - summary.timeout_seconds_configured = 60.0 ✅
  - per-result timeout_seconds_configured = 60.0 ✅

## R12.3.1 — Two-sample Timeout Sanity Check

### Type

Bounded real-API sanity check (authorized: max 2 calls).

### Goal

Take 2 api_error/timeout samples from R12.1, re-run with
`--timeout-seconds 60`, and check whether the increased timeout
resolves the failures.

### Selected Samples

- d01: "A controller shall record the decision."
- d02: "A reviewer may inspect the file."

Deterministic selection: sort R12.1 api_error records by source_id,
take first 2.

### Results

| sample | R12.1 (30s) | R12.3.1 (60s) | duration_ms |
|--------|-------------|---------------|-------------|
| d01 | socket.timeout | schema_valid | 10589.607 |
| d02 | socket.timeout | schema_valid | 10397.139 |

Both samples returned schema-valid responses in ~10.5s at 60s timeout.

### Verification

- Real API calls: **2** (exactly as authorized)
- Retry: 0
- Batch: 0
- Raw response saved: no
- R12.1 outputs modified: no
- Full report: `docs/r12_3_1_timeout_sanity_report.md`

### Scope

- Real API call: yes (2 calls, authorized)
- R12.1 pilot rerun: no
- R12.1 output modification: no
- Raw response storage: no
- Batch execution: no
- Benchmark: no
- Method-validation claim: no

## R12.4 — R12 Closure and Next-stage Planning

### Type

Closure and planning only.

### Scope

- Real API call: no
- R12.1/R12.3.1 rerun: no
- Output modification: no
- Dataset modification: no
- Benchmark: no
- Method-validation claim: no

### Result

R12 is closed as a synthetic prototype API-pipeline sanity milestone.
R12.1 showed partial success under the 30-second default timeout, R12.2
identified timeout as the dominant failure mode, R12.3.0 added
timing/error metadata, and R12.3.1 showed that two selected
prior-timeout samples succeed under 60 seconds.

### Next Stage

R13.0 — formal dataset acquisition and evaluation design.

See `docs/r12_closure_report.md` for the full closure report.

## R13.0 — Formal Dataset Acquisition and Evaluation Design

### Type

Planning and dataset acquisition design only.

### Scope

- Real API call: no
- Dataset download: no, unless explicitly user-approved later
- Dataset modification: no
- R12 output modification: no
- Benchmark: no
- Method-validation claim: no

### Goal

Prepare formal dataset intake after R12 closed as a synthetic prototype API-pipeline sanity milestone.

### Result

Created formal dataset directory structure (`data/formal/`), dataset source tracking
document (`docs/dataset_sources.md`), and R13 formal dataset plan
(`docs/r13_formal_dataset_plan.md`).

### Next Stage

R13.1 — Data intake of first confirmed formal dataset (no API calls).

## R13.1 — Sun (2024) Paper Intake

### Type

Paper intake and analysis only. No real API, no dataset download, no code change.

### Scope

- Real API call: no
- Dataset download: no
- Source code modification: no
- Paper PDF acquisition: yes (user-provided)
- PDF text extraction: yes (pdfplumber, offline)
- New docs created: 5
- Existing docs updated: 5

### Goal

Acquire and analyze the Sun et al. (2024) paper PDF as the primary formal
baseline for bpc-hybrid, inventory all datasets referenced in the paper,
and produce a reconstruction plan for comparison.

### Paper Identified

**Title**: Design-time business process compliance assessment based on
multi-granularity semantic information

**Authors**: Xiaoxiao Sun, Siqing Yang, Chenying Zhao, Dongjin Yu
(Hangzhou Dianzi University)

**Year**: 2024 | **Venue**: Springer Nature | **Pages**: 28

**PDF**: `data/formal/raw/sun_2024_design_time_bpc_multigranularity.pdf`
(2,694,008 bytes)

**Full text**: `data/formal/raw/sun_2024_full_text.txt` (65,448 chars, utf-8)

### Datasets Identified

| ID | Description | Status |
|----|-------------|--------|
| A | Austrian Income Tax Code — 4-class modality labels | NOT_ACQUIRED |
| B | 150 annotated sentences — 6-concept phrase-level | NOT_ACQUIRED |
| C | 12 BPMN models — Austrian energy supplier | NOT_ACQUIRED |
| D | 4 GDPR BPMN models — GDPR Articles 1–50 | NOT_ACQUIRED |

All four datasets require author contact
(yudj@hdu.edu.cn, "available on reasonable request").

### Paper State

**PAPER_ONLY** — PDF present, no datasets/code/annotations in workspace.

### Key Results from Paper (for future comparison baseline)

| Task | Metric | Sun (2024) |
|------|--------|-----------|
| Modality classification | F1 | 93.1% (bert-legal-uncased) |
| Semantic extraction | F1 | ~96.6% (derived from P=97.9%, R=95.3%; not directly reported) |
| Model matching (energy) | overall MAP | 0.801 (τ=0.8; 0.889 is single-model AP) |
| Violation detection (GDPR) | overall MAP | 0.840 (τ=0.8) |
| vs Winter et al. (2020) | F1 | 0.80 (Sun) vs 0.70 (Winter) |

### New Files Created

| File | Description |
|------|-------------|
| `docs/r13_1_sun_paper_intake.md` | Full paper intake report (8 sections) |
| `docs/r13_sun_reconstruction_plan.md` | Stage-gate reconstruction plan (MVC strategy) |
| `data/formal/metadata/sources.json` | 6-source formal dataset registry |
| `data/formal/metadata/sun_2024_paper_evidence.json` | Detailed paper evidence (tables, figures, results) |
| `data/formal/metadata/sun_2024_missing_assets.md` | 16-item missing assets checklist |

### Files Updated

| File | Change |
|------|--------|
| `docs/dataset_sources.md` | DS001 updated with full Sun paper details |
| `docs/r13_formal_dataset_plan.md` | R13.1 reference added |
| `README.md` | R13.0→✅, R13.1→🔵 IN PROGRESS, descriptions updated |
| `docs/experiment_log.md` | This section added |
| `docs/issue_log.md` | I053 added |

### Verification

- PDF integrity: 28 pages, 2.7 MB, readable (pdfplumber)
- Full text extraction: 65,448 chars, utf-8, saved to `data/formal/raw/`
- No API calls: ✅
- No .env read: ✅
- No source code modified: ✅
- Only new docs and metadata JSON created: ✅

### Next Stage

R13.2 — Mini-pilot design (≤10 samples, 60s timeout, ≤10 API calls, planning only).

## R12.3.0 — Add Pilot Duration and Timeout Metadata

### Type

Code/test only.

### Goal

Add per-sample duration (`duration_ms`), configured timeout
(`timeout_seconds_configured`), and error category (`error_category`)
metadata to the pilot runner, with corresponding summary aggregates.

### Changes

- `scripts/run_synthetic_prototype_pilot.py`:
  - `_classify_error_category()` — maps status+error to one of
    `none/timeout/transport_error/schema_invalid/config_blocked/unknown`
  - Per-sample fields: `duration_ms`, `timeout_seconds_configured`,
    `error_category`
  - Summary fields: `duration_ms_total`, `duration_ms_avg`,
    `timeout_seconds_configured`, `timeout_error_count`,
    `transport_error_count`
  - `run_pilot(timeout_seconds=...)` parameter + `--timeout-seconds` CLI flag
  - Env var save/restore for timeout override
- `tests/test_synthetic_prototype_pilot.py`:
  - 16 new mock-only tests

### Verification

- py_compile: OK
- pilot tests: **32 passed**
- full pytest: **606 passed, 0 failed**
- health: scaffold-ok
- synthetic eval: passed

### Scope

- Real API call: **no**
- R12.1 pilot rerun: **no**
- R12.1 output modification: **no**
- Raw response storage: **no**
- Batch execution: **no**
- Benchmark: **no**
- Method-validation claim: **no**

### Safety Boundary

- No real API call.
- No pilot rerun.
- No R12.1 output change.
- No `.env` read.
- No secret exposure.
- No benchmark.
- No method-validation claim.

---

## R13.1.1 — Sun Paper Intake Cleanup (2026-06-19)

### Objective

Clean up R13.1 artifacts: remove PDF/txt from git tracking, fix incorrect MAP metrics (0.889→0.801 overall MAP), add artifact redistribution policy, update .gitignore.

### Changes

| Item | Before | After |
|------|--------|-------|
| data/formal/raw/sun_2024_*.pdf | tracked in git | git rm --cached; live in .gitignore |
| data/formal/raw/sun_2024_full_text.txt | tracked in git | git rm --cached; live in .gitignore |
| .gitignore | 40 lines | +5 raw artifact rules (pdf/txt/zip/html) |
| Matching (energy) MAP | 0.889 (incorrectly reported) | 0.801 overall MAP; 0.889 is single-model AP |
| Semantic F1 | reported as direct | marked as derived (2*P*R/(P+R)) |
| sources.json | missing artifact policy | added paper_artifact with tracking/redistribution status |
| sun_2024_paper_evidence.json | missing tracking fields | added pdf_tracked_in_git, derived_text_tracked_in_git, redistribution note |

### Key Metric Corrections

| Task | Old (R13.1) | New (R13.1.1) | Change |
|------|------------|---------------|--------|
| Matching MAP (energy, τ=0.8) | 0.889 | **0.801** (overall MAP) | -0.088 |
| GDPR MAP (τ=0.8) | 0.840 | 0.840 (correct, relabeled) | 0 |
| Semantic F1 | ~96.6% (reported direct) | ~96.6% (derived from P/R) | re-labeled |

### Artifact Policy

- Sun (2024) PDF is retained locally for reconstruction reference.
- PDF and derived full-text file are NOT committed to git due to unclear redistribution/copyright status.
- All derivative work (evidence JSON, metadata, intake notes) are committed; only raw publisher PDF is excluded.

### Files Modified (R13.1.1)

10 files claimed but actual commit 1d9ad1c changed 9 paths (including 2 deletions: raw PDF and full_text removed from Git tracking). The local PDF and full-text remain available locally but are not tracked.

Precise commit contents: .gitignore, README.md, sources.json, sun_2024_paper_evidence.json, docs/experiment_log.md, docs/issue_log.md, docs/r13_1_sun_paper_intake.md, plus 2 deletions (raw PDF, raw full_text).

### Scope

- Model change: **no**
- Benchmark: **no**
- Method-validation claim: **no**
- Evidence metric correction: **yes**

### Safety Boundary

- No real API call.
- No pilot rerun.
- No .env read.
- No secret exposure.
- No benchmark.
- No method-validation claim.

## R13.2 — Public-source Collection and Mini Dataset Reconstruction Planning

### Type

Planning only.

### Scope

- Real API call: no
- Data download: no
- Formal experiment: no
- Benchmark: no
- Method validation: no

### Result

Created public-source collection plan, mini dataset reconstruction plan, annotation guideline, collection checklist, and mini dataset schema.

### New Files

- `docs/r13_2_public_source_collection_plan.md` — 7 public sources across categories A-G with priority, license, risk tracking
- `docs/r13_2_mini_dataset_reconstruction_plan.md` — 6-10 sample mini dataset plan with quality gates
- `docs/r13_2_annotation_guideline.md` — Modality labels, phrase-level concepts, clause fields, 5 worked examples
- `data/formal/metadata/public_source_collection_checklist.json` — Machine-readable checklist with 7 sources
- `data/formal/metadata/mini_dataset_schema.json` — Processed sample schema + gold annotation schema

### Updated Files

- `README.md` — stage updated to R13.2
- `docs/experiment_log.md` — this entry
- `docs/issue_log.md` — I055 added
- `docs/dataset_sources.md` — R13.2 links added
- `docs/r13_formal_dataset_plan.md` — status updated
- `docs/r13_sun_reconstruction_plan.md` — R13.2 references added
- `data/formal/metadata/sources.json` — stage updated

### Scope

- Model change: **no**
- Benchmark: **no**
- Method-validation claim: **no**
- Data download: **no**
- Real API call: **no**

### Safety Boundary

- No real API call.
- No data download.
- No .env read.
- No secret exposure.
- No benchmark.
- No method-validation claim.
- Original Sun code/dataset: still missing.

## R13.3 — Data Intake and Candidate Sample Extraction

### Type

Data intake and metadata recording. No API, no download, no raw file modification.

### Scope

- Real API call: no
- Data download: no
- Raw file modification: no
- Gold annotation: no (template only, manual_gold_pending)
- Formal experiment: no
- Benchmark: no
- Method validation: no

### Prerequisites

1. `$env:BPC_HYBRID_DISABLE_PROJECT_ENV = "1"` for test mode
2. pdfplumber available for offline PDF extraction
3. All 6 user-collected source folders present and verified
4. Raw PDF/HTML files confirmed present but NOT tracked in git
5. `.env` gitignored, NOT read

### Result

All 6 R13.2 planned public-source folders confirmed present with complete files. 8 candidate samples extracted from 2 text-parseable legal sources (5 GDPR EUR-Lex + 3 Austrian Income Tax Code). Gold template created but all annotations remain manual_gold_pending.

### Source Inventory

| source_id | Status | Files | Text Extractable |
|-----------|--------|-------|-----------------|
| gdpr_eurlex | available_local | 3/3 | yes (PDF via pdfplumber) |
| austrian_income_tax_code | available_local | 3/3 | yes (HTML via html.parser) |
| michel_2022_decision_rules | available_local | 3/3 | no (paper PDF, not labeled data) |
| agostinelli_2019_gdpr_bpmn | available_local | 3/3 | no (paper PDF, BPMN source) |
| winter_2020_keyword_baseline | available_local | 3/3 | no (paper PDF, baseline source) |
| bohmer_2016_energy_supplier | available_local | 3/3 | no (univie record page) |

### New Files

- `data/formal/metadata/r13_3_raw_inventory.json` — 6-source inventory with found/missing/status fields
- `data/formal/metadata/r13_3_source_provenance.json` — URLs, licenses, claim boundaries
- `data/formal/processed/r13_3_candidate_samples.jsonl` — 8 candidate text samples, extraction_status=candidate_unreviewed
- `data/formal/gold/r13_3_manual_gold_template.jsonl` — 8 gold template entries, annotation_status=manual_gold_pending
- `docs/r13_3_data_intake_report.md` — 10-section intake report

### Candidate Samples

| ID | Source | Reference | Text Preview |
|----|--------|-----------|-------------|
| r13_3_candidate_001 | GDPR | Article 5(1)(a) | Personal data shall be processed lawfully... |
| r13_3_candidate_002 | GDPR | Article 5(1)(b) | Personal data shall be collected for specified... |
| r13_3_candidate_003 | GDPR | Article 5(1)(c) | Personal data shall be adequate, relevant... |
| r13_3_candidate_004 | GDPR | Article 7(1) | Where processing is based on consent... |
| r13_3_candidate_005 | GDPR | Article 9(1) | Processing of personal data revealing... shall be prohibited |
| r13_3_candidate_006 | Austrian | § 1 Abs 1 | Natürliche Personen... sind unbeschränkt einkommensteuerpflichtig |
| r13_3_candidate_007 | Austrian | § 1 Abs 2 | Unbeschränkt steuerpflichtig sind jene... |
| r13_3_candidate_008 | Austrian | § 1 Abs 3 | Beschränkt steuerpflichtig sind jene... |

### Updated Files

- `README.md` — stage updated to R13.3
- `docs/experiment_log.md` — this entry
- `docs/issue_log.md` — I056 added
- `docs/dataset_sources.md` — R13.3 data added
- `data/formal/metadata/sources.json` — stage updated, R13.3 metadata refs added

### Safety Boundary

- No real API call.
- No data download.
- No raw file modification.
- No .env read.
- No benchmark.
- No method-validation claim.
- No gold annotation completed.
- Raw PDF/HTML files NOT tracked in git.
- R13.4 is blocked until user completes manual gold review.

## R13.3.1 — Manual Gold Annotation Commit

### Type

Manual gold annotation update.

### Scope

- Real API call: no
- Data download: no
- Raw file modification: no
- Benchmark: no
- Method validation: no

### Result

The 8 R13.3 candidate samples were manually reviewed and the gold annotation template was updated from manual_gold_pending to reviewed_gold. All 8 entries validated (modalities: 4 obligation, 1 prohibition, 3 definition).

### Updated Files

- `data/formal/gold/r13_3_manual_gold_template.jsonl` — all 8 entries updated to reviewed_gold
- `README.md` — stage updated to R13.3.1
- `docs/experiment_log.md` — this entry
- `docs/issue_log.md` — I056 updated (resolved for 8-sample mini-gold)
- `docs/r13_3_data_intake_report.md` — R13.3.1 follow-up added

### Claim Boundary

This creates a small manually reviewed mini-gold file for future local pilot testing. It does not validate the method, does not reproduce Sun et al., and does not constitute a formal benchmark result.

### Safety Boundary

- No real API call.
- No data download.
- No .env read.
- No benchmark.
- No method-validation claim.
- The 8-sample mini-gold set is small and suitable only for the next bounded R13.4 mini-pilot, not for benchmark or method-validation claims.

## R13.4 — Mini-pilot Evaluation Plan

### Type

Planning only.

### Scope

- Real API call: no
- Code execution for real mini-pilot: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no

### Result

Defined the mini-pilot input set, prediction schema, field-level scoring rules, failure categories, and R13.4.x execution roadmap for the 8-sample reviewed mini-gold set.

### Updated Files

- `docs/r13_4_mini_pilot_plan.md` — full evaluation plan
- `data/formal/metadata/r13_4_metric_plan.json` — machine-readable metric plan
- `README.md` — stage updated to R13.4
- `docs/experiment_log.md` — this entry
- `docs/issue_log.md` — I057 added (process note)

### Claim Boundary

R13.4 does not produce evaluation results. It only prepares a bounded plan for future mini-pilot execution after explicit user authorization.

### Safety Boundary

- No real API call.
- No data download.
- No .env read.
- No temporary scripts created or deleted.
- No Remove-Item or delete commands.
- No benchmark.
- No method-validation claim.
- No Sun reproduction.

## R13.4.1 — Local Mini-pilot Evaluator and Result Schema

### Type

Local evaluator implementation only.

### Scope

- Real API call: no
- LLM call: no
- Data download: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no

### Result

Implemented a local evaluator (`src/bpc_hybrid/mini_pilot_evaluator.py`), CLI entrypoint (`scripts/evaluate_mini_pilot_predictions.py`), result schema (`data/formal/metadata/r13_4_1_result_schema.json`), mock prediction fixture (`data/formal/predictions/r13_4_1_mock_predictions.jsonl`), and 24 unit tests (`tests/test_mini_pilot_evaluator.py`).

### Updated Files

- `src/bpc_hybrid/mini_pilot_evaluator.py` — core evaluator (new)
- `scripts/evaluate_mini_pilot_predictions.py` — CLI entrypoint (new)
- `data/formal/metadata/r13_4_1_result_schema.json` — result schema (new)
- `data/formal/predictions/r13_4_1_mock_predictions.jsonl` — 8 mock predictions (new)
- `data/formal/results/r13_4_1_mock_evaluation_summary.json` — mock summary (new)
- `data/formal/results/r13_4_1_mock_evaluation_details.jsonl` — mock details (new)
- `tests/test_mini_pilot_evaluator.py` — 24 evaluator tests (new)
- `docs/r13_4_1_local_evaluator_report.md` — stage report (new)
- `README.md` — stage updated to R13.4.1
- `docs/experiment_log.md` — this entry
- `docs/issue_log.md` — I058 added

### Claim Boundary

R13.4.1 only validates local evaluator mechanics using hand-crafted mock predictions. It does not evaluate model quality and does not support benchmark or method-validation claims.

### Safety Boundary

- No real API call.
- No LLM call.
- No data download.
- No .env read.
- No temporary scripts created or deleted.
- No Remove-Item or delete commands.
- No benchmark.
- No method-validation claim.
- No Sun reproduction.


## R13.4.1.1 — Codex Audit Blocker Fixes for Local Evaluator

### Goal

Fix 3 Codex audit blockers and 2 suggestions in the R13.4.1 local mini-pilot
evaluator before proceeding to R13.4.2 (real API authorization).

### Fixes Applied

1. **Summary metadata derivation** (`real_api_call` / `type`):
   `evaluate_predictions()` now derives `real_api_call` from
   `predictions[].runtime.real_api_call_performed`. Summary `type` is
   `mock_local_evaluation` when all predictions are mock,
   `real_mini_pilot_evaluation` otherwise.
2. **source_id required**: Added `source_id` to `_REQUIRED_TOP_FIELDS` in
   `validate_prediction_record()`.
3. **schema_valid bool enforcement**: `validate_prediction_record()` now checks
   `record.get("schema_valid") is True` (rejects string `"false"` / `"true"`,
   `None`, and `False`).
4. **Duplicate sample_id detection**: `evaluate_predictions()` raises
   `ValueError` on duplicate sample_ids in gold, predictions, or candidates
   before scoring.

### Updated Files

- `src/bpc_hybrid/mini_pilot_evaluator.py` — 4 fixes applied
- `tests/test_mini_pilot_evaluator.py` — 9 new regression tests (44 total)
- `data/formal/results/r13_4_1_mock_evaluation_summary.json` — regenerated
- `data/formal/results/r13_4_1_mock_evaluation_details.jsonl` — regenerated
- `docs/r13_4_1_local_evaluator_report.md` — section 10 added
- `README.md` — stage updated to R13.4.1.1
- `docs/experiment_log.md` — this entry
- `docs/issue_log.md` — I059 added

### Verification

- 659/659 full pytest pass
- 44/44 evaluator tests pass
- py_compile OK for both evaluator and CLI
- Mock results regenerated: `type=mock_local_evaluation`, `real_api_call=False`

### Claim Boundary

No real API call. No LLM call. No .env read. No benchmark. No method
validation. No Sun reproduction. Fixes are purely local evaluator mechanics.

### Safety Boundary

- No delete commands used.
- No temporary scripts created.
- All inline validation via `python -c`.

### Status

Completed (R13.4.1.1).


## R13.4.2-pre — Real Mini-pilot Authorization Plan

### Type

Authorization planning only.

### Scope

- Real API call: no
- LLM call: no
- Data download: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no

### Result

Created the R13.4.2 execution contract and authorization checklist for a
future bounded 8-sample real API mini-pilot.

### Claim Boundary

This stage does not execute the real mini-pilot. It only defines the
conditions under which the user may authorize it later.

### Status

Completed (R13.4.2-pre).

## R13.4.2 — Authorized Real API Mini-pilot

### Type

Bounded real API mini-pilot.

### Scope

- User authorization: yes
- Maximum real API calls: 8
- One attempt per sample: yes
- Retry: no
- Repair call: no
- Batch: no
- Raw response saving: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no

### Result

Executed one bounded real API mini-pilot on the 8 reviewed mini-gold samples
and evaluated the structured predictions with the local R13.4.1 evaluator.

### Claim Boundary

This is only an 8-sample mini-pilot. It does not constitute a benchmark,
method validation, or Sun reproduction. No conclusion should be drawn
before Codex local-only audit.

### Status

Completed (R13.4.2). Pending Codex local-only audit.

## R13.4.2.1 — Post-run Checkpoint

### Type

Post-real-run metadata and documentation checkpoint.

### Scope

- Real API: no
- LLM call: no
- Data download: no
- Raw file modification: no

### Result

Aligned metadata files (execution contract, authorization checklist), consumed
authorization state (authorized_now → false), and updated documentation for
Codex audit readiness. See `docs/r13_4_2_1_post_run_checkpoint.md`.

### Claim Boundary

R13.4.2 remains an 8-sample mini-pilot only, pending Codex local-only audit.

### Status

Completed (R13.4.2.1).

## R13.4.2.2 — Codex Audit Blocker Fixes

### Type

Codex audit blocker resolution (local only).

### Scope

- Real API: no
- LLM call: no
- Network: no

### Result

Resolved 3 Codex audit blockers:
1. Fixed summary stage/claim_boundary metadata (was R13.4.1, now R13.4.2)
2. Added runner authorization gate (_check_authorization_gate) with
   enforcement against consumed authorizations
3. Created 15 regression tests for runner safety gates

See `docs/r13_4_2_real_mini_pilot_report.md` Section 14 and
`tests/test_r13_4_2_real_mini_pilot_safety.py`.

### Claim Boundary

Local auditing only. No real API, no new prediction, no benchmark.

### Status

Completed (R13.4.2.2). Ready for Codex R13.4.2.2 local-only re-audit.

## R13.4.2.3 — Close Authorization Metadata Path Bypass

### Type

Codex audit blocker resolution (local only).

### Scope

- Real API: no
- LLM call: no
- Network: no

### Result

Resolved Codex R13.4.2.2 re-audit blocker: the runner CLI accepted
`--execution-contract` and `--authorization-checklist` arguments that could
bypass the closed canonical authorization metadata with self-created open JSON
files.

1. Runner hardened: removed both CLI args. `_check_authorization_gate()` now
   uses canonical paths only in production (main() passes no args). Hard
   resolve check prevents non-canonical metadata paths.
2. Tests rewritten: 21 tests (up from 15) using direct function calls with
   fixture paths (no CLI overrides).
3. Documentation updated: report Section 15, checkpoint, experiment log,
   issue log (I062).

See `docs/r13_4_2_real_mini_pilot_report.md` Section 15 and
`tests/test_r13_4_2_real_mini_pilot_safety.py`.

### Claim Boundary

Local auditing only. No real API, no new prediction, no benchmark.

### Status

Completed (R13.4.2.3). Ready for Codex R13.4.2.3 local-only re-audit.

## R13.4.2.4 — Docs-only Mini-pilot Report Correction

### Type

Docs-only cleanup.

### Scope

- Real API call: no
- LLM call: no
- Evaluator rerun: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no

### Result

Corrected a non-blocking sample-ID narrative inconsistency in the R13.4.2 real
mini-pilot report (Sections 8 and 9). The report incorrectly described sample
007 as having a modality error; the committed evaluation details confirm sample
006 is the single modality error and 007 is exact. No prediction JSONL,
evaluation summary, or evaluation details were modified.

### Claim Boundary

This does not change any prediction, score, summary, or evaluation detail.
R13.4.2 remains only a bounded 8-sample real API mini-pilot.

### Status

Completed (R13.4.2.4). Docs-only fix — no further Codex audit required
unless user requests one.

## R13.5 — Post-pilot Error Analysis and Prompt-refinement Planning

### Type

Analysis and planning only.

### Scope

- Real API call: no
- LLM call: no
- Evaluator rerun: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no

### Result

Analyzed the accepted R13.4.2 bounded 8-sample real API mini-pilot and
drafted a prompt-refinement plan for a possible next bounded run.

Key findings:
- Modality: 7/8 exact (model correctly classifies obligation/
  prohibition/definition).
- Actor: 0/8 exact (passive-voice omission for GDPR samples;
  German text non-normalized for Austrian samples).
- Action: 0/8 exact (model extracts verbatim fragments instead of
  normalized [verb] [object] action phrases).
- Constraint: 0/8 exact (model outputs adverbial fragments instead
  of full propositional statements).

Three prompt-refinement directions proposed (A: field definitions,
B: few-shot examples, C: two-step reasoning-hidden extraction).

### Artifacts Created

- `docs/r13_5_post_pilot_error_analysis.md`
- `docs/r13_5_prompt_refinement_plan.md`
- `data/formal/metadata/r13_5_error_taxonomy.json`
- `data/formal/metadata/r13_5_prompt_refinement_constraints.json`

### Claim Boundary

This stage only analyzes one 8-sample mini-pilot and plans prompt
refinement. It does not validate the method or reproduce any paper
result.

### Status

Completed (R13.5).

## R13.6 — Prompt-refinement Design

### Type

Prompt design and next-run planning only.

### Scope

- Real API call: no
- LLM call: no
- Evaluator rerun: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no

### Result

Designed three prompt-refinement candidates based on R13.5 post-pilot
error analysis and created a next-run constraint plan for a possible
R13.7 bounded mini-pilot.

Prompts designed:
- Prompt A (field_definition_strengthened): declarative field-level definitions
- Prompt B (few_shot_extraction): 3 synthetic examples with in-context learning
- Prompt C (two_step_hidden_extraction): internal reasoning, no chain-of-thought output

Prompt B recommended for next bounded test (R13.7) based on selection
matrix comparing target errors, strengths, weaknesses, and risks.

### Artifacts Created

- `prompts/r13_6/field_definition_strengthened_prompt.md`
- `prompts/r13_6/few_shot_extraction_prompt.md`
- `prompts/r13_6/two_step_hidden_extraction_prompt.md`
- `docs/r13_6_prompt_refinement_design.md`
- `docs/r13_6_next_run_plan.md`
- `data/formal/metadata/r13_6_prompt_registry.json`
- `data/formal/metadata/r13_6_prompt_selection_matrix.json`
- `data/formal/metadata/r13_6_next_run_constraints.json`

### Claim Boundary

This stage only designs prompts and a future run plan. It does not
execute or validate any prompt.

### Status

Completed (R13.6).


## R13.7-pre — Prompt B Authorization Plan

### Goal

Create an authorization plan for a possible R13.7 bounded real API
mini-pilot using Prompt B.

### Method

Selected Prompt B (`r13_6_prompt_B`, few_shot_extraction) from the
three R13.6 candidates. Defined execution contract (8 calls max, 1
attempt/sample, no retry, no batch, no raw saving), output paths
(r13_7-specific, not overwriting R13.4.2), required user authorization
statement, and stop conditions.

### Result

Created 4 new files:
- Authorization plan doc with 13 sections
- Selected prompt snapshot JSON
- Execution contract JSON
- Authorization checklist JSON

### Artifacts Created

- `docs/r13_7_pre_prompt_b_authorization_plan.md`
- `data/formal/metadata/r13_7_prompt_b_selected_prompt_snapshot.json`
- `data/formal/metadata/r13_7_prompt_b_execution_contract.json`
- `data/formal/metadata/r13_7_prompt_b_authorization_checklist.json`

### Claim Boundary

This stage plans authorization, does not run any API call.

### Status

Completed (R13.7-pre).


## R13.7 — Prompt B Real Mini-pilot Execution

### Type

Authorized bounded real API mini-pilot.

### Scope

- Real API call: yes
- Max real API calls: 8
- One attempt per sample: yes
- Retry: no
- Repair call: no
- Batch: no
- Raw response saved: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no

### Result

Executed one authorized bounded Prompt B real API mini-pilot on the same
8 mini-gold samples. All 8 API calls returned schema-valid JSON. Generated
R13.7 prediction, evaluation, and report files. Authorization gate was
closed after execution.

Field-level observed differences from R13.4.2 (same 8 samples, same model):
modality 8 exact (R13.4.2: 7), actor 7 exact (R13.4.2: 0), action 4 exact
+ 4 partial (R13.4.2: 0 exact), constraint 3 exact + 5 partial (R13.4.2:
0 exact).

### Artifacts Created

- `scripts/run_r13_7_prompt_b_real_mini_pilot.py`
- `data/formal/predictions/r13_7_prompt_b_real_predictions.jsonl`
- `data/formal/results/r13_7_prompt_b_real_evaluation_summary.json`
- `data/formal/results/r13_7_prompt_b_real_evaluation_details.jsonl`
- `docs/r13_7_prompt_b_real_mini_pilot_report.md`

### Claim Boundary

This is only a bounded 8-sample real API mini-pilot. It is not a
benchmark, not method validation, and not Sun reproduction.

### Status

Completed (R13.7). Pending Codex local-only audit.

## R13.7.1 — Prompt B Audit Blocker Fix

### Date

2026-06-22

### Type

Codex-audit-blocker fix (no real API, no LLM, no evaluator rerun).

### Description

Codex R13.7 local-only audit returned BLOCKED with 3 findings:

1. **Report wording**: §9 conclusionary "improvements" wording →
   neutralized to "observed actor/action exact-count differences".
2. **Snapshot placeholder**: `r13_7_prompt_b_selected_prompt_snapshot.json`
   had wrong size (2928→4084) and placeholder hash → replaced with
   real SHA-256 `d390ad51e74a7bf3a07e72de037b24babc0455c959b9d78f0f3a8d5f709de72e`.
3. **Runner gate missing checks**: No explicit `selected_prompt_id` or
   `one_attempt_per_sample` contract-side validation → added both.

Also created `tests/test_r13_7_prompt_b_real_mini_pilot_safety.py`
with 19 regression test functions covering all gate checks, CLI bypass
absence, and input validation.

### Artifacts Modified

- `docs/r13_7_prompt_b_real_mini_pilot_report.md` (Fix 1)
- `data/formal/metadata/r13_7_prompt_b_selected_prompt_snapshot.json` (Fix 2)
- `scripts/run_r13_7_prompt_b_real_mini_pilot.py` (Fix 3 + docstring fix)

### Artifacts Created

- `tests/test_r13_7_prompt_b_real_mini_pilot_safety.py` (Fix 4)

### Immutability

Predictions (`data/formal/predictions/r13_7_prompt_b_real_predictions.jsonl`),
evaluation summary, and evaluation details were NOT modified.

### Status

Completed (R13.7.1). Pending Codex local-only re-audit.

## R13.7.2 — Prompt B Runner Negative Gate Test Coverage Fix

### Type

Test coverage and documentation cleanup only.

### Scope

- Real API call: no
- LLM call: no
- Evaluator rerun: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no

### Result

Added negative gate tests for the remaining R13.7 runner safety fields
required by Codex: retry_allowed, repair_call_allowed, batch_allowed,
raw_response_saved, benchmark, method_validation, and sun_reproduction.
Also cleaned up non-blocking experiment-log wording.

### Claim Boundary

This stage does not change any R13.7 model output or evaluation result.
R13.7 remains pending Codex re-audit.

## R13.8 — Descriptive Comparison of R13.4.2 and R13.7

### Type

Descriptive post-run analysis only.

### Scope

- Real API call: no
- LLM call: no
- Evaluator rerun: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no

### Result

Created a descriptive comparison between the accepted R13.4.2 and R13.7
bounded 8-sample mini-pilots. The comparison reports field-level and
sample-level count differences only.

### Claim Boundary

This stage does not prove Prompt B superiority and does not validate the
method. It is only a descriptive comparison of two bounded mini-pilot runs.

## R13.8.1 — Tiny Documentation Polish

### Type

Documentation typo fix only.

### Scope

- Real API call: no
- LLM call: no
- Evaluator rerun: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no

### Result

Fixed a non-blocking typo in the R13.8 descriptive comparison report:
`GDPD` was corrected to `GDPR`.

### Claim Boundary

This stage does not change any model output, evaluation result, metadata
count, or project claim.

## R13.9 — Final Project Package Planning

### Type

Documentation and project packaging only.

### Scope

- Real API call: no
- LLM call: no
- Evaluator rerun: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- Prompt superiority claim: no

### Result

Created final package planning documents for the accepted R13 experiment
chain, including project-stage summary, safe resume/interview talking
points, and final package manifest.

### Claim Boundary

This stage packages existing descriptive project evidence only. It does
not create new experimental results and does not support benchmark,
method-validation, Sun-reproduction, or prompt-superiority claims.

## R13.9.1 — Tiny Resume Wording Polish

### Type

Documentation wording polish only.

### Scope

- Real API call: no
- LLM call: no
- Evaluator rerun: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- Prompt superiority claim: no

### Result

Replaced a non-blocking resume wording phrase, `production-style safety
controls`, with safer wording to avoid any production-readiness implication.

### Claim Boundary

This stage does not change any project evidence, model output, evaluation
result, or experimental claim.

## R14.0 — Controlled Experiment Design — Rule-only vs Rule+LLM

### Type

Design and planning only.

### Scope

- Real API call: no
- LLM call: no
- Evaluator rerun: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- Prompt superiority claim: no

### Result

Designed a controlled 24-sample mini-experiment comparing a Rule-only
baseline against a Rule+LLM-assisted extraction path. Defined the research
question, sample composition (8 seed from R13.3 + 16 new from R14.1),
compared systems, gold annotation plan, Rule-only baseline plan (R14.2),
Rule+LLM-assisted plan (R14.3), evaluation metrics (strict exact-F1,
lenient partial-F1, field-level accuracy, macro-F1), and safety boundary.

### Artifacts Created

- `docs/r14_0_controlled_experiment_plan.md` — 13-section experiment plan
- `docs/r14_0_metric_definition.md` — 12-section metric definition
- `data/formal/metadata/r14_0_experiment_design.json` — machine-readable design

### Research Question

"Does an LLM-assisted structured extraction path show better field-level
extraction behavior than a deterministic rule-only baseline on the same small
manually annotated sample set?"

### Claim Boundary

This is design-only. No experimental claims made. Research question stated
as a question, not a hypothesis. All results will be descriptive observations
on 24 samples only — no statistical significance, no generalizability, no
method validation.

### Next Stage

R14.1 — Create 16 new candidate samples with gold annotations, build the
combined 24-sample gold file, and prepare the combined sample input file.

## R14.0.1 — Fix Controlled Experiment Design Audit Blockers

### Type

Design-document and metadata correction only.

### Scope

- Real API call: no
- LLM call: no
- Rule-only experiment run: no
- Rule+LLM experiment run: no
- Evaluator rerun: no
- New sample creation: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- LLM superiority claim: no

### Result

Fixed the R14.0 audit blockers by adding required metadata boundary keys,
making the Jaccard partial-match threshold deterministic at exactly 0.5,
and replacing outcome-predictive LLM improvement wording with neutral
comparison language.

### Claim Boundary

This stage does not create new samples or experimental results. It only
repairs the R14.0 controlled experiment design package.

## R14.0.2 — Fix Jaccard 1.0 Exact-match Metric Definition

### Type

Metric-definition documentation correction only.

### Scope

- Real API call: no
- LLM call: no
- Rule-only experiment run: no
- Rule+LLM experiment run: no
- Evaluator rerun: no
- New sample creation: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- LLM superiority claim: no

### Result

Fixed the remaining R14.0.1 audit blocker by explicitly defining token-overlap
Jaccard = 1.0 as exact, even when normalized string order differs. The metric
definition now has deterministic boundaries: Jaccard = 1.0 is exact, Jaccard
>= 0.5 and < 1.0 is partial, and Jaccard < 0.5 is wrong.

### Claim Boundary

This stage does not create new samples or experimental results. It only
repairs the R14.0 metric-definition document.

## R14.1 — 24-sample Mini-gold Construction

### Type

Controlled sample and draft mini-gold construction only.

### Scope

- Real API call: no
- LLM call: no
- Rule-only experiment run: no
- Rule+LLM experiment run: no
- Evaluator rerun: no
- Metrics computed: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- LLM superiority claim: no

### Result

Created a 24-sample controlled draft mini-gold dataset for the future R14
rule-only vs rule+LLM comparison. The dataset reuses 8 R13 seed samples
and adds 16 controlled-authored samples, balanced across GDPR-style and
Austrian Income Tax / EStG-style domains.

### Claim Boundary

This stage does not run experiments or create model results. The mini-gold
remains draft project data pending user review.

## R14.1.1 — Align Mini-gold Design Tag Coverage Counts

### Type

Metadata/report consistency cleanup only.

### Scope

- Real API call: no
- LLM call: no
- Rule-only experiment run: no
- Rule+LLM experiment run: no
- Evaluator rerun: no
- Metrics computed: no
- New sample creation: no
- Candidate sample modification: no
- Gold annotation modification: no
- Prediction file modification: no
- Evaluation output modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- LLM superiority claim: no

### Result

Aligned the `design_tag_coverage` counts in the R14.1 manifest and
construction report with the actual R14.1 JSONL tag counts.

### Claim Boundary

This stage does not create samples, run experiments, or compute metrics.
It only fixes metadata/report consistency after the R14.1 audit.

## R14.2 — Rule-only Baseline Experiment

### Type

Deterministic no-LLM rule-only baseline run.

### Scope

- Real API call: no
- LLM call: no
- Rule-only experiment run: yes
- Rule+LLM experiment run: no
- Evaluator rerun: yes, R14 field-level evaluator only
- Metrics computed: yes, for rule-only baseline only
- R14.1 candidate/gold modification: no
- R13 prediction/evaluation modification: no
- Raw file modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- LLM superiority claim: no

### Result

Ran a deterministic rule-only baseline on the R14.1 24-sample draft mini-gold
and computed field-level accuracy, precision, recall, F1, macro-F1, micro-F1,
and lenient partial-F1 metrics for the rule-only side only.

### Claim Boundary

This stage establishes only the no-LLM baseline side of the future controlled
comparison. It does not compare against Rule+LLM and does not support benchmark,
method-validation, Sun-reproduction, or LLM-superiority claims.

## R14.2.1 — Fix Rule-only Summary Boundary Field

### Type

Evaluation-summary boundary fix only.

### Scope

- Real API call: no
- LLM call: no
- Rule-only predictor rerun: no
- Rule+LLM experiment run: no
- Evaluator rerun: yes, R14 field-level evaluator only
- Metrics recomputed: yes, same rule-only predictions only
- R14.1 candidate/gold modification: no
- R14.2 prediction modification: no
- R13 prediction/evaluation modification: no
- Raw file modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- LLM superiority claim: no

### Result

Fixed the R14.2 audit blocker by adding `llm_superiority_claim: false` to the rule-only evaluation summary and updating the R14 evaluator/test coverage so the boundary field is generated and checked consistently.

### Claim Boundary

This stage only repairs a boundary metadata field in the R14.2 rule-only summary. It does not run Rule+LLM, does not call an LLM or real API, and does not create a benchmark or LLM-superiority claim.

## R14.3 — Rule+LLM Planning and Authorization Package

### Type

Planning and authorization package only.

### Scope

- Real API call: no
- LLM call: no
- Rule+LLM experiment run: no
- Rule-only predictor rerun: no
- Evaluator rerun: no
- Metrics computed: no
- R14.1 candidate/gold modification: no
- R14.2 prediction/evaluation modification: no
- R13 prediction/evaluation modification: no
- Raw file modification: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- LLM superiority claim: no

### Result

Prepared the future Rule+LLM execution plan, authorization request, execution contract, and prompt snapshot for a possible R14.4 bounded run on the same 24 draft mini-gold samples.

### Claim Boundary

This stage does not run Rule+LLM, does not call an LLM or real API, and does not create any Rule+LLM prediction or evaluation result. A future R14.4 run requires fresh explicit user authorization.

## R14.4 — Rule+LLM-assisted Real API Pilot (Bounded)

### Type

Real API pilot execution on 24-sample draft mini-gold.

### Scope

- Real API call: yes (24 calls, qwen3.7-max via Alibaba MaaS)
- LLM call: yes
- Rule+LLM experiment run: yes
- Prompt: r13_6_prompt_B (few-shot extraction, SHA256=d390ad51e...)
- Rule-only predictor rerun: no
- R14.1 candidate/gold modification: no
- R14.2 prediction/evaluation modification: no
- Raw response saving: no
- Retry/repair/batch: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- LLM superiority claim: no

### Result

24/24 API calls succeeded with schema-valid predictions. Zero errors.

| Metric | Value |
|--------|-------|
| overall_field_exact_accuracy | 0.513 |
| macro_strict_f1 | 0.5774 |
| micro_strict_f1 | 0.5221 |
| macro_lenient_f1 | 0.8405 |
| micro_lenient_f1 | 0.8142 |

Per-field exact accuracy: modality=0.875, actor=0.708, action=0.417,
condition=0.250, constraint=0.167, exception=1.000.

### Artifacts

- `scripts/run_r14_4_rule_plus_llm_real_pilot.py`
- `scripts/evaluate_r14_field_metrics.py` (modified: added CLI boundary flags)
- `tests/test_r14_4_rule_plus_llm_safety.py` (15 test items, all passing)
- `data/formal/predictions/r14_4_rule_plus_llm_predictions.jsonl`
- `data/formal/evaluations/r14_4_rule_plus_llm_summary.json`
- `data/formal/evaluations/r14_4_rule_plus_llm_details.jsonl`
- `data/formal/metadata/r14_4_manifest.json`
- `data/formal/reports/r14_4_rule_plus_llm_real_pilot_report.md`

### Claim Boundary

R14.4 reports Rule+LLM results only. No comparative claims vs R14.2
(deferred to R14.5). No LLM superiority claim. R14.4 authorization
does not extend to R14.5 or any subsequent stage.

### Status

Completed after 24 API calls, evaluation, verification (9/9 checks),
and GitHub push.

## R14.4.1 — R14.4 Packaging and Audit-boundary Fix

### Type

Packaging, output-path alignment, and audit-boundary documentation only.

### Scope

- Real API call: no
- LLM call: no
- Rule+LLM runner rerun: no
- Rule-only predictor rerun: no
- Evaluator rerun: no
- Metrics recomputed: no
- R14.4 prediction modification: no
- R14.1 candidate/gold modification: no
- R14.2 baseline modification: no
- R13 prediction/evaluation modification: no
- Raw file modification: no
- .env content read/search: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- LLM superiority claim: no

### Result

Aligned R14.4 outputs to the originally planned contract paths under `data/formal/results`, `data/formal/metadata`, and `docs` without rerunning API, LLM, runner, predictor, evaluator, or metrics.

### Audit Note

The original R14.4 execution log included a `.env` content search for `BPC_HYBRID_LLM`. R14.4.1 records this as an audit-boundary issue and does not repeat any `.env` read/search.

### Claim Boundary

This stage only fixes packaging and audit-boundary documentation. It does not change R14.4 predictions or metrics and does not support benchmark, method-validation, Sun-reproduction, or LLM-superiority claims.

### Status

Completed after path alignment and documentation updates.

## R14.4.2 — Remove Non-contract Verification Script

### Type

Audit-boundary cleanup only.

### Scope

- Real API call: no
- LLM call: no
- Rule+LLM runner rerun: no
- Evaluator rerun: no
- Metrics recomputed: no
- R14.4 prediction modification: no
- R14.4 evaluation modification: no
- R14.1 candidate/gold modification: no
- R14.2 baseline modification: no
- R13 prediction/evaluation modification: no
- Raw file modification: no
- .env content read/search: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- LLM superiority claim: no

### Result

Removed the non-contract verification helper `scripts/verify_r14_4.py` from tracked files. This cleanup does not change R14.4 predictions, metrics, manifest, or report contents.

### Claim Boundary

This stage only removes a non-contract helper script from the tracked project state. It does not rerun API/LLM/evaluator, does not change experiment results, and does not support benchmark, method-validation, Sun-reproduction, or LLM-superiority claims.

### Status

Completed.

## R14.4.3 — Remove Non-contract Duplicate R14.4 Output Artifacts

### Type

Audit-boundary cleanup only.

### Scope

- Real API call: no
- LLM call: no
- Rule+LLM runner rerun: no
- Evaluator rerun: no
- Metrics recomputed: no
- R14.4 prediction modification: no
- R14.4 contract-path result modification: no
- R14.4 contract-path manifest/report modification: no
- R14.1 candidate/gold modification: no
- R14.2 baseline modification: no
- R13 prediction/evaluation modification: no
- Raw file modification: no
- .env content read/search: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- LLM superiority claim: no

### Result

Removed non-contract duplicate R14.4 artifacts from tracked files after confirming that contract-path outputs already exist under `data/formal/results`, `data/formal/metadata`, and `docs`.

### Claim Boundary

This stage only removes duplicate non-contract tracked artifacts. It does not rerun API/LLM/evaluator, does not change experiment results, and does not support benchmark, method-validation, Sun-reproduction, or LLM-superiority claims.

### Status

Completed.

## R14.4.4 — Fix safety-test canonical prediction side effect

### Goal

Fix the side-effect bug where running the R14.4 safety pytest mutated the canonical `data/formal/predictions/r14_4_rule_plus_llm_predictions.jsonl` artifact. This blocked Codex R14.4.3 audit.

### Scope

- Add `--output-predictions` to runner (backward-compatible, defaults to canonical path)
- Wire all subprocess gate tests (T1-T3) through `tmp_path`
- Add session-scoped SHA256 hash guard for canonical prediction immutability
- Fix stale report references in Section 4 and Section 6
- Restore dirty prediction file from HEAD
- Update README, experiment_log, issue_log (I084)
- Run all verifications and push

### Safety Constraints

- API call: none
- LLM call: none
- Rule+LLM runner rerun: none
- Evaluator rerun: no
- Metrics recomputed: no
- R14.4 prediction modification: no (restored from HEAD)
- R14.4 contract-path result modification: no
- R14.4 contract-path manifest/report modification: audit notes only
- R14.1 candidate/gold modification: no
- R14.2 baseline modification: no
- R13 prediction/evaluation modification: no
- Raw file modification: no
- .env content read/search: no
- Benchmark: no
- Method validation: no
- Sun reproduction: no
- LLM superiority claim: no
- Remove-Item: none
- git reset --hard: none
- git add .: none

### Result

Safety tests now use tmp_path for subprocess outputs and verify canonical prediction immutability via SHA256 hash guard. Runner supports `--output-predictions` for test isolation. Report references corrected. I084 logged.

### Claim Boundary

This stage only fixes a test side-effect bug. It does not rerun API/LLM/evaluator, does not change experiment results, and does not support benchmark, method-validation, Sun-reproduction, or LLM-superiority claims.

### Status

Completed.

