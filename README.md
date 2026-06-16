# bpc-hybrid

## Current Status

**R0 ✅ | R1 ✅ | R1.5 ✅ | R1.6 ✅ | R2 ✅ | R3 ✅ | R4 ✅ | R5 ✅ | R5.1 ✅ | R6 ✅ | R7 ✅**

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
- R6 ✅: Mock LLM fallback interface and deterministic normalization foundation completed.
- R7 ✅: Safe LLM fallback adapter scaffold completed.

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
- **Tests**: `test_llm_config.py` (24 tests) + `test_llm_client.py` (28 tests)
- **Integration**: `extract_hybrid()` in fallback.py accepts any client with
  `.complete(FallbackRequest) → FallbackResult` (duck-typed)

R7 does **not** call real LLM APIs, does not access the network, does not
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

R8 — Codex R7 audit — must pass before any real LLM experimentation begins.
R8 will verify: no network calls, no .env access, no API key leaks,
all config defaults disabled, mock transport only.
