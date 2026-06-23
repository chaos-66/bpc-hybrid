# R13.9 Project Stage Summary

## 1. Project One-line Description

A rule-first, LLM-assisted prototype workflow for structured regulatory
semantic extraction and bounded compliance-analysis experimentation.

## 2. Research Motivation

Regulatory texts (GDPR, tax codes, financial regulations) contain normative
sentences with structured semantic components: modality (obligation,
prohibition, permission, definition), actor, action, condition, constraint,
and exception. Extracting these components is a prerequisite for any automated
compliance reasoning.

Existing approaches fall into two families:
- **Pure rule-based**: Deterministic, interpretable, and consistent, but brittle
  to linguistic variation, passive voice, cross-lingual text, and implicit agents.
- **Pure LLM-based**: Flexible and language-agnostic, but prone to hallucination,
  inconsistent terminology, and output format drift.

This project explores a **rule-first, LLM-assisted hybrid** — where a
deterministic regex-based extractor is the primary path and LLMs are invoked
only when rule extraction is insufficient, under strict schema and
normalization constraints.

## 3. Technical Route

### 3.1 Core Pipeline (R2–R6)

1. **Multi-clause schema** (`ClauseExtraction`, `MultiClauseExtractionResponse`):
   Six semantic fields per clause — modality, actor, action, condition,
   constraint, exception — each with text spans, confidence scores, and
   null-safe representations.

2. **Rule-first extractor** (`RuleFirstExtractor`): Priority-ordered modality
   marker detection, active/passive voice actor extraction, unless-to-condition/
   exception mapping, constraint region detection, and action truncation.

3. **Multi-clause splitter** (`RuleBasedClauseSplitter`): Decomposes compound
   sentences into individual normative clauses based on modality markers and
   clause-boundary conjunctions.

4. **Evaluator**: Field-level micro metrics (TP/FP/FN → precision/recall/F1)
   with exact/partial/wrong/missing/not_applicable scoring. Gold-standard
   alignment by source_id and clause position.

5. **Mock LLM fallback**: `MockLLMFallbackClient` with configurable responses,
   `should_trigger_fallback()` decision logic, and deterministic span repair
   — all without real API calls.

### 3.2 Real API Infrastructure (R7–R9)

6. **Safety-gated LLM config**: `LLMConfig` with env-whitelist loading,
   secret redaction in all repr/str paths, base_url secret-material rejection,
   and `BPC_HYBRID_DISABLE_PROJECT_ENV` audit control.

7. **Real API transport**: `RealAPITransport` with timeout/SSL/DNS/HTTP error
   classification, secret redacted error envelopes, and openai-compatible
   endpoint construction.

8. **Schema alignment normalizer**: Deterministic mapping from LLM-native
   field names (normative_type, subject, object, conditions, original_text)
   to project schema fields — removing unsupported fields and rejecting
   malformed output.

### 3.3 Mini-pilot Experiment Chain (R12–R13)

9. **Synthetic prototype pilot** (R12.1): 14-sample synthetic test, identified
   timeout pattern (10/14 `socket.timeout` at 30s).

10. **Timeout fix** (R12.3): Per-sample timing metadata, CLI timeout flag,
    confirmed 60s timeout resolves connectivity issue in 2-sample sanity check.

11. **Data intake** (R13.3): 8 real legal samples from GDPR EUR-Lex and Austrian
    Income Tax Code, manually reviewed gold annotation.

12. **Baseline mini-pilot** (R13.4.2): 8-sample real API run with baseline prompt
    (instruction-only, no few-shot, no prompt refinement). Results recorded with
    field-level evaluation.

13. **Error analysis** (R13.5): Identified 7 error-pattern categories from
    baseline results — null actors, verbatim action fragments, wrong modality,
    German-language outputs, wrong/missing conditions and constraints.

14. **Prompt refinement design** (R13.6): Designed 3 prompt variants — A
    (instruction-only strengthened), B (few-shot extraction with 4 examples),
    C (chain-of-thought reasoning).

15. **Prompt B bounded mini-pilot** (R13.7): 8-sample real API run with Prompt
    B under an explicit authorization contract. Authorization consumed, gate
    closed after single run.

16. **Descriptive comparison** (R13.8): Post-run comparison of R13.4.2 vs R13.7
    field-level counts — no new API calls, no evaluator rerun, strict
    anti-overclaim language.

## 4. Dataset and Evidence Boundary

### Dataset Composition

| Source | Language | Samples | Type |
|--------|----------|---------|------|
| GDPR EUR-Lex Art 5(1)(a)–(c), 7(1), 9(1) | English | 5 | 4 obligation, 1 prohibition |
| Austrian Income Tax Code § 1 Abs 1–3 | German | 3 | 3 definition |

- Total: **8 samples**
- Gold annotation: Manual review by project author (not expert-annotated)
- Evaluation: Field-level exact/partial/wrong/missing/not_applicable

### Evidence Boundary

- This is a **bounded mini-pilot**, not a formal experiment.
- 8 samples from 2 legal domains. No statistical significance.
- No held-out validation set. No cross-validation. No multi-annotator gold.
- Models: qwen3.7-max only (via openai-compatible endpoint).

## 5. Real API Mini-pilot Chain

| Stage | Date | API Calls | Result |
|-------|------|-----------|--------|
| R11.4.3 | — | 1 (single-sentence smoke) | Schema-valid |
| R12.1 | — | 14 (synthetic prototype) | 4 schema-valid, 10 timeout |
| R12.3.1 | — | 2 (timeout sanity check) | Both schema-valid at 60s |
| R13.4.2 | — | 8 (baseline, 8 samples) | 8/8 schema-valid |
| R13.7 | — | 8 (Prompt B, 8 samples) | 8/8 schema-valid |

All real API calls were:
- Explicitly user-authorized (no unsupervised execution)
- Single-attempt per sample (no retry, no repair calls)
- Non-batch (one call per sample)
- Raw-response-suppressed (raw LLM output never saved to disk)
- Schema-gated (output validated against project JSON Schema)

## 6. Evaluation Method

### 6.1 Field-level Scoring

Each of 6 fields per sample is scored against the manual gold:

| Score | Definition |
|-------|-----------|
| exact | Field text matches gold exactly (normalized lowercase comparison) |
| partial | Field is non-null and has content overlap with gold but is not exact |
| wrong | Field is non-null but does not match gold content |
| missing | Field is null but gold is non-null |
| not_applicable | Both prediction and gold are null |

### 6.2 Failure Categories

Pre-defined failure categories: `actor_missing`, `actor_wrong`, `action_wrong`,
`condition_wrong`, `constraint_wrong`, `modality_wrong`, `exception_wrong`.

### 6.3 What We Do Not Measure

- End-to-end accuracy (not meaningful at field level)
- AP/MAP (requires multi-threshold ranking — not applicable to single-prediction
  extraction)
- Statistical significance (8 samples is insufficient)
- Inter-annotator agreement (single gold annotator)
- Cross-domain generalization (only 2 legal domains)

## 7. Observed Descriptive Findings

The R13.8 descriptive comparison reports the following count differences between
the R13.4.2 baseline and R13.7 Prompt B 8-sample mini-pilots:

| Field | R13.4.2 Exact | R13.7 Exact | Key Change |
|-------|---------------|-------------|------------|
| Modality | 7/8 | 8/8 | Sample 006: wrong→exact (definition recognition) |
| Actor | 0/8 | 7/8 | Null actors → inferred actors from passive voice |
| Action | 0/8 | 4/8 | Verbatim fragments → normalized action phrases |
| Condition | 1/6 | 2/6 | Wrong conditions eliminated; partial-dominated |
| Constraint | 0/8 | 3/8 | Wrong constraints eliminated; partial-dominated |
| Exception | — | — | Not applicable in all 8 samples |

Failure category count: 15 → 1 (single condition_wrong remaining in sample 003).

**These are count differences in an 8-sample set only. They do not constitute
benchmark evidence, method validation, or proof of prompt superiority.**

## 8. Engineering Safety Design

### 8.1 Authorization Gates

- Every real API call requires explicit user authorization text.
- Authorization is consumed on use — no persistent API permission.
- The Prompt B runner (`run_r13_7_prompt_b_real_mini_pilot.py`) implements
  7 safety flags in `_check_authorization_gate()`.

### 8.2 Secret Redaction

- `LLMConfig.__repr__`/`__str__` always redact `api_key`.
- `redact_secret()` shows first 4 chars + `***REDACTED***`.
- `redact_mapping()` replaces values for keys containing key/secret/token
  or values containing `sk-`/`Bearer`.
- Base URLs containing `?api_key=`, `?token=`, `?secret=`, `?access_token=`,
  `?authorization=`, or `user:password@` are rejected at validation time.

### 8.3 Raw Response Suppression

- `raw_response_saved: false` in all pilot metadata.
- No raw LLM JSON is ever written to disk.
- Only schema-valid normalized predictions are saved.

### 8.4 Audit-safe Environment Isolation

- `BPC_HYBRID_DISABLE_PROJECT_ENV=1` blocks project `.env` reading.
- `--no-project-env` CLI flag for test/audit scenarios.
- `.env` is gitignored; `.env.example` (with placeholders) is committed.

## 9. Limitations

1. **Sample size**: 8 samples. Insufficient for statistical claims.
2. **Domain coverage**: GDPR EUR-Lex + Austrian Income Tax Code only.
   No financial regulations, no contract law, no multi-jurisdiction text.
3. **Single model**: All pilots used qwen3.7-max. No cross-model comparison.
4. **Single gold annotator**: Gold template was manually reviewed by the
   project author, not by multiple legal experts.
5. **No exception evaluation**: None of the 8 gold samples contain exceptions.
6. **No adversarial evaluation**: All inputs are clean legislative text.
   No OCR errors, no tables, no cross-references, no footnotes.
7. **Single language pair**: English legislative text + German tax code.
   No other languages or mixed-language documents.
8. **No held-out set**: The same 8 samples were used for both baseline and
   Prompt B pilots. No independent test set exists.
9. **No temporal stability test**: Single-run per prompt variant. No
   measurement of output variability across repeated runs.

## 10. Next Steps

1. **Return to Codex for R13.9 local-only audit** before using any R13.9
   documentation externally.
2. **Consider another bounded prompt variant pilot** (Prompt A or C) for
   additional descriptive evidence — requires new authorization.
3. **Expand sample set** if domain coverage or statistical robustness is
   needed — requires new data intake and gold annotation.
4. **Cross-model comparison** if model-specific effects are of interest.
5. **Exception-bearing samples** if exception-field evaluation is desired.

All future real API stages require fresh explicit user authorization and
new Codex audit checkpoints.

---

**This is not a benchmark.**
**This is not method validation.**
**This is not Sun reproduction.**
**This does not prove Prompt B superiority.**
