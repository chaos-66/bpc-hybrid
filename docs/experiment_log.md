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
