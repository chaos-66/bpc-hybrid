# R11 Plan — Real Fallback Schema Alignment and Single-call Entrypoint

## 1. Current Status

R10 is closed and accepted:

- **R10.2/R10.2.1** — Mock optional fallback pipeline accepted (31 mock-only tests pass).
- **R10.3** — Single-sample real fallback pipeline smoke reached the real provider but ended as `SINGLE_SAMPLE_REAL_FALLBACK_SCHEMA_INVALID`. The real LLM response did not match the project `MultiClauseExtractionResponse` schema. The conservative fallback path correctly returned the rule-first result. No raw response saved, no batch, no benchmark.
- **R10.4/R10.4.1** — Documentation and claim-boundary cleanup accepted. R10.3 metadata (provider/model/entrypoint/adapter/transport) and real-call count evidence limitation are recorded.

R10 did **not** perform benchmark, accuracy evaluation, method validation, Sun comparison, or real GDPR/BPMN evaluation.

## 2. Problem Statement

R10.3 demonstrated that:

1. API connectivity to the real provider succeeds.
2. The empty-rule trigger path (`_should_trigger_optional_fallback`) works correctly.
3. The real LLM returns structured JSON, but the field names do not match the project `ClauseExtraction` / `MultiClauseExtractionResponse` schema.
4. The `LLMFallbackAdapter` correctly rejects schema-invalid responses and returns the rule-first result, preserving conservative behavior.

The root cause is that the project's system prompt (defined in `LLMFallbackAdapter`) does not enforce the exact field names expected by `MultiClauseExtractionResponse`. The LLM produces semantically similar fields with different names, which fail `MultiClauseExtractionResponse.model_validate()`.

Additionally, R10.4.1 identified that the inline Python execution path used in R10.3 cannot independently prove historical real API call count. Future real-API stages need a dedicated audited single-call entrypoint.

## 3. R11 Goals

R11 should plan and then implement a safer real-fallback path that can produce schema-valid project output while preserving:

- **Rule-first primary behavior**: The rule-first extractor remains the default path.
- **Optional fallback only**: LLM is invoked only when the rule-first output is empty or low-confidence.
- **Schema-gated acceptance**: LLM responses must pass `MultiClauseExtractionResponse` validation before being used.
- **Conservative fallback failure handling**: Schema-invalid fallback results return rule-first, never a partially-valid LLM output.
- **No raw response storage**: Raw API responses are not saved to disk or committed.
- **No batch by default**: Exactly one API call per authorized smoke.
- **One-call real API controls**: A dedicated audited single-call script/CLI entrypoint records safe call-count metadata.
- **No benchmark/accuracy/method-validation overclaims**: Planning and implementation stages maintain the same strict claim boundary as R10.

## 4. Non-goals

Explicit non-goals for all R11 stages:

- No benchmark.
- No accuracy claim.
- No method-validation claim.
- No Sun comparison.
- No real GDPR/BPMN evaluation.
- No formal BPMN compliance checking.
- No over-compliance detection claim.
- No batch real API calls.
- No raw response storage.
- No `.env` content exposure in audit or documentation.

## 5. Proposed Stage Plan

### R11.1 — Schema Alignment Design

**Type**: Planning/design-only.

Decide the approach for aligning real LLM output with the project schema. Options include stricter prompt engineering, post-hoc normalizer/adapter mapping, or two-step validation/repair (see §8).

**Deliverable**: Design document analyzing tradeoffs.

**Gates**: Codex audit before R11.2.

### R11.2 — Mock-only Schema Alignment Implementation

**Type**: Implementation, mock-only.

Implement the chosen schema-alignment logic using mock LLM responses only. No real API calls.

**Scope**:
- Update system prompt / JSON skeleton / adapter logic.
- Add mock tests that simulate schema-mismatched LLM output and verify repair/normalization.
- Ensure existing mock fallback pipeline tests still pass.
- Keep `LLMFallbackAdapter` backward-compatible.

**Gates**: All mock tests pass; Codex audit before R11.3.

### R11.3 — Dedicated Single-call Real API Entrypoint

**Type**: Implementation, CLI/script, no real API call during implementation.

Implement or document a dedicated audited CLI/script for exactly one real API call with safe call-count metadata (see §7). The entrypoint itself does not make real API calls during R11.3 — it only provides the controlled interface.

**Scope**:
- A single-call wrapper that records `attempted_call_count`, `successful_call_count`, and safety metadata.
- No raw response printed or saved.
- Explicit authorization variable or flag required.
- Works with mock provider for offline testing.

**Gates**: Offline tests pass; Codex audit before R11.4.

### R11.4 — Single-sample Real Schema-aligned Smoke

**Type**: Real API, single-sample only.

Only after R11.2 and R11.3 pass Codex audit AND the user separately authorizes.

**Scope**:
- One synthetic sentence only (e.g., the same `r10_3_real_fallback_smoke_001` input or equivalent).
- Uses the dedicated single-call entrypoint from R11.3.
- Uses the schema-aligned adapter from R11.2.
- Records all safety metadata.
- No raw response saved.

**Gates**: User authorization; Codex audit after.

### R11.5 — Documentation and Claim-boundary Cleanup

**Type**: Documentation-only.

Record the R11.4 result without overclaiming. Update README, experiment_log, and issue_log.

**Gates**: Codex audit; closes R11.

## 6. Safety Gates

Required safety gates for every R11 stage:

| Gate | Description |
|------|-------------|
| `.env` ignored and untracked | `.gitignore` rule verified; `git check-ignore -v .env` passes |
| No `.env` content read in audit | `BPC_HYBRID_DISABLE_PROJECT_ENV=1` set; no `Get-Content .env` |
| Explicit real API authorization | `--execute-real-api` flag or equivalent env var required |
| One-call limit | Script/CLI enforces at most one real API call per invocation |
| No retry unless separately authorized | Failed real API calls do not auto-retry |
| No batch | Batch mode disabled; `batch: false` recorded in metadata |
| No raw response saved | Raw API output never written to disk or committed |
| Schema validation required | All LLM responses validated against `MultiClauseExtractionResponse` |
| Fallback failure returns rule-first | Schema-invalid or transport-error paths return rule-first conservatively |
| Codex audit after every stage | Each R11.x stage gated on Codex local-only audit |

## 7. Dedicated Single-call Entrypoint Requirements

The R11.3 entrypoint must record the following safe metadata without printing or saving raw responses or secrets:

| Field | Type | Description |
|-------|------|-------------|
| `source_id` | `str` | Unique identifier for this smoke run |
| `input_text` | `str` | The synthetic input sentence |
| `provider` | `str` | Provider name (e.g., `openai_compatible`) |
| `model` | `str` | Model name (e.g., `qwen3.7-max`) |
| `entrypoint` | `str` | Entrypoint function or script name |
| `real_api_call_performed` | `bool` | Whether a real API call was attempted |
| `attempted_call_count` | `int` | Number of API call attempts made |
| `successful_call_count` | `int` | Number of API calls that reached the server |
| `fallback_status` | `str` | `fallback_schema_valid`, `fallback_schema_invalid`, or `fallback_transport_error` |
| `schema_valid` | `bool` | Whether the LLM response passed schema validation |
| `raw_response_saved` | `bool` | Must be `false` |
| `secret_redacted` | `bool` | Must be `true` |
| `batch` | `bool` | Must be `false` |

The entrypoint must **not** print or save:
- API keys, base URLs, or other secrets.
- Raw API response bodies.
- LLM-generated text that could be misconstrued as benchmark data.

## 8. Schema Alignment Options

Three approaches are considered for aligning real LLM output with the project `MultiClauseExtractionResponse` schema.

### Option 1: Prompt-only stricter JSON instruction

**Approach**: Strengthen the system prompt and user prompt in `LLMFallbackAdapter` to explicitly require the exact field names (`modality`, `actor`, `action`, `condition`, `constraint`, `exception`) and the `MultiClauseExtractionResponse` JSON structure. Include a JSON skeleton in the prompt.

**Pros**:
- No new code paths.
- No adapter/mapping layer needed.
- Aligned with R9.7's `build_schema_json_skeleton()` approach.

**Cons**:
- Relies on LLM instruction-following; may still produce non-conforming output.
- No post-hoc correction if the LLM ignores the skeleton.

**Risk**: Medium. Prompt-only approaches are not guaranteed to produce schema-conformant output.

**Recommendation**: Try first as the lowest-cost option. If R11.4 smoke still fails, fall back to Option 2 or 3.

### Option 2: Adapter/normalizer mapping model output to project schema

**Approach**: Add a post-processing layer that maps known alternative field names (e.g., `normative_type` → `modality`, `subject` → `actor`, `object` → `action`, `conditions` → `condition`, `original_text` → discard) to the project schema fields. The mapping is deterministic and does not modify the raw LLM response.

**Pros**:
- Handles common LLM field-name variations robustly.
- Deterministic — no reliance on LLM instruction-following.
- Can be tested with mock responses.

**Cons**:
- Adds a new code path (adapter/mapper layer).
- Must be maintained if LLM output patterns change.
- Risk of incorrect mapping if LLM uses semantically different fields.

**Risk**: Low-Medium. Mapping is deterministic and testable.

**Recommendation**: Implement as a fallback if Option 1 alone is insufficient. Can be combined with Option 1.

### Option 3: Two-step validation/repair under mock-only first

**Approach**: Extend the `repair_response_spans()` pattern from R6 normalization to also repair field-name mismatches. The repair step runs before schema validation. If repair fails, conservative path returns rule-first.

**Pros**:
- Reuses existing normalization patterns.
- Clear separation of concerns: repair → validate → accept/reject.
- Mock-testable without real API.

**Cons**:
- More complex than Option 1 or 2 alone.
- Span repair is already implemented; adding field-name repair increases scope.

**Risk**: Low. Built on proven R6 patterns.

**Recommendation**: Merge with Option 2. The adapter is the repair step.

### Recommended Strategy

1. **R11.1**: Design the combined approach (Option 1 + Option 2): strengthened prompt with JSON skeleton, plus an adapter/mapper layer as deterministic post-processing.
2. **R11.2**: Implement both in mock-only mode. Test with mock responses that simulate R10.3-style field-name mismatches.
3. **R11.3**: Build the dedicated single-call entrypoint wrapping the aligned pipeline.
4. **R11.4**: Single-sample real API smoke only after all offline gates pass and user authorizes.

## 9. Recommended Next Stage

**R11.1 — Schema Alignment Design** (design-only, not implementation).

R11.1 should produce a concrete design document that:
- Selects and details the schema-alignment approach.
- Specifies exact prompt changes.
- Specifies the adapter/mapper interface.
- Defines mock test cases for R10.3-style mismatches.
- Does not execute any code changes, real API calls, or benchmarks.

## 10. Claim Boundary

R11.0 is **planning-only**. It does not:

- Execute real API calls.
- Run benchmarks.
- Evaluate accuracy.
- Validate the method.
- Compare against Sun or any baseline.
- Use real GDPR/BPMN data.
- Produce any experimental result.

All subsequent R11.x stages inherit the same claim-boundary rules as R10:
single-sample, schema-gated, conservative failure, no benchmark, no accuracy claim, no method validation.
