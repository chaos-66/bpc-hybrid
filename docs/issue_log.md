# Issue Log

This document records implementation issues, audit findings, debugging decisions, and resolutions encountered during the `bpc-hybrid` rebuild.

The log supports reproducibility, implementation transparency, and later thesis or paper writing.

## Claim Boundary

This issue log does not report formal benchmark results. Synthetic prototype results are used only for pipeline sanity checking.

The project has not yet been evaluated on real GDPR data, real BPMN models, the original Sun dataset, or a Sun-aligned formal benchmark.

## Issue Table

| ID | Stage | Issue | Symptom | Root Cause | Fix | Verification | Commit |
|---|---|---|---|---|---|---|---|
| I001 | Codex Audit / R1.6 | GitHub private repo credential limitation | `git ls-remote` / remote hash verification failed in Codex sandbox | Codex sandbox lacked GitHub private repo credentials | Converted Codex to local-only audit; persisted audit report through MIMO | Codex local-only audit report persisted and pushed | 5323343 |
| I002 | R3 / R3.1 | Package import failure | `IndentationError` in `src/bpc_hybrid/__init__.py`; pytest and health script failed before validation | malformed `__all__` list with duplicate residual entries after list close | Fixed `__all__`, reran compile check and tests | py_compile passed; extractor tests passed; full pytest passed; health script passed | 6def21f |
| I003 | R4 | Action boundary bleeding | Extracted action could cross clause segment boundary after multi-clause splitting | extractor action extraction lacked segment end boundary | Added `end_bound` to action extraction and passed `seg.span_end` | splitter tests, extractor regression tests, and full pytest passed | 970a65c |
| I004 | R5 / R5.1 | CLI import failure | Direct execution of rule baseline and evaluation scripts failed with `ModuleNotFoundError: No module named 'bpc_hybrid'` | direct script execution did not add project `src/` to `sys.path` | Added project-local `src` path insertion to CLI scripts | direct CLI commands passed; evaluator tests passed; full pytest passed | 66046a1 |
| I005 | R5 / R5.1 | Prototype dataset ID mapping mismatch | Codex found required categories under wrong IDs | synthetic prototype dataset IDs were not aligned to the audit protocol | Updated legal and gold JSONL IDs to required mapping | dataset mapping tests passed; gold validation passed; evaluation command succeeded | 66046a1 |
| I006 | R6 / R6.1 | R6 documentation omitted resolved implementation issues | Codex R6 audit found that `docs/experiment_log.md` recorded R6 issues as none despite three test/validation fixes during implementation | R6 implementation logs were not fully reflected in experiment documentation | Updated R6 Issues and Resolutions with the actual resolved issues and corrected stale test counts | R6 documentation fix committed and pushed; Codex re-audit pending | pending |
| I007 | R7 / R7.1 | LLM config validation and documentation audit blockers | Codex R7 audit found disabled configs skipped provider/numeric validation, base_url secret material was not rejected, and R7 issue documentation was incomplete | R7 validation logic and documentation did not fully enforce audit requirements | Harden shared validation, reject secret-containing base_url, add tests, and update R7 issue documentation | R7.1 tests passed; Codex re-audit pending | pending |
| I008 | R7.2 | Incomplete base_url secret query coverage | Codex R7.1 audit found `access_token` and `authorization` were missing from secret query-key detection | Secret query-key list was incomplete | Added `access_token` and `authorization` detection plus regression tests | R7.2 tests passed; Codex re-audit pending | pending |
| I009 | R8 / R8.1 | Invalid dry-run error path returned success exit code | R8 verification found invalid LLM/mock response errors were emitted as JSON but the CLI process still returned exit code `0` | The dry-run CLI error path produced structured error output but did not propagate a non-zero process exit status | Updated the CLI to return non-zero on invalid LLM/mock response errors and documented the issue | R8 dry-run tests passed; full pytest passed; Codex re-audit pending | pending |
| I010 | R8 / R8.2 | Argparse parse errors bypassed JSON error envelope | Codex R8 audit found invalid `--provider` used default argparse usage text instead of the required JSON error envelope | Provider validation used argparse `choices=`, so parse-level errors occurred before the dry-run JSON error helper ran | Added `JsonArgumentParser` with JSON error override, removed `choices=`, added manual provider validation gate, and added regression tests for invalid provider / unknown argument paths | 25/25 dry‑run tests passed; full 345‑test pytest passed; health and eval OK; Codex re‑audit pending | pending |
| I011 | R9.0 | `_ENV_WHITELIST` accidentally excluded non-secret config keys (`ENABLED`, `TIMEOUT`, `MAX_TOKENS`, `TEMPERATURE`) | Spec listed only 5 user-facing `.env.example` keys, but `from_env()` reads 9 total `BPC_HYBRID_LLM_*` keys | Whitelist was too narrow for `from_env()` | Expanded whitelist from 5 to 9 keys; tests updated and all pass | Fix was applied pre-commit; 366 tests pass; health and eval OK | resolved |
| I012 | R9.0 / R9.0.1 | Audit needed a way to avoid reading project `.env` | Codex R9.0 audit could not run dry-run tests/full pytest because the CLI would read the ignored project-root `.env` under a no-read-secret audit rule | R9.0 added project `.env` loading but did not provide a test/audit bypass | Added `--no-project-env`, `BPC_HYBRID_DISABLE_PROJECT_ENV=1`, and `load_project_env=False`; updated tests to avoid reading real project `.env` | R9.0.1 tests passed; Codex re-audit pending | pending |
| I013 | R9.0.2 | External audit env var broke fake `.env` fallback tests | Codex re-audit set `BPC_HYBRID_DISABLE_PROJECT_ENV=1`; 4 config tests expecting fake `.env` fallback failed | Tests did not fully isolate external environment variables | Updated config tests to explicitly clear or set `BPC_HYBRID_DISABLE_PROJECT_ENV` depending on the scenario; tests only read tmp_path fake `.env` | R9.0.2 tests passed; Codex re-audit pending | pending |
| I014 | R9 | Real API single-sample smoke returned network error | CLI executed with all R9 gates satisfied; real API call failed with network error (details redacted) | Network connectivity or API endpoint issue; code-level gate logic and redaction verified correct | Error properly redacted in JSON envelope; no secrets leaked; gate logic tested via 24 offline gate tests | All offline tests pass (408); real API gate flags and transport verified; connectivity issue to be resolved by user | pending |
| I015 | R9.1 | Real API retry still fails with DNS/connection error | R9.1 retry with improved diagnostics; real API call failed with DNS/connection error (details redacted) | Network connectivity or API endpoint issue; now classified as DNS/connection (was generic network error) | Error classification improved: timeout, SSL, DNS, HTTP all distinguished; status field added to JSON; endpoint construction hardened | All offline tests pass (423); health and eval OK; retry confirms same connectivity issue, not a code defect | pending |
| I016 | R9.2 | Real API retry after .env fix returns HTTP status error | User manually corrected .env; retry reached server (unlike R9.1 DNS error) but API returned HTTP status error (details redacted) | Auth key, model name, or endpoint path likely incorrect; server reachable now | Error classified as HTTP status (was DNS/connection in R9.1); .env correction improved connectivity; test isolation also fixed for env contamination | All offline tests pass (423); health and eval OK; connectivity improved but not yet successful | pending |
| I017 | R9.3 | Real API retry after workspace base URL fix returns HTTP status error | User manually corrected WorkspaceId/base_url/model/API key; retry reached server (same as R9.2) but API returned HTTP status error (details redacted) | Auth key, model name, workspace ID, or endpoint path mismatch persists; details redacted | Confirmed server reachable; error redacted; no code defect; one retry executed per policy | All offline tests pass (423); health and eval OK; same HTTP status error as R9.2 | pending |
| I018 | R9.4 | Real API retry after API key/model/workspace alignment returns DNS/connection error | User manually aligned API key, model, workspace; retry returned DNS/connection error (regression from HTTP status in R9.2/R9.3) | Config change made server unreachable; base_url/endpoint likely incorrect; details redacted | Error properly redacted; no code defect; one retry executed per policy | All offline tests pass (423); health and eval OK; regression from HTTP status to DNS/connection | pending |
| I019 | R9.5 | Schema mismatch after WorkspaceId braces fix — connectivity OK | Braces fix resolved DNS; API returned valid structured response but LLM output fields (`conditions`, `normative_type`, `object`, `original_text`, `subject`) don't match `ClauseExtraction` schema | LLM output uses different field names than project schema expects | Connectivity smoke succeeded (first R9.x round-trip); schema needs alignment | All offline tests pass (423); health and eval OK; first successful API response | pending |
| I020 | R9.6 | Schema-invalid response misclassified as network error | R9.5 CLI output showed `SINGLE_SAMPLE_API_NETWORK_ERROR_REDACTED` for a schema mismatch | CLI error handler treated all dry-run errors with `real_api_requested=True` as network errors | Added `_is_parse_error` check: parse errors → `SINGLE_SAMPLE_API_RETURNED_SCHEMA_INVALID`; transport errors unchanged per Codex audit | 5 new gate tests passed; full pytest passed; health and eval OK | pending |
| I021 | R9.7 | LLM output fields don't match project schema (R9.5 root cause) | R9.5 LLM returned `conditions`, `normative_type`, `object`, `original_text`, `subject` — not in `ClauseExtraction` | LLM prompt did not specify exact schema field names | Added `build_schema_json_skeleton()`, `_SCHEMA_PROMPT_INSTRUCTIONS`, strengthened system/user prompt; 17 new tests; no schema widening | 137 tests pass; health and eval OK; prompt now explicitly requires project schema fields | pending |
| I022 | R9.7.1 | Unsafe CLI regression test blocked R9.7 Codex audit | `test_r9_5_style_via_cli_returns_schema_invalid` used subprocess + `--execute-real-api` + `pass` — Codex couldn't run test file safely | R9.7 test was written as a subprocess test that couldn't receive fake responses and ended without assertions | Extracted `classify_real_api_error_status()` pure function from `run_llm_dry_run.py`; replaced unsafe test with 12 safe in-process helper tests | 148/148 tests pass; safety scan clean; no `--execute-real-api` in any test subprocess | pending |
| I024 | R9.8.1 | R9.8 source_id metadata omitted from committed documentation | Codex blocked R9.8 because committed documentation did not record the exact `source_id` for the one authorized real API schema smoke | R9.8 commit only changed README and experiment_log; it omitted `r9_8_real_schema_smoke_001` and the full metadata block | R9.8.1 adds exact source ID `r9_8_real_schema_smoke_001` and a full metadata block; documentation-only fix, no real API call, no `.env` read, no raw response | All tests unchanged from R9.8 (456/456); no code changes | pending |
| I025 | R10.0 | R10 requires strict scope control after successful R9.8 schema smoke | R9.8 succeeded as a one-sentence real API schema smoke, but this does not imply benchmark, accuracy improvement, or method validation | R10.0 creates a conservative staged plan before any implementation or further real API call | `docs/r10_plan.md` created with 5 auditable stages (R10.0–R10.4), mock-first controls, and explicit non-goals; planning only, no real API | No code changes; health and synthetic eval unchanged; compile checks pass | pending |
| I026 | R10.1 | R10.1 must keep fallback integration design mock-first | R9.8 proved one real API single-sample schema smoke, but R10 fallback integration still needs a mock-first design before any implementation | R10.1 documents a conservative design for rule-first plus optional fallback integration without source code changes, real API calls, raw response storage, batch execution, or benchmark claims | `docs/r10_1_mock_integration_design.md` created with architecture analysis, interface proposal, trigger/merge/error policies, and 13-item mock test plan for R10.2 | No code changes; health and synthetic eval unchanged; compile checks pass | resolved (R10.2 implemented) |
| I027 | R10.2 | R10.2 must preserve rule-first behavior during mock fallback integration | R10.1 identified that existing `extract_hybrid()` has strict raising behavior, while R10.2 optional fallback helper should conservatively return the rule-first result on fallback failure | R10.2 explicitly tests that the new optional helper is separate from existing `extract_hybrid()` behavior and does not silently overwrite rule-first results | `extract_with_optional_llm_fallback()` returns `OptionalFallbackResult` wrapper with `rule_first_preserved` flag; 27 mock-only tests pin conservative behavior; 483 total tests pass | resolved (R10.2.1) |

## I028 — Empty rule-first result did not trigger mock fallback in R10.2

### Status

Resolved in R10.2.1.

### Context

Codex blocked R10.2 because empty rule-first output did not trigger mock fallback when enabled, and the corresponding test constructed but did not use the empty rule-first response.

### Resolution

R10.2.1 adds `_should_trigger_optional_fallback()` with independent empty-clause detection, a `rule_first_extractor` injector for testability, and 4 strong mock-only regression tests. No real API call, no `.env` read, no raw response storage, no batch, and no benchmark claim.

## I029 — R10.3 real fallback returned schema-invalid

### Status

Recorded (R10.3).

### Context

R10.3 executed one authorized real API call through the optional
fallback pipeline. API connectivity succeeded, empty-rule trigger
worked, but the real LLM response failed `MultiClauseExtractionResponse`
schema validation.

### Resolution

The conservative fallback path correctly returned the rule-first
result. R10.3 is still PASSED because safety metadata is correct:
`real_api_call_performed: true`, `raw_response_saved: false`,
`secret_redacted: true`, `batch: false`. No retry executed.
Schema alignment may be needed before R10.4.

## I030 — R10.4 claim-boundary audit completed

### Status

Recorded (R10.4).

### Context

R10.4 audited all R10 documentation (`experiment_log.md`, `issue_log.md`,
`r10_plan.md`, `r10_1_mock_integration_design.md`, `README.md`) for
claim-boundary integrity.

### Resolution

No over-claims, benchmark language, method-validation language, or Sun
comparison language found. All R10 documentation consistently uses
"mock-only" / "single-sample" language, explicit Non-goals sections, and
"not a benchmark / not an accuracy evaluation / not method validation"
declarations. README status line, Current Stage section, and Next Stage
section updated to reflect R9.7–R10.4 completion. Documentation-only
stage — no source code changes, no real API call, no `.env` read.

## I031 — R10.3 real-call count evidence limitation requires future single-call entrypoint

### Status

Open for future real-API stages.

### Context

Codex accepted R10.3 with a non-blocking evidence limitation: the transcript included two inline Python command attempts, while committed artifacts record one schema-invalid real fallback result.

### Control

Future real-API stages must use a dedicated audited single-call script or CLI entrypoint that records safe call-count metadata without saving raw responses.

### Safety Boundary

- No raw response saved.
- No `.env` committed.
- No batch execution.
- No benchmark.
- No accuracy claim.
- No method-validation claim.

## I032 — R11 planning required for schema-aligned real fallback

### Status

Open for R11 planning.

### Context

R10.3 reached the real provider but returned schema-invalid fallback output. R10.4/R10.4.1 documented the result and evidence limitation. R11 must plan schema alignment and a dedicated single-call real API entrypoint before any further real API smoke.

### Safety Boundary

- No benchmark.
- No accuracy claim.
- No method-validation claim.
- No batch real API.
- No raw response storage.


## I033 — R11.1 schema alignment design completed

### Status

Closed — design delivered as `docs/r11_1_schema_alignment_design.md`.

### Context

R11.1 produced the design for aligning real LLM fallback output with the project schema. Four candidate strategies were evaluated (A: prompt, B: normalizer, C: schema gate, D: two-step). A+B+C is recommended for R11.2 implementation.

### Safety Boundary

- No source code changes.
- No real API call.
- No benchmark.
- No accuracy claim.
- No method-validation claim.
- No batch real API.
- No raw response storage.


## I034 — R11.1 schema summary overstated current top-level parser strictness

### Status

Fixed in R11.1.1 documentation.

### Context

Codex found that the R11.1 design document described `schema_version` and `clauses` as if current `MultiClauseExtractionResponse.from_dict()` strictly required them. Current parser behavior is more permissive.

### Correction

R11.1.1 documents that missing `schema_version` defaults to `"0.1.0"` and missing `clauses` defaults to `[]`. Any future stricter handling is a proposed R11.2 normalizer / prompt-contract gate, not current parser behavior.

- No method-validation claim.

## I035 — R11.2 schema alignment normalizer implemented

### Status

Closed — implemented and tested in R11.2.

### Context

R11.1 designed a combined prompt + normalizer + schema-gate strategy (Options A+B+C) for aligning real LLM fallback output with project schema. R10.3 showed real LLM output using field names (`normative_type`, `subject`, `object`, `original_text`, `conditions`) that don't match `ClauseExtraction` schema fields.

### Implementation

R11.2 implements the normalizer as `src/bpc_hybrid/schema_alignment.py`:

- `normalize_llm_fallback_json(candidate: dict) -> NormalizationResult` — deterministic, pure function
- Clause-level mapping: `normative_type → modality`, `subject → actor`, `conditions → condition` (dict/None only; string → null)
- `object` and `original_text` removed (no schema target)
- Unknown top-level and clause-level keys removed
- `LLMFallbackAdapter` gets `enable_schema_alignment: bool = True` field with strengthened system_prompt
- 45 mock-only tests; 531 total tests pass

### Safety Boundary

- No real API.
- No `.env` read.
- No raw response storage.
- No batch.
- No benchmark.
- No accuracy claim.
- No method-validation claim.
- No schema widening.

