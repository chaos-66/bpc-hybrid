# R10.1 — Mock-First Fallback Integration Design

> **R10.1 is design-only.**
> No implementation. No source code changes. No test changes.
> No real API calls. No `.env` reads. No benchmark. No validation claims.

---

## 1. R10.1 Goal

Design how a real-LLM fallback path can be integrated into the existing
rule-first pipeline using mock/offline contracts only.

The design must be mock-first, rule-first, schema-gated, and fully
auditable by Codex before any implementation in R10.2.

---

## 2. Current Architecture (from read-only code inspection)

### 2.1 Component Map

| File | Responsibility | Key Exports |
|------|---------------|-------------|
| `src/bpc_hybrid/schema.py` | Data structures for extraction results | `MultiClauseExtractionResponse`, `ClauseExtraction` (13 fields), `FieldSpan` (4 fields), `SchemaValidationError` |
| `src/bpc_hybrid/extractor.py` | Rule-based marker extraction (modality/actor/action/condition) | `extract_rule_first(source_text, source_id) -> MultiClauseExtractionResponse` |
| `src/bpc_hybrid/splitter.py` | Multi-clause splitting of source text | `split_normative_clauses()`, `ClauseSegment` |
| `src/bpc_hybrid/fallback.py` | Fallback trigger logic + mock client + hybrid extractor | `should_trigger_fallback()`, `FallbackDecision`, `FallbackRequest`, `FallbackResult`, `MockLLMFallbackClient`, `extract_hybrid()` |
| `src/bpc_hybrid/llm_client.py` | LLM transport, parsing, adapter, prompt builder | `LLMRequest`, `LLMResponse`, `LLMTransport`, `MockLLMTransport`, `RealAPITransport`, `LLMFallbackAdapter`, `parse_llm_json_response()`, `build_schema_json_skeleton()`, `_SCHEMA_PROMPT_INSTRUCTIONS` |
| `src/bpc_hybrid/llm_config.py` | `.env` loading, config models | `LLMConfig`, `LLMProvider`, `load_project_env_file()`, `project_env_disabled()` |
| `src/bpc_hybrid/normalization.py` | Span repair for fallback results | `repair_response_spans()` |
| `src/bpc_hybrid/evaluator.py` | Clause/field-level metrics | `evaluate_responses()`, `load_gold_responses()` |
| `scripts/run_llm_dry_run.py` | CLI harness for single-sample dry-runs | `main()`, gate checks, `classify_real_api_error_status()`, `_success()`, `_error()` |
| `scripts/evaluate_multi_clause.py` | CLI for gold-vs-pred evaluation | `main()`, runs `extract_rule_first()` on input, computes F1 |
| `scripts/check_project_health.py` | Read-only project health check | Calls `project_health()` from `smoke.py` |

### 2.2 Current Data Flow (from `run_llm_dry_run.py`)

```
CLI args → gate checks → [optional .env load]
  → extract_rule_first(text, source_id)          # rule-first
  → LLMFallbackAdapter(config, transport)
       .complete(FallbackRequest(...))            # LLM fallback
  → error classification / success emit
```

### 2.3 Existing Integration Points

1. **`extract_hybrid()`** in `fallback.py` already chains rule-first → trigger-check → fallback.
   It accepts any duck-typed `fallback_client` with `.complete(FallbackRequest) -> FallbackResult`.
   `LLMFallbackAdapter` already satisfies this interface.

2. **`LLMFallbackAdapter.complete()`** already:
   - Checks `config.enabled`
   - Builds schema-aware prompts (`build_schema_json_skeleton()` + `_SCHEMA_PROMPT_INSTRUCTIONS`)
   - Calls `transport.send(llm_req)`
   - Parses + validates via `parse_llm_json_response()`
   - Returns `FallbackResult`

3. **`run_llm_dry_run.py`** already does the full chain but in a CLI-only
   context, not as a reusable pipeline component.

### 2.4 Gaps (to be confirmed in R10.2)

- `run_llm_dry_run.py` currently runs rule-first AND fallback unconditionally
  (it does not call `should_trigger_fallback()`). The trigger logic exists
  but is not wired into the CLI harness.
- The `clause_id` and `source_id` fields are populated in `parse_llm_json_response()`
  and the adapter, but provenance (rule-first vs fallback) is not tracked in the output.
- `evaluate_multi_clause.py` only calls `extract_rule_first()` — it has no
  fallback path, mock or real.
- No unified pipeline module exists — the components are scattered across
  `extractor.py`, `fallback.py`, `llm_client.py`, and `run_llm_dry_run.py`.

---

## 3. Design Principles

```
Rule-first extraction remains primary.
LLM fallback is optional and gated.
LLM fallback must return MultiClauseExtractionResponse.
LLM fallback must not bypass schema validation.
LLM fallback must not save raw response.
LLM fallback must not log secrets.
LLM fallback must not execute unless explicitly enabled.
All new real API behavior must have mock-first tests.
```

---

## 4. Mock Fallback Interface Proposal

### 4.1 Proposed Architecture (pseudo-code, not implementation)

```
                     ┌─────────────────────┐
  source_text ──────▶│ extract_rule_first() │──────▶ rule_response
  source_id          └──────────┬──────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │ should_trigger_fb()  │
                     │ (confidence/missing  │
                     │  field checks)       │
                     └──────────┬──────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
              no trigger              trigger
                    │                       │
                    ▼                       ▼
              rule_response      ┌──────────────────────┐
                                 │ fallback_client       │
                                 │ .complete(request)    │
                                 │ (mock or real, gated) │
                                 └──────────┬───────────┘
                                            │
                                ┌───────────┴───────────┐
                                │                       │
                           success                  error
                                │                       │
                                ▼                       ▼
                     FallbackResult             FallbackResult
                     (response=parsed)          (error=message)
                                │                       │
                                ▼                       ▼
                     ┌──────────────────────────────────┐
                     │ merge: rule_response + fallback   │
                     │ (preserve provenance)             │
                     └──────────────┬───────────────────┘
                                    │
                                    ▼
                          MultiClauseExtractionResponse
```

### 4.2 Proposed Interface (pseudo-code)

```python
# NOT implementation — design contract only.
# All types already exist in the codebase.

from bpc_hybrid.fallback import (
    FallbackRequest,
    FallbackResult,
    should_trigger_fallback,
)
from bpc_hybrid.schema import MultiClauseExtractionResponse


class FallbackProvider:
    """Protocol for fallback clients (mock or real).

    Already satisfied by:
    - MockLLMFallbackClient (fallback.py)
    - LLMFallbackAdapter (llm_client.py)
    """
    def complete(self, request: FallbackRequest) -> FallbackResult:
        ...


def extract_with_optional_llm_fallback(
    source_id: str,
    source_text: str,
    *,
    fallback_enabled: bool = False,
    fallback_provider: FallbackProvider | None = None,
    field_confidence_threshold: float = 0.5,
    clause_confidence_threshold: float = 0.5,
) -> MultiClauseExtractionResponse:
    """Rule-first extraction with optional gated LLM fallback.

    Input:
        source_id: str        — unique identifier for this extraction
        source_text: str      — the regulatory sentence to extract
        fallback_enabled: bool — if False, skip trigger check entirely
        fallback_provider      — must implement .complete(FallbackRequest)
        field_confidence_threshold — for should_trigger_fallback()
        clause_confidence_threshold — for should_trigger_fallback()

    Output:
        MultiClauseExtractionResponse with:
        - source_id: str
        - source_text: str
        - clauses: list[ClauseExtraction]
        - _provenance: "rule-first" | "mock-fallback" | "real-fallback"
          (R10.1 does NOT add provenance field; R10.2 decides representation)

    Error handling:
        - If fallback is disabled → return rule_response as-is
        - If no trigger needed → return rule_response as-is
        - If trigger + fallback succeeds → return fallback result
        - If trigger + fallback fails:
          - schema-invalid → return rule_response (fallback rejected)
          - network error → return rule_response (fallback unavailable)
          - config missing → return rule_response (fallback unavailable)
        - NEVER raise unhandled exception from fallback path

    Schema validation:
        - Rule-first output is always schema-valid (guaranteed by extractor)
        - Fallback output must pass parse_llm_json_response() before use
        - Invalid fallback output is rejected silently; rule-first is returned

    Fallback-disabled behavior:
        When fallback_enabled=False:
        - should_trigger_fallback() is NOT called
        - fallback_provider.complete() is NOT called
        - Real API flags are NOT checked
        - .env is NOT read
        - Returns rule_response directly

    Mock provider behavior:
        MockLLMFallbackClient or LLMFallbackAdapter+MockLLMTransport:
        - No network, no .env, no API key
        - Returns pre-configured or auto-generated MultiClauseExtractionResponse
        - Schema-invalid simulation possible via flags
    """
    # 1. Rule-first (always)
    rule_response = extract_rule_first(source_text, source_id=source_id)

    # 2. Gate: fallback disabled
    if not fallback_enabled:
        return rule_response

    # 3. Gate: no provider
    if fallback_provider is None:
        return rule_response

    # 4. Trigger check
    decision = should_trigger_fallback(
        rule_response,
        field_confidence_threshold=field_confidence_threshold,
        clause_confidence_threshold=clause_confidence_threshold,
    )

    if not decision.should_trigger:
        return rule_response

    # 5. Execute fallback
    request = FallbackRequest(
        source_text=source_text,
        source_id=source_id,
        rule_response=rule_response,
        reasons=decision.reasons,
    )

    try:
        result = fallback_provider.complete(request)
    except Exception:
        # Fallback unavailable — return rule-first
        return rule_response

    # 6. Validate fallback result
    if not result.is_valid or result.response is None:
        # Schema-invalid or error — return rule-first
        return rule_response

    return result.response
```

### 4.3 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Fallback always returns rule-first on failure | Conservative — never lose the rule-first result |
| No automatic fallback | Must be explicitly enabled via flag |
| No raw response in output | `raw_response_saved: false` enforced |
| No schema change in R10.1 | Provenance tracking deferred to R10.2 |
| Uses existing types only | `FallbackRequest`, `FallbackResult`, `MultiClauseExtractionResponse` already exist |
| `LLMFallbackAdapter` already satisfies `FallbackProvider` | No new interface needed |

---

## 5. Fallback Trigger Policy

```
fallback is disabled by default
fallback can be enabled only by explicit CLI/config gate
fallback should be considered only when rule-first extraction is
  empty, low-confidence, or explicitly requested in a controlled smoke
fallback must never trigger batch real API silently
```

### Trigger conditions (already implemented in `should_trigger_fallback()`)

1. Schema validation failure on rule-first output
2. Missing actor in a normative clause
3. Missing action in a normative clause
4. Any semantic field confidence below threshold (default 0.5)
5. Clause-level confidence below threshold (default 0.5)

Non-normative clauses (modality is `None`) are **not** checked for
missing fields — they do not trigger fallback.

---

## 6. Result Merge Policy

```
No automatic replacement of rule-first results in R10.1.
Mock design must preserve provenance.
If both rule-first and fallback produce results, merged output must
mark source of extraction.
No schema change unless separately planned and audited.
```

### R10.1 Position on Provenance

R10.1 does **not** add provenance fields to the schema. R10.2 must
decide whether provenance is represented:

- **Externally** (return a `(response, provenance)` tuple, or wrap in
  a dataclass with a `provenance` field alongside `MultiClauseExtractionResponse`)
- **Internal to the schema** (add an optional `provenance` field to
  `MultiClauseExtractionResponse` or `ClauseExtraction`)

The conservative choice for R10.2 is to keep provenance external to
avoid any accidental benchmark interpretation.

---

## 7. Error/Status Policy

Inherits R9 classification boundaries:

| Status | Meaning | Action |
|--------|---------|--------|
| `fallback_disabled` | Fallback gate is off | Return rule-first |
| `fallback_mock_used` | Mock provider returned valid schema | Accept fallback |
| `fallback_schema_valid` | Real/mock fallback schema valid | Accept fallback |
| `fallback_schema_invalid` | LLM response doesn't parse as schema | Reject fallback, return rule-first |
| `fallback_network_error_redacted` | Transport/network/DNS/timeout error | Reject fallback, return rule-first |
| `fallback_config_missing` | API key/base URL/model missing | Reject fallback, return rule-first |

**Inherited invariants from R9:**

```
schema invalid != network error
raw response is never saved
secret/base_url/API key redacted
```

---

## 8. R10.2 Mock-Only Test Plan

These tests must pass before any real API call in R10.3. None of these
tests use `--execute-real-api`, real network, or `.env`.

| # | Test | What It Verifies |
|---|------|-----------------|
| 1 | `test_fallback_disabled_returns_rule_first` | `fallback_enabled=False` skips trigger + fallback |
| 2 | `test_mock_fallback_valid_schema_accepted` | Mock provider valid response is returned |
| 3 | `test_mock_fallback_schema_invalid_rejected` | Schema-invalid mock response → rule-first returned |
| 4 | `test_no_raw_response_saved` | `raw_response_saved: false` in all paths |
| 5 | `test_no_secret_leak` | No API key, base_url, or secret in output/repr |
| 6 | `test_no_env_read_in_mock_mode` | `BPC_HYBRID_DISABLE_PROJECT_ENV=1` respected |
| 7 | `test_no_real_api_in_mock_mode` | `real_api_call_performed: false` |
| 8 | `test_no_batch` | Only one extraction per call |
| 9 | `test_rule_first_not_silently_overwritten` | If fallback fails, rule-first result is returned |
| 10 | `test_empty_rule_output_routes_to_fallback` | Empty/low-confidence rule → fallback triggered when enabled |
| 11 | `test_fallback_not_triggered_without_gate` | `fallback_enabled=False` never triggers, even on low confidence |
| 12 | `test_trigger_reasons_recorded` | `DecisionReason` list available in `FallbackRequest` |
| 13 | `test_provenance_distinguishable` | External provenance marking works (no schema change needed) |

---

## 9. R10.3 Future Real API Smoke Guard (for reference only)

```
R10.3 may run at most one real API call only after R10.2 passes and
Codex approves.

R10.3 must use one synthetic sentence only.
R10.3 must not use real GDPR/BPMN/Sun data.
R10.3 must not save raw response.
R10.3 must not benchmark.
R10.3 must not claim accuracy or method validation.
R10.3 must require all R9 gate flags:
  --execute-real-api
  --confirm-real-api-single-sample
  BPC_HYBRID_R9_REAL_RUN_CONFIRMED=YES_SINGLE_SAMPLE_ONLY
```

---

## 10. Exit Criteria

- [x] `docs/r10_1_mock_integration_design.md` exists
- [x] Design is mock-first
- [x] Design is rule-first
- [x] Design is schema-gated
- [x] Design has no real API execution
- [x] Design has no code/test/data changes
- [x] Claim boundary preserved
- [ ] Codex can audit the design (pending Codex review)

---

## 11. Claim Boundary (Repeated for Emphasis)

```
R10.1 IS A DESIGN DOCUMENT ONLY.
R10.1 DOES NOT IMPLEMENT FALLBACK INTEGRATION.
R10.1 DOES NOT EXECUTE REAL API CALLS.
R10.1 DOES NOT MODIFY SOURCE CODE.
R10.1 DOES NOT MODIFY TESTS.
R10.1 DOES NOT BENCHMARK.
R10.1 DOES NOT VALIDATE THE METHOD.
R10.1 DOES NOT COMPARE AGAINST SUN BASELINE.
R10.1 DOES NOT USE REAL GDPR/BPMN DATA.
```
