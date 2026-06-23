# R14.3 Rule+LLM Authorization Request

## 1. Purpose

This document requests explicit user authorization for a future **R14.4 Rule+LLM
bounded experiment**. R14.3 itself is planning-only — it does NOT execute any
LLM call or API call.

The purpose is to provide the user with full transparency about what R14.4 will
do, how many API calls it will make, what safety controls are in place, and what
claims will NOT be made even after R14.4 completes.

## 2. What Will Be Run Later (R14.4)

If authorized, R14.4 will:

1. Load the same 24 R14.1 candidate samples used in R14.2 rule-only baseline.
2. Run `RuleFirstExtractor` with `few_shot_extraction` Prompt B fallback.
3. Make one LLM extraction call per sample (24 total).
4. Output schema-constrained JSON (6 fields: modality, actor, action, condition, constraint, exception).
5. Evaluate predictions using the same `scripts/evaluate_r14_field_metrics.py` as R14.2.
6. Produce a comparison summary (R14.2 rule-only vs R14.4 Rule+LLM).

## 3. Input Data

```
input_samples = data/formal/r14_controlled/r14_1_candidate_samples.jsonl
input_gold = data/formal/r14_controlled/r14_1_mini_gold.jsonl
baseline_reference = data/formal/results/r14_2_rule_only_evaluation_summary.json
```

- 24 samples (8 R13.3 seed + 16 R14.1 new)
- 12 GDPR EurLex (English) + 12 Austrian Income Tax Code (German)
- Gold annotations are manually reviewed draft gold

## 4. Maximum API Calls

```
max_api_calls = 24 (one per sample)
retry = 0
repair calls = 0
batch execution = no
total ceiling = 24
```

If any sample fails (timeout, schema invalid, API error), it is NOT retried.
The failure is recorded in the prediction metadata but does not trigger a second call.

## 5. Safety Controls

- `.env` must contain `BPC_HYBRID_LLM_ENABLED=true` (checked at runtime)
- `$env:BPC_HYBRID_DISABLE_PROJECT_ENV = "1"` (prevents accidental env chaining)
- All API calls go through `LLMFallbackAdapter` → `RealAPITransport`
- Secret redaction active: `redact_secret()`, `redact_mapping()` applied to all logs/metadata
- No raw response saved to disk (`raw_response_saved = false`)
- Each prediction record includes `llm_used=true`, `api_used=true` but no raw content
- Call counter enforces the 24-call ceiling; harness refuses 25th call

## 6. Output Files

If authorized and executed, R14.4 will create:

- `data/formal/predictions/r14_4_rule_plus_llm_predictions.jsonl` (24 predictions)
- `data/formal/results/r14_4_rule_plus_llm_evaluation_summary.json`
- `data/formal/results/r14_4_rule_plus_llm_evaluation_details.jsonl`

These do NOT exist yet. R14.3 is planning-only.

## 7. What Will Not Be Done

Even after R14.4 completes:

- Will NOT be claimed as a benchmark
- Will NOT be claimed as method validation
- Will NOT be claimed as Sun reproduction
- Will NOT be claimed as proof of LLM superiority
- Will NOT be claimed as production-ready GDPR compliance checker
- Results will NOT generalize beyond n=24 on these specific domains

Any comparison will be descriptive and small-scale only.

## 8. Required User Authorization Text

To authorize R14.4, the user must provide the following exact text (or a
semantically equivalent statement that unambiguously confirms all constraints):

> 我授权 R14.4 使用 Rule+LLM-assisted path 在 R14.1 的 24 条 draft mini-gold 样本上执行一次有界真实 API 试点，最多 24 次 API 调用，每个样本一次尝试，无重试，无修复调用，无批量执行，不保存原始响应。我理解这不是正式 benchmark，不是方法验证，不是 Sun 复现，也不能直接证明 LLM 优越性。

**Without this exact future authorization, R14.4 must not run.**

A simple "run R14.4" or "proceed" is NOT sufficient. The agent will require the
authorization text or an equivalent explicit acknowledgment of all constraints
listed above.

## 9. Claim Boundary

R14.3 does not authorize R14.4. R14.3 only prepares the authorization package.
This document itself does not run LLM, does not call API, and does not produce
experiment results.

No benchmark, method-validation, Sun-reproduction, or LLM-superiority claim is
permitted in R14.3.
