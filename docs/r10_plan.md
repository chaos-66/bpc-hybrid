# R10 — Controlled Real-LLM Fallback Integration Plan

> **R10.0 is planning only.**
> No implementation. No real API calls. No `.env` reads. No benchmark.
> No accuracy claims. No method validation. No Sun baseline comparison.
> No real GDPR/BPMN data.

---

## 1. R10 Overall Goal

Integrate a controlled real-LLM fallback path into the existing
rule-first compliance extraction pipeline, under strict gate,
mock-first, and single-sample-first controls.

The fallback is invoked only when the rule-based extraction produces
low-confidence or incomplete results, and only after explicit opt-in
flags are set.

---

## 2. Baseline Summary (R9 Completed)

| Stage | Summary | Status |
|-------|---------|--------|
| R9.0 | Project-local `.env` support | ✅ |
| R9.1 | Connectivity diagnostics (timeout/SSL/DNS/HTTP classification) | ✅ |
| R9.2–R9.4 | Config/debug attempts (connectivity refined) | ✅ |
| R9.5 | Service/model reached but schema mismatch detected | ✅ |
| R9.6 | Schema mismatch classification fixed (`_is_parse_error`) | ✅ |
| R9.7 | Prompt/schema alignment (`build_schema_json_skeleton()`, `_SCHEMA_PROMPT_INSTRUCTIONS`) | ✅ |
| R9.7.1 | Unsafe subprocess test removed; 12 safe helper tests added | ✅ |
| R9.8 | One real API single-sample schema smoke **succeeded** (`schema_valid: true`) | ✅ |
| R9.8.1 | Source ID metadata documented (`r9_8_real_schema_smoke_001`) | ✅ |

**Key takeaway from R9.8:**
`qwen3.7-max` via `openai_compatible` provider returned a valid
`MultiClauseExtractionResponse` for a synthetic toy sentence.
This proves the prompt/schema alignment works in one controlled case.
It does **not** prove benchmark-level accuracy, method superiority,
or readiness for real GDPR/BPMN data.

---

## 3. R10 Non-Goals (Explicit)

R10 will **not**:

- Run benchmark
- Compare against Sun baseline
- Claim accuracy improvement
- Validate the method
- Process real GDPR/BPMN datasets (unless separately planned and audited)
- Execute batch real API calls
- Save raw LLM responses to disk
- Print or log secrets, API keys, or tokens
- Modify the existing rule-based extraction logic except for the
  controlled fallback integration point

---

## 4. R10 Risk Controls

| Control | Mechanism |
|---------|-----------|
| `.env` remains ignored and untracked | `.gitignore:19` verified every stage |
| Real API calls remain opt-in | `--execute-real-api` + `--confirm-real-api-single-sample` required |
| No real API without confirmation env | `BPC_HYBRID_R9_REAL_RUN_CONFIRMED=YES_SINGLE_SAMPLE_ONLY` required |
| No raw response storage | `raw_response_saved: false` enforced in CLI output |
| No batch execution | Each stage enforces at-most-one real API call |
| No secrets in logs | `secret_redacted: true` enforced; `--no-project-env` for audits |
| No prompt/output body committed | Only schema-validated output committed; never raw model JSON |
| All new real API behavior has mock-first tests | Tests must pass before any `--execute-real-api` is allowed |
| All real API stages require Codex audit | Each stage gates on Codex acceptance before next stage |

---

## 5. Recommended R10 Staged Plan

Each stage is small, auditable, and has a clear exit criterion.

---

### R10.0 — Planning (current stage)

- **Goal:** Produce this plan document.
- **Allowed:** Create/update `docs/r10_plan.md`, `docs/experiment_log.md`,
  `README.md`, `docs/issue_log.md` (documentation only).
- **Forbidden:** Real API calls, `.env` reads, source code changes,
  benchmark claims, accuracy claims, method-validation claims.
- **Test requirements:** Compile-check key files; health script;
  synthetic eval unchanged.
- **Documentation:** `docs/r10_plan.md` exists; experiment log updated;
  README updated.
- **Codex audit gate:** Codex must accept R10.0 before R10.1.
- **Exit criteria:**
  - `docs/r10_plan.md` exists with all required sections
  - No real API executed
  - No `.env` read
  - No code modified
  - Git commit pushed

---

### R10.1 — Offline/Mock Integration Design

- **Goal:** Design the fallback integration point in the rule-first
  pipeline without any real API calls. Define interfaces, data flow,
  and mock test strategy.
- **Allowed:** Design documents; interface sketches; mock-only test
  plans; no source code changes unless explicitly scoped and audited.
- **Forbidden:** Real API calls; `.env` reads; benchmark claims;
  accuracy claims; method-validation claims; batch execution;
  raw response storage.
- **Test requirements:** All existing tests pass; new mock-only tests
  for the fallback integration interface.
- **Documentation:** Updated `docs/r10_plan.md` or a new
  `docs/r10_1_design.md` with interface specs.
- **Codex audit gate:** Codex must accept R10.1 design before R10.2.
- **Exit criteria:**
  - Fallback interface design documented
  - Mock test strategy defined
  - No real API executed
  - No `.env` read

---

### R10.2 — Mock-Only Pipeline Integration Tests

- **Goal:** Implement and test the fallback integration using mock
  LLM responses only. Verify the pipeline can receive a
  `MultiClauseExtractionResponse` through the fallback path.
- **Allowed:** Source code changes for the integration interface;
  mock-only tests; no real API flags.
- **Forbidden:** Real API calls; `.env` reads; benchmark claims;
  accuracy claims; method-validation claims; raw response storage.
- **Test requirements:** All existing tests pass; new mock-integration
  tests cover: rule-first success (no fallback), rule-first low-confidence
  triggers fallback, mock LLM fallback returns valid schema, mock LLM
  schema-invalid is handled, fallback disabled by gate flags.
- **Documentation:** Updated test inventory; integration flow diagram
  or description.
- **Codex audit gate:** Codex must accept R10.2 before R10.3.
- **Exit criteria:**
  - Mock fallback pipeline passes all offline tests
  - No real API executed
  - No `.env` read
  - Full pytest passes (≥ existing count)

---

### R10.3 — Single-Sample Real Fallback Pipeline Smoke (if authorized)

- **Goal:** Run **at most one** real API call through the fallback
  pipeline with a synthetic sentence, verifying end-to-end schema
  validity.
- **Allowed:** One real API call with all gate flags; documentation
  of result; no code changes beyond what R10.2 already implemented.
- **Forbidden:** Batch calls; multiple retries; real GDPR/BPMN data;
  benchmark claims; accuracy claims; method-validation claims;
  raw response storage.
- **Test requirements:** All offline tests pass before real API call;
  `--no-project-env` dry-run gate checks pass.
- **Documentation:** Record `source_id`, `schema_valid`, provider,
  model, and all safety flags in experiment log and issue log.
- **Codex audit gate:** Codex must accept R10.3 before R10.4.
- **Exit criteria:**
  - Exactly one real API call executed
  - Result documented (schema_valid or schema_invalid or network_error)
  - No raw response saved
  - No secrets leaked

---

### R10.4 — Documentation and Claim-Boundary Audit

- **Goal:** Review all R10 stages for claim-boundary integrity.
  Ensure no over-claiming, no benchmark language, no method-validation
  language, no Sun comparison language.
- **Allowed:** Documentation edits only.
- **Forbidden:** Real API calls; `.env` reads; source code changes;
  new claims.
- **Test requirements:** All existing tests still pass.
- **Documentation:** Final audit of all R10 documentation for
  claim-boundary compliance.
- **Codex audit gate:** Codex must accept R10.4 before any R11 or
  formal experiment.
- **Exit criteria:**
  - All R10 documentation audited
  - No over-claims found or all corrected
  - No real API executed in this stage

---

## 6. R10.1 Preliminary Scope (for reference only)

R10.1 does **not** run real API. It only designs the offline/mock
integration.

**Suggested design focus:**

> Enable the rule-first pipeline to accept a
> `MultiClauseExtractionResponse` through a mock LLM fallback path
> when rule confidence falls below a configurable threshold.

Key design questions (to be resolved in R10.1, not here):
- What is the integration point in the existing pipeline?
- What is the confidence threshold for triggering fallback?
- How does the fallback result merge with rule-based results?
- What is the mock test strategy?

**This section is a planning placeholder — no design decisions are
made in R10.0.**

---

## 7. R10 Success Criteria (for this planning stage)

- [x] `docs/r10_plan.md` exists
- [x] R10 claim boundary is explicit
- [x] R10 stages are small and auditable (5 stages: R10.0–R10.4)
- [x] No real API is executed
- [x] No `.env` is read
- [x] No code is modified
- [x] No benchmark claim appears
- [ ] Codex can audit the plan (pending Codex review)

---

## 8. Claim Boundary (Repeated for Emphasis)

```
R10 IS NOT A BENCHMARK.
R10 IS NOT AN ACCURACY EVALUATION.
R10 IS NOT A METHOD VALIDATION.
R10 IS NOT A SUN BASELINE COMPARISON.
R10 IS NOT A REAL GDPR/BPMN EVALUATION.

R10 IS a controlled, staged integration of a real-LLM fallback path
into a rule-first pipeline, with strict gates, mock-first testing,
and Codex audit at every stage.
```
