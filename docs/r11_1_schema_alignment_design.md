# R11.1 — Schema Alignment Design for Real Fallback Output

## 1. Design Status

R11.1 is **design-only**.

- No source code was changed.
- No tests were changed.
- No data was changed.
- No real API call was executed.
- No `.env` content was read.
- No raw response was saved.
- No benchmark, accuracy evaluation, method validation, Sun comparison, or real GDPR/BPMN evaluation was performed.

R11.1 produces one deliverable: this design document (`docs/r11_1_schema_alignment_design.md`). Implementation is deferred to R11.2.

---

## 2. Current Project Schema Summary

Based on `src/bpc_hybrid/schema.py` (schema version `0.1.0`).

### 2.1 Top-level: `MultiClauseExtractionResponse`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | `str` | Yes (`""` raises) | Always `"0.1.0"` |
| `source_id` | `str` | Yes (`""` raises) | Document identifier |
| `source_text` | `str` | Yes (`""` raises) | Full regulatory text processed |
| `clauses` | `list[ClauseExtraction]` | Yes (must be list) | Extracted clauses |

**Unknown top-level keys are rejected** — `from_dict()` checks against the allowed set `_MULTI_CLAUSE_KEYS = {"schema_version", "source_id", "source_text", "clauses"}`.

### 2.2 Clause-level: `ClauseExtraction`

13 fields, ALL required by `from_dict()`:

| # | Field | Type | Nullable |
|---|-------|------|----------|
| 1 | `clause_id` | `str` | No (must be non-empty) |
| 2 | `source_id` | `str \| None` | Yes |
| 3 | `source_text` | `str` | No (must be non-empty) |
| 4 | `clause_text` | `str` | No (must be non-empty) |
| 5 | `clause_span_start` | `int` | No (>= 0) |
| 6 | `clause_span_end` | `int` | No (>= span_start) |
| 7 | `modality` | `FieldSpan \| None` | Yes |
| 8 | `actor` | `FieldSpan \| None` | Yes |
| 9 | `action` | `FieldSpan \| None` | Yes |
| 10 | `condition` | `FieldSpan \| None` | Yes |
| 11 | `constraint` | `FieldSpan \| None` | Yes |
| 12 | `exception` | `FieldSpan \| None` | Yes |
| 13 | `confidence` | `float` | No (in [0.0, 1.0]) |

**Unknown clause-level keys are rejected** — `from_dict()` checks against `_CLAUSE_KEYS`.

### 2.3 Field-level: `FieldSpan`

4 fields, ALL required when present (not null):

| Field | Type | Constraints |
|-------|------|-------------|
| `text` | `str` | Non-empty |
| `span_start` | `int` | >= 0 |
| `span_end` | `int` | >= span_start, <= len(source_text) |
| `confidence` | `float` | [0.0, 1.0] |

### 2.4 Schema Validation Behavior

- `MultiClauseExtractionResponse.validate()` — validates top-level fields + delegates to each clause.
- `ClauseExtraction.validate()` — validates clause_text, offsets, confidence, and all 6 semantic `FieldSpan` fields.
- `FieldSpan.validate(source_text=...)` — validates text, offsets, confidence, and optional cross-check against source_text.
- `from_dict()` on all three types enforces:
  - Unknown keys → `SchemaValidationError`.
  - Missing required keys → `SchemaValidationError`.
  - Wrong types → `SchemaValidationError`.

### 2.5 Current LLMFallbackAdapter Prompt

From `src/bpc_hybrid/llm_client.py`:

- **`system_prompt`** (line ~572): Instructs the LLM to output a single JSON matching `MultiClauseExtractionResponse` schema exactly, use only exact field names from the skeleton, never add extra fields, use `null` for undetermined fields.
- **`user_prompt`** (constructed at line ~606): Includes the JSON skeleton from `build_schema_json_skeleton()` and `_SCHEMA_PROMPT_INSTRUCTIONS`.
- **`_SCHEMA_PROMPT_INSTRUCTIONS`** (line ~534): Explicitly requires 13 clause fields, 4 FieldSpan fields, integer offsets, exclusive span_end, float confidence, no markdown, no explanation, output only JSON.
- **`build_schema_json_skeleton()`** (line ~479): Returns a valid example `MultiClauseExtractionResponse` dict with all 13 clause fields present.

The prompt already contains strong schema-enforcement instructions. The R10.3 mismatch demonstrates that even with this prompt, the LLM may still produce non-conforming output.

---

## 3. Observed R10.3 Mismatch Summary

Based on R10.3 committed documentation (no raw response included here).

### 3.1 What Is Known

The real LLM (provider: `openai_compatible`, model: `qwen3.7-max`) returned a response that:

- Had valid HTTP status and parseable JSON.
- Contained semantically meaningful content (not empty, not garbage).
- Used field names that differ from `MultiClauseExtractionResponse` / `ClauseExtraction`.

### 3.2 Known Non-matching Field Names

From R9.5/R9.6/R10.3 documentation (high-level only, no raw response body):

| Model output field | Project schema expects |
|---|---|
| `conditions` | `condition` (singular FieldSpan or null) |
| `normative_type` | `modality` (FieldSpan or null) |
| `object` | Not in schema (no matching field) |
| `original_text` | Not in schema (closest is `source_text` or `clause_text`, string not FieldSpan) |
| `subject` | `actor` (FieldSpan or null) |

Additional unknown top-level keys may have been present.

### 3.3 Conservative Fallback Behavior

The `LLMFallbackAdapter.complete()` method:
1. Calls `parse_llm_json_response(llm_resp.content)` which calls `MultiClauseExtractionResponse.from_dict()`.
2. `from_dict()` rejects unknown top-level keys → `SchemaValidationError`.
3. The error is caught, producing `FallbackResult(error=...)`.
4. `extract_with_optional_llm_fallback()` sees the error and returns rule-first.

This conservative path is correct. The issue is not in the rejection logic — it's in the LLM output format.

### 3.4 What This Represents

R10.3 showed **schema mismatch, not model failure and not benchmark failure**.

---

## 4. Candidate Alignment Strategies

### Option A — Prompt-only stricter JSON instruction

**Approach**: Strengthen the existing system prompt and `_SCHEMA_PROMPT_INSTRUCTIONS` further. Add explicit negative constraints naming the non-matching field names the model should NOT use (`conditions`, `normative_type`, `object`, `original_text`, `subject`). Emphasize that `modality`, `actor`, `action`, `condition`, `constraint`, `exception` are the ONLY allowed semantic field names.

**Pros**:
- Zero code complexity.
- No new modules or classes.
- Prompt changes are testable and reversible.

**Cons**:
- Cannot guarantee LLM instruction-following.
- Some models are finetuned to output specific field names and resist prompt overrides.
- R10.3 already had strong schema instructions in prompt — adding more may not help.

**Risk**: **Medium-high if used alone**. Prompt-only approaches are unreliable for strict schema enforcement across providers.

**Verdict**: Useful as a reinforcement layer, but **not sufficient as the sole strategy**.

---

### Option B — Adapter / normalizer mapping

**Approach**: Add a post-processing layer between LLM output parsing and schema validation. The normalizer inspects the raw JSON dict, maps known alternative field names to project schema fields, and produces a cleaned candidate dict for schema validation.

**Mapping Table (based on observed mismatches)**:

| Model field | Maps to project field | Condition |
|---|---|---|
| `normative_type` | `modality` | Only if value is a dict (→ `FieldSpan`) or `null` |
| `subject` | `actor` | Only if value is a dict or `null` |
| `object` | *Do not map* | No matching field in `ClauseExtraction` |
| `original_text` | *Do not map* | No matching field in `ClauseExtraction`; discard |
| `conditions` | `condition` | Only if value is a dict or `null` |

**Normalizer rules**:
1. **Whitelist-only**: Only fields in the mapping table are renamed. Everything else passes through as-is.
2. **No invention**: If a model output field has no mapping target, it is **removed** (not renamed to a guessed target).
3. **Type check**: If a mapped field expects `FieldSpan | None` but the model value is a plain string, the field is set to `null` (conservative).
4. **Top-level enforcement**: Unknown top-level keys that are not in the mapping table are **removed** before schema validation.

**Pros**:
- Deterministic, testable, no LLM dependence.
- Handles the known mismatch patterns from R10.3.
- Can be implemented mock-only and validated before real API.
- Protected against future field-name variation.

**Cons**:
- Adds a new code path (normalizer module).
- Mapping table must be maintained if LLM output patterns change.
- Cannot recover from fundamentally wrong output (e.g., missing all fields).

**Risk**: **Low**. Deterministic, testable, narrow scope.

**Verdict**: **Recommended as primary defense**. Should be combined with Option A.

---

### Option C — Parser / validation / conservative rejection

**Approach**: Keep the existing strict validation unchanged. Only accept responses that pass `MultiClauseExtractionResponse.from_dict()` without any normalizer. Schema-invalid → return rule-first (current behavior).

**Pros**:
- Zero code changes.
- Proves the value of schema-gated acceptance.
- Already demonstrated to work safely in R10.3.

**Cons**:
- Does not resolve the schema mismatch — just gracefully handles it.
- Every future real API call may fail schema validation for the same reason.
- Defeats the purpose of LLM fallback if the LLM cannot produce acceptable output.

**Risk**: **Zero** (it's the current state). But not a path forward.

**Verdict**: **Retain as the safety net**, not as the solution. After normalizer (Option B), the schema validation in Option C is the final gate.

---

### Option D — Two-step repair loop

**Approach**: First call produces raw output; a second LLM call "repairs" the output to match the schema. Or, a dedicated repair prompt asks the LLM to fix its own output.

**Pros**:
- Could handle complex mismatches beyond field-name differences.
- Can leverage LLM's own understanding of the schema.

**Cons**:
- **Increases real API call count** — directly violates the one-call limit.
- R10.4.1 already identified call-count evidence limitation as a blocking concern.
- Two calls create ambiguity about which call produced the final result.
- Repair prompt may not succeed either.

**Risk**: **High**. Violates the single-call constraint established in R10.4.1 and R11.0.

**Verdict**: **Not recommended for any real API stage**. Could be explored as a mock-only research track separate from R11.

---

## 5. Recommended Design

**Recommended strategy: Option A + Option B + Option C (combined).**

### Layered Architecture

```
LLM raw JSON output
       │
       ▼
┌──────────────────────┐
│  Normalizer (Option B) │  ← Deterministic field-name mapping
│  - whitelist renaming   │     + unknown-field removal
│  - type coercion        │
│  - unknown-key removal  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Schema Validation     │  ← MultiClauseExtractionResponse.from_dict()
│  (Option C)            │     Strict: unknown keys, missing fields,
│                        │     wrong types all reject.
└──────────┬───────────┘
           │
     ┌─────┴─────┐
     │           │
  valid       invalid
     │           │
     ▼           ▼
 Fallback    Return
 accepted    rule-first
```

### Design Principles

1. **Prompt (Option A)** asks the LLM to use exact project field names — reinforced with negative constraints.
2. **Normalizer (Option B)** corrects known field-name mismatches deterministically — no LLM, no network, no `.env`.
3. **Schema validation (Option C)** is the final gate — only schema-valid output enters the fallback path.
4. **Conservative failure**: If normalizer + validation fails, return rule-first. Never accept schema-invalid fallback output.

### Hard Rules

- **No schema-invalid fallback output may be accepted.**
- **No guessed fields may be invented.**
- **No raw response may be saved.**
- **Normalizer must not call LLM.**
- **Normalizer must not read `.env`.**
- **Normalizer must not access network.**

---

## 6. Proposed Normalizer Boundary

### 6.1 Input / Output Contract

| Property | Description |
|----------|-------------|
| **Input** | A `dict` — the raw JSON parsed from LLM response |
| **Output** | A `dict` — cleaned and mapped, ready for `MultiClauseExtractionResponse.from_dict()` |
| **Side effects** | None. Pure function. |
| **LLM calls** | None. |
| **Network** | None. |
| **`.env` read** | None. |
| **Raw response storage** | None. |

### 6.2 Normalization Steps (in order)

1. **Top-level key normalization**: For each key in the raw dict:
   - If key is in `_MULTI_CLAUSE_KEYS` → keep as-is.
   - If key is in the whitelist mapping table (see §6.4) → rename to mapped key.
   - Otherwise → **remove** (do not pass unknown keys to schema validation).

2. **Clause-level key normalization** (for each dict in `clauses`):
   - If key is in `_CLAUSE_KEYS` → keep as-is.
   - If key is in the clause mapping table (see §6.4) → rename to mapped key.
   - Otherwise → **remove**.

3. **Field-level type coercion**: For each semantic field that expects `FieldSpan | None`:
   - If value is `None` → keep as `None`.
   - If value is a `dict` with `text`/`span_start`/`span_end`/`confidence` → keep (schema validation checks correctness).
   - If value is a plain `str` → set to `None` (cannot coerce — conservative).
   - If value is missing → set to `None`.

4. **Top-level required fields**: If `schema_version`, `source_id`, or `source_text` are missing from the raw dict, the normalizer sets them to sentinel values that will fail schema validation (preserving the rejection path).

### 6.3 Failure and Non-recovery Behavior

The normalizer is a **best-effort function**. It does not guarantee output validity. If the normalized dict still fails `MultiClauseExtractionResponse.from_dict()`:

- The caller (`LLMFallbackAdapter.complete()`) catches the `SchemaValidationError`.
- Returns `FallbackResult(error=...)`.
- `extract_with_optional_llm_fallback()` returns rule-first.

The normalizer must **never** force an invalid dict to pass validation by fabricating missing fields or guessing values.

### 6.4 Clause-level Field Mapping Table

Based on observed mismatches and project schema fields. Only fields that map to existing `_CLAUSE_KEYS` are listed.

| Model field | Project field | Notes |
|---|---|---|
| `normative_type` | `modality` | If dict → keep as FieldSpan candidate; if string → discard |
| `subject` | `actor` | If dict → keep as FieldSpan candidate; if string → discard |
| `object` | *Remove* | No matching field in ClauseExtraction |
| `original_text` | *Remove* | `source_text` and `clause_text` are already required strings in the top-level/clause; this field is redundant |
| `conditions` | `condition` | If dict → keep as FieldSpan candidate; if string → discard |

### 6.5 Top-level Field Mapping Table

`_MULTI_CLAUSE_KEYS = {"schema_version", "source_id", "source_text", "clauses"}`. No additional top-level fields have known alternatives. Unknown top-level keys are removed.

---

## 7. Prompt Boundary for Future R11.2

The R11.2 system prompt for `LLMFallbackAdapter` should be updated with additional schema enforcement. Based on the current prompt (which already has strong instructions), the following additions are recommended:

### 7.1 Reinforcement Statements to Add

```
Your response MUST be a single JSON object matching the
MultiClauseExtractionResponse schema.

- Output JSON ONLY — no markdown, no code fences, no explanation.
- Use EXACTLY these top-level keys:
  "schema_version", "source_id", "source_text", "clauses".
- Each clause MUST include ALL 13 fields:
  clause_id, source_id, source_text, clause_text,
  clause_span_start, clause_span_end,
  modality, actor, action, condition, constraint, exception,
  confidence.
- The ONLY allowed semantic field names are:
  "modality", "actor", "action", "condition", "constraint", "exception".
- DO NOT USE these field names:
  "normative_type", "subject", "object", "original_text", "conditions".
- Each semantic field is a FieldSpan object with 4 fields:
  "text", "span_start", "span_end", "confidence".
  Or null if the field cannot be determined.
- span_start and span_end are integer character offsets
  (0-indexed) into source_text. span_end is exclusive.
- confidence is a float in [0.0, 1.0].
- schema_version MUST be "0.1.0".
- source_id MUST be exactly as provided.
- source_text MUST be exactly as provided.
- One source sentence → one clause in the clauses array.
- No unknown top-level keys.
- No unknown clause-level keys.
```

### 7.2 What Must NOT Change

- The prompt must still pass through `LLMFallbackAdapter.system_prompt` and `user_prompt` as currently constructed.
- `build_schema_json_skeleton()` must not change — it already produces a valid example.
- `_SCHEMA_PROMPT_INSTRUCTIONS` may be extended in R11.2, but not in R11.1.

### 7.3 Adapter Compatibility

The `LLMFallbackAdapter` currently has `system_prompt` as a dataclass field with a default value. In R11.2, the updated default prompt should include the reinforcement statements from §7.1. The `user_prompt` construction in `complete()` should also include the negative constraints listing forbidden field names.

No interface changes to `complete(FallbackRequest) -> FallbackResult` are needed.

---

## 8. Mock-only Test Plan for R11.2

The following tests should be implemented in R11.2 using mock LLM responses only. No real API calls.

### 8.1 Normalizer Tests

| # | Test | Description |
|---|------|-------------|
| 1 | `test_norm_top_level_clean` | Top-level keys already matching pass through unchanged |
| 2 | `test_norm_top_level_unknown_removed` | Unknown top-level keys are removed |
| 3 | `test_norm_normative_type_to_modality` | `normative_type` dict → `modality` FieldSpan |
| 4 | `test_norm_subject_to_actor` | `subject` dict → `actor` FieldSpan |
| 5 | `test_norm_conditions_to_condition` | `conditions` dict → `condition` FieldSpan |
| 6 | `test_norm_object_removed` | `object` key removed (no schema target) |
| 7 | `test_norm_original_text_removed` | `original_text` key removed (no schema target) |
| 8 | `test_norm_string_value_to_null` | Plain string where FieldSpan expected → `null` |
| 9 | `test_norm_preserves_null_fields` | `null` semantic fields remain `null` |
| 10 | `test_norm_preserves_valid_clause` | Schema-valid clause passes through normalizer unchanged |
| 11 | `test_norm_preserves_non_semantic_fields` | `clause_id`, `source_id`, `source_text`, `clause_text`, offsets, `confidence` pass through unchanged |
| 12 | `test_norm_unknown_clause_key_removed` | Unknown clause-level keys are removed |
| 13 | `test_norm_model_output_to_valid` | Full model-like dict normalizes to schema-valid dict |

### 8.2 Adapter Integration Tests

| # | Test | Description |
|---|------|-------------|
| 14 | `test_adapter_with_normalizer_accepts_mapped` | Mock LLM returns model-like output → normalizer maps → adapter accepts FallbackResult with valid response |
| 15 | `test_adapter_with_normalizer_rejects_unmappable` | Mock LLM returns output with no mappable fields → normalizer removes them → schema validation fails → `FallbackResult(error=...)` |
| 16 | `test_adapter_no_normalizer_still_rejects` | Without normalizer, model-like output still rejected (baseline unchanged) |
| 17 | `test_optional_fallback_accepts_normalized` | `extract_with_optional_llm_fallback()` → mocked adapter with normalizer → valid fallback accepted |
| 18 | `test_optional_fallback_returns_rule_first_on_normalized_invalid` | Normalized output still invalid → rule-first preserved |

### 8.3 Safety Tests

| # | Test | Description |
|---|------|-------------|
| 19 | `test_normalizer_no_env_read` | Normalizer does not access `.env` |
| 20 | `test_normalizer_no_network` | Normalizer does not make network calls |
| 21 | `test_normalizer_no_raw_response_saved` | Normalizer does not write files |
| 22 | `test_no_real_api_in_normalizer` | Normalizer code has no real provider import/usage |
| 23 | `test_fallback_disabled_returns_rule_first` | `config.enabled=False` → rule-first regardless of normalizer |
| 24 | `test_no_batch` | No batch mode in normalizer or adapter |

---

## 9. Dedicated Single-call Entrypoint Implications

The R11.3 single-call entrypoint should be designed to wrap the schema-aligned adapter. Key implications:

### 9.1 Entrypoint Should Wrap the Aligned Pipeline

```
entrypoint
  └─> load LLMConfig (with explicit authorization check)
  └─> create LLMFallbackAdapter (with updated prompt + normalizer)
  └─> create extract_rule_first(...) [rule-first always runs]
  └─> extract_with_optional_llm_fallback(...) [optional path]
  └─> record metadata → output safe JSON
```

### 9.2 Required Safety Metadata

The entrypoint must record WITHOUT printing or saving raw responses or secrets:

| Field | Type | Source |
|-------|------|--------|
| `source_id` | `str` | From input |
| `input_text` | `str` | From input |
| `provider` | `str` | From `LLMConfig.provider` |
| `model` | `str` | From `LLMConfig.model` |
| `entrypoint` | `str` | Script/module name |
| `attempted_call_count` | `int` | Transport instrumentation |
| `successful_call_count` | `int` | Transport instrumentation |
| `fallback_status` | `str` | `fallback_schema_valid`, `fallback_schema_invalid`, or `fallback_transport_error` |
| `schema_valid` | `bool` | From schema validation result |
| `normalizer_used` | `bool` | `true` if normalizer was invoked |
| `normalizer_status` | `str` | `applied`, `noop`, or `error` |
| `raw_response_saved` | `bool` | Must be `false` |
| `secret_redacted` | `bool` | Must be `true` |
| `batch` | `bool` | Must be `false` |

### 9.3 Prohibited in Entrypoint Output

- API keys
- Base URLs
- Raw response body
- LLM-generated text beyond what schema validation already captures
- Any `.env` content

---

## 10. Compatibility with Existing Code

### 10.1 Files Changed in R11.2

Based on this design, R11.2 would modify:

| File | Change |
|------|--------|
| `src/bpc_hybrid/llm_client.py` | Add normalizer module/function; update `LLMFallbackAdapter.system_prompt` default; integrate normalizer into `complete()` |
| `tests/test_llm_client.py` | Add normalizer tests + integration tests |

Potentially new files:

| File | Purpose |
|------|---------|
| `src/bpc_hybrid/normalizer.py` | Standalone normalizer with mapping table (if needed separate from `llm_client.py`) |

### 10.2 Files NOT Changed

- `src/bpc_hybrid/schema.py` — Schema is correct; no widening needed.
- `src/bpc_hybrid/fallback.py` — Fallback pipeline unchanged; `extract_with_optional_llm_fallback()` already handles `FallbackResult(error=...)` conservatively.
- `src/bpc_hybrid/extractor.py` — Rule-first extractor unchanged.
- `src/bpc_hybrid/normalization.py` — Existing normalization (span repair, field text normalization) is separate from schema-alignment normalizer; no changes needed.
- `scripts/run_llm_dry_run.py` — No changes; R11.3 creates a separate entrypoint.
- `tests/test_fallback.py` / `tests/test_fallback_pipeline.py` — Existing tests should still pass unchanged.

### 10.3 Backward Compatibility

- `LLMFallbackAdapter` must retain its current `system_prompt` dataclass field with default value (the updated prompt text replaces the old default).
- MockLLMTransport behavior unchanged.
- All existing mock-only fallback tests must continue to pass.

---

## 11. Claim Boundary

R11.1 is **design-only**. It does not:

- Execute real API calls.
- Run benchmarks.
- Evaluate accuracy.
- Validate the method.
- Compare against Sun or any baseline.
- Use real GDPR/BPMN data.
- Produce any experimental result.
- Implement any code changes.

This design recommends concrete implementation for R11.2 (mock-only) and R11.3 (entrypoint scaffolding), followed by R11.4 (single-sample real API smoke, user-authorized only). All stages inherit the same claim-boundary rules: single-sample, schema-gated, conservative failure, no benchmark, no accuracy claim, no method validation.
