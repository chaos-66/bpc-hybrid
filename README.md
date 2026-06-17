# bpc-hybrid

## Current Status

**R0 ✅ | R1 ✅ | R1.5 ✅ | R1.6 ✅ | R2 ✅ | R3 ✅ | R4 ✅ | R5 ✅ | R5.1 ✅ | R6 ✅ | R7 ✅ | R7.1 ✅ | R7.2 ✅ | R8 ✅ | R8.2 ✅ | R9 ✅ | R9.8 ✅ | R10.0 ✅ | R10.1 ✅ | R10.2 ✅ | R10.2.1 ✅ | R10.3 ✅ | R10.4 ✅ | R10.4.1 ✅ | R11.0 ✅ | R11.1 ✅ | R11.1.1 ✅ | R11.2 ✅**

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
- ⚠️ R10.3 remains classified as `SINGLE_SAMPLE_REAL_FALLBACK_SCHEMA_INVALID`, not fallback success. Its documented path is `extract_with_optional_llm_fallback()` → `LLMFallbackAdapter` → `RealAPITransport` using `openai_compatible` / `qwen3.7-max`. Future real-API stages must use a dedicated audited single-call entrypoint to avoid call-count ambiguity.
- ⚠️ R11.0 is a planning-only stage for real fallback schema alignment and a dedicated single-call real API entrypoint. It does not execute real API calls, run benchmarks, evaluate accuracy, validate the method, compare against Sun, or use real GDPR/BPMN data.
- ⚠️ R11.1 is a design-only stage producing `docs/r11_1_schema_alignment_design.md`. It does not change source code, tests, or data; does not execute real API calls; and does not make any benchmark, accuracy, method-validation, or Sun-comparison claims. The design recommends a combined prompt + normalizer + schema-gate strategy (Options A+B+C) for R11.2 mock implementation.
- ⚠️ R11.1.1 corrects the R11.1 schema summary: current `MultiClauseExtractionResponse.from_dict()` defaults missing `schema_version` to `"0.1.0"` and missing `clauses` to `[]`, while stricter top-level enforcement remains a proposed R11.2 normalizer / prompt-contract gate.
- ⚠️ R11.2 implements the schema-alignment normalizer (Option B from R11.1 design) and integrates it into `LLMFallbackAdapter` with a strengthened system prompt (Option A). The normalizer is a deterministic, mock-only pure function — no LLM calls, no network, no `.env`, no raw response storage. `LLMFallbackAdapter.enable_schema_alignment=True` by default. 45 new tests + 531 total tests pass. Requires Codex audit before R11.3.

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
- R6 ✅: Mock LLM fallback interface and deterministic normalization foundation completed.
- R7 ✅: Safe LLM fallback adapter scaffold completed.
- R7.1 ✅: Hardened LLM config validation and documentation completed.
- R7.2 ✅: Completed base_url secret query coverage.
- R8 ✅: Added controlled single-sample LLM dry-run harness.
- R9 ✅: Added controlled real API single-sample smoke with explicit gate flags.
- R9.1 ✅: Improved real API connectivity diagnostics and error classification.
- R9.2 ✅: Single retry after manual `.env` correction (HTTP status error — reached server, not a benchmark).
- R9.3 ✅: Single retry after manual WorkspaceId/base_url correction (HTTP status error — not a benchmark).
- R9.4 ✅: Single retry after manual API key/model/workspace alignment (DNS/connection error — not a benchmark).
- R9.5 ✅: Single retry after removing WorkspaceId braces (schema mismatch — connectivity OK, not a benchmark).
- R9.6 ✅: Fixed diagnostic classification — parse/schema failures now return `SINGLE_SAMPLE_API_RETURNED_SCHEMA_INVALID` (code fix, no real API call).
- R9.7 ✅: Aligned real LLM prompt with project schema (code-only, no real API call).
- R9.7.1 ✅: Fixed unsafe R9.7 CLI regression test; extracted pure `classify_real_api_error_status()` helper.
- R9.8 ✅: Real API single-sample schema smoke succeeded (`schema_valid: true`).
- R9.8.1 ✅: Documented R9.8 source ID metadata (`r9_8_real_schema_smoke_001`).
- R10.0 ✅: R10 staged plan created (planning only).
- R10.1 ✅: Offline/mock fallback integration design completed (design only).
- R10.2 ✅: Mock-only pipeline integration tests completed (27 tests).
- R10.2.1 ✅: Empty rule-first trigger regression fixed (4 strong mock-only tests).
- R10.3 ✅: Single-sample real fallback pipeline smoke completed (schema-invalid, conservative path OK).
- R10.4 ✅: Documentation claim-boundary audit completed (current stage).

## R9 Scope

R9 performs at most one explicitly authorized real API single-sample connectivity smoke using the existing dry-run harness.

R9 does not run batch experiments, does not store raw responses, does not use real GDPR/BPMN/Sun data, and does not produce benchmark results.

A successful R9 run only means single-sample API connectivity smoke succeeded.

## R9.1 Scope

R9.1 improves real API connectivity diagnostics without adding new features:

* Better error classification: timeout, SSL, DNS/connection, HTTP status
  errors are now distinguished (all redacted)
* Better endpoint construction: handles base URLs with `/chat/completions`
  already present, root-like URLs, and `/v1` / `/v1/` variants
* CLI error JSON now includes a `status` field:
  `SKIPPED_NO_API_KEY_OR_CONFIG` or `SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED`
* Diagnostic existence checks for config keys (presence yes/no, no values)

R9.1 does not add new features, does not run benchmarks, and does not
modify `.env` or `.env.example`.

## R9.2 Scope

R9.2 is a single retry after manual `.env` configuration correction.
It is not a benchmark, not a formal experiment, and not a validation
of the method.  It only confirms whether the connectivity smoke now
reaches the API server.
- R8.2 ✅: CLI parse errors (invalid provider, unknown args) return JSON error envelopes.

## R8 Scope

R8 adds a controlled single-sample LLM dry-run harness.

The harness is disabled by default and requires explicit `--allow-llm` and `--single-sample` flags. In R8, the default provider is `mock`, and real provider execution remains disabled. R8 does not call real LLM APIs, does not access the network, does not read `.env` files, does not store raw responses, and does not produce benchmark results.

R8 is intended to test safety gates, CLI behavior, schema validation, and redacted dry-run summaries before any later real API experiment.

R8.2 ensures parse-level CLI errors (invalid `--provider`, unknown arguments)
also return redacted JSON error envelopes instead of argparse usage text.
## Local API Configuration

R9.0 adds project‑local `.env` support for real API credentials during smoke tests.
This section describes how to configure your local copy of bpc‑hybrid to talk to the
LLM provider of your choice.

### Quickstart

```bash
cp .env.example .env
# Edit .env with your values (see below)
```

### File Roles

| File | Purpose | Committed to git? |
|---|---|---|
| `.env.example` | Template with placeholder values | ✅ yes |
| `.env` | Your **local** configuration with real values | ❌ no — gitignored |

### Configuration Precedence

System environment variables (`os.environ`) **always override** `.env` values.
If a key is set both in `os.environ` **and** `.env`, the system environment wins.

### Whitelisted Keys

Only whitelisted `BPC_HYBRID_*` keys are read from `.env`.

| Key | Description | Example |
|---|---|---|
| `BPC_HYBRID_LLM_PROVIDER` | LLM provider name | `openai_compatible` |
| `BPC_HYBRID_LLM_MODEL` | Model name / deployment id | `gpt-4o-mini` |
| `BPC_HYBRID_LLM_BASE_URL` | API endpoint base URL | `https://api.openai.com/v1` |
| `BPC_HYBRID_LLM_API_KEY` | API key or token | `sk-...` |
| `BPC_HYBRID_LLM_ENABLED` | Enable real LLM (`true` / `false`) | `true` |
| `BPC_HYBRID_LLM_TIMEOUT_SECONDS` | Request timeout in seconds | `30.0` |
| `BPC_HYBRID_LLM_MAX_TOKENS` | Max tokens per response | `1024` |
| `BPC_HYBRID_LLM_TEMPERATURE` | Sampling temperature | `0.0` |
| `BPC_HYBRID_R9_REAL_RUN_CONFIRMED` | Explicit gate for R9 real API runs | `true` |

### Safety Invariants

- The API key is **never** printed to stdout, stderr, repr, str, or error messages.
- `.env` is listed in `.gitignore` and must never be committed.
- If `.env` is missing or unreadable, the application silently falls back to
  `os.environ` alone — there is no error.
- For audits and tests, project-root `.env` loading can be disabled with
  `--no-project-env` or `BPC_HYBRID_DISABLE_PROJECT_ENV=1`.
- No raw response storage, no batch execution, no benchmark result.
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

## R6 Scope

R6 implements the LLM fallback interface and deterministic normalization
foundation **without** calling any real LLM APIs:

- **`fallback.py`** — `FallbackError`, `DecisionReason` (NO_FALLBACK_NEEDED /
  MISSING_ACTOR / MISSING_ACTION / LOW_FIELD_CONFIDENCE / LOW_CLAUSE_CONFIDENCE /
  SCHEMA_VALIDATION_FAILURE), `FallbackDecision` dataclass, `FallbackRequest` /
  `FallbackResult` dataclasses, `MockLLMFallbackClient` (configurable stub —
  no network, no `.env`, no API keys), `should_trigger_fallback()` (checks
  normative clauses only for missing actor/action, low confidence, and schema
  validation failure; non-normative clauses are skipped), `extract_hybrid()`
  (chains extract_rule_first → trigger-check → mock-fallback → span repair)
- **`normalization.py`** — `NormalizationError`, `normalize_field_text()`
  (lowercase, collapse whitespace, strip outer punctuation), `normalize_modality_text()`
  (map may/shall/must/shall not/must not/no person shall to canonical forms),
  `repair_field_span()` (deterministic exact-match unique-fix for wrong spans),
  `repair_response_spans()` (iterate all clauses × 6 fields, repair, preserve
  nulls, validate)
- **Tests**: `test_fallback.py` (29 tests) + `test_normalization.py` (38 tests)
  covering trigger logic, mock client, hybrid extraction, no-network guarantees,
  and span repair edge cases.

R6 does NOT call any real LLM API. No `.env` file, no API keys, no network.
All mock responses are pre-configured synthetic data.

## R7 Scope

R7 adds a safety-gated LLM provider configuration layer, secret redaction
utilities, provider-independent request/response structures, a mock transport,
and an OpenAI-compatible request builder scaffold.

- **`llm_config.py`** — `LLMConfig` dataclass (enabled=False by default,
  provider="mock"), `LLMConfigError`, `LLMProvider` constants, `redact_secret()`
  / `redact_mapping()` for key safety, `LLMConfig.from_env()` (only reads
  `BPC_HYBRID_LLM_*` vars, no `.env` / dotenv)
- **`llm_client.py`** — `LLMRequest` / `LLMResponse` (provider-independent,
  no API keys), `LLMTransport` protocol, `MockLLMTransport` (simulates valid
  JSON, invalid JSON, invalid schema, transport error), `OpenAICompatibleRequestBuilder`
  (constructs payloads — no openai SDK, no requests/httpx, no network),
  `parse_llm_json_response()` (JSON parse → dict check → from_dict → validate;
  strips markdown fences), `validate_llm_extraction_response()`,
  `LLMFallbackAdapter` (bridges LLM path into R6 `FallbackRequest`/`FallbackResult`)
- **Tests**: `test_llm_config.py` + `test_llm_client.py` + `test_llm_dry_run.py` (124 tests, all passed;
  includes R7.1 hardened validation, R7.2 base_url secret coverage,
  and R8 controlled dry-run harness)
- **Integration**: `extract_hybrid()` in fallback.py accepts any client with
  `.complete(FallbackRequest) → FallbackResult` (duck-typed)

R7 / R7.1 does **not** call real LLM APIs, does not access the network, does not
read `.env` files, does not store raw responses, and does not produce
benchmark results. Real LLM execution remains disabled by default
(`LLMConfig.enabled = False`) and must be authorized in a later stage.

## Dataset and Claim Boundary

The future formal evaluation target is a **Sun-aligned GDPR + BPMN dataset**, compared against Sun-style rule baseline and Winter-style textual baseline on precision / recall / F1 / AP / MAP.

**EStG / Austrian Income Tax Act** may only be used later as an optional generalization corpus and cannot replace the Sun-aligned main benchmark.

This project currently does **not** claim to outperform Sun-style baselines, Winter-style textual baselines, or any LLM baseline. Synthetic prototype data, if introduced later, is used for pipeline sanity checks only — not for benchmark claims.

## Reproducibility Notes

Implementation issues, audit findings, and resolutions are tracked in [`docs/issue_log.md`](docs/issue_log.md).

The issue log is intended to support reproducibility and later thesis/paper writing. It does not report formal benchmark results.

## Next Stage

R10.4 has completed the documentation claim-boundary audit.
No over-claims, benchmark language, method-validation language, or Sun
comparison language found in any R10 documentation.

All 486 offline tests pass.

**R10.4 后必须等待 Codex 审计，才能决定是否进入 R11 或任何 formal experiment。**
